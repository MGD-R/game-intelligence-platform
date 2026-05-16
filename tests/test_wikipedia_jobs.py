from src.ingestion.jobs.load_wikipedia_pages import default_page_limit
from src.ingestion.jobs.load_wikipedia_pages import main as load_wikipedia_pages_main
from src.ingestion.jobs.select_wikipedia_pages import main as select_wikipedia_pages_main


def test_wikipedia_jobs_support_dry_run() -> None:
    assert select_wikipedia_pages_main(["--dry-run", "--limit", "10"]) == 0
    assert load_wikipedia_pages_main(["--dry-run", "--limit", "1"]) == 0


def test_default_wikipedia_page_limit_is_demo_safe(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WIKIPEDIA_PAGE_LIMIT", "100")
    assert default_page_limit() == 100
