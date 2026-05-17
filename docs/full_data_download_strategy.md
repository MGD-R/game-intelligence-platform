# Full Data Download Strategy

This runbook defines the safe path from MVP-ready contour to larger API-backed downloads without triggering broad or uncontrolled ingestion.

## Current readiness

- Default MVP discovery remains `RAWG`.
- Default MVP identity matching path is targeted `Wikidata by RAWG`.
- `Steam`, `Wikipedia`, and `IGDB` remain optional enrichments and must not be part of the first full-scale run.
- The contour is ready for controlled API execution, but every larger run should end with a data-pack export so the raw snapshot can be replayed without repeating network work.

## Safe execution order

1. `make check-sources-network`
2. `make rawg-reference`
3. `make rawg-index`
4. `make rawg-details`
5. `make rawg-staging`
6. `make wikidata-by-rawg`
7. `make wikidata-staging`
8. `make match-external-ids`
9. `make candidate-pairs`
10. `make feature-base`
11. `make staging`
12. `make dq`
13. `make anomalies`
14. `make export-analysis`
15. `make ml-ready-data`
16. `make export-data-pack`

## Why this path is the default

- `wikidata-by-rawg` constrains Wikidata calls to already discovered RAWG games.
- This avoids the previous broad `wikidata-demo` pattern that is too aggressive for a first or quota-sensitive run.
- `rawg-details` is intentionally separated from `rawg-index`; run it only when the index snapshot is stable and quotas are acceptable.

## What not to run by default

- Do not start with `steam-demo`, `wikipedia-demo`, or `igdb-demo`.
- Do not use broad Wikidata identity scans as the default recovery path.
- Do not rerun expensive API stages when the same snapshot can be restored from `data_packs/`.

## Operational guidance

- Keep limits small when validating a new API key or a changed source config.
- Export a data pack after each meaningful successful run so DB and file-based recovery stay aligned.
- If a stage fails after raw tables were written, fix the issue first and prefer replay from DB or restored files instead of repeating the same network load.
