# Entity Resolution Baseline

This stage introduces the first real ML module in the project: baseline entity resolution.

## Purpose

The task is to estimate whether two source records describe the same video game:

`pair(source_game_a, source_game_b) -> P(same_game)`

## Inputs

Baseline ER uses the ML-ready artifacts from the previous stage:

- candidate pairs;
- basic non-embedding feature base;
- deterministic weak positives from external IDs;
- optional manual review seed context.

## Weak labels

Positive labels come from deterministic external ID matches, primarily:

- `wikidata_rawg_external_id`;
- `external_id` style deterministic positives.

Synthetic negatives are conservative and capped relative to the positive count.

Current negative heuristics:

- same or very similar title but implausibly different release year;
- conflicting external-ID signal with low similarity;
- low name similarity plus different release year.

## Features used now

- `name_similarity`
- `alias_similarity`
- `release_year_diff`
- `external_id_exact_match`
- `developer_overlap`
- `publisher_overlap`
- `platform_jaccard`
- `genre_jaccard`
- `tag_jaccard`
- `description_available_flag`
- `description_language_match`
- `source_count_signal`

Embeddings are intentionally postponed to a later stage.

## Baselines

### Rule-based baseline

Simple transparent rules:

- external ID exact match -> near-certain merge;
- very high title similarity plus compatible year -> high merge probability;
- very high alias similarity plus compatible year -> high merge probability;
- low similarity plus conflicting year -> low merge probability;
- otherwise score conservatively and often route to manual review.

### Logistic Regression baseline

- trains on weak positives and conservative synthetic negatives;
- uses imputation for missing values;
- saves model artifact, feature list, metrics, coefficients, and predictions locally.

## Threshold policy

- `>= 0.95` -> `auto_merge`
- `0.70 <= p < 0.95` -> `manual_review`
- `< 0.70` -> `no_merge`

Thresholds are configured in `configs/entity_resolution.yaml`.

## Outputs

- `data/processed/entity_resolution/training_dataset.parquet`
- `data/processed/entity_resolution/predictions.parquet`
- `data/processed/entity_resolution/manual_review_queue.parquet`
- `data/artifacts/models/entity_resolution/logistic_regression_baseline.joblib`
- `data/artifacts/reports/entity_resolution/metrics.json`
- `data/artifacts/reports/entity_resolution/summary.md`
- `data/artifacts/reports/entity_resolution/feature_coefficients.csv`
- `data/artifacts/reports/entity_resolution/manual_review_queue.csv`

## Dry-run

```bash
python -m src.entity_resolution.build_training_dataset --dry-run --allow-empty
python -m src.entity_resolution.run_baseline_pipeline --dry-run --allow-empty
python -m src.entity_resolution.build_manual_review_queue --dry-run --allow-empty
```

## Full local baseline

```bash
make er-dataset
make er-baseline
```

## Known limitations

- no embeddings yet;
- no active-learning loop yet;
- weak labels are narrow and currently centered on deterministic external IDs;
- the queue is meant for analyst review, not frontend consumption;
- canonical merge tables are not built in this stage.

## Next steps

- richer negatives and label audit tooling;
- embedding features;
- improved probability calibration;
- canonical catalog materialization;
- review-assisted feedback loop.
