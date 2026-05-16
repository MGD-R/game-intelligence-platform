COMPOSE := docker compose
COMPOSE_DEV := $(COMPOSE) --profile dev
WORKER_RUN := $(COMPOSE_DEV) run --rm --no-deps --build worker-dev

.PHONY: build build-dev up up-dev up-mlops up-notebook up-admin down logs ps shell test \
	lint format check-sources rawg wikidata steam wikipedia staging er recommendations rag \
	demo-data all

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

test:
	$(WORKER_RUN) python -m pytest

lint:
	$(WORKER_RUN) python -m ruff check src tests

format:
	$(WORKER_RUN) python -m ruff format src tests

check-sources:
	$(WORKER_RUN) python -m src.ingestion.check_sources

rawg:
	$(WORKER_RUN) python -m src.ingestion.rawg_client

wikidata:
	$(WORKER_RUN) python -m src.ingestion.wikidata_client

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
