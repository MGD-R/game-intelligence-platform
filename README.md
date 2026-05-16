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

Roadmap for the first data-stage work: [docs/data_stage_roadmap.md](docs/data_stage_roadmap.md).
Docker/PostgreSQL bootstrap commands: [docs/docker_db_bootstrap.md](docs/docker_db_bootstrap.md).
Database storage design: [docs/database_schema.md](docs/database_schema.md).
Ingestion framework notes: [docs/ingestion_framework.md](docs/ingestion_framework.md).
RAWG ingestion flow: [docs/rawg_ingestion.md](docs/rawg_ingestion.md).
Wikidata identity ingestion: [docs/wikidata_ingestion.md](docs/wikidata_ingestion.md).
External ID matching and candidate corpus: [docs/external_id_matching.md](docs/external_id_matching.md).
Staging normalization and data-quality layer: [docs/staging_data_quality.md](docs/staging_data_quality.md).
Steam targeted enrichment: [docs/steam_enrichment.md](docs/steam_enrichment.md).
Wikipedia summaries enrichment: [docs/wikipedia_summaries.md](docs/wikipedia_summaries.md).
ML-ready datasets and final data-stage build: [docs/ml_ready_datasets.md](docs/ml_ready_datasets.md).
Entity Resolution baseline: [docs/entity_resolution_baseline.md](docs/entity_resolution_baseline.md).

## Quick Start

```bash
cp .env.example .env
cp .env.secrets.example .env.secrets
make build
make up
make db-check
curl http://localhost:8000/health
```

For live reload development use:

```bash
make build-dev
make up-dev
```

## Main Commands

```bash
make test
make lint
make check-sources
make rawg-check
make rawg-reference
make rawg-index
make rawg-staging
make wikidata-check
make wikidata-identity
make wikidata-staging
make steam-check
make steam-appids
make steam-staging
make wikipedia-check
make wikipedia-pages
make wikipedia-staging
make match-external-ids
make candidate-pairs
make feature-base
make source-coverage
make export-ml-base
make validate-staging
make dq
make anomalies
make export-analysis
make validate-ml-data
make manual-review-seed
make export-ml-ready
make dataset-manifest
make ml-ready-data
make er-dataset
make er-rule-baseline
make er-train
make er-predict
make er-evaluate
make er-review-queue
make er-baseline
make quota-status
make rawg
make wikidata
make staging
make er
make recommendations
make rag
```

These commands run inside the `worker-dev` container and do not require local Python tooling on the host.
`make rawg` runs the safe demo pipeline (`rawg-reference`, `rawg-index`, `rawg-staging`) and does not request details by default.
`make wikidata` runs the safe demo pipeline (`wikidata-identity`, `wikidata-staging`) and does not request EntityData by default.
`make steam` runs the targeted enrichment pipeline (`steam-appids`, `steam-details`, `steam-staging`) and does not scan the full Steam catalog.
`make wikipedia` runs the targeted summaries pipeline (`wikipedia-pages`, `wikipedia-load`, `wikipedia-staging`) and does not use broad search or opensearch by default.
`make entity-data-base` prepares deterministic matches, candidate pairs, feature rows, reports, and parquet exports without calling external APIs.
`make data-quality` validates staging prerequisites, rebuilds normalized staging rows, writes DQ and anomaly reports, and exports analysis-ready parquet snapshots.
`make ml-ready-data` finalizes the local data stage: validation, candidate/feature refresh, DQ artifacts, manual review seed, parquet exports, and dataset manifest, again without external API calls.
`make er-baseline` builds the weak-label training dataset, runs rule and Logistic Regression baselines, predicts matches, evaluates metrics, and prepares a manual review queue without external APIs.

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

- `make up` starts the runtime-like MVP stack without source bind mounts or reload.
- `make up-dev` starts the local development stack with bind mounts and autoreload.
- `make up-mlops` adds `mlflow` and `minio`.
- `make up-notebook` adds `notebook`.
- `make up-admin` adds `pgadmin`.

## Security Notes

- Keep `.env`, `.codex/`, `.omx/`, data directories, and generated artifacts out of Git.
- Store real external API tokens in `.env.secrets`; keep `.env` for non-secret local defaults.
- Commit only examples such as `.env.example` and `.env.secrets.example`.
- Replace all placeholder credentials before using external APIs.
- Health endpoints return status information only and do not expose secrets.

## MVP vs Advanced

This scaffold does not implement ingestion pipelines, entity resolution training, recommendation ranking, or RAG generation yet. Those areas are intentionally represented by import-safe placeholders and CLI entrypoints for later branches.
