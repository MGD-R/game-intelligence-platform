# Game Intelligence Platform

Game Intelligence Platform is an educational end-to-end data and ML product for building a canonical video game catalog from external sources and exposing it through a FastAPI service.

## MVP Scope

- Sources: RAWG, Wikidata, Steam, Wikipedia, and IGDB targeted/search enrichment.
- Storage: PostgreSQL with `raw`, `stg`, `ml`, `dm`, `meta` schemas.
- API: FastAPI health endpoints plus read-only catalog, recommendation, review,
  explanation, and stats demo routes.
- Runtime: Docker Compose with `postgres`, `app`, and `worker`.
- Pipeline: Makefile entrypoints for ingestion, staging, ER, recommendations, explanations,
  defense artifacts, and demo/readiness checks.

Optional profiles add MLflow + MinIO, JupyterLab, and pgAdmin without making them mandatory for the MVP.

## Repository Layout

```text
docker/     container definitions and PostgreSQL init scripts
configs/    YAML configuration files
src/        application, ingestion, preprocessing, ML, RAG, and API code
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
Wikidata targeted ingestion: [docs/wikidata_ingestion.md](docs/wikidata_ingestion.md).
Controlled full download strategy: [docs/full_data_download_strategy.md](docs/full_data_download_strategy.md).
External ID matching and candidate corpus: [docs/external_id_matching.md](docs/external_id_matching.md).
Staging normalization and data-quality layer: [docs/staging_data_quality.md](docs/staging_data_quality.md).
Steam targeted enrichment: [docs/steam_enrichment.md](docs/steam_enrichment.md).
Wikipedia summaries enrichment: [docs/wikipedia_summaries.md](docs/wikipedia_summaries.md).
ML-ready datasets and final data-stage build: [docs/ml_ready_datasets.md](docs/ml_ready_datasets.md).
Entity Resolution baseline: [docs/entity_resolution_baseline.md](docs/entity_resolution_baseline.md).
ML research defense plan: [docs/ml_research_defense_plan.md](docs/ml_research_defense_plan.md).
ML research findings: [docs/ml_research_findings.md](docs/ml_research_findings.md).
ML research defense runbook: [docs/ml_research_defense_runbook.md](docs/ml_research_defense_runbook.md).
Final project execution plan RU: [docs/final_project_execution_plan_ru.md](docs/final_project_execution_plan_ru.md).
Demo script RU: [docs/demo_script_ru.md](docs/demo_script_ru.md).
Final demo cases RU: [docs/final_demo_cases_ru.md](docs/final_demo_cases_ru.md).
Final live demo script RU: [docs/live_demo_script_final_ru.md](docs/live_demo_script_final_ru.md).
Final defense smoke checklist RU:
[docs/final_defense_smoke_checklist_ru.md](docs/final_defense_smoke_checklist_ru.md).
Timed defense rehearsal RU: [docs/timed_defense_rehearsal_ru.md](docs/timed_defense_rehearsal_ru.md).
Live demo backup notebook:
[notebooks/04_live_demo_cases.ipynb](notebooks/04_live_demo_cases.ipynb).
IGDB optional/search enrichment: [docs/igdb_enrichment.md](docs/igdb_enrichment.md).
IGDB ML matching research plan: [docs/igdb_ml_matching_research_plan.md](docs/igdb_ml_matching_research_plan.md).
Pre-API download readiness report: [docs/pre_api_download_readiness.md](docs/pre_api_download_readiness.md).
Russian platform analytics summary: [docs/platform_analytics_ru.md](docs/platform_analytics_ru.md).
Final plan gap analysis RU: [docs/final_plan_gap_analysis_ru.md](docs/final_plan_gap_analysis_ru.md).
Future work RU: [docs/future_work_ru.md](docs/future_work_ru.md).

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
make wikidata-by-rawg
make wikidata-identity
make wikidata-staging
make steam-check
make steam-appids
make steam-staging
make igdb-check
make igdb-ids
make igdb-reference
make igdb-search-seeds
make igdb-search
make igdb-search-candidates
make igdb-staging
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
make export-data-pack
make import-data-pack DATA_PACK=data_packs/gip_demo_local
make restore-from-files DATA_PACK=data_packs/gip_demo_local
make er-dataset
make er-rule-baseline
make er-train
make er-predict
make er-evaluate
make er-review-queue
make er-baseline
make er-merge-strategy-comparison
make er-graph-analysis
make er-embedding-research
make igdb-matching-analysis
make ml-research-defense
make bayesian-rating
make rag-explanations
make ml-defense-readiness
make ml-defense-presentation
make ml-defense-all
make demo-readiness
make api-smoke
make notebook-check
make notebook-export
make final-smoke
make graph-analytics
make embeddings-research
make recommendations-hybrid
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
`make wikidata` runs the safe targeted pipeline (`wikidata-by-rawg`, `wikidata-staging`) and does not request broad EntityData by default.
`make wikidata-identity` remains available for the broader SPARQL identity path, but it is not the default MVP route for the first live run.
`make steam` runs the targeted enrichment pipeline (`steam-appids`, `steam-details`, `steam-staging`) and does not scan the full Steam catalog.
`make igdb` stays optional and targeted: the legacy path selects IGDB IDs from Wikidata external IDs, while the newer search path can use the current RAWG corpus as a retrieval anchor before promoting candidates into ER.
`make wikipedia` runs the targeted summaries pipeline (`wikipedia-pages`, `wikipedia-load`, `wikipedia-staging`) and does not use broad search or opensearch by default.
`make entity-data-base` prepares deterministic matches, candidate pairs, feature rows, reports, and parquet exports without calling external APIs.
`make data-quality` validates staging prerequisites, rebuilds normalized staging rows, writes DQ and anomaly reports, and exports analysis-ready parquet snapshots.
`make ml-ready-data` finalizes the local data stage: validation, candidate/feature refresh, DQ artifacts, manual review seed, parquet exports, and dataset manifest, again without external API calls.
`make er-baseline` builds the weak-label training dataset, runs rule and Logistic Regression baselines, predicts matches, evaluates metrics, and prepares a manual review queue without external APIs.
`make er-graph-analysis` builds shadow ER graph/component risk artifacts without changing canonical tables.
`make er-embedding-research` builds a lightweight TF-IDF/SVD title embedding research report for reviewed ER pairs.
`make igdb-matching-analysis` builds IGDB search-lane retrieval, review-quality, and enrichment-coverage artifacts.
`make ml-research-defense` builds defense-ready research artifacts: baseline counts, ablation study, calibration analysis, active-learning candidates, and recommendation examples.
`make bayesian-rating` builds a secondary research report that compares naive weighted source ratings with Bayesian-adjusted ratings for canonical games.
`make rag-explanations` builds grounded Russian match and recommendation explanation examples from computed facts.
`make ml-defense-readiness` checks the generated defense artifacts, metric snapshot, and demo sequence.
`make ml-defense-presentation` builds a slide outline, speaker notes, and remaining-step checklist from the readiness artifacts.
`make ml-defense-all` rebuilds the full defense artifact package and runs the final readiness gate.
`make demo-readiness` validates local demo data, report artifacts, recommendations, ER/manual review artifacts, explanations, and data-pack availability.
`make api-smoke` checks the main FastAPI demo endpoints against `API_BASE_URL`.
`make notebook-check` validates defense notebooks are present and parseable.
`make notebook-export` exports defense notebooks to HTML through the optional notebook profile.
`make final-smoke` runs the minimal pre-defense check: demo readiness, API smoke, and notebook check.
`make embeddings-research` runs the existing TF-IDF/SVD embedding research plus an optional neural-embedding fallback report.
`make graph-analytics` rebuilds ER graph risk artifacts.
`make recommendations-hybrid` writes a separate `hybrid_content_rating_v1` recommendation layer using the safe content baseline as the current fallback.
`make export-data-pack` and `make restore-from-files` support reproducible file-based restore for limited APIs and should be preferred over repeated broad downloads.

## Demo Readiness

Use this command before a rehearsal or defense:

```bash
make demo-readiness
```

It returns `ok`, `warning`, or `error`, lists found/missing artifacts, and suggests the
Makefile commands needed to rebuild missing data. The same information is available through:

```bash
curl http://localhost:8000/stats/readiness
```

## Historical First Controlled API Download

The first controlled API download plan below is kept as historical runbook context. The
current repository already contains completed data-preparation, enrichment, ER, canonical,
recommendation, explanation, and defense-demo artifacts. For current defense status, use
[docs/final_plan_gap_analysis_ru.md](docs/final_plan_gap_analysis_ru.md) and
[docs/final_defense_smoke_checklist_ru.md](docs/final_defense_smoke_checklist_ru.md).

Original first-live source order:

- `RAWG` for discovery-oriented metadata.
- `Wikidata` for identity, aliases, external IDs, and sitelinks.

Recommended command order:

```bash
make check-sources-network

make rawg-reference
make rawg-index
make rawg-staging

make wikidata-by-rawg
make wikidata-staging

make match-external-ids
make candidate-pairs
make feature-base

make dq
make anomalies
make export-analysis
make ml-ready-data
make export-data-pack
```

This order kept the original first live run narrow and reproducible. It remains useful when
rebuilding from scratch, but it is no longer the current project completion status.

## Optional Enrichment After MVP

Steam and Wikipedia are targeted enrichments already supported by the current contour. IGDB is
optional and targeted/search-based; it should still be enabled deliberately because it requires
credentials and quota control.

```bash
make steam-appids
make steam-details
make steam-staging

make wikipedia-pages
make wikipedia-load
make wikipedia-staging

make igdb-check
make igdb-ids
make igdb-games
make igdb-search
make igdb-search-candidates
make igdb-staging
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
- `GET /stats/catalog`
- `GET /stats/ml`
- `GET /stats/readiness`
- `GET /stats/graph`
- `PATCH /matches/review/{pair_id}`

The catalog, recommendation, review, explanation, and stats endpoints are read-only demo
endpoints. They read PostgreSQL when available and fall back to generated ML defense artifacts
where a database table is unavailable or the local database is not populated.

Demo API notes:

- `POST /recommend` accepts either `seed_game_ids` or `liked_games` title strings.
- Recommendation endpoints accept `algorithm=content_jaccard_v1` or
  `algorithm=hybrid_content_rating_v1`.
- `GET /matches/review` accepts `review_status` and `decision` filters.
- `PATCH /matches/review/{pair_id}` updates PostgreSQL manual review rows only; artifact
  fallback is read-only. If `GIP_WRITE_API_KEY` is set, pass it as `X-GIP-Write-API-Key`.
- Explanation endpoints include `explanation_ru`, `facts_used`, and `sources_used` fields.
  They accept `mode=template|llm`; LLM mode is disabled by default and falls back to grounded
  template text unless an approved provider is configured.

## Docker Profiles

- `make up` starts the runtime-like MVP stack without source bind mounts or reload.
- `make up-dev` starts the local development stack with bind mounts and autoreload.
- `make up-mlops` adds `mlflow` and `minio`.
- `make up-notebook` adds `notebook`.
- `make up-ui` starts the optional Streamlit demo UI on port `8501`.
- `make up-admin` adds `pgadmin`.

## Security Notes

- Keep `.env`, `.codex/`, `.omx/`, data directories, and generated artifacts out of Git.
- Store real external API tokens in `.env.secrets`; keep `.env` for non-secret local defaults.
- Commit only examples such as `.env.example` and `.env.secrets.example`.
- Replace all placeholder credentials before using external APIs.
- Health endpoints return status information only and do not expose secrets.

## MVP vs Advanced

The project now includes the full data-prepare contour, dry-run-safe optional/search IGDB
support, file-based restore tooling, and read-only FastAPI demo endpoints for catalog,
recommendations, review candidates, explanations, platform statistics, demo readiness,
manual-review write updates, optional Streamlit UI, notebook export checks, and lightweight
optional embedding/graph/hybrid recommendation research lanes.
Production-grade auth, interactive RAG chat, collaborative filtering, and full frontend UX
remain follow-up work.
