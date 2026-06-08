"""Check whether local demo data and defense artifacts are ready."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.utils.config import project_root


@dataclass(frozen=True)
class ReadinessItem:
    name: str
    path: str
    exists: bool
    required: bool
    recommendation: str
    command: str
    result: str


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    path: str
    recommendation: str
    command: str
    result: str


COMMAND_REFERENCE = {
    "path": "docs/demo_readiness_command_reference_ru.md",
    "description": (
        "Russian command reference for every Makefile action suggested by "
        "`/stats/readiness` and the demo UI."
    ),
}


REQUIRED_CHECKS: tuple[ReadinessCheck, ...] = (
    ReadinessCheck(
        "data directory",
        "data",
        "Create local data directories or restore a data pack.",
        "make restore-from-files DATA_PACK=data_packs/gip_demo_local",
        "Restores local data folders from a prepared data pack when API re-download is not needed.",
    ),
    ReadinessCheck(
        "reports directory",
        "data/artifacts/reports",
        "Run `make ml-defense-all` or restore a prepared data pack.",
        "make ml-defense-all",
        "Rebuilds the defense research package: ER analyses, recommendations, "
        "explanations, readiness, and presentation artifacts.",
    ),
)

RECOMMENDED_CHECKS: tuple[ReadinessCheck, ...] = (
    ReadinessCheck(
        "ML research defense summary",
        "data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json",
        "Run `make ml-research-defense`.",
        "make ml-research-defense",
        "Creates the central ML research summary, ablation/calibration tables, "
        "active-learning candidates, charts, and demo cases.",
    ),
    ReadinessCheck(
        "ML defense readiness summary",
        "data/artifacts/reports/ml_defense_readiness/ml_defense_readiness_summary.json",
        "Run `make ml-defense-readiness`.",
        "make ml-defense-readiness",
        "Checks the generated research artifacts and writes the final metric snapshot, "
        "demo sequence, and artifact checklist.",
    ),
    ReadinessCheck(
        "ER manual review pending artifact",
        "data/artifacts/reports/entity_resolution/entity_resolution_manual_review_pending.csv",
        "Run `make er-review-queue` and `make er-export-review-queue`.",
        "make er-review-queue && make er-export-review-queue",
        "Refreshes the manual-review candidate queue and exports pending/reviewed "
        "review CSV files.",
    ),
    ReadinessCheck(
        "ER manual review reviewed artifact",
        "data/artifacts/reports/entity_resolution/entity_resolution_manual_review_reviewed.csv",
        "Run `make er-export-review-queue` after manual review labels are available.",
        "make er-export-review-queue",
        "Exports manually reviewed ER pairs for model training audit and defense evidence.",
    ),
    ReadinessCheck(
        "Recommendation examples",
        "data/artifacts/reports/ml_research_defense/recommendation_examples.csv",
        "Run `make ml-research-defense` or `make recommendations`.",
        "make ml-research-defense",
        "Exports explainable recommendation examples used by the defense report and UI demo.",
    ),
    ReadinessCheck(
        "Bayesian rating canonical fallback",
        "data/artifacts/reports/bayesian_rating/canonical_bayesian_ratings.csv",
        "Run `make bayesian-rating`.",
        "make bayesian-rating",
        "Builds naive-vs-Bayesian rating comparison tables and charts for canonical games.",
    ),
    ReadinessCheck(
        "Recommendation explanations",
        "data/artifacts/reports/rag_explanations/recommendation_explanation_examples.csv",
        "Run `make rag-explanations`.",
        "make rag-explanations",
        "Creates grounded Russian explanations for recommendation examples from computed facts.",
    ),
    ReadinessCheck(
        "Match explanations",
        "data/artifacts/reports/rag_explanations/match_explanation_examples.csv",
        "Run `make rag-explanations`.",
        "make rag-explanations",
        "Creates grounded Russian explanations for ER match/non-match examples.",
    ),
    ReadinessCheck(
        "Grounded fact cards",
        "data/artifacts/reports/rag_explanations/grounded_fact_cards.csv",
        "Run `make rag-explanations`.",
        "make rag-explanations",
        "Exports the source-aware fact cards used as the grounding layer for explanations.",
    ),
    ReadinessCheck(
        "Data pack directory",
        "data_packs/gip_demo_local",
        "Run `make export-data-pack` or restore from an existing data pack.",
        "make export-data-pack",
        "Creates a reusable local data pack for deployment without repeating broad API downloads.",
    ),
)


def check_path(
    root: Path,
    name: str,
    relative_path: str,
    recommendation: str,
    command: str,
    result: str,
    *,
    required: bool,
) -> ReadinessItem:
    path = root / relative_path
    return ReadinessItem(
        name=name,
        path=str(path),
        exists=path.exists(),
        required=required,
        recommendation=recommendation,
        command=command,
        result=result,
    )


def evaluate_demo_readiness(root: Path | None = None) -> dict[str, Any]:
    """Return demo data readiness status without touching external APIs."""

    resolved_root = root or project_root()
    items: list[ReadinessItem] = [
        check_path(
            resolved_root,
            check.name,
            check.path,
            check.recommendation,
            check.command,
            check.result,
            required=True,
        )
        for check in REQUIRED_CHECKS
    ]
    items.extend(
        check_path(
            resolved_root,
            check.name,
            check.path,
            check.recommendation,
            check.command,
            check.result,
            required=False,
        )
        for check in RECOMMENDED_CHECKS
    )

    missing_required = [item for item in items if item.required and not item.exists]
    missing_recommended = [item for item in items if not item.required and not item.exists]
    found = [item for item in items if item.exists]

    if missing_required:
        status = "error"
    elif missing_recommended:
        status = "warning"
    else:
        status = "ok"

    recommendations = []
    seen = set()
    for item in [*missing_required, *missing_recommended]:
        if item.recommendation not in seen:
            recommendations.append(item.recommendation)
            seen.add(item.recommendation)

    warnings = [
        f"Missing recommended artifact: {item.name}"
        for item in missing_recommended
    ]
    errors = [
        f"Missing required artifact: {item.name}"
        for item in missing_required
    ]

    return {
        "status": status,
        "project_root": str(resolved_root),
        "command_reference": COMMAND_REFERENCE,
        "found_artifacts": [asdict(item) for item in found],
        "missing_artifacts": [asdict(item) for item in [*missing_required, *missing_recommended]],
        "missing_count": len(missing_required) + len(missing_recommended),
        "warnings": warnings,
        "errors": errors,
        "recommendations": recommendations,
    }


def format_human_report(result: dict[str, Any]) -> str:
    lines = [
        "Demo Data Readiness",
        f"Status: {result['status']}",
        f"Project root: {result['project_root']}",
        f"Command reference: {result['command_reference']['path']}",
        "",
        "Found artifacts:",
    ]
    found = result.get("found_artifacts") or []
    if found:
        lines.extend(f"- {item['name']}: {item['path']}" for item in found)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Missing artifacts:")
    missing = result.get("missing_artifacts") or []
    if missing:
        lines.extend(
            f"- {item['name']} ({'required' if item['required'] else 'recommended'}): "
            f"{item['path']}"
            for item in missing
        )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Recommended commands:")
    recommendations = result.get("recommendations") or []
    if recommendations:
        lines.extend(f"- {item}" for item in recommendations)
    else:
        lines.append("- no action required")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local demo data readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human report.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root override, mainly for tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = evaluate_demo_readiness(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_human_report(result))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
