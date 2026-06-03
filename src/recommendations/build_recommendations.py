"""Build baseline content-based recommendations from canonical game facts."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from psycopg.types.json import Jsonb

from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

FEATURE_WEIGHTS = {
    "genre": 3.0,
    "developer": 2.0,
    "publisher": 1.5,
    "tag": 1.0,
    "platform": 0.5,
    "decade": 0.25,
}


@dataclass(frozen=True, slots=True)
class CanonicalGameFeatures:
    canonical_game_id: str
    canonical_name: str
    release_year: int | None
    features: dict[str, float]


def normalize_feature_value(value: object) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def feature_key(feature_type: str, value: object) -> str | None:
    normalized = normalize_feature_value(value)
    if normalized is None:
        return None
    return f"{feature_type}:{normalized}"


def release_decade_feature(release_year: int | None) -> str | None:
    if release_year is None:
        return None
    return f"decade:{(int(release_year) // 10) * 10}s"


def weighted_jaccard(left: dict[str, float], right: dict[str, float]) -> float:
    shared = set(left) & set(right)
    if not shared:
        return 0.0
    overlap = sum(min(left[key], right[key]) for key in shared)
    union = sum(left.values()) + sum(right.values()) - overlap
    return overlap / union if union else 0.0


def top_overlap_features(
    left: dict[str, float],
    right: dict[str, float],
    *,
    limit: int = 8,
) -> list[str]:
    shared = sorted(
        set(left) & set(right),
        key=lambda key: min(left[key], right[key]),
        reverse=True,
    )
    return shared[:limit]


def build_recommendation_rows(
    games: list[CanonicalGameFeatures],
    *,
    top_k: int,
    max_block_size: int,
    max_candidates_per_game: int,
    min_score: float,
) -> list[dict[str, object]]:
    game_by_id = {game.canonical_game_id: game for game in games}
    inverted_index: dict[str, list[str]] = defaultdict(list)
    for game in games:
        for feature in game.features:
            inverted_index[feature].append(game.canonical_game_id)

    usable_index = {
        feature: ids for feature, ids in inverted_index.items() if 1 < len(ids) <= max_block_size
    }
    rows: list[dict[str, object]] = []
    for game in games:
        candidate_counter: Counter[str] = Counter()
        for feature, feature_weight in game.features.items():
            candidate_ids = usable_index.get(feature, [])
            for candidate_id in candidate_ids:
                if candidate_id != game.canonical_game_id:
                    candidate_counter[candidate_id] += feature_weight

        scored: list[tuple[float, str, list[str]]] = []
        for candidate_id, _overlap_weight in candidate_counter.most_common(max_candidates_per_game):
            candidate = game_by_id[candidate_id]
            score = weighted_jaccard(game.features, candidate.features)
            if score >= min_score:
                scored.append(
                    (
                        score,
                        candidate_id,
                        top_overlap_features(game.features, candidate.features),
                    )
                )

        scored.sort(
            key=lambda item: (
                -item[0],
                game_by_id[item[1]].canonical_name.lower(),
                item[1],
            )
        )
        for rank, (score, candidate_id, overlap_features) in enumerate(scored[:top_k], start=1):
            candidate = game_by_id[candidate_id]
            rows.append(
                {
                    "canonical_game_id": game.canonical_game_id,
                    "recommended_canonical_game_id": candidate_id,
                    "rank": rank,
                    "score": round(score, 6),
                    "algorithm": "content_jaccard_v1",
                    "explanation_factors_json": {
                        "shared_features": overlap_features,
                        "source_feature_count": len(game.features),
                        "candidate_feature_count": len(candidate.features),
                    },
                }
            )
    return rows


def fetch_canonical_game_features(
    repository: IngestionRepository,
    *,
    limit_games: int | None = None,
) -> list[CanonicalGameFeatures]:
    limit_sql = "LIMIT %s" if limit_games is not None else ""
    params: tuple[object, ...] = (limit_games,) if limit_games is not None else ()
    query = f"""
        WITH selected_games AS (
            SELECT canonical_game_id, canonical_name, release_year
            FROM dm.canonical_games
            ORDER BY canonical_name, canonical_game_id
            {limit_sql}
        ),
        canonical_sources AS (
            SELECT s.canonical_game_id, s.source, s.source_game_id
            FROM dm.canonical_game_sources s
            JOIN selected_games g ON g.canonical_game_id = s.canonical_game_id
        ),
        source_features AS (
            SELECT cs.canonical_game_id, 'genre' AS feature_type, f.genre_name AS feature_value
            FROM canonical_sources cs
            JOIN stg.source_game_genres f
                ON f.source = cs.source AND f.source_game_id = cs.source_game_id
            UNION ALL
            SELECT cs.canonical_game_id, 'tag', f.tag_name
            FROM canonical_sources cs
            JOIN stg.source_game_tags f
                ON f.source = cs.source AND f.source_game_id = cs.source_game_id
            UNION ALL
            SELECT cs.canonical_game_id, 'platform', f.platform_name
            FROM canonical_sources cs
            JOIN stg.source_game_platforms f
                ON f.source = cs.source AND f.source_game_id = cs.source_game_id
            UNION ALL
            SELECT cs.canonical_game_id, f.company_role, f.company_name
            FROM canonical_sources cs
            JOIN stg.source_game_companies f
                ON f.source = cs.source AND f.source_game_id = cs.source_game_id
            WHERE f.company_role IN ('developer', 'publisher')
        )
        SELECT
            g.canonical_game_id::TEXT AS canonical_game_id,
            g.canonical_name,
            g.release_year,
            sf.feature_type,
            sf.feature_value
        FROM selected_games g
        LEFT JOIN source_features sf ON sf.canonical_game_id = g.canonical_game_id
        ORDER BY g.canonical_name, g.canonical_game_id, sf.feature_type, sf.feature_value
    """
    feature_maps: dict[str, dict[str, float]] = defaultdict(dict)
    game_names: dict[str, str] = {}
    game_years: dict[str, int | None] = {}
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = list(cursor.fetchall())

    for row in rows:
        canonical_game_id = str(row["canonical_game_id"])
        game_names[canonical_game_id] = str(row["canonical_name"])
        game_years[canonical_game_id] = row["release_year"]
        feature_type = row.get("feature_type")
        feature_value = row.get("feature_value")
        if feature_type and (key := feature_key(str(feature_type), feature_value)):
            feature_maps[canonical_game_id][key] = FEATURE_WEIGHTS.get(str(feature_type), 1.0)

    for canonical_game_id, release_year in game_years.items():
        if key := release_decade_feature(release_year):
            feature_maps[canonical_game_id][key] = FEATURE_WEIGHTS["decade"]

    return [
        CanonicalGameFeatures(
            canonical_game_id=canonical_game_id,
            canonical_name=game_names[canonical_game_id],
            release_year=game_years[canonical_game_id],
            features=feature_maps.get(canonical_game_id, {}),
        )
        for canonical_game_id in sorted(game_names, key=lambda game_id: game_names[game_id].lower())
        if feature_maps.get(canonical_game_id)
    ]


def ensure_recommendations_table(repository: IngestionRepository) -> None:
    query = """
        CREATE TABLE IF NOT EXISTS dm.game_recommendations (
            id BIGSERIAL PRIMARY KEY,
            canonical_game_id UUID NOT NULL REFERENCES dm.canonical_games (canonical_game_id)
                ON DELETE CASCADE,
            recommended_canonical_game_id UUID NOT NULL REFERENCES dm.canonical_games
                (canonical_game_id) ON DELETE CASCADE,
            rank INTEGER NOT NULL,
            score NUMERIC(8, 6) NOT NULL,
            algorithm TEXT NOT NULL,
            explanation_factors_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (canonical_game_id, algorithm, rank),
            UNIQUE (canonical_game_id, recommended_canonical_game_id, algorithm)
        )
    """
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)


def replace_recommendations(repository: IngestionRepository, rows: list[dict[str, object]]) -> None:
    ensure_recommendations_table(repository)
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM dm.game_recommendations WHERE algorithm = %s", ("content_jaccard_v1",)
            )
            if not rows:
                return
            cursor.executemany(
                """
                INSERT INTO dm.game_recommendations (
                    canonical_game_id,
                    recommended_canonical_game_id,
                    rank,
                    score,
                    algorithm,
                    explanation_factors_json
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        row["canonical_game_id"],
                        row["recommended_canonical_game_id"],
                        row["rank"],
                        row["score"],
                        row["algorithm"],
                        Jsonb(row["explanation_factors_json"]),
                    )
                    for row in rows
                ],
            )


def write_report(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report_rows = [
        {
            "canonical_game_id": row["canonical_game_id"],
            "recommended_canonical_game_id": row["recommended_canonical_game_id"],
            "rank": row["rank"],
            "score": row["score"],
            "algorithm": row["algorithm"],
        }
        for row in rows
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "canonical_game_id",
                "recommended_canonical_game_id",
                "rank",
                "score",
                "algorithm",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build content-based canonical recommendations.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-block-size", type=int, default=500)
    parser.add_argument("--max-candidates-per-game", type=int, default=250)
    parser.add_argument("--min-score", type=float, default=0.12)
    parser.add_argument("--limit-games", type=int, help="Optional canonical game limit for tests.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report-path",
        default=str(
            project_root()
            / "data"
            / "artifacts"
            / "reports"
            / "recommendations"
            / "content_jaccard_recommendations.csv"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = IngestionRepository()
    games = fetch_canonical_game_features(repository, limit_games=args.limit_games)
    rows = build_recommendation_rows(
        games,
        top_k=args.top_k,
        max_block_size=args.max_block_size,
        max_candidates_per_game=args.max_candidates_per_game,
        min_score=args.min_score,
    )
    if not args.dry_run:
        replace_recommendations(repository, rows)
        write_report(Path(args.report_path), rows)
    print(
        {
            "algorithm": "content_jaccard_v1",
            "feature_game_count": len(games),
            "recommendation_count": len(rows),
            "top_k": args.top_k,
            "max_block_size": args.max_block_size,
            "max_candidates_per_game": args.max_candidates_per_game,
            "min_score": args.min_score,
            "dry_run": args.dry_run,
            "report_path": args.report_path,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
