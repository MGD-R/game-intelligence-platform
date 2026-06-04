from __future__ import annotations

from src.rag.build_explanations import (
    balanced_match_rows,
    build_match_explanation,
    build_recommendation_explanation,
    match_case_type,
    normalize_json,
    pct,
    readable_feature,
    recommendation_evidence_points,
)


def test_pct_formats_missing_and_numeric_values() -> None:
    assert pct(None) == "нет данных"
    assert pct(0.928719) == "92.9%"


def test_normalize_json_accepts_dict_and_json_string() -> None:
    assert normalize_json({"a": 1}) == {"a": 1}
    assert normalize_json('{"a": 1}') == {"a": 1}
    assert normalize_json("") == {}


def test_readable_feature_translates_known_feature_prefix() -> None:
    assert readable_feature("genre:action") == "жанр: action"
    assert readable_feature("unknown:value") == "unknown: value"
    assert readable_feature("plain") == "plain"


def test_build_match_explanation_uses_grounded_features() -> None:
    row = {
        "name_a": "Doom",
        "source_a": "rawg",
        "source_id_a": "1",
        "name_b": "Doom",
        "source_b": "igdb",
        "source_id_b": "2",
        "model_decision": "auto_merge",
        "same_game_probability": 0.95,
        "name_similarity": 1.0,
        "alias_similarity": 0.8,
        "release_year_diff": 0,
        "developer_overlap": 1.0,
        "review_status": "reviewed",
        "review_label": True,
    }

    explanation = build_match_explanation(row)

    assert "Doom (rawg:1)" in explanation
    assert "сильным кандидатом на объединение" in explanation
    assert "сходство названий: 100.0%" in explanation
    assert "ручная разметка: положительная" in explanation


def test_match_case_type_and_balanced_rows_cover_multiple_case_types() -> None:
    rows = [
        {"pair_id": "p1", "review_status": "reviewed", "review_label": True},
        {"pair_id": "p2", "review_status": "reviewed", "review_label": False},
        {"pair_id": "p3", "model_decision": "auto_merge"},
        {"pair_id": "p4", "model_decision": "manual_review"},
        {"pair_id": "p5", "same_game_probability": 0.50},
    ]

    selected = balanced_match_rows(rows, limit=5)

    assert match_case_type(rows[0]) == "reviewed_positive"
    assert [row["explanation_case_type"] for row in selected] == [
        "reviewed_positive",
        "reviewed_negative",
        "model_auto_merge",
        "model_manual_review",
        "high_uncertainty",
    ]


def test_recommendation_explanation_uses_shared_features() -> None:
    row = {
        "seed_game": "Doom",
        "recommended_game": "Quake",
        "score": 0.75,
        "seed_release_year": 1993,
        "recommended_release_year": 1996,
        "explanation_factors_json": {"shared_features": ["genre:shooter", "developer:id software"]},
    }

    evidence = recommendation_evidence_points(row)
    explanation = build_recommendation_explanation(row)

    assert "общий признак `жанр: shooter`" in evidence
    assert "content score: 75.0%" in evidence
    assert "Для игры `Doom` рекомендация `Quake`" in explanation
    assert "без LLM-решений" in explanation
