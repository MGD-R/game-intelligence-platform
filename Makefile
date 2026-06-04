COMPOSE := docker compose
COMPOSE_DEV := $(COMPOSE) --profile dev
WORKER_RUN := $(COMPOSE_DEV) run --rm --no-deps --build worker-dev

.PHONY: build build-dev up up-dev up-mlops up-notebook up-admin down logs ps shell db-shell \
	db-check test test-db lint format check-sources check-sources-network cache-list quota-status \
	rawg-check rawg-reference rawg-index rawg-details rawg-staging rawg-demo rawg \
	wikidata-check wikidata-by-rawg wikidata-identity wikidata-entities wikidata-staging wikidata-demo wikidata full-data-plan \
	steam-check steam-appids steam-details steam-staging steam-demo steam \
	igdb-check igdb-ids igdb-reference igdb-games igdb-staging igdb-search-seeds igdb-search igdb-search-candidates igdb-search-demo igdb-demo igdb \
	wikipedia-check wikipedia-pages wikipedia-load wikipedia-staging wikipedia-demo wikipedia \
	match-external-ids candidate-pairs feature-base source-coverage export-ml-base entity-data-base \
	validate-staging validate-ml-data manual-review-seed manual-review-db manual-review-db-seed canonical-v0 canonical-v1 dataset-manifest export-ml-ready \
	ml-ready-data data-stage dq anomalies export-analysis data-quality \
	staging er er-dataset er-rule-baseline er-train er-predict er-evaluate er-training-report er-review-queue er-export-review-queue \
	er-baseline er-merge-strategy-comparison er-graph-analysis er-embedding-research igdb-matching-analysis ml-research-defense ml-defense-readiness ml-defense-presentation ml-defense-all code-graph code-graph-watch code-graph-mcp export-data-pack import-data-pack restore-from-files export-raw-cache data-pack-check \
	recommendations bayesian-rating rag-explanations rag demo-data all

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

wikidata-by-rawg:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_by_rawg_ids

wikidata-identity:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_identity

wikidata-entities:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_wikidata_entities

wikidata-staging:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.wikidata_to_staging

wikidata-demo: wikidata-by-rawg wikidata-staging

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

igdb-search-seeds:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.select_igdb_search_seeds

igdb-search:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.ingestion.jobs.load_igdb_search

igdb-search-candidates:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.igdb_search_to_candidates

igdb-search-demo: igdb-search igdb-staging
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.preprocessing.igdb_search_to_candidates --promote-pairs

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

manual-review-db:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.setup_manual_review

manual-review-db-seed:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.seed_manual_review_queue

canonical-v0:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_canonical_v0

canonical-v1:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_canonical_v0 --version v1

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

er-training-report:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.export_training_report

er-review-queue:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.build_manual_review_queue

er-export-review-queue:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.export_manual_review_queue --status pending

er-baseline:
	$(COMPOSE) up -d postgres
	$(WORKER_RUN) python -m src.entity_resolution.run_baseline_pipeline

er-merge-strategy-comparison:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.entity_resolution.compare_merge_strategies

er-graph-analysis:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.entity_resolution.build_graph_analysis

er-embedding-research:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.entity_resolution.build_embedding_research

igdb-matching-analysis:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.entity_resolution.build_igdb_matching_analysis

ml-research-defense:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.entity_resolution.build_research_defense_artifacts

ml-defense-readiness:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.devtools.build_ml_defense_readiness

ml-defense-presentation:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.devtools.build_ml_defense_presentation

ml-defense-all:
	$(MAKE) er-merge-strategy-comparison
	$(MAKE) er-graph-analysis
	$(MAKE) er-embedding-research
	$(MAKE) igdb-matching-analysis
	$(MAKE) ml-research-defense
	$(MAKE) bayesian-rating
	$(MAKE) rag-explanations
	$(MAKE) ml-defense-readiness
	$(MAKE) ml-defense-presentation

code-graph:
	$(WORKER_RUN) python -m src.devtools.code_graph --once

code-graph-watch:
	$(WORKER_RUN) python -m src.devtools.code_graph --watch

code-graph-mcp:
	$(WORKER_RUN) python -m src.devtools.code_graph_mcp

recommendations:
	$(WORKER_RUN) python -m src.recommendations.build_recommendations

bayesian-rating:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.recommendations.build_bayesian_rating_analysis

rag-explanations:
	$(COMPOSE_DEV) up -d postgres worker-dev
	$(COMPOSE_DEV) exec -T worker-dev python -m src.rag.build_explanations

rag: rag-explanations

demo-data:
	$(MAKE) rawg-demo
	$(MAKE) wikidata-by-rawg
	$(MAKE) wikidata-staging
	$(MAKE) match-external-ids
	$(MAKE) candidate-pairs
	$(MAKE) feature-base
	$(MAKE) anomalies
	$(MAKE) export-analysis
	$(MAKE) dq
	$(MAKE) ml-ready-data
	$(MAKE) export-data-pack

full-data-plan:
	@printf '%s\n' \
		'Controlled full download order:' \
		'1. make check-sources-network' \
		'2. make rawg-reference' \
		'3. make rawg-index' \
		'4. make rawg-details' \
		'5. make rawg-staging' \
		'6. make wikidata-by-rawg' \
		'7. make wikidata-staging' \
		'8. make match-external-ids' \
		'9. make candidate-pairs' \
		'10. make feature-base' \
		'11. make dq' \
		'12. make anomalies' \
		'13. make export-analysis' \
		'14. make ml-ready-data' \
		'15. make export-data-pack'

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
