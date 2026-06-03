"""Compare shadow canonical merge strategies without changing dm.canonical_* tables."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.entity_resolution.build_canonical_v0 import SourceKey, UnionFind
from src.entity_resolution.corpus import SourceGameRecord, load_source_records
from src.entity_resolution.io import ensure_output_directories
from src.ingestion.repository import IngestionRepository


@dataclass(frozen=True, slots=True)
class MergeStrategy:
    name: str
    description: str
    mode: str
    threshold: float | None = None
    min_name_similarity: float | None = None
    max_release_year_diff: int | None = None
    manual_negative_blacklist: bool = False


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    strategy: str
    description: str
    edge_count: int
    trusted_edge_count: int
    model_edge_count: int
    component_count: int
    multi_source_component_count: int
    max_component_size: int
    same_source_duplicate_components: int
    same_source_duplicate_links: int
    reviewed_pair_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float | None
    recall: float | None
    f1: float | None


DEFAULT_STRATEGIES = (
    MergeStrategy(
        name="canonical_v1_trusted",
        description=(
            "Current trusted canonical v1: deterministic external-id edges plus reviewed positives."
        ),
        mode="trusted",
    ),
    MergeStrategy(
        name="model_auto_095",
        description="Model-only auto merge at probability >= 0.95.",
        mode="model_only",
        threshold=0.95,
    ),
    MergeStrategy(
        name="model_auto_090",
        description="Model-only auto merge at probability >= 0.90.",
        mode="model_only",
        threshold=0.90,
    ),
    MergeStrategy(
        name="model_auto_070_research",
        description="Research-only aggressive model merge at probability >= 0.70.",
        mode="model_only",
        threshold=0.70,
    ),
    MergeStrategy(
        name="hybrid_conservative_095",
        description=(
            "Trusted canonical v1 plus model edges at probability >= 0.95; "
            "manual negatives are blocked."
        ),
        mode="hybrid",
        threshold=0.95,
        manual_negative_blacklist=True,
    ),
    MergeStrategy(
        name="hybrid_safe_090",
        description=(
            "Trusted canonical v1 plus model edges at probability >= 0.90, "
            "name similarity >= 0.90, release-year diff <= 2; "
            "manual negatives are blocked."
        ),
        mode="hybrid",
        threshold=0.90,
        min_name_similarity=0.90,
        max_release_year_diff=2,
        manual_negative_blacklist=True,
    ),
)


def source_key(source: object, source_id: object) -> SourceKey:
    return (str(source), str(source_id))


def as_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def as_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def is_reviewed_positive(row: dict[str, Any]) -> bool:
    return str(row.get("review_status") or "") == "reviewed" and row.get("review_label") is True


def is_reviewed_negative(row: dict[str, Any]) -> bool:
    return str(row.get("review_status") or "") == "reviewed" and row.get("review_label") is False


def is_trusted_canonical_edge(row: dict[str, Any]) -> bool:
    if is_reviewed_positive(row):
        return True
    if str(row.get("candidate_source") or "") != "external_id":
        return False
    if str(row.get("label_value") or "") != "1":
        return False
    if is_reviewed_negative(row):
        return False
    name_similarity = as_float(row.get("name_similarity")) or 0.0
    release_year_diff = as_int(row.get("release_year_diff"))
    return name_similarity >= 0.90 and (release_year_diff is None or release_year_diff <= 2)


def is_model_edge(row: dict[str, Any], strategy: MergeStrategy) -> bool:
    if strategy.threshold is None:
        return False
    probability = as_float(row.get("same_game_probability"))
    if probability is None or probability < strategy.threshold:
        return False
    if strategy.manual_negative_blacklist and is_reviewed_negative(row):
        return False
    if strategy.min_name_similarity is not None:
        name_similarity = as_float(row.get("name_similarity")) or 0.0
        if name_similarity < strategy.min_name_similarity:
            return False
    if strategy.max_release_year_diff is not None:
        release_year_diff = as_int(row.get("release_year_diff"))
        if release_year_diff is not None and release_year_diff > strategy.max_release_year_diff:
            return False
    return True


def edge_for_row(row: dict[str, Any]) -> tuple[SourceKey, SourceKey]:
    return (
        source_key(row["source_a"], row["source_id_a"]),
        source_key(row["source_b"], row["source_id_b"]),
    )


def select_strategy_edges(
    rows: list[dict[str, Any]],
    strategy: MergeStrategy,
) -> tuple[
    set[tuple[SourceKey, SourceKey]],
    set[tuple[SourceKey, SourceKey]],
    set[tuple[SourceKey, SourceKey]],
]:
    trusted_edges: set[tuple[SourceKey, SourceKey]] = set()
    model_edges: set[tuple[SourceKey, SourceKey]] = set()
    for row in rows:
        edge = edge_for_row(row)
        if strategy.mode in {"trusted", "hybrid"} and is_trusted_canonical_edge(row):
            trusted_edges.add(edge)
        if strategy.mode in {"model_only", "hybrid"} and is_model_edge(row, strategy):
            model_edges.add(edge)
    return trusted_edges | model_edges, trusted_edges, model_edges


def add_shared_enrichment_links(
    union_find: UnionFind,
    records: dict[SourceKey, SourceGameRecord],
) -> None:
    for key, record in records.items():
        if record.source == "wikidata":
            steam_appid = record.external_ids.get("steam")
            if steam_appid and ("steam", str(steam_appid)) in records:
                union_find.union(key, ("steam", str(steam_appid)))
            wikipedia_key = ("wikipedia", record.source_game_id)
            if wikipedia_key in records:
                union_find.union(key, wikipedia_key)


def component_index_for_edges(
    records: dict[SourceKey, SourceGameRecord],
    edges: set[tuple[SourceKey, SourceKey]],
) -> tuple[dict[SourceKey, int], list[set[SourceKey]]]:
    union_find = UnionFind()
    for key in records:
        union_find.add(key)
    for left, right in edges:
        if left in records and right in records:
            union_find.union(left, right)
    add_shared_enrichment_links(union_find, records)
    groups = union_find.groups()
    index = {
        source_key_: group_index
        for group_index, group in enumerate(groups)
        for source_key_ in group
    }
    return index, groups


def predicted_same_component(
    component_index: dict[SourceKey, int],
    left: SourceKey,
    right: SourceKey,
) -> bool:
    left_component = component_index.get(left)
    right_component = component_index.get(right)
    return left_component is not None and left_component == right_component


def precision_recall_f1(
    tp: int, fp: int, fn: int
) -> tuple[float | None, float | None, float | None]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None or precision + recall == 0:
        return precision, recall, None
    return precision, recall, 2 * precision * recall / (precision + recall)


def same_source_duplicate_stats(groups: list[set[SourceKey]]) -> tuple[int, int]:
    component_count = 0
    duplicate_links = 0
    for group in groups:
        counts = Counter(source for source, _source_id in group)
        duplicates = sum(count - 1 for count in counts.values() if count > 1)
        if duplicates:
            component_count += 1
            duplicate_links += duplicates
    return component_count, duplicate_links


def evaluate_strategy(
    records: dict[SourceKey, SourceGameRecord],
    rows: list[dict[str, Any]],
    strategy: MergeStrategy,
) -> tuple[StrategyEvaluation, list[dict[str, object]]]:
    edges, trusted_edges, model_edges = select_strategy_edges(rows, strategy)
    component_index, groups = component_index_for_edges(records, edges)

    tp = fp = tn = fn = 0
    risk_rows: list[dict[str, object]] = []
    for row in rows:
        if str(row.get("review_status") or "") != "reviewed" or row.get("review_label") is None:
            continue
        left, right = edge_for_row(row)
        predicted_positive = predicted_same_component(component_index, left, right)
        actual_positive = bool(row["review_label"])
        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
            risk_rows.append(risk_row(strategy.name, row, "manual_negative_in_same_component"))
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1

    same_source_components, same_source_links = same_source_duplicate_stats(groups)
    precision, recall, f1 = precision_recall_f1(tp, fp, fn)
    multi_source_component_count = sum(
        1 for group in groups if len({source for source, _source_id in group}) > 1
    )
    return (
        StrategyEvaluation(
            strategy=strategy.name,
            description=strategy.description,
            edge_count=len(edges),
            trusted_edge_count=len(trusted_edges),
            model_edge_count=len(model_edges),
            component_count=len(groups),
            multi_source_component_count=multi_source_component_count,
            max_component_size=max((len(group) for group in groups), default=0),
            same_source_duplicate_components=same_source_components,
            same_source_duplicate_links=same_source_links,
            reviewed_pair_count=tp + fp + tn + fn,
            true_positive=tp,
            false_positive=fp,
            true_negative=tn,
            false_negative=fn,
            precision=precision,
            recall=recall,
            f1=f1,
        ),
        risk_rows,
    )


def risk_row(strategy_name: str, row: dict[str, Any], risk_type: str) -> dict[str, object]:
    return {
        "strategy": strategy_name,
        "risk_type": risk_type,
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
        "same_game_probability": row.get("same_game_probability"),
        "name_similarity": row.get("name_similarity"),
        "release_year_diff": row.get("release_year_diff"),
        "review_label": row.get("review_label"),
        "reviewer": str(row.get("reviewer") or ""),
        "review_notes": str(row.get("review_notes") or ""),
    }


def candidate_row(row: dict[str, Any]) -> dict[str, object]:
    return {
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
        "same_game_probability": row.get("same_game_probability"),
        "model_decision": str(row.get("model_decision") or ""),
        "name_similarity": row.get("name_similarity"),
        "release_year_diff": row.get("release_year_diff"),
        "review_status": str(row.get("review_status") or ""),
        "review_label": row.get("review_label"),
        "reviewer": str(row.get("reviewer") or ""),
        "trusted_canonical_edge": is_trusted_canonical_edge(row),
    }


def model_auto_merge_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    min_probability: float,
) -> list[dict[str, object]]:
    candidates = [
        candidate_row(row)
        for row in rows
        if (as_float(row.get("same_game_probability")) or 0.0) >= min_probability
    ]
    return sorted(
        candidates,
        key=lambda row: (
            -float(row["same_game_probability"] or 0.0),
            str(row["candidate_source"]),
            str(row["name_a"]).lower(),
            str(row["name_b"]).lower(),
        ),
    )


def evaluation_to_row(evaluation: StrategyEvaluation) -> dict[str, object]:
    return {
        "strategy": evaluation.strategy,
        "description": evaluation.description,
        "edge_count": evaluation.edge_count,
        "trusted_edge_count": evaluation.trusted_edge_count,
        "model_edge_count": evaluation.model_edge_count,
        "component_count": evaluation.component_count,
        "multi_source_component_count": evaluation.multi_source_component_count,
        "max_component_size": evaluation.max_component_size,
        "same_source_duplicate_components": evaluation.same_source_duplicate_components,
        "same_source_duplicate_links": evaluation.same_source_duplicate_links,
        "reviewed_pair_count": evaluation.reviewed_pair_count,
        "true_positive": evaluation.true_positive,
        "false_positive": evaluation.false_positive,
        "true_negative": evaluation.true_negative,
        "false_negative": evaluation.false_negative,
        "precision": round(evaluation.precision, 6) if evaluation.precision is not None else None,
        "recall": round(evaluation.recall, 6) if evaluation.recall is not None else None,
        "f1": round(evaluation.f1, 6) if evaluation.f1 is not None else None,
    }


def fetch_review_candidate_rows(repository: IngestionRepository) -> list[dict[str, Any]]:
    query = """
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
            label_source,
            label_value,
            name_similarity,
            release_year_diff,
            same_game_probability,
            model_decision,
            review_label,
            review_status,
            reviewer,
            review_notes
        FROM ml.v_entity_resolution_review_candidates
        ORDER BY pair_id
    """
    with repository.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return list(cursor.fetchall())


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_markdown_summary(path: Path, report_rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Entity Resolution Merge Strategy Comparison",
        "",
        "This report compares shadow merge strategies without changing `dm.canonical_*` tables.",
        "",
        "| Strategy | Edges | Components | Precision | Recall | F1 | FP | FN | "
        "Same-source duplicate links |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report_rows:
        safe_row = {key: "" if value is None else value for key, value in row.items()}
        lines.append(
            "| {strategy} | {edge_count} | {component_count} | {precision} | {recall} | "
            "{f1} | {false_positive} | {false_negative} | {same_source_duplicate_links} |".format(
                **safe_row
            )
        )
    lines.extend(
        [
            "",
            "Interpretation notes:",
            "",
            "- `canonical_v1_trusted` is the current production-safe strategy.",
            "- `model_auto_*` strategies show pure ML inference behavior at fixed thresholds.",
            "- `hybrid_*` strategies combine trusted canonical edges with model suggestions "
            "and block manual negatives.",
            "- `model_auto_070_research` is intentionally aggressive and should be treated "
            "as a risk analysis lane.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare ER merge strategies without writing canonical tables."
    )
    parser.add_argument(
        "--reports-dir",
        default=str(ensure_output_directories().reports_dir / "merge_strategies"),
    )
    parser.add_argument("--candidate-threshold", type=float, default=0.90)
    parser.add_argument("--skip-risk-csv", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = IngestionRepository()
    records = load_source_records(repository)
    rows = fetch_review_candidate_rows(repository)

    report_rows: list[dict[str, object]] = []
    risk_rows: list[dict[str, object]] = []
    for strategy in DEFAULT_STRATEGIES:
        evaluation, strategy_risks = evaluate_strategy(records, rows, strategy)
        report_rows.append(evaluation_to_row(evaluation))
        risk_rows.extend(strategy_risks)

    reports_dir = Path(args.reports_dir)
    comparison_csv_path = reports_dir / "merge_strategy_comparison.csv"
    comparison_json_path = reports_dir / "merge_strategy_comparison.json"
    summary_md_path = reports_dir / "merge_strategy_summary.md"
    risk_csv_path = reports_dir / "hybrid_merge_risk_cases.csv"
    model_candidates_csv_path = reports_dir / "model_auto_merge_candidates.csv"
    model_candidate_rows = model_auto_merge_candidate_rows(
        rows,
        min_probability=args.candidate_threshold,
    )
    write_csv(comparison_csv_path, report_rows)
    write_csv(model_candidates_csv_path, model_candidate_rows)
    write_markdown_summary(summary_md_path, report_rows)
    write_json(
        comparison_json_path,
        {
            "strategy_count": len(report_rows),
            "source_record_count": len(records),
            "candidate_pair_count": len(rows),
            "model_candidate_threshold": args.candidate_threshold,
            "model_candidate_count": len(model_candidate_rows),
            "strategies": report_rows,
            "risk_case_count": len(risk_rows),
        },
    )
    if not args.skip_risk_csv:
        write_csv(risk_csv_path, risk_rows)

    print(
        {
            "comparison_csv": str(comparison_csv_path),
            "comparison_json": str(comparison_json_path),
            "summary_md": str(summary_md_path),
            "model_candidates_csv": str(model_candidates_csv_path),
            "risk_csv": None if args.skip_risk_csv else str(risk_csv_path),
            "strategy_count": len(report_rows),
            "model_candidate_count": len(model_candidate_rows),
            "risk_case_count": len(risk_rows),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
