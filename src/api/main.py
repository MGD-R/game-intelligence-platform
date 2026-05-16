"""FastAPI entrypoint for local development."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.utils.config import enabled_sources, load_yaml_config
from src.utils.logging import configure_logging

LOGGER = configure_logging()


class RecommendationRequest(BaseModel):
    seed_game_ids: list[int] = Field(default_factory=list)
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
        return {"status": "ok", "service": "api"}

    @app.get("/health/db")
    def health_db() -> JSONResponse:
        ok, detail = check_database_connection()
        payload = {"status": "ok" if ok else "degraded", "service": "database", "detail": detail}
        status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=status_code, content=payload)

    @app.get("/health/sources")
    def health_sources() -> dict[str, Any]:
        sources = enabled_sources()
        return {
            "status": "ok",
            "enabled": sources["enabled"],
            "disabled": sources["disabled"],
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
    def list_games() -> JSONResponse:
        return todo_response("Game catalog endpoint is scaffolded for a later feature branch.")

    @app.get("/games/{game_id}")
    def get_game(game_id: int) -> JSONResponse:
        return todo_response(
            f"Game detail for id={game_id} is scaffolded for a later feature branch."
        )

    @app.get("/games/{game_id}/similar")
    def get_similar_games(game_id: int) -> JSONResponse:
        return todo_response(
            f"Similarity endpoint for game id={game_id} is scaffolded for a later feature branch."
        )

    @app.post("/recommend")
    def recommend_games(request: RecommendationRequest) -> JSONResponse:
        return todo_response(
            "Recommendation endpoint is scaffolded for a later feature branch.",
            extra={"request_preview": request.model_dump()},
        )

    @app.get("/matches/review")
    def review_matches() -> JSONResponse:
        return todo_response(
            "Entity resolution review endpoint is scaffolded for a later feature branch."
        )

    @app.get("/explain/recommendation")
    def explain_recommendation() -> JSONResponse:
        return todo_response(
            "Recommendation explanation endpoint is scaffolded for a later feature branch."
        )

    @app.get("/explain/match")
    def explain_match() -> JSONResponse:
        return todo_response("Match explanation endpoint is scaffolded for a later feature branch.")

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
