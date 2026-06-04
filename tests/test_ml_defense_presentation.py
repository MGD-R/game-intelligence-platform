from __future__ import annotations

from src.devtools.build_ml_defense_presentation import (
    build_remaining_steps,
    build_slide_outline,
    metric_lookup,
    metric_text,
)


def test_metric_lookup_and_metric_text_use_available_values() -> None:
    metrics = metric_lookup(
        [
            {"metric": "source_records", "value": "31462"},
            {"metric": "candidate_pairs", "value": "17320"},
        ]
    )

    assert metrics["source_records"] == "31462"
    assert metric_text(metrics, "source_records", "missing", "candidate_pairs") == (
        "source_records=31462; candidate_pairs=17320"
    )


def test_build_slide_outline_contains_required_defense_sections() -> None:
    slides = build_slide_outline(
        [{"metric": "v3c_f1", "value": "0.948675"}],
        [{"section": "ER model", "evidence": "ablation_study.csv"}],
    )
    titles = {str(row["title"]) for row in slides}

    assert len(slides) == 12
    assert "Explainable ER Baseline" in titles
    assert "Grounded RAG Explanations" in titles
    assert "Conclusions And Next Research Steps" in titles
    assert slides[3]["metric_anchor"] == "v3c_f1=0.948675"


def test_remaining_steps_start_with_timed_rehearsal() -> None:
    steps = build_remaining_steps()

    assert steps[0]["step"] == "Run a timed defense rehearsal"
    assert steps[-1]["status"] == "release_workflow"
