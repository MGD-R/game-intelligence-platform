# IGDB Name-Based Matching Research Plan

## Purpose

This plan describes the next research-oriented stage where `IGDB` is used not only as an `ID-based` enrichment source, but also as a `candidate source` for ML-driven entity resolution.

Target use case:

`RAWG/Wikidata record -> IGDB candidates by name/aliases -> feature model -> same_game_probability`

This is not meant to replace the current deterministic `RAWG <-> Wikidata` path. It is an advanced layer for:

- unmatched or weakly matched games;
- manual-review cases;
- ambiguous franchise titles, remasters, re-releases, and localizations;
- richer ML demonstrations beyond direct external-ID joins.

## Current State

Current full data snapshot:

- `rawg source games = 400`
- `wikidata source games = 385`
- `steam source games = 202`
- `wikipedia summaries = 697`
- `entity candidate pairs = 394`
- `entity resolution feature rows = 394`
- `igdb game count = 0`
- `wikidata igdb id count = 0`

Current implication:

- the project is ready for baseline ER research on `RAWG <-> Wikidata`;
- the project is not yet ready for real `IGDB` matching experiments because there are no live IGDB rows in staging.

## Research Goal

Demonstrate that `IGDB` can improve matching quality for difficult cases where:

- deterministic external IDs are absent;
- title normalization alone is insufficient;
- source metadata is conflicting or sparse;
- multilingual/localized names matter.

The expected result is a second ER lane:

1. deterministic lane:
   `RAWG <-> Wikidata` by external IDs and conservative heuristics
2. research lane:
   `RAWG/Wikidata -> IGDB search candidates -> ML scoring`

## Why IGDB Is Useful

Compared with the current MVP corpus, `IGDB` can add:

- `themes`
- `keywords`
- richer company roles
- localizations / alternate titles
- extra URLs and platform coverage
- additional rating or popularity-like signals

This is especially useful for:

- sequel chains;
- remasters vs originals;
- subtitle-heavy titles;
- regional/localized naming variants;
- records where `Wikipedia` text exists but canonical identity is still uncertain.

## Recommended Scope

Do not turn `IGDB` into a full discovery source.

Use it only for targeted subsets:

1. `RAWG` games unmatched after `Wikidata`
2. `manual_review` pairs from current ER outputs
3. high-value `RAWG` games:
   - high `rating_count`
   - high `playtime`
   - missing `RAWG` descriptions or companies
4. name-conflict cases:
   - similar titles with different years
   - titles with suffixes like `Definitive Edition`, `Remastered`, `Director's Cut`

## Data Prerequisites

Before implementing the IGDB ML lane, the dataset should be expanded.

### Minimum recommended corpus

- `RAWG source games`: `2,000+`
- `RAWG details`: `500-1,500`
- `Wikidata games`: `1,000+` or as many as the expanded RAWG slice can support
- `manual review seed`: at least `200+` meaningful ambiguous cases

### Better target for a convincing demo

- `RAWG source games`: `5,000-10,000`
- `RAWG details`: `1,500-3,000`
- `IGDB live rows`: at least `500+` targeted candidates
- labeled IGDB match examples: `300-1,000`

Without that scale, `IGDB` research is still possible, but the model evaluation will be weak.

## Loading Strategy

### Phase 1. Expand the existing core corpus

1. Increase `RAWG` discovery volume.
2. Run more targeted `RAWG details`.
3. Rebuild `Wikidata by RAWG`.
4. Refresh:
   - candidate pairs
   - feature base
   - DQ reports
   - ML-ready outputs

Reason:
`IGDB` research should sit on top of a broader and cleaner core corpus, not the current small MVP sample.

### Phase 2. Add IGDB search-based raw capture

Implement a new targeted search path:

- input:
  - `RAWG` title
  - aliases if available
  - release year
  - optional platform hints
- request:
  - IGDB `search` or APICalypse text query
- output:
  - top-k IGDB candidates per source record

Recommended new raw tables:

- `raw.igdb_search_results`
- optional `raw.igdb_search_request_groups`

Each raw search row should preserve:

- source record reference
- query text
- query filters
- rank position
- full returned IGDB payload fragment

### Phase 3. Normalize IGDB candidate staging

Recommended staging objects:

- `stg.source_games` rows for IGDB games
- `stg.source_game_aliases`
- `stg.source_game_external_ids`
- `stg.source_game_genres`
- `stg.source_game_tags`
- `stg.source_game_themes`
- `stg.source_game_platforms`
- `stg.source_game_companies`
- `stg.source_game_descriptions`
- `stg.source_game_urls`

Recommended additional candidate table:

- `ml.igdb_search_candidates`

Suggested columns:

- `source_name`
- `source_game_id`
- `candidate_source = 'igdb'`
- `igdb_id`
- `search_rank`
- `query_text`
- `query_strategy`
- `retrieved_at`

This table should be separate from final pair labels so retrieval quality can be audited independently.

## Candidate Generation Design

Use a two-step design.

### Step 1. Retrieval

Generate top-k IGDB candidates per source record.

Recommended strategies:

- exact title
- normalized title
- title without edition/remaster suffixes
- alias/title variants
- title + release year guard

Recommended `k`:

- start with `k = 5`
- expand to `k = 10` only if recall is poor

### Step 2. Pair materialization

Convert retrieved candidates into ER pairs:

- `RAWG -> IGDB`
- optionally `Wikidata -> IGDB`

Store them in either:

- `ml.entity_candidate_pairs`
- or a dedicated pre-pair table before promotion

## Feature Plan

This is the core ML-demonstration piece.

### Title and alias features

- normalized title similarity
- token sort ratio
- token set ratio
- prefix/suffix agreement
- subtitle overlap
- alias similarity
- localization title similarity

### Temporal features

- release year difference
- exact year match flag
- within-one-year flag

### Company features

- developer overlap
- publisher overlap
- any-company overlap

### Taxonomy features

- platform overlap
- genre overlap
- theme overlap
- keyword/tag overlap

### Description/text features

- description present flag
- short-text cosine similarity
- embedding cosine similarity, later stage

### Retrieval features

- IGDB search rank
- query strategy type
- candidate count for the query

### External-ID features

- whether candidate is later confirmed by another external source
- whether Steam/Wikipedia evidence is consistent

## Labeling Strategy

There are two viable approaches.

### Weak-label bootstrap

Use deterministic positives where available:

- future `Wikidata -> IGDB` IDs if they appear
- rare direct external links

Use conservative negatives:

- high name mismatch
- large year mismatch
- no company/platform overlap

This is fast but narrow.

### Manual-review dataset

Preferred for this research stage.

Build a labeled review set from:

- top-k IGDB search candidates for high-value games
- ambiguous pairs from current ER outputs
- intentional hard cases:
  - remasters
  - sequels
  - same franchise / different game

Recommended first labeled set:

- `300-500` labeled pairs minimum
- better: `800-1,500`

Class balance:

- positives: `30-50%`
- negatives: `50-70%`

This should be enough for:

- logistic regression baseline
- tree-based baseline
- ranking or calibration experiments later

## Model Plan

### Baseline 1. Rule scorer

Simple transparent score:

- high title similarity
- compatible year
- company/platform support
- low retrieval rank

Use this as a retrieval-quality benchmark.

### Baseline 2. Logistic Regression

Inputs:

- numeric/string-derived features above

Outputs:

- `same_game_probability`
- thresholded decision

Why:

- easy to explain
- good baseline for ML demo

### Baseline 3. Gradient boosting

Recommended next step:

- `CatBoost` or `LightGBM`

Why:

- handles mixed sparse features better
- often stronger for tabular ER tasks

### Optional later stage

- bi-encoder title/description embeddings
- cross-encoder reranking on top candidates

This is useful, but not necessary for the first demonstration.

## Evaluation Plan

Recommended metrics:

- retrieval recall@k
- precision@k
- pairwise precision
- pairwise recall
- F1
- PR-AUC
- calibration curve

Recommended splits:

- random split for first check
- franchise-aware split later
- year-stratified split if enough data exists

Important:

- evaluate retrieval separately from final classifier
- otherwise it is hard to tell whether failure comes from search or from matching

## Output Artifacts

Recommended new outputs:

- `data/processed/igdb_search_candidates.parquet`
- `data/processed/igdb_matching_training_dataset.parquet`
- `data/processed/igdb_matching_predictions.parquet`
- `data/artifacts/reports/igdb_candidate_recall.csv`
- `data/artifacts/reports/igdb_matching_metrics.json`
- `data/artifacts/reports/igdb_manual_review_queue.csv`

Recommended doc outputs:

- research note comparing:
  - no IGDB
  - IGDB ID-only
  - IGDB name-based ML

## Stop Conditions

Stop or postpone the stage if any of the following hold:

- no stable IGDB credentials/token behavior
- no usable targeted subset
- fewer than `100` meaningful labeled pairs
- corpus remains too small for evaluation
- search retrieval quality is so poor that classifier work is premature

## Recommended Next Implementation Order

1. Expand `RAWG` discovery and `RAWG details`.
2. Rebuild `Wikidata` targeted identity on the broader corpus.
3. Add `IGDB search results` raw capture.
4. Add `ml.igdb_search_candidates`.
5. Create a manual-review labeling slice.
6. Implement `IGDB matching feature base`.
7. Train logistic regression baseline.
8. Compare with rule baseline.
9. Only then consider tree models or embeddings.

## Bottom Line

`IGDB` name-based matching is a strong next-stage research topic for this project.

It is valuable because it demonstrates:

- candidate retrieval
- tabular entity-resolution features
- weak labels vs manual labels
- explainable ML scoring
- source fusion beyond deterministic IDs

But it should start only after:

- the core corpus is expanded;
- more `RAWG details` are loaded;
- a real IGDB subset is available;
- a small but credible labeled set exists.
