from __future__ import annotations

import pytest

import src.api.main as api_main
from src.api.demo_readonly import db_catalog_stats
from src.api.main import app


class _BrokenRepository:
    def connection(self):
        raise RuntimeError("database unavailable")


def test_write_api_requires_configured_key_outside_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("GIP_WRITE_API_KEY", raising=False)

    response = api_main.validate_write_api_key(None)

    assert response is not None
    assert response.status_code == 401
    assert response.body


def test_write_api_accepts_matching_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GIP_WRITE_API_KEY", "expected-test-key")

    assert api_main.validate_write_api_key("expected-test-key") is None


def test_write_api_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GIP_WRITE_API_KEY", "expected-test-key")

    response = api_main.validate_write_api_key("wrong-key")

    assert response is not None
    assert response.status_code == 401


def test_write_api_allows_empty_key_only_in_local_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("GIP_WRITE_API_KEY", raising=False)

    assert api_main.validate_write_api_key(None) is None


def test_strict_db_mode_raises_instead_of_artifact_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIP_STRICT_DB_MODE", "true")

    with pytest.raises(RuntimeError, match="database unavailable"):
        db_catalog_stats(repository=_BrokenRepository())  # type: ignore[arg-type]


def test_default_db_mode_keeps_artifact_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIP_STRICT_DB_MODE", raising=False)

    assert db_catalog_stats(repository=_BrokenRepository()) is None  # type: ignore[arg-type]


def test_openapi_keeps_manual_review_patch_documented() -> None:
    paths = app.openapi()["paths"]

    assert "patch" in paths["/matches/review/{pair_id}"]
