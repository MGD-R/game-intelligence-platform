from __future__ import annotations

from pathlib import Path

import pytest

from src.preprocessing.restore_from_files import main as restore_from_files_main


def test_restore_dry_run_does_not_call_rebuild_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_root = tmp_path / "pack"
    pack_root.mkdir()

    for target in (
        "import_data_pack_main",
        "build_staging_main",
        "steam_to_staging_main",
        "wikipedia_to_staging_main",
        "igdb_to_staging_main",
        "match_external_ids_main",
        "candidate_pairs_main",
        "feature_base_main",
        "data_quality_main",
        "ml_ready_main",
        "export_data_pack_main",
    ):
        monkeypatch.setattr(
            "src.preprocessing.restore_from_files." + target,
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        )

    assert restore_from_files_main(["--input", str(pack_root), "--dry-run"]) == 0


def test_restore_missing_pack_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Data pack does not exist"):
        restore_from_files_main(["--input", str(tmp_path / "missing"), "--dry-run"])
