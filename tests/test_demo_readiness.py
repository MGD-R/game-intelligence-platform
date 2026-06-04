from __future__ import annotations

from src.demo.check_readiness import evaluate_demo_readiness, format_human_report


def test_demo_readiness_errors_when_required_directories_are_missing(tmp_path) -> None:
    result = evaluate_demo_readiness(tmp_path)

    assert result["status"] == "error"
    assert result["errors"]
    assert any("Missing required artifact" in item for item in result["errors"])


def test_demo_readiness_warns_when_optional_artifacts_are_missing(tmp_path) -> None:
    (tmp_path / "data" / "artifacts" / "reports").mkdir(parents=True)

    result = evaluate_demo_readiness(tmp_path)

    assert result["status"] == "warning"
    assert not result["errors"]
    assert result["warnings"]
    assert result["recommendations"]


def test_demo_readiness_ok_when_all_expected_artifacts_exist(tmp_path) -> None:
    paths = [
        "data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json",
        "data/artifacts/reports/ml_defense_readiness/ml_defense_readiness_summary.json",
        "data/artifacts/reports/entity_resolution/entity_resolution_manual_review_pending.csv",
        "data/artifacts/reports/entity_resolution/entity_resolution_manual_review_reviewed.csv",
        "data/artifacts/reports/ml_research_defense/recommendation_examples.csv",
        "data/artifacts/reports/bayesian_rating/canonical_bayesian_ratings.csv",
        "data/artifacts/reports/rag_explanations/recommendation_explanation_examples.csv",
        "data/artifacts/reports/rag_explanations/match_explanation_examples.csv",
        "data/artifacts/reports/rag_explanations/grounded_fact_cards.csv",
    ]
    for relative_path in paths:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    (tmp_path / "data_packs" / "gip_demo_local").mkdir(parents=True)

    result = evaluate_demo_readiness(tmp_path)

    assert result["status"] == "ok"
    assert not result["missing_artifacts"]
    assert "Status: ok" in format_human_report(result)
