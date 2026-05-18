"""Transform Wikidata raw payloads into source-normalized staging tables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.ingestion.repository import IngestionRepository


def normalize_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    value = binding.get(key)
    if not isinstance(value, dict):
        return None
    raw_value = value.get("value")
    return str(raw_value) if raw_value not in (None, "") else None


def parse_qid(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return value


def parse_release_date(value: str | None) -> tuple[str | None, int | None]:
    if not value:
        return None, None
    if not re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return None, None
    date_value = value[:10]
    year = int(date_value[:4]) if len(date_value) >= 4 and date_value[:4].isdigit() else None
    return date_value, year


def wikipedia_title_to_url(language: str, title: str | None) -> str | None:
    if not title:
        return None
    return f"https://{language}.wikipedia.org/wiki/{title.replace(' ', '_')}"


def parse_sparql_bindings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results", {})
    bindings = results.get("bindings", []) if isinstance(results, dict) else []
    return [item for item in bindings if isinstance(item, dict)]


def parse_entity_claim_strings(entity: dict[str, Any], property_id: str) -> list[str]:
    claims = entity.get("claims", {})
    property_claims = claims.get(property_id, []) if isinstance(claims, dict) else []
    values: list[str] = []
    for claim in property_claims:
        if not isinstance(claim, dict):
            continue
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {}) if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else None
        if value is None:
            continue
        values.append(str(value))
    return values


def parse_entity_labels(entity: dict[str, Any], language: str) -> str | None:
    labels = entity.get("labels", {})
    lang_data = labels.get(language, {}) if isinstance(labels, dict) else {}
    if isinstance(lang_data, dict) and lang_data.get("value"):
        return str(lang_data["value"])
    return None


def parse_entity_aliases(entity: dict[str, Any], language: str) -> list[str]:
    aliases = entity.get("aliases", {})
    entries = aliases.get(language, []) if isinstance(aliases, dict) else []
    values: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("value"):
            values.append(str(entry["value"]))
    return values


def parse_entity_sitelink_title(entity: dict[str, Any], site: str) -> str | None:
    sitelinks = entity.get("sitelinks", {})
    site_data = sitelinks.get(site, {}) if isinstance(sitelinks, dict) else {}
    if isinstance(site_data, dict) and site_data.get("title"):
        return str(site_data["title"])
    return None


@dataclass(slots=True)
class WikidataGame:
    qid: str
    label: str | None = None
    label_ru: str | None = None
    label_en: str | None = None
    release_date: str | None = None
    release_year: int | None = None
    raw_loaded_at: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, set[str]] = field(default_factory=lambda: {"ru": set(), "en": set()})
    sitelinks: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WikidataStagingBundle:
    source_games: list[dict[str, object]] = field(default_factory=list)
    source_game_aliases: list[dict[str, object]] = field(default_factory=list)
    source_game_external_ids: list[dict[str, object]] = field(default_factory=list)
    source_game_urls: list[dict[str, object]] = field(default_factory=list)


def merge_sparql_bindings(
    records: dict[str, WikidataGame],
    payloads: list[tuple[dict[str, Any], str]],
) -> dict[str, WikidataGame]:
    for payload, loaded_at in payloads:
        for binding in parse_sparql_bindings(payload):
            qid = parse_qid(binding_value(binding, "qid") or binding_value(binding, "game"))
            if not qid:
                continue
            record = records.setdefault(qid, WikidataGame(qid=qid))
            record.raw_loaded_at = loaded_at
            record.label = record.label or binding_value(binding, "label")
            record.label_ru = record.label_ru or binding_value(binding, "labelRu")
            record.label_en = record.label_en or binding_value(binding, "labelEn")
            if release_value := binding_value(binding, "releaseDate"):
                record.release_date, record.release_year = parse_release_date(release_value)
            for external_source, binding_key in (
                ("rawg", "rawg"),
                ("steam", "steam"),
                ("igdb", "igdb"),
            ):
                if value := binding_value(binding, binding_key):
                    record.external_ids[external_source] = value
            if alias_ru := binding_value(binding, "aliasRu"):
                record.aliases["ru"].add(alias_ru)
            if alias_en := binding_value(binding, "aliasEn"):
                record.aliases["en"].add(alias_en)
            if article_ru := binding_value(binding, "articleRu"):
                record.sitelinks["ruwiki"] = article_ru
            if article_en := binding_value(binding, "articleEn"):
                record.sitelinks["enwiki"] = article_en
    return records


def merge_entity_payloads(
    records: dict[str, WikidataGame],
    payloads: dict[str, tuple[dict[str, Any], str]],
) -> dict[str, WikidataGame]:
    for qid, (payload, loaded_at) in payloads.items():
        entities = payload.get("entities", {})
        entity = entities.get(qid, {}) if isinstance(entities, dict) else {}
        if not isinstance(entity, dict):
            continue
        record = records.setdefault(qid, WikidataGame(qid=qid))
        record.raw_loaded_at = loaded_at
        record.label_ru = record.label_ru or parse_entity_labels(entity, "ru")
        record.label_en = record.label_en or parse_entity_labels(entity, "en")
        record.label = record.label or record.label_ru or record.label_en
        for language in ("ru", "en"):
            for alias in parse_entity_aliases(entity, language):
                record.aliases[language].add(alias)
        for external_source, property_id in (
            ("rawg", "P9968"),
            ("steam", "P1733"),
            ("igdb", "P9043"),
        ):
            values = parse_entity_claim_strings(entity, property_id)
            if values:
                record.external_ids[external_source] = values[0]
        for site_name, language in (("ruwiki", "ru"), ("enwiki", "en")):
            title = parse_entity_sitelink_title(entity, site_name)
            if title:
                url = wikipedia_title_to_url(language, title)
                if url:
                    record.sitelinks[site_name] = url
    return records


def transform_wikidata_payloads(
    sparql_payloads: list[tuple[dict[str, Any], str]],
    entity_payloads: dict[str, tuple[dict[str, Any], str]],
) -> WikidataStagingBundle:
    records: dict[str, WikidataGame] = {}
    merge_sparql_bindings(records, sparql_payloads)
    merge_entity_payloads(records, entity_payloads)

    bundle = WikidataStagingBundle()
    now = datetime.now(UTC).isoformat()
    seen_aliases: set[tuple[str, str, str]] = set()
    seen_external_ids: set[tuple[str, str, str]] = set()
    seen_urls: set[tuple[str, str]] = set()

    for qid, record in sorted(records.items()):
        name = record.label_ru or record.label_en or record.label or qid
        bundle.source_games.append(
            {
                "source": "wikidata",
                "source_game_id": qid,
                "name": name,
                "name_normalized": normalize_name(name),
                "release_date": record.release_date,
                "release_year": record.release_year,
                "slug": qid,
                "game_type": "video_game",
                "is_dlc": False,
                "is_demo": False,
                "is_remake": False,
                "is_remaster": False,
                "is_bundle": False,
                "raw_loaded_at": record.raw_loaded_at,
                "stg_loaded_at": now,
                "source_priority": 80,
                "quality_flags_json": {
                    "has_external_ids": bool(record.external_ids),
                    "has_sitelinks": bool(record.sitelinks),
                    "has_ru_label": bool(record.label_ru),
                    "has_en_label": bool(record.label_en),
                },
            }
        )

        for language, aliases in record.aliases.items():
            for alias in sorted(aliases):
                alias_key = (qid, language, alias)
                if alias_key in seen_aliases:
                    continue
                seen_aliases.add(alias_key)
                bundle.source_game_aliases.append(
                    {
                        "source": "wikidata",
                        "source_game_id": qid,
                        "alias": alias,
                        "language": language,
                        "alias_type": "wikidata_alt_label",
                        "source_specific_json": {},
                        "stg_loaded_at": now,
                    }
                )

        for external_source, external_id in sorted(record.external_ids.items()):
            ext_key = (qid, external_source, external_id)
            if ext_key in seen_external_ids:
                continue
            seen_external_ids.add(ext_key)
            bundle.source_game_external_ids.append(
                {
                    "source": "wikidata",
                    "source_game_id": qid,
                    "external_source": external_source,
                    "external_id": external_id,
                    "confidence": 1.0,
                    "source_specific_json": {"match_type": "wikidata_direct_property"},
                    "stg_loaded_at": now,
                }
            )

        for site_name, url in sorted(record.sitelinks.items()):
            url_key = (qid, site_name)
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            bundle.source_game_urls.append(
                {
                    "source": "wikidata",
                    "source_game_id": qid,
                    "url_type": site_name,
                    "url": url,
                    "source_specific_json": {
                        "language": "ru" if site_name == "ruwiki" else "en",
                    },
                    "stg_loaded_at": now,
                }
            )

    return bundle


def load_wikidata_payloads(
    repository: IngestionRepository,
) -> tuple[list[tuple[dict[str, Any], str]], dict[str, tuple[dict[str, Any], str]]]:
    sparql_rows = repository.fetch_raw_rows("raw.wikidata_sparql_results")
    entity_rows = repository.fetch_raw_rows("raw.wikidata_entities")
    sparql_payloads = [
        (row.get("response_json") or {}, str(row.get("loaded_at")))
        for row in sparql_rows
        if isinstance(row.get("response_json"), dict)
    ]
    entity_payloads = {
        str(row.get("source_record_id")): (
            row.get("response_json") or {},
            str(row.get("loaded_at")),
        )
        for row in entity_rows
        if isinstance(row.get("response_json"), dict) and row.get("source_record_id") is not None
    }
    return sparql_payloads, entity_payloads


def write_bundle(repository: IngestionRepository, bundle: WikidataStagingBundle) -> None:
    repository.replace_source_staging_rows(
        source="wikidata",
        table_name="stg.source_games",
        rows=bundle.source_games,
        key_columns=["source", "source_game_id"],
    )
    repository.replace_source_staging_rows(
        source="wikidata",
        table_name="stg.source_game_aliases",
        rows=bundle.source_game_aliases,
        key_columns=["source", "source_game_id", "alias", "language", "alias_type"],
    )
    repository.replace_source_staging_rows(
        source="wikidata",
        table_name="stg.source_game_external_ids",
        rows=bundle.source_game_external_ids,
        key_columns=["source", "source_game_id", "external_source", "external_id"],
    )
    repository.replace_source_staging_rows(
        source="wikidata",
        table_name="stg.source_game_urls",
        rows=bundle.source_game_urls,
        key_columns=["source", "source_game_id", "url_type", "url"],
    )


def main() -> int:
    repository = IngestionRepository()
    sparql_payloads, entity_payloads = load_wikidata_payloads(repository)
    bundle = transform_wikidata_payloads(sparql_payloads, entity_payloads)
    write_bundle(repository, bundle)
    print(
        {
            "source_games": len(bundle.source_games),
            "aliases": len(bundle.source_game_aliases),
            "external_ids": len(bundle.source_game_external_ids),
            "urls": len(bundle.source_game_urls),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
