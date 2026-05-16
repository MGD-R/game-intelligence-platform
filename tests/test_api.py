from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_sources_reports_mvp_sources() -> None:
    response = client.get("/health/sources")

    assert response.status_code == 200
    body = response.json()
    assert "rawg" in body["enabled"]
    assert "wikidata" in body["enabled"]
