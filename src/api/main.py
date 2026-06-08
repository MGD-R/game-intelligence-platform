"""FastAPI entrypoint for local development."""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.demo_readonly import (
    ManualReviewDatabaseError,
    ManualReviewNotFoundError,
    get_catalog_stats,
    get_game,
    get_graph_stats,
    get_ml_stats,
    list_games,
    match_explanations,
    recommendation_explanations,
    recommendations,
    review_matches,
    similar_games,
    update_manual_review_record,
)
from src.demo.check_readiness import evaluate_demo_readiness
from src.utils.config import enabled_sources, load_yaml_config, source_configuration_status
from src.utils.logging import configure_logging

LOGGER = configure_logging()


class RecommendationRequest(BaseModel):
    seed_game_ids: list[str] = Field(default_factory=list)
    liked_games: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)
    algorithm: Literal["content_jaccard_v1", "hybrid_content_rating_v1"] = "content_jaccard_v1"


class ManualReviewUpdateRequest(BaseModel):
    review_label: Literal["same_game", "different_game", "uncertain"] | None = None
    review_status: Literal["pending", "reviewed", "skipped", "unsure"] = "reviewed"
    review_notes: str | None = Field(default=None, max_length=2000)
    reviewer: str | None = Field(default=None, max_length=120)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


def review_label_to_bool(label: str | None) -> bool | None:
    if label == "same_game":
        return True
    if label == "different_game":
        return False
    return None


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details or {},
            "warnings": warnings or [],
        },
    )


def validate_write_api_key(header_value: str | None) -> JSONResponse | None:
    expected_key = os.getenv("GIP_WRITE_API_KEY", "").strip()
    app_env = os.getenv("APP_ENV", "local").strip().lower()
    demo_mode = os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    if not expected_key:
        if app_env in {"local", "dev", "development", "demo", "test"} or demo_mode:
            return None
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="write_api_key_not_configured",
            message=(
                "GIP_WRITE_API_KEY must be configured before write endpoints can be used "
                "outside local/demo environments."
            ),
        )
    if header_value == expected_key:
        return None
    return error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="write_api_key_required",
        message="A valid X-GIP-Write-API-Key header is required for write endpoints.",
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=os.getenv("APP_NAME", "game-intelligence-platform"),
        version=os.getenv("APP_VERSION", "0.1.0"),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    cors_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["*"],
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
        algorithm: Literal["content_jaccard_v1", "hybrid_content_rating_v1"] = Query(
            default="content_jaccard_v1"
        ),
    ) -> dict[str, Any]:
        return similar_games(game_id, limit=limit, algorithm=algorithm)

    @app.post("/recommend")
    def recommend_games(request: RecommendationRequest) -> dict[str, Any]:
        return recommendations(
            seed_game_ids=request.seed_game_ids,
            liked_games=request.liked_games,
            limit=request.limit,
            algorithm=request.algorithm,
        )

    @app.get("/matches/review")
    def list_review_matches(
        limit: int = Query(default=20, ge=1, le=100),
        review_status: str = Query(default="pending"),
        decision: str = Query(default="all"),
    ) -> dict[str, Any]:
        return review_matches(limit=limit, status_filter=review_status, decision_filter=decision)

    @app.patch("/matches/review/{pair_id}")
    def update_review_match(
        pair_id: str,
        request: ManualReviewUpdateRequest,
        write_api_key: str | None = Header(default=None, alias="X-GIP-Write-API-Key"),
    ) -> JSONResponse:
        auth_error = validate_write_api_key(write_api_key)
        if auth_error:
            return auth_error
        label_value = review_label_to_bool(request.review_label)
        if request.review_status == "reviewed" and label_value is None:
            return error_response(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="review_label_required",
                message="review_status=reviewed requires review_label same_game or different_game.",
            )
        try:
            payload = update_manual_review_record(
                pair_id=pair_id,
                review_label=label_value,
                review_status=request.review_status,
                review_notes=request.review_notes,
                reviewer=request.reviewer,
                confidence=request.confidence,
            )
        except ManualReviewNotFoundError:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="manual_review_not_found",
                message=f"Manual review row for pair_id={pair_id} was not found.",
                details={"pair_id": pair_id},
            )
        except ManualReviewDatabaseError as exc:
            return error_response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="manual_review_database_unavailable",
                message="Manual review database storage is unavailable.",
                details={"error": str(exc)},
                warnings=["Artifact fallback is read-only and cannot be updated."],
            )
        return JSONResponse(content=payload)

    @app.get("/stats/catalog")
    def catalog_stats() -> dict[str, Any]:
        return get_catalog_stats()

    @app.get("/stats/ml")
    def ml_stats() -> dict[str, Any]:
        return get_ml_stats()

    @app.get("/stats/readiness")
    def demo_readiness() -> dict[str, Any]:
        return evaluate_demo_readiness()

    @app.get("/stats/graph")
    def graph_stats() -> dict[str, Any]:
        return get_graph_stats()

    @app.get("/explain/recommendation")
    def explain_recommendation(
        game_id: str | None = Query(default=None),
        recommended_game_id: str | None = Query(default=None),
        seed_game: str | None = Query(default=None),
        recommended_game: str | None = Query(default=None),
        limit: int = Query(default=5, ge=1, le=25),
        mode: Literal["template", "llm"] = Query(default="template"),
    ) -> dict[str, Any]:
        return recommendation_explanations(
            game_id=game_id,
            recommended_game_id=recommended_game_id,
            seed_game=seed_game,
            recommended_game=recommended_game,
            limit=limit,
            mode=mode,
        )

    @app.get("/explain/match")
    def explain_match(
        pair_id: str | None = Query(default=None),
        limit: int = Query(default=5, ge=1, le=25),
        mode: Literal["template", "llm"] = Query(default="template"),
    ) -> dict[str, Any]:
        return match_explanations(pair_id=pair_id, limit=limit, mode=mode)

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


app = create_app()
