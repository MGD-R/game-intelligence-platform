# Wikidata MVP Data Run

## Scope

This run completes the first local MVP snapshot for:

- `RAWG`
- `Wikidata`
- external ID matching
- candidate pairs
- feature base
- DQ reports
- ML-ready parquet exports
- final data-pack export

Optional enrichments were intentionally not run:

- `Steam`
- `Wikipedia`
- `IGDB`

## Key fixes

1. Failed-cache handling no longer treats cached `502/504` Wikidata responses as valid.
2. Targeted Wikidata ingestion now uses RAWG slugs from `stg.source_games.slug`.
   `Wikidata P9968` stores RAWG slugs, not numeric RAWG IDs.
3. External ID matching now bridges:
   - RAWG `source_game_id` as canonical left ID
   - RAWG `slug` as source-native external key
   - Wikidata `external_id(rawg)` as the joining value
4. Parquet export now normalizes:
   - `UUID -> str`
   - schema-bound scalar values such as `date -> Utf8`
5. ML-ready export no longer fails when optional MVP datasets are empty:
   - `source_aliases`
   - `source_companies`
   - `source_descriptions`

## Commands run

```bash
make wikidata-by-rawg
make wikidata-staging
make match-external-ids
make candidate-pairs
make feature-base
make dq
make anomalies
make export-analysis
make ml-ready-data
docker compose exec -T worker-dev python -m src.preprocessing.export_data_pack \
  --output data_packs/gip_mvp_rawg_wikidata_v1 \
  --include-cache \
  --include-processed \
  --include-reports
```

## Result

- `raw.wikidata_sparql_results = 8`
- `stg.source_games where source='wikidata' = 385`
- `stg.source_game_external_ids where source='wikidata' and external_source='rawg' = 385`
- `ml.entity_candidate_pairs = 394`
- `ml.entity_resolution_features = 394`

Data-pack:

- path: `data_packs/gip_mvp_rawg_wikidata_v1`
- manifest: `run_status=completed`
- manifest: `ml_ready=true`

## Notes

- `RAWG + Wikidata` is now sufficient for the first end-to-end local ML-ready snapshot.
- `Wikidata` coverage is high but not total: `385 / 400` RAWG games matched in this run.
- Remaining enrichments should be run later as optional follow-up stages, not as MVP blockers.
