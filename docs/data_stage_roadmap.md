# Data Stage Roadmap

This roadmap defines the safe execution order for the first data-stage implementation work.

1. Docker and PostgreSQL bootstrap stabilization.
2. Data storage schema confirmation for `raw`, `stg`, `ml`, `dm`, `meta`.
3. Ingestion framework with request cache, quota tracking, and retries.
4. RAWG ingestion implementation with low-volume validation.
5. Wikidata ingestion implementation with low-volume validation.
6. External ID matching between source records.
7. Staging normalization and data quality checks.
8. Optional Steam enrichment through targeted external IDs only.
9. Optional Wikipedia summaries through grounded sitelinks.
10. Optional IGDB enrichment after MVP ingestion is stable.
11. ML-ready dataset export for downstream entity resolution and recommendation work.

Current non-goals for this stage:

- mass API loading;
- model training;
- embedding generation;
- RAG execution;
- Airflow adoption.
