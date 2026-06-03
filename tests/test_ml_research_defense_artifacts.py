from __future__ import annotations

import pytest

from src.entity_resolution import build_research_defense_artifacts as module


def test_quantile_interpolates_sorted_values() -> None:
    assert module.quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert module.quantile([1.0, 2.0, 3.0, 4.0], 0.25) == 1.75


def test_round_or_none_handles_missing_values() -> None:
    assert module.round_or_none(None) is None
    assert module.round_or_none(0.123456789) == 0.123457


def test_selected_feature_names_excludes_requested_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        module,
        "feature_columns",
        lambda: ["name_similarity", "alias_similarity", "release_year_diff"],
    )

    selected = module.selected_feature_names({"name_similarity", "alias_similarity"})

    assert selected == ["release_year_diff"]
