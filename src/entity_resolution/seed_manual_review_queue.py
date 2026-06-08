"""Seed DB-backed manual-review queues for ER training labels."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from src.entity_resolution.setup_manual_review import apply_manual_review_schema
from src.ingestion.repository import IngestionRepository


@dataclass(frozen=True, slots=True)
class ReviewSelectionStrategy:
    name: str
    where_sql: str
    priority_sql: str
    order_sql: str
    description: str


STRATEGIES: dict[str, ReviewSelectionStrategy] = {
    "igdb_suspicious_auto_merge": ReviewSelectionStrategy(
        name="igdb_suspicious_auto_merge",
        where_sql="""
            candidate_source = 'igdb_search'
            AND model_decision = 'auto_merge'
            AND (
                COALESCE(name_similarity, 0) < 0.75
                OR COALESCE(igdb_search_rank, 1) > 1
                OR COALESCE(igdb_search_confidence, 0) < 0.85
            )
        """,
        priority_sql="""
            (1 - COALESCE(name_similarity, 0))
            + (COALESCE(igdb_search_rank, 1) * 0.10)
            + (1 - COALESCE(igdb_search_confidence, 0))
        """,
        order_sql="""
            name_similarity ASC NULLS LAST,
            igdb_search_rank DESC NULLS LAST,
            igdb_search_confidence ASC NULLS LAST
        """,
        description="Likely false-positive IGDB auto-merge rows.",
    ),
    "igdb_low_similarity": ReviewSelectionStrategy(
        name="igdb_low_similarity",
        where_sql="""
            candidate_source = 'igdb_search'
            AND COALESCE(name_similarity, 0) < 0.70
        """,
        priority_sql="1 - COALESCE(name_similarity, 0)",
        order_sql="name_similarity ASC NULLS LAST, igdb_search_rank DESC NULLS LAST",
        description="IGDB pairs with weak title similarity.",
    ),
    "igdb_rank_2_3": ReviewSelectionStrategy(
        name="igdb_rank_2_3",
        where_sql="""
            candidate_source = 'igdb_search'
            AND COALESCE(igdb_search_rank, 1) >= 2
        """,
        priority_sql="COALESCE(igdb_search_rank, 1) * 0.25 + (1 - COALESCE(name_similarity, 0))",
        order_sql="igdb_search_rank DESC NULLS LAST, name_similarity ASC NULLS LAST",
        description="Non-top IGDB search candidates.",
    ),
    "igdb_borderline": ReviewSelectionStrategy(
        name="igdb_borderline",
        where_sql="""
            candidate_source = 'igdb_search'
            AND COALESCE(name_similarity, 0) >= 0.70
            AND COALESCE(name_similarity, 0) < 0.90
        """,
        priority_sql="ABS(COALESCE(name_similarity, 0) - 0.80) * -1 + 1",
        order_sql="ABS(COALESCE(name_similarity, 0) - 0.80) ASC, igdb_search_rank DESC NULLS LAST",
        description="Ambiguous IGDB title matches.",
    ),
    "igdb_likely_positive": ReviewSelectionStrategy(
        name="igdb_likely_positive",
        where_sql="""
            candidate_source = 'igdb_search'
            AND COALESCE(name_similarity, 0) >= 0.90
            AND COALESCE(release_year_diff, 99) <= 1
            AND COALESCE(igdb_search_rank, 1) = 1
            AND COALESCE(igdb_search_confidence, 0) >= 0.85
        """,
        priority_sql="COALESCE(name_similarity, 0) + COALESCE(igdb_search_confidence, 0)",
        order_sql="name_similarity DESC NULLS LAST, igdb_search_confidence DESC NULLS LAST",
        description="Likely positive IGDB examples for calibration.",
    ),
    "external_id_positive_control": ReviewSelectionStrategy(
        name="external_id_positive_control",
        where_sql="""
            candidate_source = 'external_id'
            AND label_value = '1'
        """,
        priority_sql="COALESCE(name_similarity, 0) + COALESCE(same_game_probability, 0)",
        order_sql="name_similarity ASC NULLS LAST, same_game_probability ASC NULLS LAST",
        description="Trusted positive-control rows from external IDs.",
    ),
    "same_name_year_negative_control": ReviewSelectionStrategy(
        name="same_name_year_negative_control",
        where_sql="""
            candidate_source = 'same_normalized_name'
            AND COALESCE(release_year_diff, 0) >= 10
        """,
        priority_sql="COALESCE(release_year_diff, 0)",
        order_sql="release_year_diff DESC NULLS LAST, name_similarity DESC NULLS LAST",
        description="Likely negative-control rows with same names but far-apart years.",
    ),
}


def strategy_names() -> list[str]:
    return sorted(STRATEGIES)


def seed_strategy(
    repository: IngestionRepository,
    strategy: ReviewSelectionStrategy,
    *,
    limit: int,
    dry_run: bool = False,
) -> int:
    query = f"""
        WITH selected AS (
            SELECT
                pair_id,
                %s::TEXT AS selection_strategy,
                ({strategy.priority_sql})::NUMERIC(10, 6) AS priority_score
            FROM ml.v_entity_resolution_review_candidates
            WHERE ({strategy.where_sql})
              AND (review_status IS NULL OR review_status = 'pending')
              AND review_label IS NULL
            ORDER BY {strategy.order_sql}, pair_id
            LIMIT %s
        )
        INSERT INTO ml.entity_resolution_manual_reviews (
            pair_id,
            selection_strategy,
            priority_score
        )
        SELECT
            pair_id,
            selection_strategy,
            priority_score
        FROM selected
        ON CONFLICT (pair_id)
        DO NOTHING
        RETURNING pair_id
    """
    if dry_run:
        count_query = f"""
            SELECT COUNT(*) AS candidate_count
            FROM ml.v_entity_resolution_review_candidates
            WHERE ({strategy.where_sql})
              AND (review_status IS NULL OR review_status = 'pending')
              AND review_label IS NULL
        """
        with repository.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(count_query)
                row = cursor.fetchone()
                return int(row["candidate_count"])

    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (strategy.name, limit))
            return len(cursor.fetchall())


def seed_manual_review_queue(
    *,
    strategy_name: str,
    limit_per_strategy: int,
    dry_run: bool = False,
    repository: IngestionRepository | None = None,
) -> list[dict[str, object]]:
    repository = repository or IngestionRepository()
    apply_manual_review_schema(repository)
    selected_strategies = (
        list(STRATEGIES.values())
        if strategy_name == "all"
        else [STRATEGIES[strategy_name]]
    )
    return [
        {
            "strategy": strategy.name,
            "description": strategy.description,
            "row_count": seed_strategy(
                repository,
                strategy,
                limit=limit_per_strategy,
                dry_run=dry_run,
            ),
            "dry_run": dry_run,
        }
        for strategy in selected_strategies
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed DB-backed manual-review rows.")
    parser.add_argument(
        "--strategy",
        choices=["all", *strategy_names()],
        default="all",
        help="Selection strategy to seed.",
    )
    parser.add_argument(
        "--limit-per-strategy",
        type=int,
        default=50,
        help="Maximum rows inserted per strategy.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count candidates without inserts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = seed_manual_review_queue(
        strategy_name=args.strategy,
        limit_per_strategy=args.limit_per_strategy,
        dry_run=args.dry_run,
    )
    print({"manual_review_seed_summary": summary})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
