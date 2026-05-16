## Steam Enrichment

Steam is used as a targeted enrichment source, not as the primary discovery source for the MVP.

### Why Steam AppIDs Come From Wikidata

- Wikidata already acts as the identity hub for cross-source external IDs.
- This keeps Steam usage narrow and deterministic.
- It prevents accidental broad Steam catalog scans.

### Why Store Appdetails Is Primary

- `store.steampowered.com/api/appdetails` is public and sufficient for MVP enrichment.
- It returns names, descriptions, genres, categories, developers, publishers, platforms, store URLs, recommendations, and metacritic snippets.
- Partner-only endpoints are not required for the current stage.

### Safety Defaults

- Full Steam app-list loading is disabled by default.
- Partner endpoints are disabled by default.
- `steam-details` only loads AppIDs already selected from Wikidata staging external IDs.
- Cache is used unless `--force-refresh` is explicitly passed.
- Steam `403` responses are treated as permanent and are not retried in a loop.

### Main Commands

```bash
make steam-check
make steam-appids
make steam-details
make steam-staging
make steam-demo
```

Safe local previews:

```bash
python -m src.ingestion.jobs.select_steam_appids --dry-run --limit 10
python -m src.ingestion.jobs.load_steam_details --dry-run --limit 1
python -m src.preprocessing.steam_to_staging --dry-run
```

### Tables Populated

Raw:

- `raw.steam_app_details`

Staging:

- `stg.source_games`
- `stg.source_game_genres`
- `stg.source_game_tags`
- `stg.source_game_platforms`
- `stg.source_game_companies`
- `stg.source_game_descriptions`
- `stg.source_game_ratings`
- `stg.source_game_popularity`
- `stg.source_game_urls`
- `stg.source_game_external_ids`

### What Is Not Loaded Yet

- full Steam app list by default;
- partner-only endpoints;
- achievements, reviews, screenshots, packages, DLC graph expansion;
- any recommendation, embedding, or RAG logic.

### Known Limitations

- Steam enrichment depends on prior Wikidata staging that already contains Steam AppIDs.
- Localized Steam release dates can be partially parsed; when exact day-month parsing is not reliable, only `release_year` is preserved.
- The current stage enriches only selected AppIDs and does not attempt broad reconciliation outside the existing identity graph.
