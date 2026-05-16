# Ingestion Framework

This stage adds the reusable ingestion foundation that future RAWG, Wikidata, Steam, Wikipedia, and IGDB jobs must reuse.

## Why Request Cache Exists

External APIs are rate-limited and some of them have strict monthly quotas. The framework writes redacted response cache files to:

`data/raw/cache/<source>/<request_hash>.json`

Re-running the same logical request reuses the cached response unless `--force-refresh` is explicitly passed.

## How Request Hash Prevents Duplicate API Calls

`src.ingestion.request_hash` builds a deterministic hash from:

- source
- HTTP method
- normalized URL
- normalized query params
- request body

Authentication-only secrets are redacted before hashing, so rotating an API key does not create a different logical request hash.

## How Raw Response Files Are Stored

Each cache file stores:

- source
- endpoint
- request hash
- created timestamp
- HTTP status
- response payload
- response hash
- redacted request metadata

These files are local runtime artifacts and must never be committed.

## How Database Logging Works

The framework uses `meta.api_request_log` for request start/finish tracking and cache-hit visibility. It also writes:

- `meta.api_quota_usage`
- `meta.pipeline_run_log`
- `meta.ingestion_checkpoint`

Database logging failures do not hide the API response, but they are surfaced as warnings.

## How Quota Tracking Works

Quota checks happen before the network request. The current stage implements reusable monthly quota protection for RAWG through `RAWG_MONTHLY_LIMIT`.

After a successful uncached request, usage is recorded in `meta.api_quota_usage`.

## Safe Checks

Local-only source validation:

```bash
python -m src.ingestion.check_sources --no-network
make check-sources
```

This verifies config loading, known env var names, cache path resolution, source enable flags, and database URL presence without printing secrets.

## Minimal Network Checks

Minimal opt-in checks:

```bash
python -m src.ingestion.check_sources --network --limit 1
make check-sources-network
```

Use them only when local secrets are configured and only for tiny requests.

## Reuse Contract

Future source-specific clients and ingestion jobs must reuse:

- `BaseAPIClient`
- request hashing
- response cache
- redaction helpers
- rate limiter
- quota helpers
- repository and pipeline logging helpers
