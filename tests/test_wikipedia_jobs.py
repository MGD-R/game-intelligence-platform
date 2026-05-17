import types

import pytest

from src.ingestion.base_client import HTTPStatusError
from src.ingestion.jobs import load_wikipedia_pages as wikipedia_pages_job
from src.ingestion.jobs.load_wikipedia_pages import (
    default_page_limit,
    load_page_with_backoff,
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
