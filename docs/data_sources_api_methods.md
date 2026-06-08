# Data Sources and API Methods

- RAWG: discovery-oriented source for game metadata and search.
- Wikidata: identity hub for multilingual labels, aliases, and external identifiers.
- Steam: optional targeted enrichment after Wikidata IDs are available.
- Wikipedia: optional text enrichment for grounded explanations.
- IGDB: targeted/search enrichment path used for optional matching research and coverage.

Current ingestion clients use cache/logging, rate-limit controls, retries/timeouts where
implemented, and Makefile jobs for targeted source loading. Broad crawls are intentionally
avoided: RAWG drives discovery, Wikidata supplies identity/sitelinks, Steam and Wikipedia are
targeted enrichments, and IGDB is handled through ID-based and search-based lanes.

For defense/demo purposes, the FastAPI layer is read-only: it reads prepared PostgreSQL
tables and generated artifacts instead of calling external APIs online.
