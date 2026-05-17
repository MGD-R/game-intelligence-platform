from __future__ import annotations

import pytest

from src.ingestion.jobs.load_igdb_games import default_details_limit
from src.ingestion.jobs.load_igdb_games import main as load_igdb_games_main
from src.ingestion.jobs.load_igdb_reference import main as load_igdb_reference_main
from src.ingestion.jobs.select_igdb_ids import main as select_igdb_ids_main
from src.preprocessing.igdb_to_staging import main as igdb_to_staging_main


def test_igdb_jobs_support_dry_run() -> None:
    assert select_igdb_ids_main(["--dry-run", "--limit", "10"]) == 0
    assert load_igdb_games_main(["--dry-run", "--limit", "1"]) == 0
    assert load_igdb_reference_main(["--dry-run"]) == 0
    assert igdb_to_staging_main(["--dry-run"]) == 0


def test_default_igdb_details_limit_is_demo_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGDB_DETAILS_LIMIT", "50")
    assert default_details_limit() == 50
