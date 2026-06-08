"""Build Bayesian rating research artifacts from canonical source ratings."""

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

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "bayesian_rating"
SUPPORTED_BAYESIAN_RATING_TYPES = (
    "rawg_rating",
    "igdb_rating",
    "igdb_aggregated_rating",
    "igdb_total_rating",
)


def normalize_rating(value: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("rating scale must be positive")
    return max(0.0, min(100.0, (float(value) / float(scale)) * 100.0))


def bayesian_average(
    rating: float, vote_count: float, global_mean: float, prior_votes: float
) -> float:
    if vote_count < 0:
        raise ValueError("vote_count must be non-negative")
    if prior_votes < 0:
        raise ValueError("prior_votes must be non-negative")
    denominator = vote_count + prior_votes
    if denominator == 0:
        return float(global_mean)
    return ((vote_count * rating) + (prior_votes * global_mean)) / denominator


def fetch_rows(
    repository: IngestionRepository, query: str, params: tuple[object, ...] = ()
) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def fetch_rating_source_summary(repository: IngestionRepository) -> list[dict[str, Any]]:
    return fetch_rows(
        repository,
        """
        SELECT
            source,
            rating_type,
            rating_scale,
            COUNT(*) AS row_count,
            COUNT(*) FILTER (WHERE rating_count IS NOT NULL AND rating_count > 0)
                AS with_vote_count,
            MIN(rating_value) AS min_rating,
            MAX(rating_value) AS max_rating,
            MAX(rating_count) AS max_vote_count
        FROM stg.source_game_ratings
        GROUP BY source, rating_type, rating_scale
        ORDER BY source, rating_type, rating_scale
        """,
    )


def fetch_canonical_rating_inputs(repository: IngestionRepository) -> list[dict[str, Any]]:
    return fetch_rows(
        repository,
        """
        SELECT
            cgs.canonical_game_id::TEXT AS canonical_game_id,
            cg.canonical_name,
            cg.release_year,
            r.source,
            r.source_game_id,
            r.rating_type,
            r.rating_value::FLOAT AS rating_value,
            r.rating_scale,
            r.rating_count,
            CASE
                WHEN r.rating_scale ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN (r.rating_value::FLOAT / NULLIF(r.rating_scale::FLOAT, 0)) * 100
                ELSE r.rating_value::FLOAT
            END AS normalized_rating
        FROM stg.source_game_ratings r
        JOIN dm.canonical_game_sources cgs
            ON cgs.source = r.source
           AND cgs.source_game_id = r.source_game_id
        JOIN dm.canonical_games cg
            ON cg.canonical_game_id = cgs.canonical_game_id
        WHERE r.rating_type = ANY(%s)
          AND r.rating_count IS NOT NULL
          AND r.rating_count > 0
          AND r.rating_value IS NOT NULL
          AND r.rating_value > 0
          AND r.rating_scale ~ '^[0-9]+(\\.[0-9]+)?$'
          AND r.rating_scale::FLOAT > 0
        """,
        (list(SUPPORTED_BAYESIAN_RATING_TYPES),),
    )


def build_canonical_bayesian_rows(
    rating_rows: list[dict[str, Any]],
    *,
    prior_votes: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    usable_rows = [
        {
            **row,
            "normalized_rating": normalize_rating(
                float(row["rating_value"]),
                float(row["rating_scale"]),
            ),
            "rating_count": int(row["rating_count"]),
        }
        for row in rating_rows
        if row.get("rating_count") is not None and int(row["rating_count"]) > 0
    ]
    total_votes = sum(int(row["rating_count"]) for row in usable_rows)
    if not usable_rows or total_votes <= 0:
        return [], {
            "rating_input_count": 0,
            "canonical_game_count": 0,
            "global_weighted_mean": None,
            "prior_votes": prior_votes,
        }

    global_weighted_mean = (
        sum(float(row["normalized_rating"]) * int(row["rating_count"]) for row in usable_rows)
        / total_votes
    )

    grouped: dict[str, dict[str, object]] = {}
    for row in usable_rows:
        canonical_game_id = str(row["canonical_game_id"])
        grouped.setdefault(
            canonical_game_id,
            {
                "canonical_game_id": canonical_game_id,
                "canonical_name": str(row["canonical_name"]),
                "release_year": row.get("release_year"),
                "weighted_rating_sum": 0.0,
                "vote_count": 0,
                "rating_source_count": 0,
                "rating_types": set(),
            },
        )
        target = grouped[canonical_game_id]
        target["weighted_rating_sum"] = float(target["weighted_rating_sum"]) + (
            float(row["normalized_rating"]) * int(row["rating_count"])
        )
        target["vote_count"] = int(target["vote_count"]) + int(row["rating_count"])
        target["rating_source_count"] = int(target["rating_source_count"]) + 1
        target["rating_types"].add(str(row["rating_type"]))  # type: ignore[union-attr]

    result_rows: list[dict[str, object]] = []
    for group in grouped.values():
        vote_count = int(group["vote_count"])
        naive_rating = float(group["weighted_rating_sum"]) / vote_count
        bayesian_rating = bayesian_average(
            naive_rating,
            vote_count,
            global_weighted_mean,
            prior_votes,
        )
        result_rows.append(
            {
                "canonical_game_id": group["canonical_game_id"],
                "canonical_name": group["canonical_name"],
                "release_year": group["release_year"],
                "naive_weighted_rating": round(naive_rating, 6),
                "bayesian_rating": round(bayesian_rating, 6),
                "vote_count": vote_count,
                "rating_source_count": group["rating_source_count"],
                "rating_types": ", ".join(sorted(group["rating_types"])),  # type: ignore[arg-type]
                "shrinkage_delta": round(bayesian_rating - naive_rating, 6),
            }
        )

    result_rows.sort(
        key=lambda row: (
            -float(row["bayesian_rating"]),
            -int(row["vote_count"]),
            str(row["canonical_name"]).lower(),
        )
    )
    return result_rows, {
        "rating_input_count": len(usable_rows),
        "canonical_game_count": len(result_rows),
        "global_weighted_mean": round(global_weighted_mean, 6),
        "prior_votes": prior_votes,
        "total_vote_count": total_votes,
    }


def low_vote_shift_examples(
    rows: list[dict[str, object]], limit: int = 25
) -> list[dict[str, object]]:
    examples = [
        row
        for row in rows
        if int(row["vote_count"]) < 50 and abs(float(row["shrinkage_delta"])) > 1.0
    ]
    examples.sort(
        key=lambda row: (
            -abs(float(row["shrinkage_delta"])),
            int(row["vote_count"]),
            str(row["canonical_name"]).lower(),
        )
    )
    return examples[:limit]


def build_chart_rows(rows: list[dict[str, object]], limit: int = 20) -> list[dict[str, object]]:
    return [
        {
            "canonical_name": row["canonical_name"],
            "bayesian_rating": row["bayesian_rating"],
            "vote_count": row["vote_count"],
        }
        for row in rows[:limit]
    ]


def write_markdown_summary(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# Bayesian Rating Analysis",
        "",
        "This generated report compares naive weighted source ratings with Bayesian "
        "adjusted ratings.",
        "",
        f"- Rating inputs: `{summary['rating_input_count']}`",
        f"- Canonical games with vote-backed ratings: `{summary['canonical_game_count']}`",
        f"- Global weighted mean: `{summary['global_weighted_mean']}`",
        f"- Prior votes: `{summary['prior_votes']}`",
        f"- Total vote count: `{summary['total_vote_count']}`",
        "",
        "Interpretation:",
        "",
        "- Naive ratings can over-rank games with very few votes.",
        "- Bayesian adjustment shrinks low-vote games toward the global mean.",
        "- This is a secondary ML/statistics block for defense, not a replacement "
        "for recommendations.",
        "",
    ]
    write_text(path, "\n".join(lines))


def build_bayesian_rating_analysis(output_dir: Path, *, prior_votes: float) -> dict[str, object]:
    repository = IngestionRepository()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_summary = fetch_rating_source_summary(repository)
    rating_inputs = fetch_canonical_rating_inputs(repository)
    bayesian_rows, summary = build_canonical_bayesian_rows(
        rating_inputs,
        prior_votes=prior_votes,
    )
    shift_examples = low_vote_shift_examples(bayesian_rows)
    chart_rows = build_chart_rows(bayesian_rows)

    write_csv(output_dir / "rating_source_summary.csv", source_summary)
    write_csv(output_dir / "canonical_bayesian_ratings.csv", bayesian_rows)
    write_csv(output_dir / "low_vote_shrinkage_examples.csv", shift_examples)
    write_json(output_dir / "bayesian_rating_summary.json", summary)
    write_markdown_summary(output_dir / "bayesian_rating_summary.md", summary)
    write_text(
        output_dir / "top_bayesian_ratings.svg",
        horizontal_bar_chart_svg(
            chart_rows,
            title="Top Bayesian Adjusted Ratings",
            label_key="canonical_name",
            value_key="bayesian_rating",
            value_label="Bayesian rating, 0-100",
        ),
    )
    return {
        "output_dir": str(output_dir),
        "rating_input_count": summary["rating_input_count"],
        "canonical_game_count": summary["canonical_game_count"],
        "low_vote_shift_examples": len(shift_examples),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Bayesian rating analysis artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--prior-votes", type=float, default=50.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_bayesian_rating_analysis(Path(args.output_dir), prior_votes=args.prior_votes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
