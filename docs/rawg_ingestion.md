# RAWG Ingestion

This stage adds the first concrete source pipeline for the MVP.

## Scope

- `src/ingestion/rawg_client.py` wraps RAWG endpoints on top of the shared ingestion framework.
- `src/ingestion/jobs/load_rawg_reference.py` stores genres, platforms, stores, and tags in `raw.rawg_reference_data`.
- `src/ingestion/jobs/load_rawg_index.py` stores paginated discovery payloads in `raw.rawg_game_index`.
- `src/ingestion/jobs/load_rawg_details.py` stores targeted game details in `raw.rawg_game_details`.
- `src/preprocessing/rawg_to_staging.py` converts RAWG raw payloads into `stg` source tables.

## Safety Model

- Dry-run mode is supported for client and jobs.
- `make rawg-check` is the safest validation command and does not call the network.
- `make rawg` runs the demo pipeline only and intentionally skips details.
- Details loading is targeted only and requires explicit ids.

## Idempotency

- Raw tables use request hashes and source record identifiers for repeated loads.
- RAWG staging currently uses a full source rebuild strategy per table: rows for `source='rawg'` are deleted and re-inserted.
- This is acceptable for the MVP bootstrap because RAWG is the first fully implemented source and the transform remains deterministic.

## Main Commands

```bash
make rawg-check
make rawg-reference
make rawg-index
make rawg-details
make rawg-staging
make rawg
```

## Config

Relevant environment variables:

```bash
RAWG_API_KEY=change_me
RAWG_MONTHLY_LIMIT=20000
RAWG_REQUESTS_PER_SECOND=1
RAWG_PAGE_SIZE=40
RAWG_DISCOVERY_PAGE_LIMIT=10
RAWG_DETAILS_LIMIT=0
DEMO_MODE=true
```
