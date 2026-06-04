"""Optional LLM rendering over already grounded explanation facts."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderResult:
    explanation_ru: str
    provider: str
    facts_referenced: list[str]
    warnings: list[str]


def verify_grounded_output(output: str, facts: list[str]) -> bool:
    """Reject obvious hallucinations for the lightweight demo renderer."""

    forbidden_markers = ("unknown_source", "invented_fact", "неизвестный источник")
    lowered = output.lower()
    if any(marker in lowered for marker in forbidden_markers):
        return False
    fact_tokens = [
        token.strip().lower()
        for fact in facts
        for token in fact.replace("=", " ").replace(":", " ").split()
        if len(token.strip()) >= 4
    ]
    if not fact_tokens:
        return True
    return any(token in lowered for token in fact_tokens)


def render_with_mock_provider(template_text: str, facts: list[str]) -> str:
    fact_text = "; ".join(facts[:6]) if facts else "нет дополнительных фактов"
    return (
        f"{template_text} Дополнительная LLM-формулировка основана только на фактах: "
        f"{fact_text}."
    )


def render_grounded_explanation(
    *,
    template_text: str,
    facts: list[str],
    mode: str = "template",
    provider: str | None = None,
) -> RenderResult:
    selected_provider = provider or os.getenv("LLM_PROVIDER", "none")
    if mode != "llm":
        return RenderResult(template_text, "template", facts, [])
    if selected_provider == "none":
        return RenderResult(
            template_text,
            "none",
            facts,
            ["LLM rendering is disabled; returned template grounded explanation."],
        )
    if selected_provider == "mock":
        rendered = render_with_mock_provider(template_text, facts)
    else:
        return RenderResult(
            template_text,
            selected_provider,
            facts,
            [
                "External LLM rendering is not configured in this local demo; "
                "returned template grounded explanation."
            ],
        )
    if not verify_grounded_output(rendered, facts):
        return RenderResult(
            template_text,
            selected_provider,
            facts,
            ["LLM rendering failed groundedness verification; returned template explanation."],
        )
    return RenderResult(rendered, selected_provider, facts, [])
