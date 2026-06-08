"""Build grounded RAG-style explanation examples from computed facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.entity_resolution.build_research_defense_artifacts import (
    write_csv,
    write_json,
    write_text,
)
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "rag_explanations"


def pct(value: object) -> str:
    if value is None:
        return "нет данных"
    return f"{float(value) * 100:.1f}%"


def normalize_json(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def readable_feature(feature: str) -> str:
    if ":" not in feature:
        return feature
    feature_type, value = feature.split(":", 1)
    labels = {
        "genre": "жанр",
        "tag": "тег",
        "platform": "платформа",
        "developer": "разработчик",
        "publisher": "издатель",
        "decade": "десятилетие",
    }
    return f"{labels.get(feature_type, feature_type)}: {value}"


def match_decision_text(row: dict[str, Any]) -> str:
    decision = str(row.get("model_decision") or "unknown")
    probability = row.get("same_game_probability")
    if decision == "auto_merge":
        return f"модель считает пару сильным кандидатом на объединение ({pct(probability)})."
    if decision == "manual_review":
        return f"модель отправляет пару на ручную проверку ({pct(probability)})."
    if decision == "no_merge":
        return f"модель считает пару кандидатом на отказ от объединения ({pct(probability)})."
    return f"решение модели не задано, вероятность совпадения {pct(probability)}."


def match_evidence_points(row: dict[str, Any]) -> list[str]:
    points = [
        f"сходство названий: {pct(row.get('name_similarity'))}",
        f"сходство alias: {pct(row.get('alias_similarity'))}",
    ]
    year_diff = row.get("release_year_diff")
    if year_diff is None:
        points.append("разница годов выпуска: нет данных")
    else:
        points.append(f"разница годов выпуска: {year_diff}")
    for label, key in (
        ("пересечение разработчиков", "developer_overlap"),
        ("пересечение издателей", "publisher_overlap"),
        ("пересечение платформ", "platform_jaccard"),
        ("пересечение жанров", "genre_jaccard"),
        ("пересечение тегов", "tag_jaccard"),
    ):
        if row.get(key) is not None:
            points.append(f"{label}: {pct(row.get(key))}")
    if row.get("external_id_exact_match") is True:
        points.append("есть точное совпадение внешнего ID")
    if row.get("review_status") == "reviewed":
        label = "положительная" if row.get("review_label") is True else "отрицательная"
        points.append(f"ручная разметка: {label}")
    return points


def build_match_explanation(row: dict[str, Any]) -> str:
    left = f"{row.get('name_a')} ({row.get('source_a')}:{row.get('source_id_a')})"
    right = f"{row.get('name_b')} ({row.get('source_b')}:{row.get('source_id_b')})"
    evidence = "; ".join(match_evidence_points(row)[:7])
    return (
        f"Пара `{left}` и `{right}`: {match_decision_text(row)} "
        f"Основание: {evidence}. "
        "Важно: объяснение основано только на рассчитанных признаках, прогнозе модели "
        "и ручной разметке, если она есть."
    )


def match_case_type(row: dict[str, Any]) -> str:
    if row.get("review_status") == "reviewed" and row.get("review_label") is True:
        return "reviewed_positive"
    if row.get("review_status") == "reviewed" and row.get("review_label") is False:
        return "reviewed_negative"
    if str(row.get("model_decision") or "") == "auto_merge":
        return "model_auto_merge"
    probability = row.get("same_game_probability")
    if probability is not None and 0.45 <= float(probability) <= 0.55:
        return "high_uncertainty"
    if str(row.get("model_decision") or "") == "manual_review":
        return "model_manual_review"
    return "other"


def balanced_match_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    wanted_order = [
        "reviewed_positive",
        "reviewed_negative",
        "model_auto_merge",
        "model_manual_review",
        "high_uncertainty",
        "other",
    ]
    per_bucket = max(1, limit // max(1, len(wanted_order) - 1))
    selected: list[dict[str, Any]] = []
    used_pair_ids: set[str] = set()
    selected_by_case: dict[str, int] = {case_type: 0 for case_type in wanted_order}
    for case_type in wanted_order:
        bucket = [row for row in rows if match_case_type(row) == case_type]
        for row in bucket[:per_bucket]:
            pair_id = str(row.get("pair_id") or "")
            if pair_id in used_pair_ids:
                continue
            row["explanation_case_type"] = case_type
            selected.append(row)
            used_pair_ids.add(pair_id)
            selected_by_case[case_type] = selected_by_case.get(case_type, 0) + 1
            if len(selected) >= limit:
                return selected
    for row in rows:
        pair_id = str(row.get("pair_id") or "")
        if pair_id in used_pair_ids:
            continue
        case_type = match_case_type(row)
        if selected_by_case.get(case_type, 0) >= per_bucket:
            continue
        row["explanation_case_type"] = case_type
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def recommendation_evidence_points(row: dict[str, Any]) -> list[str]:
    factors = normalize_json(row.get("explanation_factors_json"))
    shared_features = factors.get("shared_features") or []
    points = [
        f"общий признак `{readable_feature(str(feature))}`" for feature in shared_features[:6]
    ]
    if row.get("seed_release_year") is not None and row.get("recommended_release_year") is not None:
        points.append(
            f"годы выпуска: {row.get('seed_release_year')} и {row.get('recommended_release_year')}"
        )
    points.append(f"content score: {pct(row.get('score'))}")
    return points


def build_recommendation_explanation(row: dict[str, Any]) -> str:
    seed = str(row.get("seed_game") or "unknown seed")
    recommended = str(row.get("recommended_game") or "unknown recommendation")
    evidence = "; ".join(recommendation_evidence_points(row))
    return (
        f"Для игры `{seed}` рекомендация `{recommended}` объясняется совпадением контента. "
        f"Основание: {evidence}. "
        "Это content-based объяснение без user interactions и без LLM-решений."
    )


def fetch_rows(
    repository: IngestionRepository, query: str, params: tuple[object, ...] = ()
) -> list[dict[str, Any]]:
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())


def fetch_match_rows(repository: IngestionRepository, limit: int) -> list[dict[str, Any]]:
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
            name_similarity,
            alias_similarity,
            release_year_diff,
            external_id_exact_match,
            developer_overlap,
            publisher_overlap,
            platform_jaccard,
            genre_jaccard,
            tag_jaccard,
            same_game_probability,
            model_decision,
            review_status,
            review_label,
            selection_strategy
        FROM ml.v_entity_resolution_review_candidates
        WHERE same_game_probability IS NOT NULL
          AND name_a IS NOT NULL
          AND name_b IS NOT NULL
          AND name_a !~ '^Q[0-9]+$'
          AND name_b !~ '^Q[0-9]+$'
        ORDER BY
            CASE
                WHEN review_status = 'reviewed' AND review_label IS TRUE THEN 0
                WHEN review_status = 'reviewed' AND review_label IS FALSE THEN 1
                WHEN model_decision = 'auto_merge' THEN 2
                WHEN model_decision = 'manual_review' THEN 3
                ELSE 4
            END,
            ABS(COALESCE(same_game_probability, 0.5) - 0.5) ASC,
            same_game_probability DESC,
            pair_id
        LIMIT %s
        """,
        (max(limit * 500, 20000),),
    )
    return balanced_match_rows(rows, limit)


def fetch_recommendation_rows(repository: IngestionRepository, limit: int) -> list[dict[str, Any]]:
    return fetch_rows(
        repository,
        """
        SELECT
            seed.canonical_game_id::TEXT AS seed_canonical_game_id,
            seed.canonical_name AS seed_game,
            seed.release_year AS seed_release_year,
            rec_game.canonical_game_id::TEXT AS recommended_canonical_game_id,
            rec_game.canonical_name AS recommended_game,
            rec_game.release_year AS recommended_release_year,
            r.rank,
            r.score,
            r.algorithm,
            r.explanation_factors_json
        FROM dm.game_recommendations r
        JOIN dm.canonical_games seed
            ON seed.canonical_game_id = r.canonical_game_id
        JOIN dm.canonical_games rec_game
            ON rec_game.canonical_game_id = r.recommended_canonical_game_id
        WHERE jsonb_array_length(r.explanation_factors_json->'shared_features') >= 3
          AND seed.canonical_name !~ '^Q[0-9]+$'
          AND rec_game.canonical_name !~ '^Q[0-9]+$'
        ORDER BY r.score DESC, seed.canonical_name, r.rank
        LIMIT %s
        """,
        (limit,),
    )


def fetch_fact_cards(repository: IngestionRepository, limit: int) -> list[dict[str, Any]]:
    return fetch_rows(
        repository,
        """
        SELECT
            cg.canonical_game_id::TEXT AS canonical_game_id,
            cg.canonical_name,
            cg.release_year,
            COUNT(DISTINCT cgs.source) AS source_count,
            STRING_AGG(DISTINCT cgs.source, ', ' ORDER BY cgs.source) AS sources,
            COUNT(DISTINCT d.source_game_id) FILTER (WHERE d.description_text IS NOT NULL)
                AS description_source_count
        FROM dm.canonical_games cg
        JOIN dm.canonical_game_sources cgs
            ON cgs.canonical_game_id = cg.canonical_game_id
        LEFT JOIN stg.source_game_descriptions d
            ON d.source = cgs.source
           AND d.source_game_id = cgs.source_game_id
        WHERE cg.canonical_name !~ '^Q[0-9]+$'
        GROUP BY cg.canonical_game_id, cg.canonical_name, cg.release_year
        ORDER BY source_count DESC, description_source_count DESC, cg.canonical_name
        LIMIT %s
        """,
        (limit,),
    )


def build_match_explanation_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    result = []
    for row in rows:
        result.append(
            {
                "explanation_type": "match",
                "case_type": row.get("explanation_case_type") or match_case_type(row),
                "pair_id": row.get("pair_id"),
                "subject": f"{row.get('name_a')} <> {row.get('name_b')}",
                "model_decision": row.get("model_decision"),
                "same_game_probability": row.get("same_game_probability"),
                "review_status": row.get("review_status"),
                "review_label": row.get("review_label"),
                "grounded_explanation_ru": build_match_explanation(row),
            }
        )
    return result


def build_recommendation_explanation_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    result = []
    for row in rows:
        result.append(
            {
                "explanation_type": "recommendation",
                "seed_game": row.get("seed_game"),
                "recommended_game": row.get("recommended_game"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "algorithm": row.get("algorithm"),
                "grounded_explanation_ru": build_recommendation_explanation(row),
            }
        )
    return result


def write_markdown_report(
    path: Path,
    match_rows: list[dict[str, object]],
    recommendation_rows: list[dict[str, object]],
) -> None:
    lines = [
        "# Grounded RAG Explanation Examples",
        "",
        "These examples are grounded in computed ER features, predictions, canonical facts "
        "and recommendation factors. No LLM decides matches or recommendations.",
        "",
        "## Match Explanations",
        "",
    ]
    for row in match_rows[:10]:
        lines.extend([f"- {row['grounded_explanation_ru']}", ""])
    lines.extend(["## Recommendation Explanations", ""])
    for row in recommendation_rows[:10]:
        lines.extend([f"- {row['grounded_explanation_ru']}", ""])
    write_text(path, "\n".join(lines))


def build_grounded_explanations(
    output_dir: Path,
    *,
    match_limit: int,
    recommendation_limit: int,
    fact_card_limit: int,
) -> dict[str, object]:
    repository = IngestionRepository()
    output_dir.mkdir(parents=True, exist_ok=True)
    match_source_rows = fetch_match_rows(repository, match_limit)
    recommendation_source_rows = fetch_recommendation_rows(repository, recommendation_limit)
    fact_cards = fetch_fact_cards(repository, fact_card_limit)
    match_rows = build_match_explanation_rows(match_source_rows)
    recommendation_rows = build_recommendation_explanation_rows(recommendation_source_rows)
    summary = {
        "match_explanation_count": len(match_rows),
        "recommendation_explanation_count": len(recommendation_rows),
        "fact_card_count": len(fact_cards),
        "language": "ru",
        "grounding_policy": (
            "Explanations use computed features, model predictions, manual labels, "
            "canonical facts and recommendation shared features only."
        ),
    }
    write_csv(output_dir / "match_explanation_examples.csv", match_rows)
    write_csv(output_dir / "recommendation_explanation_examples.csv", recommendation_rows)
    write_csv(output_dir / "grounded_fact_cards.csv", fact_cards)
    write_json(output_dir / "rag_explanation_summary.json", summary)
    write_markdown_report(
        output_dir / "rag_explanation_examples.md",
        match_rows,
        recommendation_rows,
    )
    return {"output_dir": str(output_dir), **summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build grounded RAG explanation examples.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--match-limit", type=int, default=25)
    parser.add_argument("--recommendation-limit", type=int, default=25)
    parser.add_argument("--fact-card-limit", type=int, default=50)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        build_grounded_explanations(
            Path(args.output_dir),
            match_limit=args.match_limit,
            recommendation_limit=args.recommendation_limit,
            fact_card_limit=args.fact_card_limit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
