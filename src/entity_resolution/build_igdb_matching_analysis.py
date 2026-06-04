"""Build IGDB-specific ER matching research artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.entity_resolution.build_research_defense_artifacts import (
    horizontal_bar_chart_svg,
    write_csv,
    write_json,
    write_text,
)
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "igdb_matching"


def safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "unknown"
    if rank <= 1:
        return "1"
    if rank <= 3:
        return "2-3"
    if rank <= 5:
        return "4-5"
    return "6+"


def confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    if confidence >= 0.95:
        return "0.95-1.00"
    if confidence >= 0.85:
        return "0.85-0.95"
    if confidence >= 0.70:
        return "0.70-0.85"
    return "<0.70"


def precision_row(
    *,
    bucket_name: str,
    bucket_value: str,
    reviewed_positive_count: int,
    reviewed_negative_count: int,
) -> dict[str, object]:
    reviewed_count = reviewed_positive_count + reviewed_negative_count
    return {
        "bucket_name": bucket_name,
        "bucket_value": bucket_value,
        "reviewed_count": reviewed_count,
        "reviewed_positive_count": reviewed_positive_count,
        "reviewed_negative_count": reviewed_negative_count,
        "reviewed_precision": safe_ratio(reviewed_positive_count, reviewed_count),
    }


def reviewed_precision_by_bucket(
    rows: list[dict[str, Any]],
    *,
    bucket_name: str,
    bucket_key: str,
) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.get("review_status") != "reviewed" or row.get("review_label") is None:
            continue
        bucket_value = str(row[bucket_key])
        counts = buckets.setdefault(bucket_value, {"positive": 0, "negative": 0})
        if row["review_label"] is True:
            counts["positive"] += 1
        else:
            counts["negative"] += 1
    return [
        precision_row(
            bucket_name=bucket_name,
            bucket_value=bucket_value,
            reviewed_positive_count=counts["positive"],
            reviewed_negative_count=counts["negative"],
        )
        for bucket_value, counts in sorted(buckets.items())
    ]


def fetch_rows(
    repository: IngestionRepository, query: str, params: tuple[object, ...] = ()
) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def fetch_scalar_counts(repository: IngestionRepository) -> dict[str, int]:
    rows = fetch_rows(
        repository,
        """
        SELECT 'igdb_search_candidates' AS metric, COUNT(*) AS value
        FROM ml.igdb_search_candidates
        UNION ALL
        SELECT 'igdb_pairs', COUNT(*)
        FROM ml.v_entity_resolution_review_candidates
        WHERE candidate_source = 'igdb_search'
        UNION ALL
        SELECT 'igdb_source_games', COUNT(*)
        FROM stg.source_games
        WHERE source = 'igdb'
        UNION ALL
        SELECT 'rawg_anchors', COUNT(DISTINCT source_game_id)
        FROM ml.igdb_search_candidates
        WHERE source_name = 'rawg'
        """,
    )
    return {str(row["metric"]): int(row["value"]) for row in rows}


def fetch_candidate_summary(repository: IngestionRepository) -> dict[str, list[dict[str, Any]]]:
    candidates = fetch_rows(
        repository,
        """
        SELECT
            source_name,
            COUNT(*) AS candidate_count,
            COUNT(DISTINCT source_game_id) AS anchor_count,
            ROUND(AVG(search_rank)::NUMERIC, 6) AS avg_search_rank,
            MIN(search_rank) AS min_search_rank,
            MAX(search_rank) AS max_search_rank,
            ROUND(AVG(confidence)::NUMERIC, 6) AS avg_confidence
        FROM ml.igdb_search_candidates
        GROUP BY source_name
        ORDER BY source_name
        """,
    )
    query_strategy = fetch_rows(
        repository,
        """
        SELECT
            query_strategy,
            COUNT(*) AS candidate_count,
            COUNT(DISTINCT source_game_id) AS anchor_count,
            ROUND(AVG(search_rank)::NUMERIC, 6) AS avg_search_rank,
            ROUND(AVG(confidence)::NUMERIC, 6) AS avg_confidence
        FROM ml.igdb_search_candidates
        GROUP BY query_strategy
        ORDER BY candidate_count DESC, query_strategy
        """,
    )
    rank_distribution = fetch_rows(
        repository,
        """
        SELECT
            search_rank,
            COUNT(*) AS candidate_count,
            COUNT(DISTINCT source_game_id) AS anchor_count,
            ROUND(AVG(confidence)::NUMERIC, 6) AS avg_confidence
        FROM ml.igdb_search_candidates
        GROUP BY search_rank
        ORDER BY search_rank
        """,
    )
    return {
        "source_summary": candidates,
        "query_strategy_summary": query_strategy,
        "rank_distribution": rank_distribution,
    }


def fetch_review_rows(repository: IngestionRepository) -> list[dict[str, Any]]:
    rows = fetch_rows(
        repository,
        """
        SELECT
            pair_id::TEXT AS pair_id,
            source_a,
            source_id_a,
            name_a,
            release_year_a,
            source_b,
            source_id_b,
            name_b,
            release_year_b,
            candidate_source,
            igdb_search_rank,
            igdb_query_strategy,
            igdb_search_confidence,
            name_similarity,
            alias_similarity,
            release_year_diff,
            same_game_probability,
            model_decision,
            review_label,
            review_status,
            selection_strategy,
            priority_score,
            review_notes
        FROM ml.v_igdb_manual_review_queue
        ORDER BY pair_id
        """,
    )
    for row in rows:
        row["igdb_rank_bucket"] = rank_bucket(
            int(row["igdb_search_rank"]) if row.get("igdb_search_rank") is not None else None
        )
        row["igdb_confidence_bucket"] = confidence_bucket(
            float(row["igdb_search_confidence"])
            if row.get("igdb_search_confidence") is not None
            else None
        )
    return rows


def review_label_summary(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        status = str(row.get("review_status") or "missing")
        counts = summary.setdefault(
            status,
            {"row_count": 0, "positive": 0, "negative": 0, "unlabeled": 0},
        )
        counts["row_count"] += 1
        if row.get("review_label") is True:
            counts["positive"] += 1
        elif row.get("review_label") is False:
            counts["negative"] += 1
        else:
            counts["unlabeled"] += 1
    return [
        {
            "review_status": status,
            "row_count": counts["row_count"],
            "reviewed_positive_count": counts["positive"],
            "reviewed_negative_count": counts["negative"],
            "unlabeled_count": counts["unlabeled"],
            "reviewed_precision": safe_ratio(
                counts["positive"], counts["positive"] + counts["negative"]
            ),
        }
        for status, counts in sorted(summary.items())
    ]


def high_risk_reviewed_negatives(
    rows: list[dict[str, Any]], limit: int = 100
) -> list[dict[str, object]]:
    result = []
    for row in rows:
        if row.get("review_status") != "reviewed" or row.get("review_label") is not False:
            continue
        probability = float(row["same_game_probability"] or 0)
        if probability < 0.70 and str(row.get("model_decision") or "") != "auto_merge":
            continue
        result.append(export_review_row(row, "reviewed_negative_high_model_score"))
    result.sort(
        key=lambda row: (
            -float(row.get("same_game_probability") or 0),
            str(row.get("name_a") or "").lower(),
            str(row.get("name_b") or "").lower(),
        )
    )
    return result[:limit]


def likely_positive_candidates(
    rows: list[dict[str, Any]], limit: int = 100
) -> list[dict[str, object]]:
    result = []
    for row in rows:
        if row.get("review_status") == "reviewed":
            continue
        name_similarity = float(row["name_similarity"] or 0)
        release_year_diff = row.get("release_year_diff")
        rank = int(row["igdb_search_rank"] or 999)
        confidence = float(row["igdb_search_confidence"] or 0)
        if (
            name_similarity >= 0.90
            and rank == 1
            and confidence >= 0.85
            and (release_year_diff is None or int(release_year_diff) <= 1)
        ):
            result.append(export_review_row(row, "unreviewed_likely_positive"))
    result.sort(
        key=lambda row: (
            -float(row.get("name_similarity") or 0),
            -float(row.get("igdb_search_confidence") or 0),
            str(row.get("name_a") or "").lower(),
        )
    )
    return result[:limit]


def export_review_row(row: dict[str, Any], case_type: str) -> dict[str, object]:
    return {
        "case_type": case_type,
        "pair_id": row.get("pair_id"),
        "source_a": row.get("source_a"),
        "source_id_a": row.get("source_id_a"),
        "name_a": row.get("name_a"),
        "release_year_a": row.get("release_year_a"),
        "source_b": row.get("source_b"),
        "source_id_b": row.get("source_id_b"),
        "name_b": row.get("name_b"),
        "release_year_b": row.get("release_year_b"),
        "igdb_search_rank": row.get("igdb_search_rank"),
        "igdb_query_strategy": row.get("igdb_query_strategy"),
        "igdb_search_confidence": row.get("igdb_search_confidence"),
        "name_similarity": row.get("name_similarity"),
        "alias_similarity": row.get("alias_similarity"),
        "release_year_diff": row.get("release_year_diff"),
        "same_game_probability": row.get("same_game_probability"),
        "model_decision": row.get("model_decision"),
        "review_label": row.get("review_label"),
        "review_status": row.get("review_status"),
        "selection_strategy": row.get("selection_strategy"),
        "review_notes": row.get("review_notes"),
    }


def fetch_enrichment_coverage(repository: IngestionRepository) -> list[dict[str, object]]:
    rows = fetch_rows(
        repository,
        """
        WITH igdb_games AS (
            SELECT source_game_id
            FROM stg.source_games
            WHERE source = 'igdb'
        ),
        coverage AS (
            SELECT 'aliases' AS feature, COUNT(DISTINCT source_game_id) AS game_count
            FROM stg.source_game_aliases
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'companies', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_companies
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'descriptions', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_descriptions
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'genres', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_genres
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'platforms', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_platforms
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'ratings', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_ratings
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'tags', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_tags
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'themes', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_themes
            WHERE source = 'igdb'
            UNION ALL
            SELECT 'urls', COUNT(DISTINCT source_game_id)
            FROM stg.source_game_urls
            WHERE source = 'igdb'
        )
        SELECT
            feature,
            game_count,
            (SELECT COUNT(*) FROM igdb_games) AS igdb_game_count
        FROM coverage
        ORDER BY feature
        """,
    )
    return [
        {
            "feature": row["feature"],
            "game_count": int(row["game_count"]),
            "igdb_game_count": int(row["igdb_game_count"]),
            "coverage_rate": safe_ratio(int(row["game_count"]), int(row["igdb_game_count"])),
        }
        for row in rows
    ]


def write_markdown_summary(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# IGDB Matching Analysis",
        "",
        "This report analyzes the IGDB search-based ER lane without mutating canonical tables.",
        "",
        f"- IGDB search candidates: `{summary['igdb_search_candidates']}`",
        f"- IGDB candidate pairs: `{summary['igdb_pairs']}`",
        f"- IGDB staged games: `{summary['igdb_source_games']}`",
        f"- RAWG anchors with IGDB candidates: `{summary['rawg_anchors']}`",
        f"- Reviewed IGDB pairs: `{summary['reviewed_pair_count']}`",
        f"- Reviewed positives: `{summary['reviewed_positive_count']}`",
        f"- Reviewed negatives: `{summary['reviewed_negative_count']}`",
        f"- Reviewed precision: `{summary['reviewed_precision']}`",
        f"- High-risk reviewed negatives: `{summary['high_risk_reviewed_negative_count']}`",
        f"- Likely positive unreviewed candidates: `{summary['likely_positive_candidate_count']}`",
        "",
        "Interpretation:",
        "",
        "- IGDB is now a real search-based candidate lane, not only an ID enrichment source.",
        "- Reviewed precision is useful for measuring retrieval quality, but it depends on the "
        "manual-review sampling strategy.",
        "- High-risk reviewed negatives expose remaster, edition, sequel and franchise cases.",
        "- Enrichment coverage shows which IGDB fields can improve downstream ER and ranking.",
        "",
    ]
    write_text(path, "\n".join(lines))


def build_igdb_matching_analysis(output_dir: Path) -> dict[str, object]:
    repository = IngestionRepository()
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = fetch_scalar_counts(repository)
    candidate_summary = fetch_candidate_summary(repository)
    review_rows = fetch_review_rows(repository)
    reviewed_count = sum(1 for row in review_rows if row.get("review_status") == "reviewed")
    reviewed_positive_count = sum(1 for row in review_rows if row.get("review_label") is True)
    reviewed_negative_count = sum(1 for row in review_rows if row.get("review_label") is False)
    rank_precision_rows = reviewed_precision_by_bucket(
        review_rows,
        bucket_name="igdb_rank_bucket",
        bucket_key="igdb_rank_bucket",
    )
    confidence_precision_rows = reviewed_precision_by_bucket(
        review_rows,
        bucket_name="igdb_confidence_bucket",
        bucket_key="igdb_confidence_bucket",
    )
    high_risk_rows = high_risk_reviewed_negatives(review_rows)
    likely_positive_rows = likely_positive_candidates(review_rows)
    enrichment_rows = fetch_enrichment_coverage(repository)
    summary = {
        **counts,
        "reviewed_pair_count": reviewed_count,
        "reviewed_positive_count": reviewed_positive_count,
        "reviewed_negative_count": reviewed_negative_count,
        "reviewed_precision": safe_ratio(reviewed_positive_count, reviewed_count),
        "high_risk_reviewed_negative_count": len(high_risk_rows),
        "likely_positive_candidate_count": len(likely_positive_rows),
    }

    write_csv(
        output_dir / "igdb_candidate_retrieval_summary.csv", candidate_summary["source_summary"]
    )
    write_csv(
        output_dir / "igdb_query_strategy_summary.csv", candidate_summary["query_strategy_summary"]
    )
    write_csv(output_dir / "igdb_rank_distribution.csv", candidate_summary["rank_distribution"])
    write_csv(output_dir / "igdb_review_label_summary.csv", review_label_summary(review_rows))
    write_csv(output_dir / "igdb_review_precision_by_rank.csv", rank_precision_rows)
    write_csv(output_dir / "igdb_review_precision_by_confidence.csv", confidence_precision_rows)
    write_csv(output_dir / "igdb_high_risk_reviewed_negatives.csv", high_risk_rows)
    write_csv(output_dir / "igdb_likely_positive_candidates.csv", likely_positive_rows)
    write_csv(output_dir / "igdb_enrichment_coverage.csv", enrichment_rows)
    write_json(
        output_dir / "igdb_matching_summary.json",
        {
            **summary,
            "candidate_summary": candidate_summary,
            "rank_precision": rank_precision_rows,
            "confidence_precision": confidence_precision_rows,
            "enrichment_coverage": enrichment_rows,
        },
    )
    write_markdown_summary(output_dir / "igdb_matching_summary.md", summary)
    write_text(
        output_dir / "igdb_rank_distribution.svg",
        horizontal_bar_chart_svg(
            candidate_summary["rank_distribution"],
            title="IGDB Search Candidate Distribution By Rank",
            label_key="search_rank",
            value_key="candidate_count",
            value_label="candidate rows",
        ),
    )
    write_text(
        output_dir / "igdb_enrichment_coverage.svg",
        horizontal_bar_chart_svg(
            enrichment_rows,
            title="IGDB Enrichment Coverage By Feature",
            label_key="feature",
            value_key="coverage_rate",
            value_label="coverage rate",
        ),
    )
    return {
        "output_dir": str(output_dir),
        **summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build IGDB matching analysis artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_igdb_matching_analysis(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
