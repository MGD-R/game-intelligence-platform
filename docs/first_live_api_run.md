# First Live API Run

Date: `2026-05-17`

## Goal

Run the first live ingestion against external APIs, save the result both to PostgreSQL and to files, and document the first operational stop-point.

## Start state

- Running stack: `postgres`, `app-dev`, `worker-dev`
- Source check was already green before the live run.
- Real secrets were loaded from local env files and were not printed into this document.

## Actual run sequence

### 1. RAWG network readiness

Command:

```bash
make check-sources-network
```

Result:

- RAWG, Wikidata, Steam, and Wikipedia network checks responded.
- This was only a readiness check, not a data-stage success signal.

### 2. RAWG live ingestion to `raw`

Commands:

```bash
make rawg-reference
make rawg-index
```

Result:

- `raw.rawg_reference_data`: `4` rows
- `raw.rawg_game_index`: `10` rows
- `meta.api_request_log` recorded RAWG requests successfully.

### 3. RAWG transform to `stg`

Initial command:

```bash
make rawg-staging
```

Initial failure:

- `psycopg.ProgrammingError: cannot adapt type 'dict' using placeholder '%s'`

Root cause:

- `replace_source_staging_rows()` inserted Python `dict` / `list` values into `JSONB` columns without adaptation.

Fix:

- Added runtime detection of `json/jsonb` columns in `src/ingestion/repository.py`.
- Wrapped `dict` / `list` values with `psycopg.types.json.Jsonb`.

Re-run:

```bash
docker compose exec -T worker-dev python -m src.preprocessing.rawg_to_staging
```

Result:

- `stg.source_games`: `400`
- `stg.source_game_genres`: `937`
- `stg.source_game_platforms`: `1904`
- `stg.source_game_tags`: `7904`

### 4. Wikidata live ingestion attempt

Initial command:

```bash
make wikidata-identity
```

Observed failures across retries:

- `ReadTimeout`
- `429 Too Many Requests`
- `502 Bad Gateway`
- `504 Gateway Timeout`

Additional internal issues found during the attempt:

1. Repeated request hashes could collide in `meta.api_request_log`.
2. SPARQL query templates applied `LIMIT` too late, after expensive joins.
3. HTTP `5xx` responses could be logged but still let the job exit as success.

Fixes applied:

- `src/ingestion/repository.py`
  - `insert_started_request_log()` now uses conflict-safe upsert for repeated request hashes.
- `src/ingestion/wikidata_queries.py`
  - both named queries now limit the candidate game set in a subquery before label/alias expansion.
- `configs/sources.yaml`
  - Wikidata timeout raised from `10` to `90` seconds for first live runs.
- `src/ingestion/base_client.py`
  - HTTP `4xx/5xx` now raise after logging/caching, so jobs fail honestly.

Validation after the fixes:

```bash
docker compose exec -T worker-dev env WIKIDATA_DEMO_LIMIT=10 \
  python -m src.ingestion.jobs.load_wikidata_identity --query-name external_ids_sitelinks
```

Result:

- The job now fails explicitly on `HTTPStatusError: 504 Gateway Timeout`.
- This is the current first live-run stop-point.
- Invalid previously written `raw.wikidata_sparql_results` rows with `http_status >= 400` were removed from PostgreSQL.

Current Wikidata state after cleanup:

- `raw.wikidata_sparql_results`: `0`
- `raw.wikidata_entities`: `0`
- `stg.source_games` for `wikidata`: `0`

### 5. First downstream boundary check

Command:

```bash
docker compose exec -T worker-dev python -m src.preprocessing.match_external_ids
```

Result:

- Failed as expected with missing prerequisite:
  - `wikidata staging data`

This confirms that the current pipeline can progress through live RAWG ingestion, but it correctly stops before matching / ML-ready datasets when Wikidata ingestion is unavailable.

### 6. File export of the first live run

Initial issue:

- `data_packs/` was not mounted into `worker-dev`, so export landed only inside the container filesystem.

Fix:

- Added `./data_packs:/app/data_packs` to dev service volumes in `docker-compose.yml`.

Export command:

```bash
docker compose exec -T worker-dev python -m src.preprocessing.export_data_pack \
  --output data_packs/gip_first_live_run \
  --include-cache \
  --include-processed \
  --include-reports
```

Validation:

```bash
docker compose exec -T worker-dev python -m src.preprocessing.import_data_pack \
  --input data_packs/gip_first_live_run --dry-run

docker compose exec -T worker-dev python -m src.preprocessing.restore_from_files \
  --input data_packs/gip_first_live_run --dry-run
```

Result:

- Export directory exists on the host:
  - `data_packs/gip_first_live_run`
- Pack manifest and checksums exist:
  - `data_packs/gip_first_live_run/manifest.json`
  - `data_packs/gip_first_live_run/checksums.sha256`
- Dry-run import and dry-run restore both succeed.

Important note:

- `git_branch` and `git_commit` remain `null` in the manifest because the dev image does not contain the `git` binary. This does not block export/import, but it is still a reproducibility gap.

## Final state after the run

### PostgreSQL

- Live RAWG data is persisted in `raw` and normalized into `stg`.
- Invalid failed Wikidata raw rows were removed.
- API request logs preserve the history of both successful RAWG calls and failed Wikidata attempts.

### Files

- Saved first-run pack:
  - `data_packs/gip_first_live_run`
- The pack currently reflects a partial run:
  - RAWG data present
  - Wikidata data absent
  - downstream ML-ready outputs absent

### Stack

- Left running intentionally:
  - `postgres`
  - `app-dev`
  - `worker-dev`

## What is ready now

- Live RAWG ingestion to DB works.
- RAWG-to-staging transform works.
- File export/import/restore path works on the host.
- Wikidata failures are now explicit and do not silently poison `raw`.

## What is not finished yet

- Live Wikidata ingestion is not yet operational against `query.wikidata.org` under the current public endpoint behavior.
- Because of that, `external ID matching`, `candidate pairs`, `feature base`, `DQ`, and `ML-ready datasets` are not yet runnable on real combined source data.

## Recommended next attempt

1. Re-run Wikidata only, sequentially, during a quieter window:

```bash
docker compose exec -T worker-dev env WIKIDATA_DEMO_LIMIT=10 \
  python -m src.ingestion.jobs.load_wikidata_identity --query-name external_ids_sitelinks
```

2. If it succeeds, run:

```bash
docker compose exec -T worker-dev env WIKIDATA_DEMO_LIMIT=10 \
  python -m src.ingestion.jobs.load_wikidata_identity --query-name labels_aliases

docker compose exec -T worker-dev python -m src.preprocessing.wikidata_to_staging
docker compose exec -T worker-dev python -m src.preprocessing.match_external_ids
```

3. Only after valid Wikidata staging exists, continue to:

```bash
make candidate-pairs
make feature-base
make dq
make ml-ready-data
```
