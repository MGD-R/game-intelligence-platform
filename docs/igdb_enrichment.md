# IGDB Enrichment

IGDB is an optional advanced enrichment source. It is not used for first-pass discovery and stays disabled by default.

## Role

- targeted detail enrichment after RAWG + Wikidata;
- themes, keywords, companies, localizations, external links, and extra rating signals;
- ID source: Wikidata property `P9043` mapped into `stg.source_game_external_ids`.

## Why Disabled By Default

- IGDB requires Twitch OAuth2 client-credentials flow;
- it is quota-constrained and should not run before the core RAWG + Wikidata contour is stable;
- this repository currently provides a dry-run-safe scaffold and staging transform, not a default live ingestion path.

## Auth

Primary env vars:

- `IGDB_CLIENT_ID`
- `IGDB_CLIENT_SECRET`

Fallback env vars:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`

Dry-run never requests a token:

```bash
python -m src.ingestion.igdb_auth --dry-run
```

## Request Model

- API base: `https://api.igdb.com/v4`
- token endpoint: `https://id.twitch.tv/oauth2/token`
- request style: `POST` + APICalypse query body
- limits in current scaffold:
  - `4` requests/sec
  - `max 8` concurrent requests
  - `max 500` IDs per request

## Commands

```bash
make igdb-check
make igdb-ids
make igdb-reference
make igdb-games
make igdb-staging
make igdb-demo
```

Dry-run-safe paths:

```bash
python -m src.ingestion.igdb_client --check --dry-run
python -m src.ingestion.jobs.select_igdb_ids --dry-run --limit 10
python -m src.ingestion.jobs.load_igdb_games --dry-run --limit 1
python -m src.preprocessing.igdb_to_staging --dry-run
```

## Tables

Raw:

- `raw.igdb_games`
- `raw.igdb_reference_data`

Staging:

- `stg.source_games`
- `stg.source_game_aliases`
- `stg.source_game_external_ids`
- `stg.source_game_genres`
- `stg.source_game_tags`
- `stg.source_game_themes`
- `stg.source_game_platforms`
- `stg.source_game_companies`
- `stg.source_game_descriptions`
- `stg.source_game_ratings`
- `stg.source_game_popularity`
- `stg.source_game_urls`

## Limitations

- IGDB is scaffolded for dry-run validation and targeted batch loading by IDs.
- It is still optional and not part of default `make demo-data`.
- First live download should still start with RAWG + Wikidata, then data quality, then optional enrichments.
