"""Build a defense presentation outline from ML readiness artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.devtools.build_ml_defense_readiness import (
    DEFAULT_OUTPUT_DIR as DEFAULT_READINESS_DIR,
)
from src.devtools.build_ml_defense_readiness import (
    build_ml_defense_readiness,
    read_json,
)
from src.entity_resolution.build_research_defense_artifacts import (
    write_csv,
    write_json,
    write_text,
)
from src.utils.config import project_root

REPORTS_DIR = project_root() / "data" / "artifacts" / "reports"
DEFAULT_OUTPUT_DIR = REPORTS_DIR / "ml_defense_presentation"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def metric_lookup(metric_rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["metric"]: row.get("value", "") for row in metric_rows if row.get("metric")}


def metric_text(metrics: dict[str, str], *names: str) -> str:
    parts = []
    for name in names:
        value = metrics.get(name)
        if value not in (None, ""):
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def build_slide_outline(
    metric_rows: list[dict[str, str]],
    demo_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    metrics = metric_lookup(metric_rows)
    demo_by_section = {row.get("section", ""): row for row in demo_rows}
    return [
        {
            "slide": 1,
            "title": "Problem And Research Goal",
            "key_message": (
                "Build an end-to-end ML/data product for game intelligence, "
                "not an isolated model demo."
            ),
            "metric_anchor": metric_text(metrics, "source_records", "candidate_pairs"),
            "evidence": "docs/ml_research_findings.md",
            "demo_action": "Open the project pipeline diagram and state the ER-first hypothesis.",
        },
        {
            "slide": 2,
            "title": "Data Pipeline And Corpus Scale",
            "key_message": (
                "Multiple source records are normalized before ML scoring and "
                "canonical catalog construction."
            ),
            "metric_anchor": metric_text(
                metrics, "source_records", "candidate_pairs", "manual_reviewed_labels"
            ),
            "evidence": demo_by_section.get("Data pipeline", {}).get(
                "evidence", "ml_research_defense_summary.json"
            ),
            "demo_action": "Show source counts, candidate pairs and manual labels.",
        },
        {
            "slide": 3,
            "title": "Manual Review As Supervision",
            "key_message": (
                "Positive and negative labels make the matching problem measurable and trainable."
            ),
            "metric_anchor": metric_text(metrics, "manual_reviewed_labels"),
            "evidence": "ml.entity_resolution_manual_reviews",
            "demo_action": "Show examples of positive, negative and ambiguous game pairs.",
        },
        {
            "slide": 4,
            "title": "Explainable ER Baseline",
            "key_message": (
                "Weighted Logistic Regression gives a strong, interpretable baseline "
                "for same-game probability."
            ),
            "metric_anchor": metric_text(metrics, "v3c_f1"),
            "evidence": demo_by_section.get("ER model", {}).get("evidence", "ablation_study.csv"),
            "demo_action": "Show metrics, threshold table, ablation and calibration charts.",
        },
        {
            "slide": 5,
            "title": "Merge Governance",
            "key_message": (
                "Model scores should control review and hybrid candidates, "
                "not blindly overwrite canonical merges."
            ),
            "metric_anchor": "",
            "evidence": demo_by_section.get("Merge governance", {}).get(
                "evidence", "merge_strategy_comparison.json"
            ),
            "demo_action": "Compare trusted canonical, model-only and hybrid strategies.",
        },
        {
            "slide": 6,
            "title": "Graph Risk Analysis",
            "key_message": (
                "Pair-level decisions can create risky transitive components; "
                "graph analysis exposes this risk."
            ),
            "metric_anchor": metric_text(metrics, "risky_components"),
            "evidence": demo_by_section.get("Graph risk", {}).get(
                "evidence", "graph_analysis_summary.json"
            ),
            "demo_action": "Show risky components and same-source duplicate links.",
        },
        {
            "slide": 7,
            "title": "Lightweight Title Embeddings",
            "key_message": (
                "Local TF-IDF/SVD vectors improve the fuzzy-title baseline "
                "without external model downloads."
            ),
            "metric_anchor": metric_text(metrics, "best_lightweight_embedding_f1"),
            "evidence": demo_by_section.get("Embeddings", {}).get(
                "evidence", "embedding_model_comparison.csv"
            ),
            "demo_action": "Show embedding model comparison and error cases.",
        },
        {
            "slide": 8,
            "title": "IGDB Search Lane",
            "key_message": (
                "IGDB is useful as a ranked candidate/enrichment source, "
                "but lower ranks require review governance."
            ),
            "metric_anchor": metric_text(metrics, "rank_1_reviewed_precision"),
            "evidence": demo_by_section.get("IGDB", {}).get(
                "evidence", "igdb_matching_summary.json"
            ),
            "demo_action": "Show rank-1 precision, lower-rank risks and enrichment coverage.",
        },
        {
            "slide": 9,
            "title": "Content-Based Recommendations",
            "key_message": (
                "Recommendations are an explainable secondary ML block based on "
                "shared canonical features."
            ),
            "metric_anchor": "",
            "evidence": demo_by_section.get("Recommendations", {}).get(
                "evidence", "recommendation_examples.csv"
            ),
            "demo_action": "Show seed game, recommended games and shared genres/tags/platforms.",
        },
        {
            "slide": 10,
            "title": "Bayesian Rating",
            "key_message": (
                "Vote-adjusted ratings reduce ranking noise for games with sparse votes."
            ),
            "metric_anchor": metric_text(metrics, "bayesian_canonical_games"),
            "evidence": demo_by_section.get("Bayesian rating", {}).get(
                "evidence", "bayesian_rating_summary.json"
            ),
            "demo_action": "Compare naive rating with Bayesian-adjusted rating examples.",
        },
        {
            "slide": 11,
            "title": "Grounded RAG Explanations",
            "key_message": (
                "The explanation layer renders computed facts; it does not make "
                "ER or recommendation decisions."
            ),
            "metric_anchor": metric_text(metrics, "grounded_explanations"),
            "evidence": demo_by_section.get("Grounded RAG", {}).get(
                "evidence", "rag_explanation_examples.md"
            ),
            "demo_action": "Show Russian match and recommendation explanations grounded in facts.",
        },
        {
            "slide": 12,
            "title": "Conclusions And Next Research Steps",
            "key_message": (
                "The current work is defense-ready for ER-first research; "
                "next cycles can add neural embeddings and LLM rendering."
            ),
            "metric_anchor": "",
            "evidence": "docs/model_card.md",
            "demo_action": "Summarize accepted limitations and the research roadmap.",
        },
    ]


def build_remaining_steps() -> list[dict[str, object]]:
    return [
        {
            "priority": 1,
            "step": "Create final slide deck",
            "why": "Convert the generated outline into PPTX or another presentation format.",
            "status": "next",
        },
        {
            "priority": 2,
            "step": "Run a timed defense rehearsal",
            "why": "Validate that the demo sequence fits the available presentation time.",
            "status": "planned",
        },
        {
            "priority": 3,
            "step": "Add neural embedding comparison",
            "why": "Compare local TF-IDF/SVD vectors with multilingual neural embeddings.",
            "status": "optional_research",
        },
        {
            "priority": 4,
            "step": "Add LLM rendering over grounded facts",
            "why": "Demonstrate RAG as explanation rendering while preserving model governance.",
            "status": "optional_research",
        },
        {
            "priority": 5,
            "step": "Merge feature branch into develop",
            "why": "Integrate completed research artifacts after final checks.",
            "status": "release_workflow",
        },
    ]


def write_speaker_notes(path: Path, slides: list[dict[str, object]]) -> None:
    lines = ["# ML Defense Speaker Notes", ""]
    for slide in slides:
        lines.extend(
            [
                f"## Slide {slide['slide']}. {slide['title']}",
                "",
                f"Key message: {slide['key_message']}",
                "",
                f"Metric anchor: {slide['metric_anchor'] or 'Use qualitative evidence.'}",
                "",
                f"Evidence: `{slide['evidence']}`",
                "",
                f"Demo action: {slide['demo_action']}",
                "",
            ]
        )
    write_text(path, "\n".join(lines))


def write_outline_markdown(
    path: Path,
    slides: list[dict[str, object]],
    remaining_steps: list[dict[str, object]],
) -> None:
    lines = [
        "# ML Defense Presentation Outline",
        "",
        "This outline is generated from the current readiness metric snapshot and demo sequence.",
        "",
        "## Slide Plan",
        "",
        "| Slide | Title | Metric Anchor | Evidence |",
        "|---:|---|---|---|",
    ]
    for slide in slides:
        metric_anchor = slide["metric_anchor"] or "-"
        lines.append(
            f"| {slide['slide']} | {slide['title']} | {metric_anchor} | `{slide['evidence']}` |"
        )
    lines.extend(["", "## Remaining Steps", "", "| Priority | Step | Status |", "|---:|---|---|"])
    for step in remaining_steps:
        lines.append(f"| {step['priority']} | {step['step']} | `{step['status']}` |")
    write_text(path, "\n".join(lines))


def build_ml_defense_presentation(output_dir: Path) -> dict[str, object]:
    if not (DEFAULT_READINESS_DIR / "ml_defense_readiness_summary.json").exists():
        build_ml_defense_readiness(DEFAULT_READINESS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    metric_rows = read_csv_rows(DEFAULT_READINESS_DIR / "ml_defense_metric_snapshot.csv")
    demo_rows = read_csv_rows(DEFAULT_READINESS_DIR / "ml_defense_demo_sequence.csv")
    readiness_summary = read_json(DEFAULT_READINESS_DIR / "ml_defense_readiness_summary.json")
    slides = build_slide_outline(metric_rows, demo_rows)
    remaining_steps = build_remaining_steps()
    summary = {
        "readiness_status": readiness_summary.get("overall_status"),
        "slide_count": len(slides),
        "remaining_step_count": len(remaining_steps),
        "metric_count": len(metric_rows),
    }
    write_csv(output_dir / "ml_defense_slide_outline.csv", slides)
    write_csv(output_dir / "ml_defense_remaining_steps.csv", remaining_steps)
    write_json(output_dir / "ml_defense_presentation_summary.json", summary)
    write_speaker_notes(output_dir / "ml_defense_speaker_notes.md", slides)
    write_outline_markdown(
        output_dir / "ml_defense_presentation_outline.md", slides, remaining_steps
    )
    return {"output_dir": str(output_dir), **summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build ML defense presentation outline.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_ml_defense_presentation(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
