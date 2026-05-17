COMPOSE := docker compose
COMPOSE_DEV := $(COMPOSE) --profile dev
WORKER_RUN := $(COMPOSE_DEV) run --rm --no-deps --build worker-dev

.PHONY: build build-dev up up-dev up-mlops up-notebook up-admin down logs ps shell db-shell \
	db-check test test-db lint format check-sources check-sources-network cache-list quota-status \
	rawg-check rawg-reference rawg-index rawg-details rawg-staging rawg-demo rawg \
	wikidata-check wikidata-identity wikidata-by-rawg wikidata-entities wikidata-staging wikidata-demo wikidata mvp-rawg-wikidata \
	steam-check steam-appids steam-details steam-staging steam-demo steam \
	igdb-check igdb-ids igdb-reference igdb-games igdb-staging igdb-demo igdb \
	wikipedia-check wikipedia-pages wikipedia-load wikipedia-staging wikipedia-demo wikipedia \
	match-external-ids candidate-pairs feature-base source-coverage export-ml-base entity-data-base \
	validate-staging validate-ml-data manual-review-seed dataset-manifest export-ml-ready \
	ml-ready-data data-stage dq anomalies export-analysis data-quality \
	staging er er-dataset er-rule-baseline er-train er-predict er-evaluate er-review-queue \
	er-baseline export-data-pack import-data-pack restore-from-files export-raw-cache data-pack-check \
	recommendations rag demo-data all

DATA_PACK ?= data_packs/gip_demo_local

build:
	$(COMPOSE) build app worker

build-dev:
	$(COMPOSE_DEV) build app-dev worker-dev

up:
	$(COMPOSE) up -d postgres app worker

up-dev:
	$(COMPOSE_DEV) up -d postgres app-dev worker-dev

up-mlops:
	$(COMPOSE) --profile mlops up -d postgres app worker minio mlflow

up-notebook:
	$(COMPOSE) --profile notebook up -d postgres app worker notebook

up-admin:
	$(COMPOSE) --profile admin up -d postgres app worker pgadmin

down:
	$(COMPOSE) --profile dev --profile mlops --profile notebook --profile admin down --remove-orphans

logs:
	$(COMPOSE) --profile dev --profile mlops --profile notebook --profile admin logs -f --tail=100

ps:
	$(COMPOSE) --profile dev --profile mlops --profile notebook --profile admin ps

shell:
	$(COMPOSE_DEV) run --rm worker-dev /bin/sh

db-shell:
	$(COMPOSE) up -d postgres
	$(COMPOSE) exec postgres sh -lc 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-check:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.database.check_schema

test:
	$(WORKER_RUN) python -m pytest

test-db:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m pytest tests/test_raw_idempotency.py

lint:
	$(WORKER_RUN) python -m ruff check src tests

format:
	$(WORKER_RUN) python -m ruff format src tests

check-sources:
	$(WORKER_RUN) python -m src.ingestion.check_sources --no-network

check-sources-network:
	$(WORKER_RUN) python -m src.ingestion.check_sources --network --limit 1

cache-list:
	$(WORKER_RUN) python -m src.ingestion.request_cache --list

quota-status:
	$(WORKER_RUN) python -m src.ingestion.quota --status

rawg:
	$(MAKE) rawg-demo

rawg-check:
	$(WORKER_RUN) python -m src.ingestion.rawg_client --check --dry-run --page-size 1

rawg-reference:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_rawg_reference

rawg-index:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_rawg_index

rawg-details:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_rawg_details

rawg-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.rawg_to_staging

rawg-demo: rawg-reference rawg-index rawg-staging

wikidata:
	$(MAKE) wikidata-demo

wikidata-check:
	$(WORKER_RUN) python -m src.ingestion.wikidata_client --check --dry-run --limit 1

wikidata-identity:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_identity

wikidata-by-rawg:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_by_rawg_ids --limit 400 --batch-size 50

wikidata-entities:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_entities

wikidata-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.wikidata_to_staging

wikidata-demo: wikidata-identity wikidata-staging

mvp-rawg-wikidata:
	$(MAKE) wikidata-by-rawg
	$(MAKE) wikidata-staging
	$(MAKE) match-external-ids
	$(MAKE) candidate-pairs
	$(MAKE) feature-base
	$(MAKE) dq
	$(MAKE) anomalies
	$(MAKE) export-analysis
	$(MAKE) ml-ready-data

match-external-ids:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.match_external_ids

candidate-pairs:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_candidate_pairs

feature-base:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_feature_base

source-coverage:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.source_coverage

export-ml-base:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.export_ml_ready_base

entity-data-base: match-external-ids candidate-pairs feature-base source-coverage export-ml-base

steam:
	$(MAKE) steam-demo

steam-check:
	$(WORKER_RUN) python -m src.ingestion.steam_client --check --dry-run --app-id 271590

steam-appids:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.select_steam_appids

steam-details:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_steam_details

steam-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.steam_to_staging

steam-demo: steam-appids steam-details steam-staging

igdb:
	$(MAKE) igdb-demo

igdb-check:
	$(WORKER_RUN) python -m src.ingestion.igdb_client --check --dry-run

igdb-ids:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.select_igdb_ids

igdb-reference:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_igdb_reference

igdb-games:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_igdb_games

igdb-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.igdb_to_staging

igdb-demo: igdb-ids igdb-games igdb-staging

wikipedia:
	$(MAKE) wikipedia-demo

wikipedia-check:
	$(WORKER_RUN) python -m src.ingestion.wikipedia_client --check --dry-run --language en --title Minecraft

wikipedia-pages:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.select_wikipedia_pages

wikipedia-load:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikipedia_pages

wikipedia-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.wikipedia_to_staging

wikipedia-demo: wikipedia-pages wikipedia-load wikipedia-staging

validate-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.validate_staging_state

staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.build_staging --all

dq:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.data_quality

anomalies:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.anomaly_reports

export-analysis:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.export_analysis_data

validate-ml-data:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.validate_ml_ready_data

manual-review-seed:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_manual_review_seed

dataset-manifest:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.build_dataset_manifest

export-ml-ready:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.export_ml_ready_datasets

ml-ready-data:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.build_ml_ready_datasets

data-stage: validate-ml-data staging match-external-ids candidate-pairs feature-base dq anomalies export-analysis manual-review-seed export-ml-ready dataset-manifest

data-quality: validate-staging staging dq anomalies export-analysis

er:
	$(MAKE) er-baseline

er-dataset:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_training_dataset

er-rule-baseline:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.rule_baseline

er-train:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.train_baseline_model

er-predict:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.predict_matches

er-evaluate:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.evaluate_model

er-review-queue:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_manual_review_queue

er-baseline:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.run_baseline_pipeline

recommendations:
	$(WORKER_RUN) python -m src.recommendations.build_recommendations

rag:
	$(WORKER_RUN) python -m src.rag.build_index

demo-data:
	$(MAKE) rawg-demo
	$(MAKE) wikidata-demo
	$(MAKE) match-external-ids
	$(MAKE) candidate-pairs
	$(MAKE) feature-base
	$(MAKE) dq
	$(MAKE) ml-ready-data
	$(MAKE) export-data-pack

export-data-pack:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.export_data_pack --output data_packs/gip_demo_local --include-cache --include-processed --include-reports

import-data-pack:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.import_data_pack --input $(DATA_PACK)

restore-from-files:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.restore_from_files --input $(DATA_PACK)

export-raw-cache:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.export_data_pack --output data_packs/gip_raw_cache_local --include-cache

data-pack-check:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.import_data_pack --input $(DATA_PACK) --dry-run

all:
	$(MAKE) check-sources
	$(MAKE) staging
	$(MAKE) er
	$(MAKE) recommendations
	$(MAKE) rag
