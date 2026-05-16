COMPOSE := docker compose
COMPOSE_DEV := $(COMPOSE) --profile dev
WORKER_RUN := $(COMPOSE_DEV) run --rm --no-deps --build worker-dev

.PHONY: build build-dev up up-dev up-mlops up-notebook up-admin down logs ps shell db-shell \
	db-check test lint format check-sources check-sources-network cache-list quota-status \
	rawg-check rawg-reference rawg-index rawg-details rawg-staging rawg-demo rawg \
	wikidata-check wikidata-identity wikidata-entities wikidata-staging wikidata-demo wikidata \
	match-external-ids candidate-pairs feature-base source-coverage export-ml-base entity-data-base \
	steam wikipedia staging er recommendations rag demo-data all

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

lint:
	$(WORKER_RUN) python -m ruff check src tests

format:
	$(WORKER_RUN) python -m ruff format src tests

check-sources:
	$(COMPOSE) run --rm --no-deps worker python -m src.ingestion.check_sources --no-network

check-sources-network:
	$(COMPOSE) run --rm --no-deps worker python -m src.ingestion.check_sources --network --limit 1

cache-list:
	$(COMPOSE) run --rm --no-deps worker python -m src.ingestion.request_cache --list

quota-status:
	$(COMPOSE) run --rm --no-deps worker python -m src.ingestion.quota --status

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

wikidata-entities:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_entities

wikidata-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.wikidata_to_staging

wikidata-demo: wikidata-identity wikidata-staging

match-external-ids:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.preprocessing.match_external_ids

candidate-pairs:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.entity_resolution.build_candidate_pairs

feature-base:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.entity_resolution.build_feature_base

source-coverage:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.preprocessing.source_coverage

export-ml-base:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps worker python -m src.preprocessing.export_ml_ready_base

entity-data-base: match-external-ids candidate-pairs feature-base source-coverage export-ml-base

steam:
	$(WORKER_RUN) python -m src.ingestion.steam_client

wikipedia:
	$(WORKER_RUN) python -m src.ingestion.wikipedia_client

staging:
	$(WORKER_RUN) python -m src.preprocessing.build_staging

er:
	$(WORKER_RUN) python -m src.entity_resolution.run_pipeline

recommendations:
	$(WORKER_RUN) python -m src.recommendations.build_recommendations

rag:
	$(WORKER_RUN) python -m src.rag.build_index

demo-data:
	$(WORKER_RUN) python -m src.preprocessing.build_staging --demo

all:
	$(MAKE) check-sources
	$(MAKE) staging
	$(MAKE) er
	$(MAKE) recommendations
	$(MAKE) rag
