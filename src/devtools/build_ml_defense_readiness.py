"""Build a final ML defense readiness report from generated research artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.entity_resolution.build_research_defense_artifacts import (
    write_csv,
    write_json,
    write_text,
)
from src.utils.config import project_root

REPORTS_DIR = project_root() / "data" / "artifacts" / "reports"
DEFAULT_OUTPUT_DIR = REPORTS_DIR / "ml_defense_readiness"


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    section: str
    path: Path
    purpose: str
    required: bool = True


REQUIRED_ARTIFACTS = (
    ArtifactSpec(
        "ER",
        REPORTS_DIR / "entity_resolution" / "merge_strategies" / "merge_strategy_comparison.json",
        "Shadow merge strategy metrics.",
    ),
    ArtifactSpec(
        "ER",
        REPORTS_DIR / "ml_research_defense" / "ml_research_defense_summary.json",
        "Main ER research summary.",
    ),
    ArtifactSpec(
        "ER",
        REPORTS_DIR / "ml_research_defense" / "ablation_study.csv",
        "Feature ablation study.",
    ),
    ArtifactSpec(
        "ER",
        REPORTS_DIR / "ml_research_defense" / "calibration_bins.csv",
        "Calibration bins.",
    ),
    ArtifactSpec(
        "Graph",
        REPORTS_DIR / "graph_analysis" / "graph_analysis_summary.json",
        "Component-level ER graph risk analysis.",
    ),
    ArtifactSpec(
        "Embeddings",
        REPORTS_DIR / "embedding_research" / "embedding_research_summary.json",
        "Lightweight title embedding comparison.",
    ),
    ArtifactSpec(
        "IGDB",
        REPORTS_DIR / "igdb_matching" / "igdb_matching_summary.json",
        "IGDB search-lane retrieval analysis.",
    ),
    ArtifactSpec(
        "Recommendations",
        REPORTS_DIR / "ml_research_defense" / "recommendation_examples.csv",
        "Content-based recommendation examples.",
    ),
    ArtifactSpec(
        "Bayesian",
        REPORTS_DIR / "bayesian_rating" / "bayesian_rating_summary.json",
        "Bayesian rating analysis.",
    ),
    ArtifactSpec(
        "RAG",
        REPORTS_DIR / "rag_explanations" / "rag_explanation_summary.json",
        "Grounded Russian explanation examples.",
    ),
)


def relative_artifact_path(path: Path) -> str:
    try:
        return str(path.relative_to(project_root()))
    except ValueError:
        return str(path)


def artifact_status_rows(artifacts: tuple[ArtifactSpec, ...]) -> list[dict[str, object]]:
    rows = []
    for artifact in artifacts:
        exists = artifact.path.exists()
        size_bytes = artifact.path.stat().st_size if exists else 0
        rows.append(
            {
                "section": artifact.section,
                "artifact_path": relative_artifact_path(artifact.path),
                "purpose": artifact.purpose,
                "required": artifact.required,
                "exists": exists,
                "non_empty": size_bytes > 0,
                "size_bytes": size_bytes,
                "status": "ok" if exists and size_bytes > 0 else "missing",
            }
        )
    return rows


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if isinstance(current, list) and key.isdigit():
            index = int(key)
            current = current[index] if index < len(current) else None
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def metric_row(section: str, metric: str, value: object, interpretation: str) -> dict[str, object]:
    return {
        "section": section,
        "metric": metric,
        "value": value,
        "interpretation": interpretation,
    }


def sum_row_count(rows: object, *, status_filter: str | None = None) -> int | None:
    if not isinstance(rows, list):
        return None
    total = 0
    matched = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if status_filter is not None and row.get("review_status") != status_filter:
            continue
        if row.get("row_count") is None:
            continue
        total += int(row["row_count"])
        matched = True
    return total if matched else None


def build_metric_snapshot() -> list[dict[str, object]]:
    research = read_json(REPORTS_DIR / "ml_research_defense" / "ml_research_defense_summary.json")
    graph = read_json(REPORTS_DIR / "graph_analysis" / "graph_analysis_summary.json")
    embedding = read_json(REPORTS_DIR / "embedding_research" / "embedding_research_summary.json")
    igdb = read_json(REPORTS_DIR / "igdb_matching" / "igdb_matching_summary.json")
    bayesian = read_json(REPORTS_DIR / "bayesian_rating" / "bayesian_rating_summary.json")
    rag = read_json(REPORTS_DIR / "rag_explanations" / "rag_explanation_summary.json")
    metrics = [
        metric_row(
            "Data",
            "source_records",
            sum_row_count(nested_get(research, "baseline_counts", "source_games_by_source")),
            "Total normalized source records in staging.",
        ),
        metric_row(
            "ER",
            "candidate_pairs",
            sum_row_count(nested_get(research, "baseline_counts", "candidate_pairs_by_source")),
            "Entity-resolution candidate pairs.",
        ),
        metric_row(
            "ER",
            "manual_reviewed_labels",
            sum_row_count(
                nested_get(research, "baseline_counts", "manual_review_labels"),
                status_filter="reviewed",
            ),
            "Manual labels available for supervised ER evaluation.",
        ),
        metric_row(
            "ER",
            "v3c_f1",
            nested_get(research, "existing_er_artifacts", "v3c_metrics", "f1"),
            "Weighted Logistic Regression baseline F1.",
        ),
        metric_row(
            "Graph",
            "risky_components",
            graph.get("risky_component_count"),
            "Exported risky graph components across merge strategies.",
        ),
        metric_row(
            "Embeddings",
            "best_lightweight_embedding_f1",
            embedding.get("best_f1"),
            "Best F1 from local TF-IDF/SVD title-vector research lane.",
        ),
        metric_row(
            "IGDB",
            "rank_1_reviewed_precision",
            nested_get(igdb, "rank_precision", "0", "reviewed_precision"),
            "Rank-1 IGDB reviewed precision.",
        ),
        metric_row(
            "Bayesian",
            "bayesian_canonical_games",
            bayesian.get("canonical_game_count"),
            "Canonical games with vote-backed Bayesian ratings.",
        ),
        metric_row(
            "RAG",
            "grounded_explanations",
            (
                (rag.get("match_explanation_count") or 0)
                + (rag.get("recommendation_explanation_count") or 0)
            ),
            "Grounded Russian match and recommendation explanations.",
        ),
    ]
    return metrics


def build_demo_sequence_rows() -> list[dict[str, object]]:
    return [
        {
            "step": 1,
            "section": "Data pipeline",
            "show": "source counts, candidate pairs, manual labels",
            "evidence": "ml_research_defense_summary.json",
        },
        {
            "step": 2,
            "section": "ER model",
            "show": "v3c metrics, thresholds, calibration, ablation",
            "evidence": "ablation_study.csv, calibration_bins.csv",
        },
        {
            "step": 3,
            "section": "Merge governance",
            "show": "trusted vs model-only vs hybrid merge strategies",
            "evidence": "merge_strategy_comparison.json",
        },
        {
            "step": 4,
            "section": "Graph risk",
            "show": "same-source duplicate links and risky components",
            "evidence": "graph_analysis_summary.json",
        },
        {
            "step": 5,
            "section": "Embeddings",
            "show": "TF-IDF/SVD title-vector comparison",
            "evidence": "embedding_model_comparison.csv",
        },
        {
            "step": 6,
            "section": "IGDB",
            "show": "rank-1 vs lower-rank retrieval quality and enrichment coverage",
            "evidence": "igdb_matching_summary.json",
        },
        {
            "step": 7,
            "section": "Recommendations",
            "show": "content-based examples and shared features",
            "evidence": "recommendation_examples.csv",
        },
        {
            "step": 8,
            "section": "Bayesian rating",
            "show": "naive vs vote-adjusted ranking",
            "evidence": "bayesian_rating_summary.json",
        },
        {
            "step": 9,
            "section": "Grounded RAG",
            "show": "Russian explanations without LLM decision-making",
            "evidence": "rag_explanation_examples.md",
        },
    ]


def write_markdown_report(
    path: Path,
    artifact_rows: list[dict[str, object]],
    metric_rows: list[dict[str, object]],
    demo_rows: list[dict[str, object]],
) -> None:
    missing_required = [
        row for row in artifact_rows if row["required"] is True and row["status"] != "ok"
    ]
    missing_metrics = [row for row in metric_rows if row["value"] is None]
    overall_status = "ready" if not missing_required and not missing_metrics else "not_ready"
    lines = [
        "# ML Defense Readiness Report",
        "",
        f"Overall status: `{overall_status}`",
        "",
        "## Artifact Gate",
        "",
        "| Section | Status | Artifact |",
        "|---|---|---|",
    ]
    for row in artifact_rows:
        lines.append(f"| {row['section']} | `{row['status']}` | `{row['artifact_path']}` |")
    lines.extend(["", "## Metric Snapshot", "", "| Section | Metric | Value |", "|---|---|---:|"])
    for row in metric_rows:
        lines.append(f"| {row['section']} | {row['metric']} | `{row['value']}` |")
    lines.extend(
        ["", "## Demo Sequence", "", "| Step | Section | Show | Evidence |", "|---:|---|---|---|"]
    )
    for row in demo_rows:
        lines.append(f"| {row['step']} | {row['section']} | {row['show']} | `{row['evidence']}` |")
    if missing_required:
        lines.extend(["", "## Missing Required Artifacts", ""])
        for row in missing_required:
            lines.append(f"- `{row['artifact_path']}`")
    if missing_metrics:
        lines.extend(["", "## Missing Metrics", ""])
        for row in missing_metrics:
            lines.append(f"- `{row['section']}.{row['metric']}`")
    write_text(path, "\n".join(lines))


def build_ml_defense_readiness(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_rows = artifact_status_rows(REQUIRED_ARTIFACTS)
    metric_rows = build_metric_snapshot()
    demo_rows = build_demo_sequence_rows()
    missing_required = [
        row for row in artifact_rows if row["required"] is True and row["status"] != "ok"
    ]
    missing_metrics = [row for row in metric_rows if row["value"] is None]
    summary = {
        "overall_status": "ready" if not missing_required and not missing_metrics else "not_ready",
        "required_artifact_count": len([row for row in artifact_rows if row["required"] is True]),
        "missing_required_count": len(missing_required),
        "missing_metric_count": len(missing_metrics),
        "metric_count": len(metric_rows),
        "demo_step_count": len(demo_rows),
    }
    write_csv(output_dir / "ml_defense_artifact_checklist.csv", artifact_rows)
    write_csv(output_dir / "ml_defense_metric_snapshot.csv", metric_rows)
    write_csv(output_dir / "ml_defense_demo_sequence.csv", demo_rows)
    write_json(output_dir / "ml_defense_readiness_summary.json", summary)
    write_markdown_report(
        output_dir / "ml_defense_readiness_report.md",
        artifact_rows,
        metric_rows,
        demo_rows,
    )
    return {"output_dir": str(output_dir), **summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build final ML defense readiness report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_ml_defense_readiness(Path(args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
