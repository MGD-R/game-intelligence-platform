## Staging Data Quality

This stage adds a normalization and quality-control layer on top of the existing RAWG and Wikidata staging tables. The goal is to keep `stg` useful for deterministic entity matching and downstream ML preparation without overfitting the source data into a premature canonical model.

### What It Adds

- deterministic normalization for names, dates, flags, and list-like attributes;
- a staging validation command that checks required schemas, tables, and prerequisite row presence;
- data-quality summary reports for completeness, overlap, conflicts, languages, external IDs, and candidate sources;
- anomaly reports for suspicious years, duplicate normalized names, risky edition/demo titles, empty descriptions, and lightweight rating outliers;
- analysis-ready parquet exports for staging and entity-resolution snapshots.

### Normalization Rules

- `normalize_text.py` standardizes titles conservatively: lowercase, trimmed whitespace, and removal of a few trademark symbols.
- `normalize_dates.py` preserves valid ISO dates and extracts `release_year`; partial years are kept as year-only quality signals instead of being invented into full dates.
- `normalize_flags.py` derives only safe title-based booleans such as `is_demo`, `is_dlc`, `is_remaster`, `is_remake`, and `is_bundle`.
- `normalize_lists.py` deduplicates normalized string collections for reusable list processing.

The implementation is intentionally conservative. It avoids destructive rewrites, transliteration, language guessing, or fuzzy canonicalization at the staging layer.

### Generated Reports

`python -m src.preprocessing.data_quality` writes into `data/artifacts/reports/`:

- `dq_summary.json`
- `field_completeness_by_source.csv`
- `source_record_counts.csv`
- `source_overlap.csv`
- `external_id_coverage.csv`
- `candidate_pair_summary.csv`
- `missingness_report.csv`
- `conflict_report.csv`

`python -m src.preprocessing.anomaly_reports` writes:

- `anomaly_report.csv`

### Analysis Exports

`python -m src.preprocessing.export_analysis_data` writes parquet snapshots into `data/processed/`:

- `source_games.parquet`
- `source_aliases.parquet`
- `source_external_ids.parquet`
- `source_genres.parquet`
- `source_platforms.parquet`
- `source_companies.parquet`
- `source_descriptions.parquet`
- `source_ratings.parquet`
- `entity_candidate_pairs.parquet`
- `entity_resolution_feature_base.parquet`

### Main Commands

```bash
make validate-staging
make staging
make dq
make anomalies
make export-analysis
make data-quality
```

If the required staged/demo inputs are missing, the commands fail explicitly and direct you to run:

```bash
make rawg-demo
make wikidata-by-rawg
make wikidata-staging
make entity-data-base
```

### Known Limitations

- Reports currently focus on RAWG and Wikidata only.
- Anomaly detection is rule-based and intentionally shallow for MVP.
- Export snapshots are designed for local analysis and demo ML preparation, not for large-scale orchestration.
