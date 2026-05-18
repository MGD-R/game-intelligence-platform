import types

import pytest

from src.ingestion.base_client import HTTPStatusError
from src.ingestion.jobs import load_wikipedia_pages as wikipedia_pages_job
from src.ingestion.jobs.load_wikipedia_pages import (
    default_page_limit,
    load_page_with_backoff,
    load_selected_pages,
    select_missing_pages_from_rows,
)
from src.ingestion.jobs.load_wikipedia_pages import (
    main as load_wikipedia_pages_main,
)
from src.ingestion.jobs.select_wikipedia_pages import (
    main as select_wikipedia_pages_main,
)


def test_wikipedia_jobs_support_dry_run() -> None:
    assert select_wikipedia_pages_main(["--dry-run", "--limit", "10"]) == 0
    assert load_wikipedia_pages_main(["--dry-run", "--limit", "1"]) == 0


def test_default_wikipedia_page_limit_is_demo_safe(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WIKIPEDIA_PAGE_LIMIT", "100")
    assert default_page_limit() == 100


def test_load_page_with_backoff_retries_http_429(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}
    slept: list[int] = []

    class _Client:
        def get_page_summary(self, language: str, title: str, **_: object):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise HTTPStatusError(
                    source="wikipedia",
                    endpoint=f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{title}",
                    status_code=429,
                    request_hash=f"hash-{attempts['count']}",
                    from_cache=False,
                )
            return types.SimpleNamespace(language=language, title=title)

    monkeypatch.setattr(wikipedia_pages_job.time, "sleep", slept.append)

    response = load_page_with_backoff(
        _Client(),
        {"language": "ru", "title": "Example"},
        force_refresh=False,
        from_cache_only=False,
        retry_limit=5,
        retry_backoff_seconds=42,
    )

    assert response.language == "ru"
    assert response.title == "Example"
    assert attempts["count"] == 3
    assert slept == [42, 42]


def test_load_selected_pages_skips_http_404(capsys) -> None:
    inserted: list[str] = []

    class _Repository:
        def insert_raw_record(self, **kwargs: object) -> None:
            inserted.append(str(kwargs["source_record_id"]))

    class _Client:
        def __init__(self) -> None:
            self.repository = _Repository()

        def get_page_summary(self, language: str, title: str, **_: object):
            if title == "Missing":
                raise HTTPStatusError(
                    source="wikipedia",
                    endpoint=f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{title}",
                    status_code=404,
                    request_hash="missing-hash",
                    from_cache=False,
                )
            return types.SimpleNamespace(
                endpoint=f"/page/summary/{title}",
                request_hash=f"hash-{title}",
                payload={"title": title},
                response_hash=f"response-{title}",
                cache_path=None,
                from_cache=False,
                http_status=200,
                error_message=None,
            )

    metrics = load_selected_pages(
        _Client(),
        [
            {"language": "ru", "title": "Missing", "qid": "Q1", "url": "", "url_type": "ruwiki"},
            {"language": "ru", "title": "Loaded", "qid": "Q2", "url": "", "url_type": "ruwiki"},
        ],
        force_refresh=False,
        from_cache_only=False,
        retry_limit=1,
        retry_backoff_seconds=1,
    )

    assert metrics == {"loaded_pages": 1, "skipped_pages": 1}
    assert inserted == ["ru:Loaded"]
    assert "skipped_page" in capsys.readouterr().out


def test_select_missing_pages_prefers_ru_and_skips_covered_games() -> None:
    pages = select_missing_pages_from_rows(
        [
            {
                "source": "wikidata",
                "source_game_id": "Q1",
                "url_type": "enwiki",
                "url": "https://en.wikipedia.org/wiki/Alpha",
            },
            {
                "source": "wikidata",
                "source_game_id": "Q1",
                "url_type": "ruwiki",
                "url": "https://ru.wikipedia.org/wiki/Alpha_ru",
            },
            {
                "source": "wikidata",
                "source_game_id": "Q2",
                "url_type": "enwiki",
                "url": "https://en.wikipedia.org/wiki/Beta",
            },
            {
                "source": "wikidata",
                "source_game_id": "Q3",
                "url_type": "ruwiki",
                "url": "https://ru.wikipedia.org/wiki/Gamma",
            },
        ],
        [
            {
                "source": "wikipedia",
                "source_game_id": "Q2",
                "description_type": "summary",
                "description_text": "already loaded",
            }
        ],
    )

    assert pages == [
        {
            "source_game_id": "Q1",
            "qid": "Q1",
            "language": "ru",
            "title": "Alpha ru",
            "url": "https://ru.wikipedia.org/wiki/Alpha_ru",
            "url_type": "ruwiki",
        },
        {
            "source_game_id": "Q3",
            "qid": "Q3",
            "language": "ru",
            "title": "Gamma",
            "url": "https://ru.wikipedia.org/wiki/Gamma",
            "url_type": "ruwiki",
        },
    ]
