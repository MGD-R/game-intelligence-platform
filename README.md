# Game Intelligence Platform

Game Intelligence Platform is an educational end-to-end data and ML product for building a canonical video game catalog from external sources and exposing it through a FastAPI service.

## MVP Scope

- Sources: RAWG and Wikidata.
- Storage: PostgreSQL with `raw`, `stg`, `ml`, `dm`, `meta` schemas.
- API: FastAPI health endpoints and placeholder catalog/recommendation routes.
- Runtime: Docker Compose with `postgres`, `app`, and `worker`.
- Pipeline: Makefile entrypoints with safe TODO placeholders for later feature branches.

Optional profiles add MLflow + MinIO, JupyterLab, and pgAdmin without making them mandatory for the MVP.

## Repository Layout

```text
docker/     container definitions and PostgreSQL init scripts
configs/    YAML configuration files
src/        application, ingestion, preprocessing, ML, and RAG placeholders
tests/      smoke tests
docs/       project and deployment notes
data/       local data directories kept out of Git
sql/        future SQL transformations by layer
```

## Quick Start

```bash
cp .env.example .env
make build
make up
curl http://localhost:8000/health
```

## Main Commands

```bash
make test
make lint
make check-sources
make rawg
make wikidata
make staging
make er
make recommendations
make rag
```

## API Endpoints

- `GET /health`
- `GET /health/db`
- `GET /health/sources`
- `GET /version`
- `GET /games`
- `GET /games/{game_id}`
- `GET /games/{game_id}/similar`
- `POST /recommend`
- `GET /matches/review`
- `GET /explain/recommendation`
- `GET /explain/match`

## Docker Profiles

- `make up` starts the MVP stack.
- `make up-mlops` adds `mlflow` and `minio`.
- `make up-notebook` adds `notebook`.
- `make up-admin` adds `pgadmin`.

## Security Notes

- Keep `.env`, `.codex/`, `.omx/`, data directories, and generated artifacts out of Git.
- Replace all placeholder credentials before using external APIs.
- Health endpoints return status information only and do not expose secrets.

## MVP vs Advanced

This scaffold does not implement ingestion pipelines, entity resolution training, recommendation ranking, or RAG generation yet. Those areas are intentionally represented by import-safe placeholders and CLI entrypoints for later branches.
