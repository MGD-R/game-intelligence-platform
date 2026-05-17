# Pre-API Download Readiness

## Status

Ready for controlled RAWG + Wikidata API download after all checks pass.

Not yet considered fully complete until the first live end-to-end run is executed and exported to a data-pack.

## What Was Checked

- repository state, ignore rules, and branch workflow;
- Docker Compose config and dev stack startup;
- PostgreSQL schema bootstrap and health endpoints;
- test suite, lint, and dry-run CLI coverage;
- raw-table idempotency at SQL level and inside PostgreSQL;
- data-pack export/import/restore dry-run behavior and table coverage;
- IGDB optional source dry-run readiness and default-disabled status;
- README and docs alignment with the implemented contour.

## Passed

- `docker compose config`
- `make build-dev`
- `make up-dev`
- `make db-check`
- `make test`
- `make lint`
- `make check-sources`
- `python -m src.ingestion.check_sources --no-network`
- `python -m src.preprocessing.export_data_pack --dry-run`
- `python -m src.ingestion.igdb_auth --dry-run`
- `python -m src.ingestion.igdb_client --check --dry-run`
- `python -m src.ingestion.jobs.load_igdb_games --dry-run --limit 1`
- `python -m src.preprocessing.igdb_to_staging --dry-run`

## Failed Or Skipped By Design

- `python -m src.preprocessing.import_data_pack --dry-run --input data_packs/nonexistent`
  Fails clearly because the input pack does not exist.
- `python -m src.preprocessing.restore_from_files --dry-run --input data_packs/nonexistent`
  Fails clearly because the input pack does not exist.
- broad live ingestion commands were intentionally skipped in this readiness pass.

## Docker And DB Status

- local dev stack is expected to run as `postgres`, `app-dev`, and `worker-dev`;
- `/health` and `/health/db` should both return `ok`;
- schema bootstrap should report `5` schemas and `31` tables.

## Test And Lint Status

- full pytest suite passes;
- lint passes with Ruff;
- dedicated DB idempotency test can be run via `make test-db`.

## Raw Idempotency Status

- raw inserts use PostgreSQL upsert semantics: `INSERT ... ON CONFLICT ... DO UPDATE`;
- conflict targets are table-specific and aligned with existing unique indexes;
- the repository now has both query-level and live PostgreSQL idempotency coverage.

## Data-Pack Restore Status

- export/import covers all expensive raw tables used in the contour:
  - `raw.rawg_game_index`
  - `raw.rawg_game_details`
  - `raw.rawg_reference_data`
  - `raw.wikidata_sparql_results`
  - `raw.wikidata_entities`
  - `raw.steam_app_details`
  - `raw.wikipedia_pages`
  - `raw.igdb_games`
  - `raw.igdb_reference_data`
- optional cache, processed parquet, and report copies are supported;
- manifest/checksum files are produced for reproducible restore.

## IGDB Status

- IGDB is implemented as optional advanced enrichment;
- `igdb.enabled` remains `false` by default;
- dry-run auth and client checks do not spend quota or request tokens;
- recommended first live run should still ignore IGDB until the MVP baseline is verified.

## Recommended First API Download Order

```bash
make check-sources-network

make rawg-reference
make rawg-index
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

## Known Limitations

- no broad live API ingestion was executed in this readiness pass;
- readiness is high, but not fully proven until one real RAWG + Wikidata run completes successfully;
- Steam, Wikipedia, and IGDB should remain follow-up enrichments after the MVP baseline data-pack is produced.
