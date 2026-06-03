"""Build the first deterministic canonical game catalog.

canonical_v0 is intentionally conservative:
- RAWG and Wikidata are merged only through trusted external-id candidate pairs.
- Steam is linked through Wikidata Steam AppID external ids.
- Wikipedia summaries are linked by Wikidata QID as enrichment-only source rows.
- IGDB records stay standalone until search-based matches are ML/manual-review validated.
"""

from __future__ import annotations

import argparse
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.entity_resolution.corpus import SourceGameRecord, load_source_records, normalize_text
from src.ingestion.repository import IngestionRepository

SourceKey = tuple[str, str]

CANONICAL_UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "game-intelligence-platform")
PREFERRED_NAME_SOURCES = ("rawg", "wikidata", "igdb", "steam")
DETERMINISTIC_SOURCE_CONFIDENCE = 1.0
STANDALONE_SOURCE_CONFIDENCE = 0.5
WIKIPEDIA_LINK_CONFIDENCE = 1.0


class UnionFind:
    def __init__(self) -> None:
        self._parent: dict[SourceKey, SourceKey] = {}

    def add(self, value: SourceKey) -> None:
        self._parent.setdefault(value, value)

    def find(self, value: SourceKey) -> SourceKey:
        self.add(value)
        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)
        return self._parent[value]

    def union(self, left: SourceKey, right: SourceKey) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        self._parent[right_root] = left_root

    def groups(self) -> list[set[SourceKey]]:
        grouped: dict[SourceKey, set[SourceKey]] = {}
        for value in self._parent:
            grouped.setdefault(self.find(value), set()).add(value)
        return list(grouped.values())


@dataclass(frozen=True, slots=True)
class CanonicalComponent:
    canonical_game_id: uuid.UUID
    canonical_name: str
    release_year: int | None
    source_keys: tuple[SourceKey, ...]


def _source_key(source: object, source_game_id: object) -> SourceKey:
    return (str(source), str(source_game_id))


def stable_canonical_id(source_keys: set[SourceKey]) -> uuid.UUID:
    signature = "|".join(
        f"{source}:{source_game_id}" for source, source_game_id in sorted(source_keys)
    )
    return uuid.uuid5(CANONICAL_UUID_NAMESPACE, f"canonical_v0:{signature}")


def valid_display_name(record: SourceGameRecord) -> bool:
    name = (record.name or "").strip()
    if not name:
        return False
    if record.source == "wikidata" and name == record.source_game_id:
        return False
    if normalize_text(name) is None:
        return False
    return True


def choose_canonical_record(
    records: dict[SourceKey, SourceGameRecord],
    source_keys: set[SourceKey],
) -> SourceGameRecord:
    valid_records = [
        records[key] for key in source_keys if key in records and valid_display_name(records[key])
    ]
    for source in PREFERRED_NAME_SOURCES:
        source_records = [record for record in valid_records if record.source == source]
        if source_records:
            return sorted(
                source_records, key=lambda record: (record.release_year is None, record.name)
            )[0]
    if valid_records:
        return sorted(valid_records, key=lambda record: (record.release_year is None, record.name))[
            0
        ]
    fallback_key = sorted(source_keys)[0]
    return records[fallback_key]


def choose_release_year(
    records: dict[SourceKey, SourceGameRecord],
    source_keys: set[SourceKey],
) -> int | None:
    for source in PREFERRED_NAME_SOURCES:
        years = sorted(
            {
                records[key].release_year
                for key in source_keys
                if key in records
                and records[key].source == source
                and records[key].release_year is not None
            }
        )
        if years:
            return years[0]
    years = sorted(
        {
            records[key].release_year
            for key in source_keys
            if key in records and records[key].release_year is not None
        }
    )
    return years[0] if years else None


def build_union_find(
    records: dict[SourceKey, SourceGameRecord],
    candidate_pairs: list[dict[str, Any]],
) -> UnionFind:
    union_find = UnionFind()
    for key in records:
        union_find.add(key)

    for pair in candidate_pairs:
        if str(pair.get("label_value") or "") != "1":
            continue
        if str(pair.get("candidate_source") or "") != "external_id" and not bool(
            pair.get("canonical_edge")
        ):
            continue
        left = _source_key(pair["source_a"], pair["source_id_a"])
        right = _source_key(pair["source_b"], pair["source_id_b"])
        if left in records and right in records:
            union_find.union(left, right)

    for key, record in records.items():
        if record.source != "wikidata":
            continue
        steam_appid = record.external_ids.get("steam")
        if not steam_appid:
            continue
        steam_key = ("steam", str(steam_appid))
        if steam_key in records:
            union_find.union(key, steam_key)

    return union_find


def build_components(
    records: dict[SourceKey, SourceGameRecord],
    candidate_pairs: list[dict[str, Any]],
) -> list[CanonicalComponent]:
    union_find = build_union_find(records, candidate_pairs)
    components: list[CanonicalComponent] = []
    for source_keys in union_find.groups():
        canonical_record = choose_canonical_record(records, source_keys)
        canonical_name = (
            canonical_record.name.strip()
            or f"{canonical_record.source}:{canonical_record.source_game_id}"
        )
        components.append(
            CanonicalComponent(
                canonical_game_id=stable_canonical_id(source_keys),
                canonical_name=canonical_name,
                release_year=choose_release_year(records, source_keys),
                source_keys=tuple(sorted(source_keys)),
            )
        )
    return sorted(components, key=lambda component: component.canonical_name.lower())


def fetch_wikipedia_source_ids(repository: IngestionRepository) -> set[str]:
    return {
        str(row["source_game_id"])
        for row in repository.fetch_staging_rows("stg.source_game_descriptions", source="wikipedia")
        if row.get("source_game_id")
    }


def fetch_source_aliases(
    repository: IngestionRepository,
) -> dict[SourceKey, set[tuple[str, str | None]]]:
    aliases: dict[SourceKey, set[tuple[str, str | None]]] = {}
    for row in repository.fetch_staging_rows("stg.source_game_aliases"):
        alias = str(row.get("alias") or "").strip()
        if not alias:
            continue
        aliases.setdefault(_source_key(row["source"], row["source_game_id"]), set()).add(
            (alias, str(row["language"]) if row.get("language") else None)
        )
    return aliases


def fetch_candidate_pairs(repository: IngestionRepository) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT source_a, source_id_a, source_b, source_id_b, candidate_source, label_value
                FROM ml.entity_candidate_pairs
                WHERE candidate_source = 'external_id'
                  AND label_value = '1'
                """
            )
            return list(cursor.fetchall())


def fetch_canonical_v1_candidate_pairs(repository: IngestionRepository) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    source_a,
                    source_id_a,
                    source_b,
                    source_id_b,
                    candidate_source,
                    '1'::TEXT AS label_value,
                    TRUE AS canonical_edge,
                    CASE
                        WHEN review_status = 'reviewed' AND review_label IS TRUE
                            THEN 'manual_positive'
                        ELSE 'deterministic_external_id'
                    END AS canonical_edge_source
                FROM ml.v_entity_resolution_review_candidates
                WHERE (
                    candidate_source = 'external_id'
                    AND label_value = '1'
                    AND NOT (review_status = 'reviewed' AND review_label IS FALSE)
                    AND (
                        review_label IS TRUE
                        OR (
                            COALESCE(name_similarity, 0) >= 0.90
                            AND (
                                release_year_diff IS NULL
                                OR release_year_diff <= 2
                            )
                        )
                    )
                )
                OR (
                    review_status = 'reviewed'
                    AND review_label IS TRUE
                )
                """
            )
            return list(cursor.fetchall())


def clear_canonical_tables(repository: IngestionRepository) -> None:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM dm.canonical_game_external_ids;
                DELETE FROM dm.canonical_game_aliases;
                DELETE FROM dm.canonical_game_sources;
                DELETE FROM dm.canonical_games;
                """
            )


def insert_canonical_components(
    repository: IngestionRepository,
    components: list[CanonicalComponent],
    records: dict[SourceKey, SourceGameRecord],
    aliases: dict[SourceKey, set[tuple[str, str | None]]],
    wikipedia_source_ids: set[str],
) -> dict[str, object]:
    source_link_counter: Counter[str] = Counter()
    alias_count = 0
    external_id_count = 0
    source_confidences = build_source_confidences(components)
    wikidata_to_canonical = {
        source_game_id: component.canonical_game_id
        for component in components
        for source, source_game_id in component.source_keys
        if source == "wikidata"
    }

    with repository.connection() as connection:
        with connection.cursor() as cursor:
            for component in components:
                cursor.execute(
                    """
                    INSERT INTO dm.canonical_games (
                        canonical_game_id,
                        canonical_name,
                        release_year
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (canonical_game_id)
                    DO UPDATE
                    SET canonical_name = EXCLUDED.canonical_name,
                        release_year = EXCLUDED.release_year,
                        updated_at = NOW()
                    """,
                    (component.canonical_game_id, component.canonical_name, component.release_year),
                )

                component_aliases: set[tuple[str, str | None]] = {(component.canonical_name, None)}
                component_external_ids: set[tuple[str, str]] = set()
                for source_key in component.source_keys:
                    record = records[source_key]
                    confidence = source_confidences[source_key]
                    cursor.execute(
                        """
                        INSERT INTO dm.canonical_game_sources (
                            canonical_game_id,
                            source,
                            source_game_id,
                            linkage_confidence
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            component.canonical_game_id,
                            record.source,
                            record.source_game_id,
                            confidence,
                        ),
                    )
                    source_link_counter[record.source] += 1

                    if valid_display_name(record):
                        component_aliases.add((record.name.strip(), None))
                    component_aliases.update(aliases.get(source_key, set()))
                    component_external_ids.add((record.source, record.source_game_id))
                    component_external_ids.update(
                        (str(source), str(external_id))
                        for source, external_id in record.external_ids.items()
                    )

                for alias, language in sorted(component_aliases):
                    cursor.execute(
                        """
                        INSERT INTO dm.canonical_game_aliases (
                            canonical_game_id,
                            alias,
                            language
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (component.canonical_game_id, alias, language),
                    )
                    alias_count += 1

                for external_source, external_id in sorted(component_external_ids):
                    cursor.execute(
                        """
                        INSERT INTO dm.canonical_game_external_ids (
                            canonical_game_id,
                            external_source,
                            external_id
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (component.canonical_game_id, external_source, external_id),
                    )
                    external_id_count += 1

            for qid in sorted(wikipedia_source_ids):
                canonical_game_id = wikidata_to_canonical.get(qid)
                if canonical_game_id is None:
                    continue
                cursor.execute(
                    """
                    INSERT INTO dm.canonical_game_sources (
                        canonical_game_id,
                        source,
                        source_game_id,
                        linkage_confidence
                    )
                    VALUES (%s, 'wikipedia', %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (canonical_game_id, qid, WIKIPEDIA_LINK_CONFIDENCE),
                )
                source_link_counter["wikipedia"] += 1

    return {
        "source_link_count_by_source": dict(sorted(source_link_counter.items())),
        "alias_count": alias_count,
        "external_id_count": external_id_count,
    }


def build_source_confidences(components: list[CanonicalComponent]) -> dict[SourceKey, float]:
    confidences: dict[SourceKey, float] = {}
    for component in components:
        deterministic_component = len(component.source_keys) > 1
        for source_key in component.source_keys:
            confidences[source_key] = (
                DETERMINISTIC_SOURCE_CONFIDENCE
                if deterministic_component
                else STANDALONE_SOURCE_CONFIDENCE
            )
    return confidences


def summarize_components(components: list[CanonicalComponent]) -> dict[str, object]:
    source_counter: Counter[str] = Counter()
    merged_component_count = 0
    for component in components:
        sources = {source for source, _ in component.source_keys}
        source_counter.update(sources)
        if len(sources) > 1:
            merged_component_count += 1
    return {
        "canonical_game_count": len(components),
        "merged_component_count": merged_component_count,
        "component_source_presence": dict(sorted(source_counter.items())),
        "max_component_size": max(
            (len(component.source_keys) for component in components), default=0
        ),
    }


def build_canonical_v0(repository: IngestionRepository | None = None) -> dict[str, object]:
    repository = repository or IngestionRepository()
    records = load_source_records(repository)
    candidate_pairs = fetch_candidate_pairs(repository)
    aliases = fetch_source_aliases(repository)
    wikipedia_source_ids = fetch_wikipedia_source_ids(repository)

    components = build_components(records, candidate_pairs)
    clear_canonical_tables(repository)
    write_summary = insert_canonical_components(
        repository,
        components,
        records,
        aliases,
        wikipedia_source_ids,
    )
    return {
        "canonical_version": "canonical_v0",
        "source_record_count": len(records),
        "trusted_candidate_pair_count": len(candidate_pairs),
        "wikipedia_description_qid_count": len(wikipedia_source_ids),
        **summarize_components(components),
        **write_summary,
    }


def build_canonical_v1(repository: IngestionRepository | None = None) -> dict[str, object]:
    repository = repository or IngestionRepository()
    records = load_source_records(repository)
    candidate_pairs = fetch_canonical_v1_candidate_pairs(repository)
    aliases = fetch_source_aliases(repository)
    wikipedia_source_ids = fetch_wikipedia_source_ids(repository)

    components = build_components(records, candidate_pairs)
    clear_canonical_tables(repository)
    write_summary = insert_canonical_components(
        repository,
        components,
        records,
        aliases,
        wikipedia_source_ids,
    )
    edge_source_counts = Counter(
        str(row.get("canonical_edge_source") or "unknown") for row in candidate_pairs
    )
    return {
        "canonical_version": "canonical_v1",
        "source_record_count": len(records),
        "trusted_candidate_pair_count": len(candidate_pairs),
        "trusted_candidate_pair_count_by_source": dict(sorted(edge_source_counts.items())),
        "wikipedia_description_qid_count": len(wikipedia_source_ids),
        **summarize_components(components),
        **write_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build dm.canonical_* tables.")
    parser.add_argument("--dry-run", action="store_true", help="Preview summary without DB writes.")
    parser.add_argument(
        "--version",
        choices=["v0", "v1"],
        default="v0",
        help="Canonical build strategy.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = IngestionRepository()
    records = load_source_records(repository)
    candidate_pairs = (
        fetch_candidate_pairs(repository)
        if args.version == "v0"
        else fetch_canonical_v1_candidate_pairs(repository)
    )
    components = build_components(records, candidate_pairs)
    edge_source_counts = Counter(
        str(row.get("canonical_edge_source") or "deterministic_external_id")
        for row in candidate_pairs
    )
    summary = {
        "canonical_version": f"canonical_{args.version}",
        "source_record_count": len(records),
        "trusted_candidate_pair_count": len(candidate_pairs),
        "trusted_candidate_pair_count_by_source": dict(sorted(edge_source_counts.items())),
        **summarize_components(components),
    }
    if args.dry_run:
        print({**summary, "dry_run": True, "writes_to": ["dm.canonical_*"]})
        return 0

    full_summary = (
        build_canonical_v0(repository) if args.version == "v0" else build_canonical_v1(repository)
    )
    print(full_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
