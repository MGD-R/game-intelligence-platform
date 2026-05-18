# IGDB Enrichment

IGDB is an optional advanced enrichment source. It is not used for first-pass discovery and stays disabled by default.

## Role

- targeted detail enrichment after RAWG + Wikidata;
- themes, keywords, companies, localizations, external links, and extra rating signals;
- ID source: Wikidata property `P9043` mapped into `stg.source_game_external_ids`.
- search-based candidate source for advanced `RAWG -> IGDB` matching when `P9043` is absent.

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
make igdb-search-seeds
make igdb-search
make igdb-search-candidates
make igdb-search-demo
make igdb-demo
```

Dry-run-safe paths:

```bash
python -m src.ingestion.igdb_client --check --dry-run
python -m src.ingestion.jobs.select_igdb_ids --dry-run --limit 10
python -m src.ingestion.jobs.select_igdb_search_seeds --dry-run --limit 10
python -m src.ingestion.jobs.load_igdb_games --dry-run --limit 1
python -m src.ingestion.jobs.load_igdb_search --dry-run --limit 1
python -m src.preprocessing.igdb_to_staging --dry-run
python -m src.preprocessing.igdb_search_to_candidates --dry-run
```

## Tables

Raw:

- `raw.igdb_games`
- `raw.igdb_reference_data`
- `raw.igdb_search_results`

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

ML candidate audit:

- `ml.igdb_search_candidates`

## Search-Based Lane

The new search lane uses the current `RAWG` corpus as the anchor set instead of crawling a separate global IGDB universe.

Flow:

1. select `RAWG` seeds from staging;
2. enrich the seed queries with linked Wikidata aliases when available;
3. run targeted IGDB search requests and cache the returned candidate payloads;
4. stage the returned IGDB games through the normal `raw.igdb_games -> stg.*` path;
5. normalize retrieval evidence into `ml.igdb_search_candidates`;
6. optionally promote those rows into `ml.entity_candidate_pairs` for later feature building.

`make igdb-search-demo` runs the promotion step automatically.

This keeps IGDB auditable as a retrieval source before it is trusted as a full match source.

## Limitations

- IGDB is scaffolded for dry-run validation and targeted batch loading by IDs.
- Search-based matching is intentionally conservative and retrieval-first. It does not auto-merge records by itself.
- It is still optional and not part of default `make demo-data`.
- First live download should still start with RAWG + Wikidata, then data quality, then optional enrichments.
- IGDB should only be enabled after `make igdb-check` and an explicitly approved tiny live-check confirm that credentials, token flow, and quota behavior are stable.

## Research Extension

The current integration treats IGDB as an optional ID-based enrichment source. A separate next-stage plan for `name-based` and metadata-based ML matching is documented here:

- [IGDB ML matching research plan](igdb_ml_matching_research_plan.md)

That plan covers:

- when IGDB should be used as a targeted search source instead of a broad crawler;
- what additional raw/staging structures are needed for search candidates;
- which matching features and labels are recommended for an ML demonstration;
- what corpus size is sufficient for a meaningful experiment.
