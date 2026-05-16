## Wikipedia Summaries

Wikipedia is used as a text enrichment source, not as the main source of truth for entity resolution.

### Why Sitelinks Come From Wikidata

- Wikidata already stores `ruwiki` and `enwiki` sitelinks for known game entities.
- This keeps Wikipedia usage deterministic and bounded to records already seen in the identity hub.
- It avoids broad title search and accidental ambiguity at the enrichment stage.

### Why Opensearch Is Disabled

- Open search is noisy for game titles and expansions.
- The MVP prefers direct page loading from known sitelinks.
- A fallback action API path can exist, but it is not the default behavior.

### User-Agent Requirement

- Wikimedia requests must include `WIKIMEDIA_USER_AGENT`.
- Logs and dry-run output redact the private value.

### Main Commands

```bash
make wikipedia-check
make wikipedia-pages
make wikipedia-load
make wikipedia-staging
make wikipedia-demo
```

Safe local previews:

```bash
python -m src.ingestion.jobs.select_wikipedia_pages --dry-run --limit 10
python -m src.ingestion.jobs.load_wikipedia_pages --dry-run --limit 1
python -m src.preprocessing.wikipedia_to_staging --dry-run
```

### Tables Populated

Raw:

- `raw.wikipedia_pages`

Staging:

- `stg.source_game_descriptions`
- `stg.source_game_urls`
- `stg.source_game_external_ids`

### Attribution and Source Preservation

- Summary text is stored with language and source URL.
- Page URL is preserved from `content_urls.desktop.page`.
- QID linkage is retained through `stg.source_game_external_ids` with `external_source='wikidata'`.

### What Is Not Loaded Yet

- broad search or discovery;
- opensearch by default;
- full page extracts/history/revisions/images beyond summary URL metadata;
- any RAG generation or explanation logic.

### Known Limitations

- Wikipedia enrichment depends on prior Wikidata sitelinks in staging.
- Summary coverage is only as good as the available `ruwiki` and `enwiki` links.
- Some pages may have short or missing extracts; the stage records that coverage but does not synthesize text.
