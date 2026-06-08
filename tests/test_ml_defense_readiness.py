from __future__ import annotations

from pathlib import Path

from src.devtools.build_ml_defense_readiness import (
    ArtifactSpec,
    artifact_status_rows,
    build_demo_sequence_rows,
    nested_get,
    sum_row_count,
)


def test_artifact_status_rows_marks_existing_and_missing_files(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing.json"
    rows = artifact_status_rows(
        (
            ArtifactSpec("A", existing, "exists"),
            ArtifactSpec("B", missing, "missing"),
        )
    )

    assert rows[0]["status"] == "ok"
    assert rows[0]["non_empty"] is True
    assert rows[1]["status"] == "missing"
    assert rows[1]["size_bytes"] == 0


def test_nested_get_supports_dicts_and_list_indexes() -> None:
    payload = {"a": {"b": [{"value": 42}]}}

    assert nested_get(payload, "a", "b", "0", "value") == 42
    assert nested_get(payload, "a", "b", "1", "value") is None


def test_sum_row_count_can_filter_reviewed_labels() -> None:
    rows = [
        {"review_status": "reviewed", "row_count": 7},
        {"review_status": "skipped", "row_count": 3},
        {"review_status": "reviewed", "row_count": 11},
    ]

    assert sum_row_count(rows) == 21
    assert sum_row_count(rows, status_filter="reviewed") == 18
    assert sum_row_count(rows, status_filter="pending") is None


def test_demo_sequence_contains_grounded_rag_step() -> None:
    rows = build_demo_sequence_rows()

    assert rows[-1]["section"] == "Grounded RAG"
    assert len(rows) >= 9
