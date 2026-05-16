from src.ingestion.jobs.select_wikipedia_pages import select_pages_from_url_rows


def test_select_wikipedia_pages_preserves_qid_language_and_title() -> None:
    rows = [
        {
            "source": "wikidata",
            "source_game_id": "Q12345",
            "url_type": "ruwiki",
            "url": "https://ru.wikipedia.org/wiki/%D0%9F%D1%80%D0%B8%D0%BC%D0%B5%D1%80_%D0%B8%D0%B3%D1%80%D1%8B",
        },
        {
            "source": "wikidata",
            "source_game_id": "Q12345",
            "url_type": "enwiki",
            "url": "https://en.wikipedia.org/wiki/Sample_Game",
        },
    ]

    pages = select_pages_from_url_rows(rows, languages={"ru", "en"}, limit=10)

    assert pages[0]["qid"] == "Q12345"
    assert pages[0]["language"] == "ru"
    assert pages[0]["title"] == "Пример игры"
    assert pages[1]["language"] == "en"
