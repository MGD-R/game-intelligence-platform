"""Read-only demo data access for FastAPI endpoints."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from src.demo.check_readiness import evaluate_demo_readiness
from src.ingestion.repository import IngestionRepository
from src.rag.llm_rendering import render_grounded_explanation
from src.utils.config import project_root

REPORTS_DIR = project_root() / "data" / "artifacts" / "reports"
ML_RESEARCH_DIR = REPORTS_DIR / "ml_research_defense"
RAG_EXPLANATIONS_DIR = REPORTS_DIR / "rag_explanations"

SUPPORTED_RECOMMENDATION_ALGORITHMS = {"content_jaccard_v1", "hybrid_content_rating_v1"}


class ManualReviewNotFoundError(Exception):
    """Raised when a manual review row does not exist for a pair."""


class ManualReviewDatabaseError(Exception):
    """Raised when manual review storage is unavailable."""


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def strict_db_mode_enabled() -> bool:
    """Return whether DB failures should fail fast instead of using artifact fallback."""

    return env_flag("GIP_STRICT_DB_MODE")


def handle_db_fallback_exception(exc: Exception) -> None:
    if strict_db_mode_enabled():
        raise exc
    return None


def optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def readiness_brief() -> dict[str, Any]:
    result = evaluate_demo_readiness(project_root())
    return {
        "status": result["status"],
        "missing_count": len(result["missing_artifacts"]),
        "warnings": [*result["errors"], *result["warnings"]],
        "recommendations": result["recommendations"],
    }


def add_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness_brief()
    payload["data_readiness"] = {
        "status": readiness["status"],
        "missing_count": readiness["missing_count"],
        "recommendations": readiness["recommendations"],
    }
    warnings = list(payload.get("warnings") or [])
    if readiness["status"] != "ok":
        warnings.extend(readiness["warnings"])
    payload["warnings"] = warnings
    return payload


def add_empty_warning(
    payload: dict[str, Any],
    *,
    subject: str,
    recommendation: str,
) -> dict[str, Any]:
    if payload.get("items"):
        payload.setdefault("warnings", [])
        return payload
    warnings = list(payload.get("warnings") or [])
    warnings.append(f"No {subject} rows are available for the current demo data snapshot.")
    warnings.append(recommendation)
    payload["warnings"] = warnings
    return payload


def sum_row_counts(rows: object) -> int:
    if not isinstance(rows, list):
        return 0
    total = 0
    for row in rows:
        if isinstance(row, dict):
            total += int(row.get("row_count") or 0)
    return total


def rows_by_key(rows: object, key: str, value_key: str = "row_count") -> dict[str, int]:
    if not isinstance(rows, list):
        return {}
    output: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get(key) is None:
            continue
        output[str(row[key])] = int(row.get(value_key) or 0)
    return output


def latest_research_summary() -> dict[str, Any]:
    return read_json(REPORTS_DIR / "ml_research_defense" / "ml_research_defense_summary.json")


def latest_readiness_summary() -> dict[str, Any]:
    return read_json(REPORTS_DIR / "ml_defense_readiness" / "ml_defense_readiness_summary.json")


def db_catalog_stats(repository: IngestionRepository | None = None) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    query = """
        WITH source_counts AS (
            SELECT COALESCE(jsonb_object_agg(source, row_count), '{}'::jsonb) AS counts
            FROM (
                SELECT source, COUNT(*)::int AS row_count
                FROM stg.source_games
                GROUP BY source
            ) s
        )
        SELECT
            (SELECT COUNT(*)::int FROM stg.source_games) AS source_games,
            (SELECT counts FROM source_counts) AS source_games_by_source,
            (SELECT COUNT(*)::int FROM dm.canonical_games) AS canonical_games,
            (SELECT COUNT(*)::int FROM dm.canonical_game_sources) AS canonical_game_sources,
            (SELECT COUNT(*)::int FROM dm.game_recommendations) AS recommendations_count,
            (
                SELECT COUNT(DISTINCT canonical_game_id)::int
                FROM dm.canonical_game_aliases
                WHERE language = 'ru'
            ) AS games_with_ru_name
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone() or {}
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    source_by_source = dict(row.get("source_games_by_source") or {})
    return {
        "data_origin": "database",
        "source_games": int(row.get("source_games") or 0),
        "source_games_by_source": source_by_source,
        "source_count": len(source_by_source),
        "canonical_games": int(row.get("canonical_games") or 0),
        "canonical_game_sources": int(row.get("canonical_game_sources") or 0),
        "games_with_ru_name": int(row.get("games_with_ru_name") or 0),
        "recommendations_count": int(row.get("recommendations_count") or 0),
    }


def artifact_catalog_stats() -> dict[str, Any]:
    summary = latest_research_summary()
    baseline = summary.get("baseline_counts", {}) if isinstance(summary, dict) else {}
    source_rows = baseline.get("source_games_by_source")
    dm_rows = rows_by_key(baseline.get("dm_counts"), "object_name")
    source_by_source = rows_by_key(source_rows, "source")
    return {
        "data_origin": "artifact",
        "source_games": sum_row_counts(source_rows),
        "source_games_by_source": source_by_source,
        "source_count": len(source_by_source),
        "canonical_games": dm_rows.get("canonical_games", 0),
        "canonical_game_sources": dm_rows.get("canonical_game_sources", 0),
        "games_with_ru_name": None,
        "recommendations_count": dm_rows.get("game_recommendations", 0),
    }


def get_catalog_stats() -> dict[str, Any]:
    payload = db_catalog_stats() or artifact_catalog_stats()
    return add_readiness(payload)


def db_ml_stats(repository: IngestionRepository | None = None) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    query = """
        WITH reviewed AS (
            SELECT
                COUNT(*) FILTER (WHERE review_status = 'reviewed')::int AS reviewed_count,
                COUNT(*) FILTER (
                    WHERE review_status = 'reviewed' AND review_label IS TRUE
                )::int AS positive_count,
                COUNT(*) FILTER (
                    WHERE review_status = 'reviewed' AND review_label IS FALSE
                )::int AS negative_count
            FROM ml.entity_resolution_manual_reviews
        ),
        decisions AS (
            SELECT COALESCE(jsonb_object_agg(decision, row_count), '{}'::jsonb) AS counts
            FROM (
                SELECT decision, COUNT(*)::int AS row_count
                FROM ml.entity_resolution_predictions
                GROUP BY decision
            ) d
        )
        SELECT
            (SELECT COUNT(*)::int FROM ml.entity_candidate_pairs) AS candidate_pairs,
            reviewed.reviewed_count,
            reviewed.positive_count,
            reviewed.negative_count,
            (SELECT counts FROM decisions) AS model_decisions
        FROM reviewed
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone() or {}
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    return {
        "data_origin": "database",
        "candidate_pairs": int(row.get("candidate_pairs") or 0),
        "labeled_pairs": int(row.get("reviewed_count") or 0),
        "manual_positive_labels": int(row.get("positive_count") or 0),
        "manual_negative_labels": int(row.get("negative_count") or 0),
        "model_decisions": dict(row.get("model_decisions") or {}),
        **artifact_ml_metrics(),
    }


def artifact_ml_metrics() -> dict[str, Any]:
    summary = latest_research_summary()
    existing = summary.get("existing_er_artifacts", {}) if isinstance(summary, dict) else {}
    metrics = existing.get("v3c_metrics", {}) if isinstance(existing, dict) else {}
    readiness = latest_readiness_summary()
    return {
        "entity_resolution_f1": metrics.get("f1"),
        "entity_resolution_precision": metrics.get("precision"),
        "entity_resolution_recall": metrics.get("recall"),
        "entity_resolution_roc_auc": metrics.get("roc_auc"),
        "entity_resolution_pr_auc": metrics.get("pr_auc"),
        "readiness_status": readiness.get("overall_status"),
    }


def artifact_ml_stats() -> dict[str, Any]:
    summary = latest_research_summary()
    baseline = summary.get("baseline_counts", {}) if isinstance(summary, dict) else {}
    manual_rows = baseline.get("manual_review_labels")
    reviewed_rows = (
        [
            row
            for row in manual_rows
            if isinstance(row, dict) and row.get("review_status") == "reviewed"
        ]
        if isinstance(manual_rows, list)
        else []
    )
    decision_rows = baseline.get("model_decisions")
    manual_positive = sum(
        int(row.get("row_count") or 0) for row in reviewed_rows if row.get("review_label") is True
    )
    manual_negative = sum(
        int(row.get("row_count") or 0) for row in reviewed_rows if row.get("review_label") is False
    )
    return {
        "data_origin": "artifact",
        "candidate_pairs": sum_row_counts(baseline.get("candidate_pairs_by_source")),
        "labeled_pairs": sum_row_counts(reviewed_rows),
        "manual_positive_labels": manual_positive,
        "manual_negative_labels": manual_negative,
        "model_decisions": rows_by_key(decision_rows, "decision"),
        **artifact_ml_metrics(),
    }


def get_ml_stats() -> dict[str, Any]:
    payload = db_ml_stats() or artifact_ml_stats()
    payload["artifact_presence"] = {
        "er_metrics": bool(artifact_ml_metrics().get("entity_resolution_f1")),
        "manual_review_candidates": (
            REPORTS_DIR / "entity_resolution" / "entity_resolution_manual_review_pending.csv"
        ).exists()
        or (
            REPORTS_DIR / "entity_resolution" / "entity_resolution_manual_review_reviewed.csv"
        ).exists(),
        "recommendation_examples": (
            ML_RESEARCH_DIR / "recommendation_examples.csv"
        ).exists(),
        "recommendation_explanations": (
            RAG_EXPLANATIONS_DIR / "recommendation_explanation_examples.csv"
        ).exists(),
        "match_explanations": (
            RAG_EXPLANATIONS_DIR / "match_explanation_examples.csv"
        ).exists(),
    }
    payload["current_model_version"] = "weighted_logistic_regression_v3c"
    payload["threshold_policy"] = {
        "auto_merge": "same_game_probability >= 0.95",
        "manual_review": "0.70 <= same_game_probability < 0.95",
        "no_merge": "same_game_probability < 0.70",
    }
    payload["metrics_summary"] = {
        "precision": payload.get("entity_resolution_precision"),
        "recall": payload.get("entity_resolution_recall"),
        "f1": payload.get("entity_resolution_f1"),
        "roc_auc": payload.get("entity_resolution_roc_auc"),
        "pr_auc": payload.get("entity_resolution_pr_auc"),
    }
    payload["calibration_available"] = (
        ML_RESEARCH_DIR / "calibration_bins.csv"
    ).exists() or (
        ML_RESEARCH_DIR / "threshold_evaluation.csv"
    ).exists()
    return add_readiness(payload)


def get_graph_stats() -> dict[str, Any]:
    summary_path = REPORTS_DIR / "graph_analysis" / "graph_analysis_summary.json"
    summary = read_json(summary_path)
    strategies = summary.get("strategies") if isinstance(summary, dict) else None
    payload = {
        "data_origin": "artifact",
        "graph_type": "entity_resolution_risk_graph",
        "summary_available": bool(summary),
        "strategy_count": len(strategies) if isinstance(strategies, list) else 0,
        "strategies": strategies or [],
        "warnings": []
        if summary
        else ["Graph analysis artifact is missing; run `make graph-analytics`."],
        "future_work": (
            "Build a product knowledge graph over games, genres, platforms and companies."
        ),
    }
    return add_readiness(payload)


def clamp_limit(limit: int, *, default: int = 20, maximum: int = 100) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


def db_list_games(
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    repository: IngestionRepository | None = None,
) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    safe_limit = clamp_limit(limit)
    safe_offset = max(offset, 0)
    search_pattern = f"%{search.strip()}%" if search and search.strip() else None
    query = """
        SELECT
            cg.canonical_game_id::text AS canonical_game_id,
            cg.canonical_name AS name,
            cg.release_year,
            COUNT(*) OVER()::int AS total,
            (
                SELECT COUNT(*)::int
                FROM dm.canonical_game_sources cgs
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ) AS source_count,
            COALESCE((
                SELECT array_agg(DISTINCT g.genre_name ORDER BY g.genre_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_genres g
                  ON g.source = cgs.source
                 AND g.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), ARRAY[]::text[]) AS genres,
            COALESCE((
                SELECT array_agg(DISTINCT p.platform_name ORDER BY p.platform_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_platforms p
                  ON p.source = cgs.source
                 AND p.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), ARRAY[]::text[]) AS platforms
        FROM dm.canonical_games cg
        WHERE (%s::text IS NULL OR cg.canonical_name ILIKE %s)
        ORDER BY cg.canonical_name
        LIMIT %s OFFSET %s
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (search_pattern, search_pattern, safe_limit, safe_offset))
                rows = cursor.fetchall()
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    total = int(rows[0]["total"]) if rows else 0
    items = [
        {
            "canonical_game_id": row["canonical_game_id"],
            "name": row["name"],
            "name_ru": None,
            "release_year": row["release_year"],
            "genres": list(row.get("genres") or []),
            "platforms": list(row.get("platforms") or []),
            "source_count": int(row.get("source_count") or 0),
        }
        for row in rows
    ]
    return {
        "data_origin": "database",
        "items": items,
        "limit": safe_limit,
        "offset": safe_offset,
        "total": total,
    }


def artifact_list_games(
    *,
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit)
    safe_offset = max(offset, 0)
    rows = read_csv_rows(REPORTS_DIR / "bayesian_rating" / "canonical_bayesian_ratings.csv")
    if search and search.strip():
        needle = search.strip().lower()
        rows = [row for row in rows if needle in str(row.get("canonical_name") or "").lower()]
    total = len(rows)
    selected = rows[safe_offset : safe_offset + safe_limit]
    items = [
        {
            "canonical_game_id": row.get("canonical_game_id"),
            "name": row.get("canonical_name"),
            "name_ru": None,
            "release_year": int(row["release_year"]) if row.get("release_year") else None,
            "genres": [],
            "platforms": [],
            "source_count": int(row["rating_source_count"])
            if row.get("rating_source_count")
            else 0,
        }
        for row in selected
    ]
    return {
        "data_origin": "artifact",
        "items": items,
        "limit": safe_limit,
        "offset": safe_offset,
        "total": total,
    }


def list_games(*, limit: int = 20, offset: int = 0, search: str | None = None) -> dict[str, Any]:
    payload = db_list_games(limit=limit, offset=offset, search=search) or artifact_list_games(
        limit=limit,
        offset=offset,
        search=search,
    )
    return add_empty_warning(
        payload,
        subject="catalog",
        recommendation="Run `make canonical-v1`, `make bayesian-rating`, or restore a data pack.",
    )


def db_get_game(
    game_id: str,
    *,
    repository: IngestionRepository | None = None,
) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    query = """
        SELECT
            cg.canonical_game_id::text AS canonical_game_id,
            cg.canonical_name AS name,
            cg.release_year,
            (
                SELECT MIN(sg.release_date)::text
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_games sg
                  ON sg.source = cgs.source
                 AND sg.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ) AS release_date,
            (
                SELECT d.description_text
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_descriptions d
                  ON d.source = cgs.source
                 AND d.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
                ORDER BY
                    CASE d.source
                        WHEN 'wikipedia' THEN 0
                        WHEN 'rawg' THEN 1
                        WHEN 'steam' THEN 2
                        WHEN 'igdb' THEN 3
                        ELSE 4
                    END,
                    LENGTH(d.description_text) DESC
                LIMIT 1
            ) AS description,
            COALESCE((
                SELECT array_agg(DISTINCT g.genre_name ORDER BY g.genre_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_genres g
                  ON g.source = cgs.source
                 AND g.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), ARRAY[]::text[]) AS genres,
            COALESCE((
                SELECT array_agg(DISTINCT p.platform_name ORDER BY p.platform_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_platforms p
                  ON p.source = cgs.source
                 AND p.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), ARRAY[]::text[]) AS platforms,
            COALESCE((
                SELECT array_agg(DISTINCT c.company_name ORDER BY c.company_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_companies c
                  ON c.source = cgs.source
                 AND c.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
                  AND c.company_role = 'developer'
            ), ARRAY[]::text[]) AS developers,
            COALESCE((
                SELECT array_agg(DISTINCT c.company_name ORDER BY c.company_name)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_companies c
                  ON c.source = cgs.source
                 AND c.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
                  AND c.company_role = 'publisher'
            ), ARRAY[]::text[]) AS publishers,
            COALESCE((
                SELECT jsonb_object_agg(r.rating_type, r.rating_value)
                FROM dm.canonical_game_sources cgs
                JOIN stg.source_game_ratings r
                  ON r.source = cgs.source
                 AND r.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), '{}'::jsonb) AS ratings,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'source', cgs.source,
                    'source_game_id', cgs.source_game_id,
                    'source_name', sg.name,
                    'confidence_score', cgs.linkage_confidence
                ) ORDER BY cgs.source, cgs.source_game_id)
                FROM dm.canonical_game_sources cgs
                LEFT JOIN stg.source_games sg
                  ON sg.source = cgs.source
                 AND sg.source_game_id = cgs.source_game_id
                WHERE cgs.canonical_game_id = cg.canonical_game_id
            ), '[]'::jsonb) AS sources
        FROM dm.canonical_games cg
        WHERE cg.canonical_game_id::text = %s
        LIMIT 1
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (game_id,))
                row = cursor.fetchone()
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    if not row:
        return None
    return {
        "data_origin": "database",
        "canonical_game_id": row["canonical_game_id"],
        "name": row["name"],
        "name_ru": None,
        "release_year": row["release_year"],
        "release_date": row["release_date"],
        "description": row["description"],
        "genres": list(row.get("genres") or []),
        "platforms": list(row.get("platforms") or []),
        "developers": list(row.get("developers") or []),
        "publishers": list(row.get("publishers") or []),
        "ratings": dict(row.get("ratings") or {}),
        "sources": list(row.get("sources") or []),
    }


def artifact_get_game(game_id: str) -> dict[str, Any] | None:
    rows = read_csv_rows(REPORTS_DIR / "bayesian_rating" / "canonical_bayesian_ratings.csv")
    for row in rows:
        if str(row.get("canonical_game_id") or "") != str(game_id):
            continue
        return {
            "data_origin": "artifact",
            "canonical_game_id": row.get("canonical_game_id"),
            "name": row.get("canonical_name"),
            "name_ru": None,
            "release_year": int(row["release_year"]) if row.get("release_year") else None,
            "release_date": None,
            "description": None,
            "genres": [],
            "platforms": [],
            "developers": [],
            "publishers": [],
            "ratings": {
                "naive_weighted_rating": row.get("naive_weighted_rating"),
                "bayesian_rating": row.get("bayesian_rating"),
                "vote_count": row.get("vote_count"),
            },
            "sources": [],
        }
    return None


def get_game(game_id: str) -> dict[str, Any] | None:
    return db_get_game(game_id) or artifact_get_game(game_id)


def db_find_games_by_names(
    names: list[str],
    *,
    repository: IngestionRepository | None = None,
) -> list[dict[str, Any]]:
    repo = repository or IngestionRepository()
    cleaned_names = [name.strip() for name in names if name and name.strip()]
    if not cleaned_names:
        return []

    output: list[dict[str, Any]] = []
    query = """
        SELECT
            canonical_game_id::text AS canonical_game_id,
            canonical_name AS name,
            release_year
        FROM dm.canonical_games
        WHERE canonical_name ILIKE %s
        ORDER BY
            CASE WHEN lower(canonical_name) = lower(%s) THEN 0 ELSE 1 END,
            length(canonical_name),
            canonical_name
        LIMIT 1
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                for name in cleaned_names:
                    cursor.execute(query, (f"%{name}%", name))
                    row = cursor.fetchone()
                    if row:
                        output.append(
                            {
                                "input_name": name,
                                "canonical_game_id": row["canonical_game_id"],
                                "name": row["name"],
                                "release_year": row["release_year"],
                            }
                        )
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return []
    return output


def artifact_find_games_by_names(names: list[str]) -> list[dict[str, Any]]:
    rows = read_csv_rows(REPORTS_DIR / "bayesian_rating" / "canonical_bayesian_ratings.csv")
    output: list[dict[str, Any]] = []
    for name in [item.strip() for item in names if item and item.strip()]:
        needle = name.lower()
        candidates = [row for row in rows if needle in str(row.get("canonical_name") or "").lower()]
        if not candidates:
            continue
        candidates.sort(
            key=lambda row: (
                str(row.get("canonical_name") or "").lower() != needle,
                len(str(row.get("canonical_name") or "")),
            )
        )
        selected = candidates[0]
        output.append(
            {
                "input_name": name,
                "canonical_game_id": selected.get("canonical_game_id"),
                "name": selected.get("canonical_name"),
                "release_year": optional_int(selected.get("release_year")),
            }
        )
    return output


def find_games_by_names(names: list[str]) -> list[dict[str, Any]]:
    return db_find_games_by_names(names) or artifact_find_games_by_names(names)


def db_similar_games(
    game_id: str,
    *,
    limit: int = 10,
    algorithm: str = "content_jaccard_v1",
    repository: IngestionRepository | None = None,
) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    safe_limit = clamp_limit(limit, default=10, maximum=50)
    query = """
        SELECT
            gr.canonical_game_id::text AS seed_game_id,
            seed.canonical_name AS seed_game,
            gr.recommended_canonical_game_id::text AS recommended_game_id,
            rec.canonical_name AS recommended_game,
            rec.release_year AS recommended_release_year,
            gr.rank,
            gr.score::float AS score,
            gr.algorithm,
            gr.explanation_factors_json
        FROM dm.game_recommendations gr
        JOIN dm.canonical_games seed
          ON seed.canonical_game_id = gr.canonical_game_id
        JOIN dm.canonical_games rec
          ON rec.canonical_game_id = gr.recommended_canonical_game_id
        WHERE gr.canonical_game_id::text = %s
          AND gr.algorithm = %s
        ORDER BY gr.rank, gr.score DESC
        LIMIT %s
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (game_id, algorithm, safe_limit))
                rows = cursor.fetchall()
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    return {
        "data_origin": "database",
        "seed_game_id": game_id,
        "seed_game": rows[0]["seed_game"] if rows else None,
        "algorithm": rows[0]["algorithm"] if rows else algorithm,
        "items": [
            {
                "canonical_game_id": row["recommended_game_id"],
                "name": row["recommended_game"],
                "release_year": row["recommended_release_year"],
                "rank": row["rank"],
                "score": row["score"],
                "explanation_factors": dict(row.get("explanation_factors_json") or {}),
            }
            for row in rows
        ],
        "limit": safe_limit,
        "total": len(rows),
    }


def artifact_similar_games(
    seed_game_name: str | None,
    *,
    limit: int = 10,
    algorithm: str = "content_jaccard_v1",
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit, default=10, maximum=50)
    rows = read_csv_rows(ML_RESEARCH_DIR / "recommendation_examples.csv")
    if seed_game_name:
        rows = [row for row in rows if row.get("seed_game") == seed_game_name]
    rows = rows[:safe_limit]
    return {
        "data_origin": "artifact",
        "seed_game_id": None,
        "seed_game": seed_game_name or (rows[0].get("seed_game") if rows else None),
        "algorithm": algorithm,
        "items": [
            {
                "canonical_game_id": None,
                "name": row.get("recommended_game"),
                "release_year": None,
                "rank": optional_int(row.get("rank")),
                "score": optional_float(row.get("score")),
                "explanation_factors": json.loads(row.get("explanation_factors_json") or "{}"),
            }
            for row in rows
        ],
        "limit": safe_limit,
        "total": len(rows),
    }


def similar_games(
    game_id: str,
    *,
    limit: int = 10,
    algorithm: str = "content_jaccard_v1",
) -> dict[str, Any]:
    selected_algorithm = (
        algorithm if algorithm in SUPPORTED_RECOMMENDATION_ALGORITHMS else "content_jaccard_v1"
    )
    game = get_game(game_id)
    payload = db_similar_games(
        game_id,
        limit=limit,
        algorithm=selected_algorithm,
    ) or artifact_similar_games(
        game.get("name") if game else None,
        limit=limit,
        algorithm=selected_algorithm,
    )
    if algorithm not in SUPPORTED_RECOMMENDATION_ALGORITHMS:
        payload.setdefault("warnings", []).append(
            f"Unsupported algorithm `{algorithm}`; using `content_jaccard_v1`."
        )
    if selected_algorithm == "hybrid_content_rating_v1" and not payload.get("items"):
        payload.setdefault("warnings", []).append(
            "Hybrid recommendation rows are not available; run `make recommendations-hybrid`."
        )
    return add_empty_warning(
        payload,
        subject="recommendation",
        recommendation="Run `make recommendations` or `make recommendations-hybrid`.",
    )


def recommendations(
    seed_game_ids: list[str],
    *,
    liked_games: list[str] | None = None,
    limit: int = 10,
    algorithm: str = "content_jaccard_v1",
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit, default=10, maximum=50)
    selected_algorithm = (
        algorithm if algorithm in SUPPORTED_RECOMMENDATION_ALGORITHMS else "content_jaccard_v1"
    )
    resolved_liked_games = find_games_by_names(liked_games or [])
    resolved_ids = [
        str(row["canonical_game_id"])
        for row in resolved_liked_games
        if row.get("canonical_game_id")
    ]
    effective_seed_game_ids = list(dict.fromkeys([*seed_game_ids, *resolved_ids]))
    if not effective_seed_game_ids:
        payload = artifact_similar_games(None, limit=safe_limit, algorithm=selected_algorithm)
        payload.update(
            {
                "algorithm": selected_algorithm,
                "seed_game_ids": seed_game_ids,
                "liked_games": liked_games or [],
                "resolved_liked_games": resolved_liked_games,
                "limit": safe_limit,
            }
        )
        return add_empty_warning(
            payload,
            subject="recommendation",
            recommendation="Provide a seed game or run `make recommendations`.",
        )

    seed_results = [
        similar_games(game_id, limit=safe_limit, algorithm=selected_algorithm)
        for game_id in effective_seed_game_ids
    ]
    by_recommendation: dict[str, dict[str, Any]] = {}
    excluded_ids = set(effective_seed_game_ids)
    for seed_result in seed_results:
        for item in seed_result.get("items", []):
            item_id = item.get("canonical_game_id")
            item_key = str(item_id or item.get("name") or "")
            if not item_key or (item_id and str(item_id) in excluded_ids):
                continue
            enriched_item = dict(item)
            enriched_item["seed_game_ids"] = [seed_result.get("seed_game_id")]
            enriched_item["seed_games"] = [seed_result.get("seed_game")]
            existing = by_recommendation.get(item_key)
            if existing is None or (enriched_item.get("score") or 0) > (existing.get("score") or 0):
                by_recommendation[item_key] = enriched_item
            elif existing is not None:
                existing.setdefault("seed_game_ids", []).append(seed_result.get("seed_game_id"))
                existing.setdefault("seed_games", []).append(seed_result.get("seed_game"))
    flattened = list(by_recommendation.values())
    flattened.sort(key=lambda row: (-(row.get("score") or 0.0), row.get("rank") or 0))
    has_database_rows = any(r.get("data_origin") == "database" for r in seed_results)
    payload = {
        "data_origin": "database" if has_database_rows else "artifact",
        "algorithm": selected_algorithm,
        "seed_game_ids": effective_seed_game_ids,
        "liked_games": liked_games or [],
        "resolved_liked_games": resolved_liked_games,
        "items": flattened[:safe_limit],
        "limit": safe_limit,
        "total": len(flattened),
    }
    if algorithm not in SUPPORTED_RECOMMENDATION_ALGORITHMS:
        payload["warnings"] = [
            f"Unsupported algorithm `{algorithm}`; using `content_jaccard_v1`."
        ]
    if selected_algorithm == "hybrid_content_rating_v1" and not payload.get("items"):
        payload.setdefault("warnings", []).append(
            "Hybrid recommendation rows are not available; run `make recommendations-hybrid`."
        )
    return add_empty_warning(
        payload,
        subject="recommendation",
        recommendation="Run `make recommendations` or `make recommendations-hybrid`.",
    )


def db_review_matches(
    *,
    limit: int = 20,
    status_filter: str = "pending",
    decision_filter: str = "all",
    repository: IngestionRepository | None = None,
) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    safe_limit = clamp_limit(limit)
    query = """
        SELECT
            pair_id::text,
            source_a,
            source_id_a,
            name_a,
            release_year_a,
            source_b,
            source_id_b,
            name_b,
            release_year_b,
            candidate_source,
            label_source,
            label_value,
            name_similarity::float AS name_similarity,
            release_year_diff,
            same_game_probability::float AS same_game_probability,
            model_decision,
            review_label,
            review_status,
            selection_strategy,
            priority_score::float AS priority_score,
            review_notes
        FROM ml.v_entity_resolution_review_candidates
        WHERE (%s::text = 'all' OR review_status = %s)
          AND (%s::text = 'all' OR model_decision = %s)
        ORDER BY priority_score DESC NULLS LAST, name_similarity ASC NULLS LAST
        LIMIT %s
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (status_filter, status_filter, decision_filter, decision_filter, safe_limit),
                )
                rows = cursor.fetchall()
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    return {
        "data_origin": "database",
        "items": [dict(row) for row in rows],
        "limit": safe_limit,
        "status_filter": status_filter,
        "decision_filter": decision_filter,
        "total": len(rows),
    }


def artifact_review_matches(
    *,
    limit: int = 20,
    status_filter: str = "pending",
    decision_filter: str = "all",
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit)
    filename = (
        "entity_resolution_manual_review_pending.csv"
        if status_filter == "pending"
        else "entity_resolution_manual_review_reviewed.csv"
    )
    rows = read_csv_rows(REPORTS_DIR / "entity_resolution" / filename)
    if decision_filter != "all":
        rows = [
            row
            for row in rows
            if (row.get("model_decision") or row.get("decision")) == decision_filter
        ]
    return {
        "data_origin": "artifact",
        "items": rows[:safe_limit],
        "limit": safe_limit,
        "status_filter": status_filter,
        "decision_filter": decision_filter,
        "total": len(rows),
    }


def review_matches(
    *,
    limit: int = 20,
    status_filter: str = "pending",
    decision_filter: str = "all",
) -> dict[str, Any]:
    normalized_status = (
        status_filter if status_filter in {"pending", "reviewed", "all"} else "pending"
    )
    normalized_decision = (
        decision_filter
        if decision_filter in {"auto_merge", "manual_review", "no_merge", "all"}
        else "all"
    )
    db_result = db_review_matches(
        limit=limit,
        status_filter=normalized_status,
        decision_filter=normalized_decision,
    )
    payload = db_result or artifact_review_matches(
        limit=limit,
        status_filter=normalized_status,
        decision_filter=normalized_decision,
    )
    return add_empty_warning(
        payload,
        subject="manual review",
        recommendation="Run `make er-review-queue` and `make er-export-review-queue`.",
    )


def update_manual_review_record(
    *,
    pair_id: str,
    review_label: bool | None,
    review_status: str,
    review_notes: str | None = None,
    reviewer: str | None = None,
    confidence: float | None = None,
    repository: IngestionRepository | None = None,
) -> dict[str, Any]:
    """Update an existing manual review row in PostgreSQL."""

    repo = repository or IngestionRepository()
    query = """
        UPDATE ml.entity_resolution_manual_reviews
        SET review_label = %s,
            review_status = %s,
            review_notes = COALESCE(%s, review_notes),
            reviewer = COALESCE(%s, reviewer),
            priority_score = COALESCE(%s, priority_score),
            reviewed_at = CASE
                WHEN %s = 'reviewed' THEN NOW()
                WHEN %s IN ('pending', 'skipped', 'unsure') THEN NULL
                ELSE reviewed_at
            END,
            updated_at = NOW()
        WHERE pair_id::text = %s
        RETURNING
            pair_id::text,
            review_label,
            review_status,
            reviewer,
            review_notes,
            reviewed_at::text AS reviewed_at,
            updated_at::text AS updated_at
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        review_label,
                        review_status,
                        review_notes,
                        reviewer,
                        confidence,
                        review_status,
                        review_status,
                        pair_id,
                    ),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise ManualReviewDatabaseError(str(exc)) from exc

    if not row:
        raise ManualReviewNotFoundError(pair_id)

    label_text = (
        "same_game"
        if row["review_label"] is True
        else "different_game"
        if row["review_label"] is False
        else "uncertain"
    )
    return {
        "pair_id": row["pair_id"],
        "status": "ok",
        "updated": True,
        "updated_at": row["updated_at"],
        "reviewed_at": row["reviewed_at"],
        "review_label": label_text,
        "review_status": row["review_status"],
        "reviewer": row["reviewer"],
        "review_notes": row["review_notes"],
    }


def recommendation_explanation_facts(row: dict[str, str]) -> list[str]:
    facts = []
    if row.get("seed_game"):
        facts.append(f"seed_game={row['seed_game']}")
    if row.get("recommended_game"):
        facts.append(f"recommended_game={row['recommended_game']}")
    if row.get("score"):
        facts.append(f"content_score={row['score']}")
    if row.get("rank"):
        facts.append(f"rank={row['rank']}")
    return facts


def match_explanation_facts(row: dict[str, str]) -> list[str]:
    facts = []
    for key in ("subject", "same_game_probability", "model_decision", "review_label"):
        if row.get(key):
            facts.append(f"{key}={row[key]}")
    return facts


def build_recommendation_explanation_ru(
    seed_game: str | None,
    recommended_game: str | None,
    score: float | None,
    factors: dict[str, Any],
) -> str:
    shared_features = factors.get("shared_features") if isinstance(factors, dict) else []
    feature_text = "; ".join(str(feature) for feature in shared_features[:8])
    score_text = f"{score:.1%}" if score is not None else "нет данных"
    if feature_text:
        basis = f"Основание: общие признаки: {feature_text}."
    else:
        basis = "Основание: рассчитанные content-based признаки рекомендации."
    return (
        f"Для игры `{seed_game}` рекомендация `{recommended_game}` построена по "
        f"content-based similarity. {basis} Итоговый score: {score_text}. "
        "Это объяснение использует только canonical facts и заранее рассчитанные "
        "recommendation factors."
    )


def db_recommendation_explanations(
    *,
    game_id: str,
    recommended_game_id: str | None = None,
    limit: int = 5,
    repository: IngestionRepository | None = None,
) -> dict[str, Any] | None:
    repo = repository or IngestionRepository()
    safe_limit = clamp_limit(limit, default=5, maximum=25)
    query = """
        SELECT
            gr.canonical_game_id::text AS seed_game_id,
            seed.canonical_name AS seed_game,
            gr.recommended_canonical_game_id::text AS recommended_game_id,
            rec.canonical_name AS recommended_game,
            gr.rank,
            gr.score::float AS score,
            gr.algorithm,
            gr.explanation_factors_json
        FROM dm.game_recommendations gr
        JOIN dm.canonical_games seed
          ON seed.canonical_game_id = gr.canonical_game_id
        JOIN dm.canonical_games rec
          ON rec.canonical_game_id = gr.recommended_canonical_game_id
        WHERE gr.canonical_game_id::text = %s
          AND (%s::text IS NULL OR gr.recommended_canonical_game_id::text = %s)
        ORDER BY gr.rank, gr.score DESC
        LIMIT %s
    """
    try:
        with repo.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (game_id, recommended_game_id, recommended_game_id, safe_limit),
                )
                rows = cursor.fetchall()
    except Exception as exc:
        handle_db_fallback_exception(exc)
        return None

    if not rows:
        return None

    items = []
    for row in rows:
        factors = dict(row.get("explanation_factors_json") or {})
        explanation_ru = build_recommendation_explanation_ru(
            row.get("seed_game"),
            row.get("recommended_game"),
            row.get("score"),
            factors,
        )
        items.append(
            {
                "algorithm": row.get("algorithm"),
                "explanation_type": "recommendation",
                "seed_game_id": row.get("seed_game_id"),
                "seed_game": row.get("seed_game"),
                "recommended_game_id": row.get("recommended_game_id"),
                "recommended_game": row.get("recommended_game"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "explanation_factors": factors,
                "grounded_explanation_ru": explanation_ru,
                "explanation_ru": explanation_ru,
                "facts_used": [
                    f"seed_game={row.get('seed_game')}",
                    f"recommended_game={row.get('recommended_game')}",
                    f"content_score={row.get('score')}",
                    f"rank={row.get('rank')}",
                    f"shared_features={len(factors.get('shared_features') or [])}",
                ],
                "sources_used": [
                    "canonical_catalog",
                    "dm.game_recommendations",
                    "recommendation_features",
                ],
            }
        )
    return {
        "data_origin": "database",
        "items": items,
        "limit": safe_limit,
        "total": len(items),
    }


def recommendation_explanations(
    *,
    game_id: str | None = None,
    recommended_game_id: str | None = None,
    seed_game: str | None = None,
    recommended_game: str | None = None,
    limit: int = 5,
    mode: str = "template",
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit, default=5, maximum=25)
    if game_id:
        db_result = db_recommendation_explanations(
            game_id=game_id,
            recommended_game_id=recommended_game_id,
            limit=safe_limit,
        )
        if db_result:
            if mode == "llm":
                for item in db_result.get("items", []):
                    rendered = render_grounded_explanation(
                        template_text=str(item.get("explanation_ru") or ""),
                        facts=list(item.get("facts_used") or []),
                        mode=mode,
                    )
                    item["explanation_ru"] = rendered.explanation_ru
                    item["llm_provider"] = rendered.provider
                    item["warnings"] = rendered.warnings
            return db_result
    if game_id and not seed_game:
        game = get_game(game_id)
        seed_game = str(game.get("name")) if game else None
    if recommended_game_id and not recommended_game:
        game = get_game(recommended_game_id)
        recommended_game = str(game.get("name")) if game else None
    rows = read_csv_rows(RAG_EXPLANATIONS_DIR / "recommendation_explanation_examples.csv")
    if seed_game:
        rows = [row for row in rows if row.get("seed_game") == seed_game]
    if recommended_game:
        rows = [row for row in rows if row.get("recommended_game") == recommended_game]
    items = []
    for row in rows[:safe_limit]:
        facts = recommendation_explanation_facts(row)
        template_text = str(row.get("grounded_explanation_ru") or "")
        rendered = render_grounded_explanation(
            template_text=template_text,
            facts=facts,
            mode=mode,
        )
        items.append(
            {
                **row,
                "explanation_ru": rendered.explanation_ru,
                "facts_used": facts,
                "sources_used": ["canonical_catalog", "recommendation_features"],
                "llm_provider": rendered.provider,
                "warnings": rendered.warnings,
            }
        )
    return {
        "data_origin": "artifact",
        "items": items,
        "limit": safe_limit,
        "total": len(rows),
        "warnings": []
        if items
        else ["No recommendation explanation rows are available; run `make rag-explanations`."],
    }


def match_explanations(
    *,
    pair_id: str | None = None,
    limit: int = 5,
    mode: str = "template",
) -> dict[str, Any]:
    safe_limit = clamp_limit(limit, default=5, maximum=25)
    rows = read_csv_rows(RAG_EXPLANATIONS_DIR / "match_explanation_examples.csv")
    if pair_id:
        rows = [row for row in rows if row.get("pair_id") == pair_id]
    items = []
    for row in rows[:safe_limit]:
        facts = match_explanation_facts(row)
        template_text = str(row.get("grounded_explanation_ru") or "")
        rendered = render_grounded_explanation(
            template_text=template_text,
            facts=facts,
            mode=mode,
        )
        items.append(
            {
                **row,
                "explanation_ru": rendered.explanation_ru,
                "facts_used": facts,
                "sources_used": [
                    "entity_resolution_features",
                    "entity_resolution_predictions",
                    "manual_review_labels",
                ],
                "llm_provider": rendered.provider,
                "warnings": rendered.warnings,
            }
        )
    return {
        "data_origin": "artifact",
        "items": items,
        "limit": safe_limit,
        "total": len(rows),
        "warnings": []
        if items
        else ["No match explanation rows are available; run `make rag-explanations`."],
    }
