from __future__ import annotations

from src.rag import llm_rendering
from src.rag.llm_rendering import render_grounded_explanation, verify_grounded_output


def test_provider_none_returns_template_with_warning() -> None:
    result = render_grounded_explanation(
        template_text="DOOM похожа на DOOM Eternal.",
        facts=["seed_game=DOOM", "recommended_game=DOOM Eternal"],
        mode="llm",
        provider="none",
    )

    assert result.explanation_ru == "DOOM похожа на DOOM Eternal."
    assert result.provider == "none"
    assert result.warnings


def test_mock_provider_returns_grounded_rendering() -> None:
    result = render_grounded_explanation(
        template_text="DOOM похожа на DOOM Eternal.",
        facts=["seed_game=DOOM", "recommended_game=DOOM Eternal"],
        mode="llm",
        provider="mock",
    )

    assert result.provider == "mock"
    assert "DOOM" in result.explanation_ru
    assert not result.warnings


def test_hallucination_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_rendering,
        "render_with_mock_provider",
        lambda template_text, facts: "invented_fact from unknown_source",
    )

    result = render_grounded_explanation(
        template_text="Template explanation.",
        facts=["seed_game=DOOM"],
        mode="llm",
        provider="mock",
    )

    assert result.explanation_ru == "Template explanation."
    assert result.warnings
    assert verify_grounded_output("Template uses DOOM", ["seed_game=DOOM"])
