# Wikidata Ingestion

Wikidata is the MVP identity hub for deterministic matching across sources. This stage loads bulk SPARQL identity data, stores raw responses, and transforms the results into reusable staging tables.

## What It Loads

- external IDs for RAWG (`P9968`), Steam (`P1733`), and IGDB (`P9043`)
- Russian and English labels
- Russian and English aliases
- Russian and English Wikipedia sitelinks
- targeted EntityData payloads for explicitly requested QIDs

## Safety Model

- `make wikidata-check` performs a dry-run request preview only
- `make wikidata` runs the safe demo pipeline and does not call EntityData
- `make wikidata-entities` is targeted only and defaults to `--limit 0`
- request metadata uses header redaction so `WIKIMEDIA_USER_AGENT` is not printed

## Main Commands

```bash
make wikidata-check
make wikidata-identity
make wikidata-entities
make wikidata-staging
make wikidata
```

## Populated Tables

- `raw.wikidata_sparql_results`
- `raw.wikidata_entities`
- `stg.source_games`
- `stg.source_game_aliases`
- `stg.source_game_external_ids`
- `stg.source_game_urls`

## Idempotency

The Wikidata staging transform follows the same full source rebuild convention as RAWG: rows for `source='wikidata'` are deleted and re-inserted per table. This keeps the MVP deterministic while preserving stable uniqueness constraints.

## What Is Not Loaded Yet

- broad per-QID EntityData backfills
- Wikipedia article content
- Steam/Wikipedia/IGDB enrichment workflows
- entity resolution, recommendations, or RAG
