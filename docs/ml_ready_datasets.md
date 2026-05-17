# ML-ready Datasets

This stage finalizes the local data-preparation contour before any model training.

## Purpose

- validate that required staged data is present;
- rebuild deterministic candidate pairs;
- rebuild non-embedding feature base;
- refresh DQ and anomaly artifacts;
- export analysis-ready and ML-ready parquet snapshots;
- generate a dataset manifest and a manual-review seed.

## Required previous stages

- `make rawg-demo`
- `make wikidata-by-rawg`
- `make wikidata-staging`
- `make match-external-ids`
- `make staging`
- `make dq`

If these inputs are missing, stage-11 commands fail clearly and do not fake success.

## Optional enrichments

- `make steam-demo`
- `make wikipedia-demo`

Steam and Wikipedia improve feature coverage but are not mandatory for the base data-stage build.

## Exported datasets

- `data/processed/source_games.parquet`
- `data/processed/source_aliases.parquet`
- `data/processed/source_external_ids.parquet`
- `data/processed/source_genres.parquet`
- `data/processed/source_tags.parquet`
- `data/processed/source_platforms.parquet`
- `data/processed/source_companies.parquet`
- `data/processed/source_descriptions.parquet`
- `data/processed/source_ratings.parquet`
- `data/processed/source_popularity.parquet`
- `data/processed/entity_candidate_pairs.parquet`
- `data/processed/entity_resolution_feature_base.parquet`
- `data/processed/manual_review_seed.parquet`

## Generated reports and manifests

- `data/artifacts/reports/dq_summary.json`
- `data/artifacts/reports/data_stage_summary.md`
- `data/artifacts/reports/source_coverage.csv`
- `data/artifacts/reports/field_completeness_by_source.csv`
- `data/artifacts/reports/external_id_coverage.csv`
- `data/artifacts/reports/candidate_pair_summary.csv`
- `data/artifacts/reports/feature_base_summary.csv`
- `data/artifacts/reports/anomaly_report.csv`
- `data/artifacts/reports/manual_review_seed_summary.csv`
- `data/artifacts/manifests/ml_ready_dataset_manifest.json`

## What is ready for ML

- normalized per-source facts in staging;
- deterministic weak labels from external IDs;
- conservative candidate pairs;
- non-embedding feature base;
- parquet snapshots for notebooks and future training.

## What is intentionally not done yet

- no model training;
- no sentence-transformer embeddings;
- no recommendation ranking;
- no RAG generation;
- no frontend or business API endpoints.

## Dry-run

```bash
python -m src.preprocessing.validate_ml_ready_data --allow-empty --dry-run
python -m src.preprocessing.build_ml_ready_datasets --dry-run --allow-empty
python -m src.preprocessing.export_ml_ready_datasets --dry-run --allow-empty
python -m src.preprocessing.build_dataset_manifest --dry-run --allow-empty
python -m src.entity_resolution.build_manual_review_seed --dry-run --allow-empty
```

## Full local build

```bash
make validate-ml-data
make ml-ready-data
```

## Inspect outputs

```bash
ls data/processed
ls data/artifacts/reports
cat data/artifacts/manifests/ml_ready_dataset_manifest.json
```

## Known limitations

- without loaded RAWG and Wikidata staging data, the final build stops early by design;
- Steam and Wikipedia remain optional enrichments;
- manual review seed is rule-based and does not use model probabilities.
