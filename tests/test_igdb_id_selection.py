from src.ingestion.jobs.select_igdb_ids import select_igdb_ids_from_rows


def test_select_igdb_ids_filters_wikidata_rows() -> None:
    rows = [
        {"source": "wikidata", "external_source": "igdb", "external_id": "1020"},
        {"source": "wikidata", "external_source": "steam", "external_id": "271590"},
        {"source": "wikidata", "external_source": "igdb", "external_id": "1020"},
    ]
    assert select_igdb_ids_from_rows(rows) == ["1020"]
