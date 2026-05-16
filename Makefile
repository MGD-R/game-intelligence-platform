COMPOSE := docker compose
PYTHON := python3

.PHONY: build up up-mlops up-notebook up-admin down logs ps shell test lint format \
	check-sources rawg wikidata steam wikipedia staging er recommendations rag demo-data all

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d postgres app worker

up-mlops:
	$(COMPOSE) --profile mlops up -d postgres app worker minio mlflow

up-notebook:
	$(COMPOSE) --profile notebook up -d postgres app worker notebook

up-admin:
	$(COMPOSE) --profile admin up -d postgres app worker pgadmin

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec worker /bin/sh

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests

check-sources:
	$(PYTHON) -m src.ingestion.check_sources

rawg:
	$(PYTHON) -m src.ingestion.rawg_client

wikidata:
	$(PYTHON) -m src.ingestion.wikidata_client

steam:
	$(PYTHON) -m src.ingestion.steam_client

wikipedia:
	$(PYTHON) -m src.ingestion.wikipedia_client

staging:
	$(PYTHON) -m src.preprocessing.build_staging

er:
	$(PYTHON) -m src.entity_resolution.run_pipeline

recommendations:
	$(PYTHON) -m src.recommendations.build_recommendations

rag:
	$(PYTHON) -m src.rag.build_index

demo-data:
	$(PYTHON) -m src.preprocessing.build_staging --demo

all:
	$(MAKE) check-sources
	$(MAKE) staging
	$(MAKE) er
	$(MAKE) recommendations
	$(MAKE) rag
