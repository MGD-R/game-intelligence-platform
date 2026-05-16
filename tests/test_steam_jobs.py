from __future__ import annotations

import pytest

from src.ingestion.jobs.load_steam_details import default_details_limit
from src.ingestion.jobs.load_steam_details import main as load_steam_details_main
from src.ingestion.jobs.select_steam_appids import main as select_steam_appids_main


def test_steam_jobs_support_dry_run() -> None:
    assert select_steam_appids_main(["--dry-run", "--limit", "10"]) == 0
    assert load_steam_details_main(["--dry-run", "--limit", "1"]) == 0


def test_default_steam_details_limit_is_demo_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STEAM_DETAILS_LIMIT", "50")
    assert default_details_limit() == 50
