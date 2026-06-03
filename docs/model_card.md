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

Embeddings are intentionally not part of this baseline. They are planned as the next
research extension.

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

- Add multilingual title/description embeddings.
- Add calibration plots and threshold governance to the presentation notebook.
- Improve IGDB-specific candidate quality and alias coverage.
- Tune Bayesian rating prior and add grounded RAG explanations as secondary research tracks.
