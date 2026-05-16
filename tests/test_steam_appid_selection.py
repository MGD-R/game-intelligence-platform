from src.ingestion.jobs.select_steam_appids import select_steam_appids_from_rows


def test_select_steam_appids_filters_wikidata_rows_and_deduplicates() -> None:
    rows = [
        {
            "source": "wikidata",
            "source_game_id": "Q1",
            "external_source": "steam",
            "external_id": "271590",
        },
        {
            "source": "wikidata",
            "source_game_id": "Q2",
            "external_source": "steam",
            "external_id": "271590",
        },
        {
            "source": "rawg",
            "source_game_id": "3498",
            "external_source": "steam",
            "external_id": "271590",
        },
    ]

    assert select_steam_appids_from_rows(rows, limit=10) == ["271590"]
