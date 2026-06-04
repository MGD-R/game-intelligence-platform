"""FastAPI entrypoint for local development."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.demo_readonly import (
    get_catalog_stats,
    get_game,
    get_ml_stats,
    list_games,
    match_explanations,
    recommendation_explanations,
    recommendations,
    review_matches,
    similar_games,
)
from src.utils.config import enabled_sources, load_yaml_config, source_configuration_status
from src.utils.logging import configure_logging

LOGGER = configure_logging()


class RecommendationRequest(BaseModel):
    seed_game_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


def create_app() -> FastAPI:
    app = FastAPI(
        title=os.getenv("APP_NAME", "game-intelligence-platform"),
        version=os.getenv("APP_VERSION", "0.1.0"),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        app_config = load_yaml_config("app").get("app", {})
        return {
            "status": "ok",
            "service": "api",
            "app": os.getenv("APP_NAME", app_config.get("name", "game-intelligence-platform")),
            "env": os.getenv("APP_ENV", app_config.get("environment", "local")),
        }

    @app.get("/health/db")
    def health_db() -> JSONResponse:
        ok, detail = check_database_connection()
        payload = {"status": "ok" if ok else "degraded", "service": "database", "detail": detail}
        status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=status_code, content=payload)

    @app.get("/health/sources")
    def health_sources() -> dict[str, Any]:
        sources = enabled_sources()
        config_status = source_configuration_status()
        return {
            "status": "ok",
            "enabled": sources["enabled"],
            "disabled": sources["disabled"],
            "configured": config_status["configured"],
            "missing_configuration": config_status["missing"],
        }

    @app.get("/version")
    def version() -> dict[str, str]:
        app_config = load_yaml_config("app").get("app", {})
        return {
            "name": os.getenv("APP_NAME", app_config.get("name", "game-intelligence-platform")),
            "version": os.getenv("APP_VERSION", app_config.get("version", "0.1.0")),
            "environment": os.getenv("APP_ENV", app_config.get("environment", "local")),
        }

    @app.get("/games")
    def list_catalog_games(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        search: str | None = Query(default=None),
    ) -> dict[str, Any]:
        return list_games(limit=limit, offset=offset, search=search)

    @app.get("/games/{game_id}")
    def get_catalog_game(game_id: str) -> JSONResponse:
        game = get_game(game_id)
        if game is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "not_found", "detail": f"Game id={game_id} was not found."},
            )
        return JSONResponse(content=game)

    @app.get("/games/{game_id}/similar")
    def get_similar_games(
        game_id: str,
        limit: int = Query(default=10, ge=1, le=50),
    ) -> dict[str, Any]:
        return similar_games(game_id, limit=limit)

    @app.post("/recommend")
    def recommend_games(request: RecommendationRequest) -> dict[str, Any]:
        return recommendations(
            seed_game_ids=request.seed_game_ids,
            limit=request.limit,
        )

    @app.get("/matches/review")
    def list_review_matches(
        limit: int = Query(default=20, ge=1, le=100),
        review_status: str = Query(default="pending"),
    ) -> dict[str, Any]:
        return review_matches(limit=limit, status_filter=review_status)

    @app.get("/stats/catalog")
    def catalog_stats() -> dict[str, Any]:
        return get_catalog_stats()

    @app.get("/stats/ml")
    def ml_stats() -> dict[str, Any]:
        return get_ml_stats()

    @app.get("/explain/recommendation")
    def explain_recommendation(
        seed_game: str | None = Query(default=None),
        recommended_game: str | None = Query(default=None),
        limit: int = Query(default=5, ge=1, le=25),
    ) -> dict[str, Any]:
        return recommendation_explanations(
            seed_game=seed_game,
            recommended_game=recommended_game,
            limit=limit,
        )

    @app.get("/explain/match")
    def explain_match(
        pair_id: str | None = Query(default=None),
        limit: int = Query(default=5, ge=1, le=25),
    ) -> dict[str, Any]:
        return match_explanations(pair_id=pair_id, limit=limit)

    return app


def check_database_connection() -> tuple[bool, str]:
    dsn = os.getenv("DATABASE_URL", "postgresql://gip:change-me@postgres:5432/gip")
    timeout = int(os.getenv("DATABASE_CONNECT_TIMEOUT", "3"))

    try:
        import psycopg
    except ImportError:
        return False, "psycopg is not installed"

    try:
        with psycopg.connect(dsn, connect_timeout=timeout) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True, "database reachable"
    except Exception as exc:  # pragma: no cover - runtime integration path
        LOGGER.warning("Database health check failed: %s", exc)
        return False, f"{exc.__class__.__name__}: connection failed"


def todo_response(message: str, extra: dict[str, Any] | None = None) -> JSONResponse:
    payload: dict[str, Any] = {"status": "todo", "detail": message}
    if extra:
        payload.update(extra)
    return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=payload)


app = create_app()
