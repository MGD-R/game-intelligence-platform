# Database Schema

This stage defines the SQL-first storage contract for ingestion, normalization, and early entity resolution work. No external API calls or data loads are performed here.

## Meta Layer

The `meta` schema keeps operational state that protects quotas and makes ingestion replayable:

- `meta.api_request_log` stores request hashes, response hashes, cache hits, timings, and error metadata.
- `meta.api_quota_usage` stores per-source quota counters by quota period.
- `meta.pipeline_run_log` stores pipeline/stage execution history and future run metrics.
- `meta.ingestion_checkpoint` stores resumable cursor/checkpoint state for source-specific jobs.

Request hashes and response hashes are the foundation for future cache-first ingestion. They let the worker detect repeated requests before spending API quota again and make it possible to map raw rows back to the originating request.

## Raw Layer

The `raw` schema preserves source payloads as `jsonb` without flattening them too early. Each table keeps technical audit columns such as:

- request hash
- source record id
- HTTP status
- cache flag
- response storage path
- error message

This allows later staging jobs to be deterministic and replayable while preserving the original source response contract.

## Staging Layer

The `stg` schema normalizes source-specific data into source-centered tables:

- base game records
- aliases
- external ids
- genres, tags, themes, and platforms
- companies and roles
- descriptions
- ratings and popularity metrics
- source URLs

Metrics remain source-specific at this stage. RAWG, Steam, IGDB, and Wikimedia values are intentionally not merged into one shared score yet.

## ML Preparation Layer

The `ml` schema includes only early preparation tables:

- `ml.entity_candidate_pairs`
- `ml.entity_resolution_features`

These tables define where blocking output and pairwise features will land. Model training, labels curation, and inference are intentionally out of scope for this stage.

## DM Layer

The `dm` schema contains placeholder canonical catalog tables:

- `dm.canonical_games`
- `dm.canonical_game_sources`
- `dm.canonical_game_aliases`
- `dm.canonical_game_external_ids`

They are created now so the target architecture is explicit, but they are not populated yet.

## Runtime Validation

The repository keeps the SQL definition twice on purpose:

- `sql/*/create_*.sql` as the readable layer-by-layer contract
- `docker/postgres/init/*.sql` as deterministic startup DDL for a fresh PostgreSQL volume

Use `make db-check` to validate that all required schemas and tables exist inside the running Docker PostgreSQL container.
