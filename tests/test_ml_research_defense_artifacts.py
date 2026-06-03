from __future__ import annotations

from decimal import Decimal

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
