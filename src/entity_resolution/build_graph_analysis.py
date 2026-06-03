"""Build ER graph analysis artifacts for defense and risk review."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.entity_resolution.build_canonical_v0 import SourceKey
from src.entity_resolution.build_research_defense_artifacts import (
    horizontal_bar_chart_svg,
    write_csv,
    write_json,
    write_text,
)
from src.entity_resolution.compare_merge_strategies import (
    DEFAULT_STRATEGIES,
    MergeStrategy,
    as_float,
    component_index_for_edges,
    edge_for_row,
    fetch_review_candidate_rows,
    is_reviewed_negative,
    is_trusted_canonical_edge,
    predicted_same_component,
    select_strategy_edges,
)
from src.entity_resolution.corpus import SourceGameRecord, load_source_records
from src.ingestion.repository import IngestionRepository
from src.utils.config import project_root

DEFAULT_OUTPUT_DIR = project_root() / "data" / "artifacts" / "reports" / "graph_analysis"


def source_pair(left: SourceKey, right: SourceKey) -> str:
    return " <-> ".join(sorted((left[0], right[0])))


def component_label(
    records: dict[SourceKey, SourceGameRecord],
    group: set[SourceKey],
    limit: int = 5,
) -> str:
    names = [
        records[key].name
        for key in sorted(group)
        if key in records and records[key].name and records[key].name != key[1]
    ]
    if not names:
        names = [f"{source}:{source_id}" for source, source_id in sorted(group)]
    return " | ".join(names[:limit])


def component_duplicate_stats(group: set[SourceKey]) -> tuple[int, str]:
    source_counts = Counter(source for source, _source_id in group)
    duplicate_links = sum(count - 1 for count in source_counts.values() if count > 1)
    duplicate_sources = ", ".join(
        f"{source}:{count}" for source, count in sorted(source_counts.items()) if count > 1
    )
    return duplicate_links, duplicate_sources


def edge_origin(
    edge: tuple[SourceKey, SourceKey],
    trusted_edges: set[tuple[SourceKey, SourceKey]],
    model_edges: set[tuple[SourceKey, SourceKey]],
) -> str:
    trusted = edge in trusted_edges
    model = edge in model_edges
    if trusted and model:
        return "trusted_and_model"
    if trusted:
        return "trusted"
    if model:
        return "model"
    return "unknown"


def source_bridge_rows(
    strategy: MergeStrategy,
    edges: set[tuple[SourceKey, SourceKey]],
    trusted_edges: set[tuple[SourceKey, SourceKey]],
    model_edges: set[tuple[SourceKey, SourceKey]],
) -> list[dict[str, object]]:
    counts: Counter[tuple[str, str]] = Counter()
    for edge in edges:
        left, right = edge
        counts[(source_pair(left, right), edge_origin(edge, trusted_edges, model_edges))] += 1
    return [
        {
            "strategy": strategy.name,
            "source_pair": source_pair_,
            "edge_origin": origin,
            "edge_count": count,
        }
        for (source_pair_, origin), count in sorted(counts.items())
    ]


def component_size_distribution_rows(
    strategy: MergeStrategy,
    groups: list[set[SourceKey]],
) -> list[dict[str, object]]:
    buckets: Counter[str] = Counter()
    for group in groups:
        size = len(group)
        if size == 1:
            bucket = "1"
        elif size == 2:
            bucket = "2"
        elif size <= 5:
            bucket = "3-5"
        elif size <= 10:
            bucket = "6-10"
        else:
            bucket = "11+"
        buckets[bucket] += 1
    return [
        {"strategy": strategy.name, "component_size_bucket": bucket, "component_count": count}
        for bucket, count in sorted(buckets.items())
    ]


def component_edge_counts(
    component_index: dict[SourceKey, int],
    edges: set[tuple[SourceKey, SourceKey]],
    trusted_edges: set[tuple[SourceKey, SourceKey]],
    model_edges: set[tuple[SourceKey, SourceKey]],
) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {"selected_edges": 0, "trusted_edges": 0, "model_edges": 0}
    )
    for edge in edges:
        left, _right = edge
        component_id = component_index.get(left)
        if component_id is None:
            continue
        counts[component_id]["selected_edges"] += 1
        if edge in trusted_edges:
            counts[component_id]["trusted_edges"] += 1
        if edge in model_edges:
            counts[component_id]["model_edges"] += 1
    return counts


def manual_negative_component_counts(
    rows: list[dict[str, Any]],
    component_index: dict[SourceKey, int],
) -> dict[int, int]:
    counts: Counter[int] = Counter()
    for row in rows:
        if not is_reviewed_negative(row):
            continue
        left, right = edge_for_row(row)
        if not predicted_same_component(component_index, left, right):
            continue
        component_id = component_index.get(left)
        if component_id is not None:
            counts[component_id] += 1
    return dict(counts)


def risky_component_rows(
    strategy: MergeStrategy,
    records: dict[SourceKey, SourceGameRecord],
    rows: list[dict[str, Any]],
    groups: list[set[SourceKey]],
    component_index: dict[SourceKey, int],
    edges: set[tuple[SourceKey, SourceKey]],
    trusted_edges: set[tuple[SourceKey, SourceKey]],
    model_edges: set[tuple[SourceKey, SourceKey]],
    *,
    limit: int = 100,
) -> list[dict[str, object]]:
    edge_counts = component_edge_counts(component_index, edges, trusted_edges, model_edges)
    negative_counts = manual_negative_component_counts(rows, component_index)
    result: list[dict[str, object]] = []
    for component_id, group in enumerate(groups):
        duplicate_links, duplicate_sources = component_duplicate_stats(group)
        manual_negative_count = negative_counts.get(component_id, 0)
        if duplicate_links == 0 and manual_negative_count == 0 and len(group) <= 6:
            continue
        sources = Counter(source for source, _source_id in group)
        source_ids = "; ".join(f"{source}:{source_id}" for source, source_id in sorted(group)[:20])
        risk_score = (manual_negative_count * 100) + (duplicate_links * 10) + max(0, len(group) - 6)
        selected_edge_counts = edge_counts.get(
            component_id, {"selected_edges": 0, "trusted_edges": 0, "model_edges": 0}
        )
        result.append(
            {
                "strategy": strategy.name,
                "component_id": component_id,
                "risk_score": risk_score,
                "component_size": len(group),
                "source_count": len(sources),
                "source_distribution": ", ".join(
                    f"{source}:{count}" for source, count in sorted(sources.items())
                ),
                "same_source_duplicate_links": duplicate_links,
                "same_source_duplicate_sources": duplicate_sources,
                "manual_negative_pairs_in_component": manual_negative_count,
                "selected_edge_count": selected_edge_counts["selected_edges"],
                "trusted_edge_count": selected_edge_counts["trusted_edges"],
                "model_edge_count": selected_edge_counts["model_edges"],
                "component_label": component_label(records, group),
                "source_keys_preview": source_ids,
            }
        )
    result.sort(
        key=lambda row: (
            -int(row["risk_score"]),
            -int(row["manual_negative_pairs_in_component"]),
            -int(row["same_source_duplicate_links"]),
            -int(row["component_size"]),
            str(row["component_label"]).lower(),
        )
    )
    return result[:limit]


def strategy_summary_row(
    strategy: MergeStrategy,
    groups: list[set[SourceKey]],
    edges: set[tuple[SourceKey, SourceKey]],
    trusted_edges: set[tuple[SourceKey, SourceKey]],
    model_edges: set[tuple[SourceKey, SourceKey]],
    risky_rows: list[dict[str, object]],
) -> dict[str, object]:
    same_source_duplicate_components = sum(
        1 for group in groups if component_duplicate_stats(group)[0] > 0
    )
    same_source_duplicate_links = sum(component_duplicate_stats(group)[0] for group in groups)
    multi_source_components = sum(
        1 for group in groups if len({source for source, _source_id in group}) > 1
    )
    return {
        "strategy": strategy.name,
        "description": strategy.description,
        "edge_count": len(edges),
        "trusted_edge_count": len(trusted_edges),
        "model_edge_count": len(model_edges),
        "component_count": len(groups),
        "multi_source_component_count": multi_source_components,
        "max_component_size": max((len(group) for group in groups), default=0),
        "same_source_duplicate_components": same_source_duplicate_components,
        "same_source_duplicate_links": same_source_duplicate_links,
        "risky_component_count": len(risky_rows),
    }


def high_probability_negative_rows(
    rows: list[dict[str, Any]],
    *,
    min_probability: float = 0.70,
    limit: int = 100,
) -> list[dict[str, object]]:
    result = []
    for row in rows:
        if not is_reviewed_negative(row):
            continue
        probability = as_float(row.get("same_game_probability"))
        if probability is None or probability < min_probability:
            continue
        result.append(
            {
                "pair_id": str(row.get("pair_id") or ""),
                "source_a": str(row.get("source_a") or ""),
                "source_id_a": str(row.get("source_id_a") or ""),
                "name_a": str(row.get("name_a") or ""),
                "release_year_a": row.get("release_year_a"),
                "source_b": str(row.get("source_b") or ""),
                "source_id_b": str(row.get("source_id_b") or ""),
                "name_b": str(row.get("name_b") or ""),
                "release_year_b": row.get("release_year_b"),
                "candidate_source": str(row.get("candidate_source") or ""),
                "same_game_probability": probability,
                "name_similarity": row.get("name_similarity"),
                "release_year_diff": row.get("release_year_diff"),
                "review_notes": str(row.get("review_notes") or ""),
                "trusted_canonical_edge": is_trusted_canonical_edge(row),
            }
        )
    result.sort(
        key=lambda row: (
            -float(row["same_game_probability"]),
            str(row["name_a"]).lower(),
            str(row["name_b"]).lower(),
        )
    )
    return result[:limit]


def write_markdown_summary(
    path: Path,
    summary_rows: list[dict[str, object]],
    high_probability_negative_count: int,
) -> None:
    lines = [
        "# ER Graph Analysis",
        "",
        "This report analyzes shadow ER graph components without mutating `dm.canonical_*`.",
        "",
        "| Strategy | Components | Multi-source | Max size | Same-source links | "
        "Risky components |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {strategy} | {component_count} | {multi_source_component_count} | "
            "{max_component_size} | {same_source_duplicate_links} | "
            "{risky_component_count} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- Same-source duplicate links indicate components where a merge policy joins "
            "multiple records from the same source.",
            "- Manual-negative pairs inside one component are high-risk evidence for false "
            "positive merge behavior.",
            "- Large components are not necessarily wrong, but they are useful defense examples "
            "for transitive ER risk.",
            f"- High-probability reviewed negatives exported: `{high_probability_negative_count}`.",
            "",
        ]
    )
    write_text(path, "\n".join(lines))


def build_graph_analysis(output_dir: Path, *, risky_limit: int) -> dict[str, object]:
    repository = IngestionRepository()
    records = load_source_records(repository)
    rows = fetch_review_candidate_rows(repository)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    all_distribution_rows: list[dict[str, object]] = []
    all_bridge_rows: list[dict[str, object]] = []
    all_risky_rows: list[dict[str, object]] = []

    for strategy in DEFAULT_STRATEGIES:
        edges, trusted_edges, model_edges = select_strategy_edges(rows, strategy)
        component_index, groups = component_index_for_edges(records, edges)
        risky_rows = risky_component_rows(
            strategy,
            records,
            rows,
            groups,
            component_index,
            edges,
            trusted_edges,
            model_edges,
            limit=risky_limit,
        )
        summary_rows.append(
            strategy_summary_row(strategy, groups, edges, trusted_edges, model_edges, risky_rows)
        )
        all_distribution_rows.extend(component_size_distribution_rows(strategy, groups))
        all_bridge_rows.extend(source_bridge_rows(strategy, edges, trusted_edges, model_edges))
        all_risky_rows.extend(risky_rows)

    high_probability_negatives = high_probability_negative_rows(rows)
    write_csv(output_dir / "graph_strategy_summary.csv", summary_rows)
    write_csv(output_dir / "component_size_distribution.csv", all_distribution_rows)
    write_csv(output_dir / "source_bridge_edges.csv", all_bridge_rows)
    write_csv(output_dir / "risky_components.csv", all_risky_rows)
    write_csv(output_dir / "high_probability_reviewed_negatives.csv", high_probability_negatives)
    write_json(
        output_dir / "graph_analysis_summary.json",
        {
            "strategy_count": len(DEFAULT_STRATEGIES),
            "source_record_count": len(records),
            "candidate_pair_count": len(rows),
            "risky_component_count": len(all_risky_rows),
            "high_probability_reviewed_negative_count": len(high_probability_negatives),
            "strategies": summary_rows,
        },
    )
    write_markdown_summary(
        output_dir / "graph_analysis_summary.md",
        summary_rows,
        len(high_probability_negatives),
    )
    write_text(
        output_dir / "same_source_duplicate_links.svg",
        horizontal_bar_chart_svg(
            summary_rows,
            title="Same-source Duplicate Links By Merge Strategy",
            label_key="strategy",
            value_key="same_source_duplicate_links",
            value_label="duplicate source links",
        ),
    )
    return {
        "output_dir": str(output_dir),
        "strategy_count": len(DEFAULT_STRATEGIES),
        "source_record_count": len(records),
        "candidate_pair_count": len(rows),
        "risky_component_count": len(all_risky_rows),
        "high_probability_reviewed_negative_count": len(high_probability_negatives),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build ER graph analysis artifacts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--risky-limit", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(build_graph_analysis(Path(args.output_dir), risky_limit=args.risky_limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
