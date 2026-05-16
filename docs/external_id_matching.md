# External ID Matching

This stage connects the first two MVP sources without training an ML model. The deterministic anchor is Wikidata property `P9968`, which stores RAWG ids and allows precise RAWG ↔ Wikidata linking.

## Why This Exists

- deterministic links create weak positive labels for later entity resolution
- candidate generation stays conservative and avoids all-vs-all comparisons
- coverage reports make it visible how much of RAWG is already anchored by Wikidata
- exported parquet snapshots give the next ML stage a stable base corpus

## Deterministic Rule

The current hard rule is:

```text
rawg.source_game_id == wikidata.external_id where external_source = 'rawg'
```

These matches are stored in `ml.entity_candidate_pairs` with:

- `candidate_source = external_id`
- `label_source = wikidata_rawg_external_id`
- `label_value = 1`
- `confidence = 1.0`

## Candidate Sources

- `external_id_positive`
- `same_normalized_name`
- `same_release_year_and_similar_name`
- `shared_alias`

## Current Feature Base

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

Intentionally postponed:

- embeddings
- sentence-transformer similarity
- learned scoring models
- advanced fuzzy blocking

## Main Commands

```bash
make match-external-ids
make candidate-pairs
make feature-base
make source-coverage
make export-ml-base
make entity-data-base
```

## Generated Reports

- `data/artifacts/reports/source_coverage.csv`
- `data/artifacts/reports/external_id_coverage.csv`
- `data/artifacts/reports/candidate_pair_summary.csv`
- `data/artifacts/reports/deterministic_match_summary.json`

## Generated Parquet Snapshots

- `data/processed/entity_candidate_pairs.parquet`
- `data/processed/entity_resolution_feature_base.parquet`
- `data/processed/source_external_ids.parquet`
- `data/processed/source_aliases.parquet`

## Before ML Training

Inspect:

- how many RAWG rows have deterministic Wikidata links
- whether candidate sources are dominated by exact positives only
- whether alias/title blocking creates plausible extra pairs
- whether key overlap features are mostly null because source data is still sparse
