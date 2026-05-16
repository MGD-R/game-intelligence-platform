from __future__ import annotations

import json
from pathlib import Path

from src.preprocessing.wikipedia_to_staging import transform_wikipedia_payloads

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "wikipedia"


def read_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_wikipedia_summary_maps_to_descriptions_urls_and_qid_links() -> None:
    payloads = [
        (
            {
                "selection": {
                    "qid": "Q12345",
                    "language": "ru",
                    "title": "Пример игры",
                    "url": "https://ru.wikipedia.org/wiki/%D0%9F%D1%80%D0%B8%D0%BC%D0%B5%D1%80_%D0%B8%D0%B3%D1%80%D1%8B",
                    "url_type": "ruwiki",
                },
                "response": read_fixture("summary_ru_example.json"),
            },
            "2026-05-17T10:00:00+00:00",
        )
    ]

    bundle = transform_wikipedia_payloads(payloads)

    assert len(bundle.source_game_descriptions) == 1
    assert bundle.source_game_descriptions[0]["language"] == "ru"
    assert bundle.source_game_urls[0]["url_type"] == "page"
    assert bundle.source_game_external_ids[0]["external_source"] == "wikidata"
    assert bundle.source_game_external_ids[0]["external_id"] == "Q12345"
