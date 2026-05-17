# Full Data Download Report

## Scope

Controlled full data loading and ML-ready dataset preparation run based on:

- `RAWG` wide discovery
- `Wikidata` targeted identity by RAWG
- optional enrichments: `Steam`, `Wikipedia`, `IGDB`
- staged `DQ`, analysis export, and ML-ready rebuilds
- reproducibility checkpoints via `data_packs/`

Run date:

- `2026-05-17`

## Execution Summary

Status: completed

Stages:

1. Pre-checks: completed
2. RAWG discovery checkpoint: completed
3. Wikidata targeted checkpoint: completed
4. IGDB optional enrichment: skipped, no IGDB IDs in current Wikidata staging
5. Steam targeted enrichment: completed
6. Wikipedia targeted summaries: completed after rate-limit hardening
7. RAWG targeted details: completed on 100 priority IDs
8. Final ML-ready rebuild: completed
9. Restore validation: completed in dry-run mode

## Final Snapshot

- `raw.rawg_game_index = 10`
- `raw.rawg_game_details = 100`
- `raw.wikidata_sparql_results = 8`
- `raw.steam_app_details = 365`
- `raw.wikipedia_pages = 697`
- `stg.source_games`: `rawg=400`, `wikidata=385`, `steam=202`
- `stg.source_game_descriptions`: `rawg=100`, `steam=603`, `wikipedia=697`
- `stg.source_game_external_ids`: `wikidata=754`, `steam=202`, `wikipedia=697`
- `ml.entity_candidate_pairs = 394`
- `ml.entity_resolution_features = 394`

API calls by source:

- `rawg = 115`
- `wikidata = 30`
- `steam = 366`
- `wikipedia = 698`

Quality highlights:

- `missing_description_rate = 0.695035`
- `missing_developer_rate = 0.694022`
- `missing_genre_rate = 0.594732`
- `missing_platform_rate = 0.390071`
- `missing_release_date_rate = 0.010132`
- `wikipedia_summary_coverage_rate = 0.992826`
- `steam_enrichment_coverage_rate = 0.553425`

## Runtime Fixes Applied During Run

- `staging` JSONB write adaptation for `dict/list` payloads
- deterministic external ID matching using RAWG slug fallback
- data-pack manifest completion status fields
- source-specific Wikimedia rate-limit env override
- non-burst rate limiter behavior for per-minute sources
- Wikipedia page-level `429` cooldown and retry
- parquet export normalization for ragged and mixed-type staging rows

## Checkpoints

### RAWG

- pack: `data_packs/gip_full_rawg_v1`
- status: completed

### RAWG + Wikidata

- pack: `data_packs/gip_full_rawg_wikidata_v1`
- status: completed

### Steam

- pack: `data_packs/gip_full_steam_v1`
- status: completed

### Wikipedia

- pack: `data_packs/gip_full_wikipedia_v1`
- status: completed

### RAWG Details

- pack: `data_packs/gip_full_rawg_details_v1`
- status: completed

### Final ML-ready

- pack: `data_packs/gip_full_ml_ready_v1`
- status: completed

Manifest checks:

- `run_status = completed`
- `ml_ready = true`
- `failed_steps = []`
- `active_sources = ['rawg', 'wikidata', 'steam', 'wikipedia']`
- `optional_sources = ['igdb']`

## Restore Validation

Validated against `data_packs/gip_full_ml_ready_v1`:

- `import_data_pack --dry-run`: passed
- `restore_from_files --dry-run`: passed
- planned restore steps:
  - import raw data pack
  - rebuild staging
  - rebuild external ID matches
  - rebuild candidate pairs
  - rebuild feature base
  - rebuild DQ reports
  - rebuild ML-ready datasets
  - export refreshed data pack manifest

## Data Pack Paths

- `data_packs/gip_full_rawg_v1`
- `data_packs/gip_full_rawg_wikidata_v1`
- `data_packs/gip_full_steam_v1`
- `data_packs/gip_full_wikipedia_v1`
- `data_packs/gip_full_rawg_details_v1`
- `data_packs/gip_full_ml_ready_v1`

## Next ML Steps

1. Train baseline ER model on `data/processed/entity_candidate_pairs.parquet` and `data/processed/entity_resolution_feature_base.parquet`.
2. Review `data/processed/manual_review_seed.parquet` to label ambiguous pairs.
3. Add optional `IGDB` only after a data source with real IGDB IDs is available in Wikidata staging.
4. Extend recommendation features with Wikipedia/Steam signals now that the corpus has broader descriptions and metadata.

## Notes

- `IGDB` remained optional and could not be activated in this run because current Wikidata staging did not contain IGDB IDs.
- `Wikipedia` required runtime hardening for real `429` handling; after that, the full targeted sitelink set completed successfully.
- `RAWG details` were executed on a prioritized set of `100` IDs selected by popularity and rating density because index-only RAWG staging left all `400` games without native RAWG descriptions.
- Generated data and data packs are intentionally not committed.
