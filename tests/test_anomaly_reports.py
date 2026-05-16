from src.entity_resolution.corpus import SourceGameRecord
from src.preprocessing.anomaly_reports import build_anomaly_rows


def test_anomaly_rows_detect_duplicates_and_suspicious_titles() -> None:
    records = {
        ("rawg", "1"): SourceGameRecord(
            source="rawg",
            source_game_id="1",
            name="Game One Demo",
            name_normalized="game one demo",
            release_year=2035,
        ),
        ("rawg", "2"): SourceGameRecord(
            source="rawg",
            source_game_id="2",
            name="Game One Demo",
            name_normalized="game one demo",
            release_year=2035,
        ),
    }
    anomalies = build_anomaly_rows(records, [], [], [])
    anomaly_types = {row["anomaly_type"] for row in anomalies}
    assert "duplicate_normalized_names" in anomaly_types
    assert "possible_dlc_or_edition_by_title" in anomaly_types
    assert "suspicious_release_year" in anomaly_types
