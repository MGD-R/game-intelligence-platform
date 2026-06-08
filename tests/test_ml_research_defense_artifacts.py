from __future__ import annotations

from decimal import Decimal

import polars as pl
import pytest

from src.entity_resolution import build_research_defense_artifacts as module


def test_quantile_interpolates_sorted_values() -> None:
    assert module.quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert module.quantile([1.0, 2.0, 3.0, 4.0], 0.25) == 1.75


def test_round_or_none_handles_missing_values() -> None:
    assert module.round_or_none(None) is None
    assert module.round_or_none(0.123456789) == 0.123457


def test_to_jsonable_converts_decimal_values() -> None:
    payload = {"score": Decimal("0.123"), "rows": [{"value": Decimal("2")}]}

    assert module.to_jsonable(payload) == {"score": 0.123, "rows": [{"value": 2.0}]}


def test_horizontal_bar_chart_svg_escapes_labels() -> None:
    svg = module.horizontal_bar_chart_svg(
        [{"scenario": "A&B", "f1": 0.75}],
        title="Ablation <F1>",
        label_key="scenario",
        value_key="f1",
        value_label="F1",
    )

    assert "<svg" in svg
    assert "A&amp;B" in svg
    assert "Ablation &lt;F1&gt;" in svg


def test_selected_feature_names_excludes_requested_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module,
        "feature_columns",
        lambda: ["name_similarity", "alias_similarity", "release_year_diff"],
    )

    selected = module.selected_feature_names({"name_similarity", "alias_similarity"})

    assert selected == ["release_year_diff"]


def test_grouped_holdout_key_prefers_left_source_identity() -> None:
    row = {"source_a": "rawg", "source_id_a": "123", "pair_id": "fallback"}

    assert module.grouped_holdout_key(row) == "rawg:123"


def test_grouped_holdout_key_falls_back_to_pair_id() -> None:
    row = {"source_a": None, "source_id_a": None, "pair_id": "pair-1"}

    assert module.grouped_holdout_key(row) == "pair-1"


def test_grouped_holdout_report_skips_when_groups_are_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "feature_columns", lambda: ["name_similarity"])
    training = pl.DataFrame(
        [
            {
                "pair_id": "p1",
                "source_a": "rawg",
                "source_id_a": "1",
                "label": 1,
                "name_similarity": 1.0,
            },
            {
                "pair_id": "p2",
                "source_a": "rawg",
                "source_id_a": "1",
                "label": 0,
                "name_similarity": 0.1,
            },
        ]
    )

    report = module.build_grouped_holdout_report(training)

    assert report["status"] == "skipped"
    assert report["group_count"] == 1
