from __future__ import annotations

from src.entity_resolution.seed_manual_review_queue import STRATEGIES, strategy_names
from src.entity_resolution.setup_manual_review import manual_review_sql_path


def test_manual_review_sql_defines_label_table_and_views() -> None:
    sql_text = manual_review_sql_path().read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS ml.entity_resolution_manual_reviews" in sql_text
    assert "review_label BOOLEAN" in sql_text
    assert "CREATE OR REPLACE VIEW ml.v_igdb_manual_review_queue" in sql_text


def test_manual_review_seed_strategies_cover_igdb_and_controls() -> None:
    names = strategy_names()

    assert "igdb_suspicious_auto_merge" in names
    assert "igdb_likely_positive" in names
    assert "external_id_positive_control" in names
    assert "same_name_year_negative_control" in names
    assert all(STRATEGIES[name].where_sql.strip() for name in names)
