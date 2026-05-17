# Full Data Download Strategy

## Purpose

This runbook defines the safe default order for the first full local API download and the subsequent ML-ready data build.

The baseline path is intentionally narrow:

- `RAWG` remains the discovery source;
- `Wikidata` is loaded through targeted `RAWG -> Wikidata` matching;
- optional enrichments stay out of the first full run.

## Controlled Execution Order

```bash
make check-sources-network

make rawg-reference
make rawg-index
make rawg-details
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

## Why This Order

- `rawg-reference` and `rawg-index` establish the discovery corpus first.
- `rawg-details` can be expanded only after the index is healthy.
- `wikidata-by-rawg` keeps the identity load bounded by actual RAWG candidates instead of using a broad identity crawl.
- `wikidata-staging` makes external IDs, aliases, and sitelinks available for matching.
- matching and feature steps are run only after both core sources exist in staging.
- DQ and export steps run after the entity-resolution base exists, so reports and parquet outputs reflect a coherent snapshot.
- `export-data-pack` is the final reproducibility checkpoint and should close the run.

## Stop Conditions

Stop the run and inspect logs if any of the following happens:

- `check-sources-network` reports source auth or quota errors;
- `rawg-index` or `wikidata-by-rawg` starts failing on repeated HTTP `4xx/5xx`;
- `match-external-ids` produces zero matches after both sources are staged;
- `dq` or `ml-ready-data` aborts on missing required source rows.

## Optional Follow-Up Enrichments

Run these only after the baseline `RAWG + Wikidata` snapshot succeeds:

```bash
make steam-appids
make steam-details
make steam-staging

make wikipedia-pages
make wikipedia-load
make wikipedia-staging
```

`IGDB` remains optional advanced enrichment and should be enabled only after a separate tiny live check.
