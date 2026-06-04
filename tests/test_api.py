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
    assert "RAWG_API_KEY" not in str(body)


def test_version_returns_app_metadata() -> None:
    response = client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "game-intelligence-platform"
    assert body["environment"] == "local"


def test_catalog_stats_returns_demo_snapshot() -> None:
    response = client.get("/stats/catalog")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert "source_games" in body
    assert "canonical_games" in body
    assert "recommendations_count" in body
    assert isinstance(body["source_games_by_source"], dict)


def test_ml_stats_returns_demo_snapshot() -> None:
    response = client.get("/stats/ml")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert "candidate_pairs" in body
    assert "labeled_pairs" in body
    assert "model_decisions" in body
    assert "entity_resolution_f1" in body


def test_games_returns_catalog_page() -> None:
    response = client.get("/games?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 3
    assert body["offset"] == 0
    assert "total" in body
    assert isinstance(body["items"], list)
    if body["items"]:
        item = body["items"][0]
        assert "canonical_game_id" in item
        assert "name" in item
        assert "source_count" in item


def test_games_search_returns_catalog_page() -> None:
    response = client.get("/games?limit=5&search=doom")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert isinstance(body["items"], list)


def test_game_detail_returns_first_catalog_item_when_available() -> None:
    list_response = client.get("/games?limit=1")
    first_items = list_response.json()["items"]
    if not first_items:
        return

    game_id = first_items[0]["canonical_game_id"]
    response = client.get(f"/games/{game_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["canonical_game_id"] == game_id
    assert "sources" in body
    assert "ratings" in body


def test_game_detail_returns_404_for_unknown_id() -> None:
    response = client.get("/games/not-a-real-game-id")

    assert response.status_code == 404


def test_similar_games_returns_recommendation_page() -> None:
    list_response = client.get("/games?limit=1")
    first_items = list_response.json()["items"]
    if not first_items:
        return

    game_id = first_items[0]["canonical_game_id"]
    response = client.get(f"/games/{game_id}/similar?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert body["algorithm"] == "content_jaccard_v1"
    assert isinstance(body["items"], list)


def test_recommend_returns_seeded_recommendations() -> None:
    list_response = client.get("/games?limit=1")
    first_items = list_response.json()["items"]
    seed_game_ids = [first_items[0]["canonical_game_id"]] if first_items else []

    response = client.post(
        "/recommend",
        json={"seed_game_ids": seed_game_ids, "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert body["algorithm"] == "content_jaccard_v1"
    assert isinstance(body["items"], list)


def test_recommend_accepts_liked_game_names() -> None:
    response = client.post(
        "/recommend",
        json={"liked_games": ["DOOM"], "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert body["algorithm"] == "content_jaccard_v1"
    assert body["liked_games"] == ["DOOM"]
    assert "resolved_liked_games" in body
    assert isinstance(body["items"], list)


def test_review_matches_returns_readonly_queue() -> None:
    response = client.get("/matches/review?limit=2&review_status=all")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert body["status_filter"] == "all"
    assert isinstance(body["items"], list)


def test_review_matches_accepts_decision_filter() -> None:
    response = client.get("/matches/review?limit=2&review_status=all&decision=no_merge")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["decision_filter"] == "no_merge"
    assert isinstance(body["items"], list)


def test_recommendation_explanation_returns_grounded_examples() -> None:
    response = client.get("/explain/recommendation?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert isinstance(body["items"], list)
    if body["items"]:
        item = body["items"][0]
        assert "explanation_ru" in item
        assert "facts_used" in item
        assert "sources_used" in item


def test_recommendation_explanation_accepts_game_ids() -> None:
    response = client.get(
        "/explain/recommendation?game_id=015078c4-059b-5a5f-ab7e-e8a43d3912eb&limit=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] in {"database", "artifact"}
    assert body["limit"] == 2
    assert isinstance(body["items"], list)
    if body["items"]:
        item = body["items"][0]
        assert "explanation_ru" in item
        assert "facts_used" in item
        assert "sources_used" in item


def test_match_explanation_returns_grounded_examples() -> None:
    response = client.get("/explain/match?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert body["data_origin"] == "artifact"
    assert body["limit"] == 2
    assert isinstance(body["items"], list)
    if body["items"]:
        item = body["items"][0]
        assert "explanation_ru" in item
        assert "facts_used" in item
        assert "sources_used" in item
