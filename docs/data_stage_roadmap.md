# Data Stage Roadmap

This roadmap defines the historical safe execution order for the first data-stage
implementation work. The project has since progressed through data loading, ER, canonical
catalog construction, recommendations, explanations, and defense-demo API readiness.

1. Stage 1: project hygiene and environment fixation.
2. Stage 2: Docker and PostgreSQL bootstrap.
3. Stage 3: raw/meta/staging database schema.
4. Stage 4: common ingestion framework with request cache, `request_hash`, rate limits, retries, and quota control.
5. Stage 5: RAWG ingestion with reference endpoints, games index, and targeted details only after data quality checks.
6. Stage 6: Wikidata ingestion through SPARQL as an identity hub with ru/en labels, aliases, external IDs, and Wikipedia sitelinks.
7. Stage 7: deterministic external-ID matching and candidate corpus creation.
8. Stage 8: staging normalization and data quality reports.
9. Stage 9: optional Steam targeted enrichment by Steam AppID.
10. Stage 10: optional Wikipedia summaries by Wikidata sitelinks.
11. Stage 11: optional IGDB batch enrichment by Wikidata IGDB IDs.
12. Stage 12: ML-ready dataset export to PostgreSQL tables and Parquet snapshots.
13. Stage 13: pre-API download readiness verification, data-pack restore hardening, and first live-run planning.

Historical data-stage goal:

- stop before ML training;
- prepare stable datasets for analysis, feature engineering, and future entity resolution;
- avoid mass API loading until cache, retry, and quota controls are implemented.

Historical first-run readiness guidance:

- first controlled live download should use RAWG + Wikidata only;
- Steam and Wikipedia should remain optional targeted enrichment after the MVP baseline is verified;
- IGDB should stay disabled by default until dry-run checks and a tiny live-check are explicitly approved;
- every first live run should finish with `make export-data-pack` so the contour can be restored without spending API quota again.

Current status:

- read-only FastAPI demo endpoints are implemented;
- ER/recommendation/RAG/Bayesian/IGDB research artifacts are available;
- defense readiness is tracked in [final_plan_gap_analysis_ru.md](final_plan_gap_analysis_ru.md)
  and [final_defense_smoke_checklist_ru.md](final_defense_smoke_checklist_ru.md).
