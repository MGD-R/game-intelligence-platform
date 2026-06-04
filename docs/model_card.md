# Model Card: Entity Resolution Baseline

## Model Purpose

The primary ML model estimates whether two source records describe the same video game:

```text
pair(source_game_a, source_game_b) -> same_game_probability
```

The model supports:

- manual review prioritization;
- threshold analysis;
- safe canonical merge research;
- explainable defense demos.

It does **not** directly overwrite `dm.canonical_*`. Production canonical tables remain based
on trusted deterministic and manual-positive edges unless explicitly changed.

## Data

Current research snapshot:

- Source records in staging: `31,462`.
- Candidate pairs: `17,320`.
- Manual reviewed labels: `1,966`.
- Manual positives: `1,029`.
- Manual negatives: `937`.
- Canonical games: `20,613`.

Training frame:

- Total rows: `7,817`.
- Positive labels: `6,881`.
- Negative labels: `936`.
- Label sources: manual review + weak external-ID positives.

## Features

Numeric feature groups:

- title and alias similarity;
- release-year difference;
- external-ID exact match;
- developer and publisher overlap;
- platform, genre and tag Jaccard similarity;
- description availability and language flags;
- source-count signal.

Neural embeddings are intentionally not part of the production baseline. A separate
lightweight research lane now evaluates local TF-IDF/SVD title vectors against fuzzy
title similarity.

## Model

Baseline model:

- Logistic Regression;
- median imputation;
- balanced class weights;
- sample weights:
  - manual review: `1.0`;
  - weak positive: `0.05`;
  - synthetic negative: `0.5`.

Decision thresholds:

- `>= 0.95`: auto-merge candidate;
- `0.70-0.95`: manual review;
- `< 0.70`: no merge.

## Metrics

Weighted baseline `v3c`:

| Metric | Value |
|---|---:|
| Precision | `0.983242` |
| Recall | `0.916455` |
| F1 | `0.948675` |
| ROC-AUC | `0.957274` |
| PR-AUC | `0.994369` |
| Brier score | `0.080893` |

Manual threshold analysis shows:

- `0.95` is safe but too conservative for broad catalog expansion.
- `0.90` is useful for high-confidence review candidates.
- `0.70` is research-only because false positives and risky clusters appear.

## Known Limitations

- Weak positives dominate the training data, so manual labels are explicitly weighted.
- Metadata features are sparse; title and alias features currently carry most signal.
- Remasters, editions, DLCs and franchise titles remain high-risk cases.
- Some source records still contain QID-like or low-quality names.
- Recommendations are content-based only and do not use user interaction data.
- Pair-level metrics do not fully capture transitive graph risk; component-level analysis is
  required before any model-assisted production merge policy.

## Secondary Research Block: Bayesian Rating

The project also includes a lightweight Bayesian rating analysis for canonical games.
This is not an Entity Resolution model and does not change canonical merges.

Purpose:

- compare naive source ratings with vote-adjusted ratings;
- reduce ranking noise from games with very few votes;
- demonstrate an additional interpretable ML/statistics method for the defense.

Current generated snapshot:

- Rating inputs: `24,344`.
- Canonical games with vote-backed ratings: `14,468`.
- Global weighted mean: `78.527138`.
- Prior votes: `50.0`.

Formula:

```text
bayesian_rating = (votes * naive_rating + prior_votes * global_mean)
                  / (votes + prior_votes)
```

Known limitations:

- Source ratings are not equally calibrated across RAWG and IGDB.
- Vote counts can be source-specific and may not represent the same user population.
- The default prior `50` is a research setting and should be tuned before production use.

## Secondary Research Block: Lightweight Title Embeddings

The project includes a reproducible title embedding experiment based on local TF-IDF/SVD
vectors. It does not download sentence-transformer or other external neural models.

Current generated snapshot:

- Reviewed pairs: `1,966`.
- Positive labels: `1,029`.
- Negative labels: `937`.
- Best model: `combined_name_embedding_year`.
- Best F1: `0.974026`.
- `name_similarity_only` F1: `0.950872`.

Purpose:

- compare vector similarity with fuzzy title similarity;
- demonstrate the value of embedding-style features for ER;
- collect high-risk remaster/edition/franchise error cases for manual review.

Known limitations:

- TF-IDF/SVD title vectors are not semantic multilingual neural embeddings.
- The experiment uses reviewed ER pairs only and does not change canonical merge policy.
- External neural embeddings remain a future research extension.

## Source-Specific Research Block: IGDB Matching

The project includes an IGDB search-based matching analysis. This evaluates IGDB as a
candidate source and enrichment source, not as a blind canonical merge authority.

Current generated snapshot:

- IGDB search candidates: `10,730`.
- Staged IGDB games: `10,344`.
- RAWG anchors with IGDB candidates: `5,686`.
- Reviewed IGDB pairs: `1,637`.
- Reviewed positives: `925`.
- Reviewed negatives: `712`.
- Rank-1 reviewed precision: `0.928719`.
- Rank 2-3 reviewed precision: `0.052392`.

Purpose:

- evaluate search-rank-dependent retrieval quality;
- identify high-risk IGDB false positives;
- measure IGDB enrichment coverage across descriptions, platforms, genres, companies,
  themes, aliases, tags and ratings.

Known limitations:

- Reviewed precision reflects the current manual-review sampling strategy and is not a
  random-sample estimate of full IGDB retrieval quality.
- Lower-rank candidates are useful as negative/ambiguous examples, not as auto-merge inputs.
- IGDB search candidates must still go through ER scoring and manual-review governance.

## Secondary Research Block: Grounded RAG Explanations

The project includes a grounded explanation layer for match and recommendation examples.
It does not use an LLM to decide matches, merges or recommendations.

Current generated snapshot:

- Match explanations: `25`.
- Recommendation explanations: `25`.
- Grounded fact cards: `50`.
- Language: `ru`.

Grounding policy:

- Match explanations use computed ER features, model predictions and manual labels.
- Recommendation explanations use canonical facts and shared recommendation features.
- LLM generation, if added later, must only render these facts and must not introduce new
  decision evidence.

Known limitations:

- Current explanations are template-based, not interactive RAG chat.
- The explanation quality depends on feature quality and canonical fact quality.
- Generated examples are for defense/demo analysis and do not replace model evaluation.

## Intended Use

Recommended:

- prioritize manual review;
- compare threshold policies;
- generate research candidates;
- explain why canonical auto-merge should be controlled.

Not recommended:

- blind model-only canonical merge;
- treating `same_game_probability` as ground truth;
- using `model_auto_070_research` as production merge policy.

## Next Steps

- Add multilingual neural title/description embeddings.
- Add calibration plots and threshold governance to the presentation notebook.
- Improve IGDB-specific candidate quality and alias coverage.
- Use graph analysis outputs to review same-source duplicate components before expanding
  canonical merge policy.
- Use IGDB rank/confidence analysis to tune candidate retrieval and manual-review sampling.
- Tune Bayesian rating prior and optionally add LLM rendering over grounded RAG facts.
