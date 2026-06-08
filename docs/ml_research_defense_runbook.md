# ML Research Defense Runbook

## Purpose

This runbook is the practical defense script for the current ML research stage. It
uses the existing ER-first strong baseline and generated artifacts. The goal is to
show a coherent ML/data-product story, not just isolated model metrics.

## Pre-Demo Checklist

Run these commands before the defense rehearsal:

```bash
make er-merge-strategy-comparison
make er-graph-analysis
make er-embedding-research
make igdb-matching-analysis
make ml-research-defense
make bayesian-rating
make rag-explanations
make ml-defense-readiness
make ml-defense-presentation
```

For a full rehearsal rebuild, use:

```bash
make ml-defense-all
```

Expected generated artifacts:

- `data/artifacts/reports/entity_resolution/merge_strategies/merge_strategy_comparison.csv`
- `data/artifacts/reports/entity_resolution/merge_strategies/model_auto_merge_candidates.csv`
- `data/artifacts/reports/graph_analysis/graph_strategy_summary.csv`
- `data/artifacts/reports/graph_analysis/risky_components.csv`
- `data/artifacts/reports/graph_analysis/high_probability_reviewed_negatives.csv`
- `data/artifacts/reports/embedding_research/embedding_model_comparison.csv`
- `data/artifacts/reports/embedding_research/embedding_error_cases.csv`
- `data/artifacts/reports/igdb_matching/igdb_matching_summary.json`
- `data/artifacts/reports/igdb_matching/igdb_review_precision_by_rank.csv`
- `data/artifacts/reports/igdb_matching/igdb_enrichment_coverage.csv`
- `data/artifacts/reports/rag_explanations/match_explanation_examples.csv`
- `data/artifacts/reports/rag_explanations/recommendation_explanation_examples.csv`
- `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`
- `data/artifacts/reports/ml_research_defense/ablation_study.csv`
- `data/artifacts/reports/ml_research_defense/calibration_bins.csv`
- `data/artifacts/reports/ml_research_defense/defense_demo_cases.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_examples.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_score_distribution.csv`
- `data/artifacts/reports/ml_research_defense/charts/ablation_f1.svg`
- `data/artifacts/reports/ml_research_defense/charts/calibration_bins.svg`
- `data/artifacts/reports/ml_research_defense/charts/merge_strategy_f1.svg`
- `data/artifacts/reports/ml_research_defense/charts/recommendation_score_distribution.svg`
- `data/artifacts/reports/graph_analysis/same_source_duplicate_links.svg`
- `data/artifacts/reports/embedding_research/embedding_model_f1.svg`
- `data/artifacts/reports/igdb_matching/igdb_rank_distribution.svg`
- `data/artifacts/reports/igdb_matching/igdb_enrichment_coverage.svg`
- `data/artifacts/reports/bayesian_rating/bayesian_rating_summary.md`
- `data/artifacts/reports/bayesian_rating/canonical_bayesian_ratings.csv`
- `data/artifacts/reports/bayesian_rating/low_vote_shrinkage_examples.csv`
- `data/artifacts/reports/bayesian_rating/top_bayesian_ratings.svg`
- `data/artifacts/reports/ml_defense_readiness/ml_defense_readiness_report.md`
- `data/artifacts/reports/ml_defense_readiness/ml_defense_metric_snapshot.csv`
- `data/artifacts/reports/ml_defense_readiness/ml_defense_demo_sequence.csv`
- `data/artifacts/reports/ml_defense_readiness/ml_defense_artifact_checklist.csv`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_presentation_outline.md`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_slide_outline.csv`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_speaker_notes.md`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_remaining_steps.csv`

Open for presentation:

- `docs/presentations/game-intelligence-ml-defense.pptx`
- `notebooks/03_ml_research_defense_report.ipynb`
- `docs/ml_research_findings.md`
- `docs/model_card.md`
- `data/artifacts/reports/rag_explanations/rag_explanation_examples.md`
- `data/artifacts/reports/ml_defense_readiness/ml_defense_readiness_report.md`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_presentation_outline.md`
- `data/artifacts/reports/ml_defense_presentation/ml_defense_speaker_notes.md`

## Demo Flow

### 1. Project Framing

Message:

> The project is an end-to-end ML/data product: multiple game data sources are
> normalized into staging, transformed into candidate pairs, manually reviewed,
> scored by an ER model, merged into a canonical catalog, and then used for
> explainable recommendations.

Evidence:

- `docs/ml_research_findings.md`
- `ml_research_defense_summary.json`

Key current counts:

- `31,462` source records.
- `17,320` ER candidate pairs.
- `1,966` reviewed manual labels.
- `20,613` canonical games.
- `147,254` recommendation rows.

### 2. Data Quality And Why ER Is Needed

Message:

> Raw source records are incomplete and sometimes conflicting, so direct joins by
> title are unsafe. DQ findings explain why manual review and conservative
> thresholds are required.

Show:

- source coverage;
- field completeness;
- conflict examples;
- anomaly examples: editions, DLCs, remasters, QID-like labels.

Evidence:

- `data/artifacts/reports/dq_summary.json`
- `field_completeness_by_source.csv`
- `conflict_report.csv`
- `anomaly_report.csv`

### 3. Manual Review As Supervision

Message:

> The model needs both positive and negative labels. Negative labels are
> especially important because games from the same franchise or remaster line can
> look very similar but still be different entities.

Show:

- manual positives: exact or equivalent records;
- manual negatives: franchise, remaster, edition and DLC ambiguity.

Evidence:

- `ml.entity_resolution_manual_reviews`
- `data/artifacts/reports/entity_resolution/entity_resolution_manual_review_reviewed.csv`

### 4. ER Model And Metrics

Message:

> The baseline is intentionally explainable: Logistic Regression over tabular
> similarity features with sample weighting for manual labels and weak positives.

Metrics to state:

- Precision: `0.983242`.
- Recall: `0.916455`.
- F1: `0.948675`.
- ROC-AUC: `0.957274`.
- PR-AUC: `0.994369`.
- Brier score: `0.080893`.

Evidence:

- `data/artifacts/reports/entity_resolution/metrics.json`
- `data/artifacts/reports/entity_resolution/iterations/metrics_v3c_weak005.json`
- `notebooks/03_ml_research_defense_report.ipynb`

### 5. Thresholds And Merge Strategy Comparison

Message:

> The model is useful, but blind model-only auto-merge is not the right production
> policy. The safe approach is trusted canonical edges plus controlled model
> candidates for review or hybrid extension.

Show strategy comparison:

- `canonical_v1_trusted`: production-safe baseline.
- `model_auto_095`: high precision, too low recall.
- `model_auto_090`: useful high-confidence candidate lane.
- `model_auto_070_research`: strong recall, but false positives and risky clusters.
- `hybrid_safe_090`: promising controlled-hybrid path.

Evidence:

- `merge_strategy_comparison.csv`
- `merge_strategy_summary.md`
- `model_auto_merge_candidates.csv`

### 6. Ablation And Calibration

Message:

> Ablation shows which feature groups matter. Name and alias similarity are the
> core signal today; sparse metadata has less effect. Calibration helps choose
> thresholds responsibly.

Show:

- `without_name` quality drop;
- probability distribution for positive vs negative labels;
- calibration bins and Brier score.

Evidence:

- `ablation_study.csv`
- `calibration_bins.csv`
- `probability_distribution.csv`
- `charts/ablation_f1.svg`
- `charts/calibration_bins.svg`

### 7. ER Graph Analysis

Message:

> Entity Resolution errors are transitive: one bad edge can pull several records into
> the same canonical component. Graph analysis makes this risk visible before any
> production canonical merge policy is changed.

Show:

- strategy-level component counts;
- same-source duplicate links;
- risky components;
- high-probability reviewed negatives.

Current snapshot:

- `248` risky components exported across strategies.
- `28` high-probability reviewed negatives.
- `model_auto_070_research`: `516` same-source duplicate links.
- `hybrid_safe_090`: `42` same-source duplicate links.

Evidence:

- `graph_strategy_summary.csv`
- `risky_components.csv`
- `high_probability_reviewed_negatives.csv`
- `same_source_duplicate_links.svg`

### 8. Lightweight Title Embedding Research

Message:

> Before using heavy neural embeddings, the project tests a reproducible local
> embedding-style baseline: TF-IDF/SVD title vectors. This shows whether vector
> similarity adds value over fuzzy name similarity.

Show:

- model comparison table;
- threshold evaluation;
- embedding error cases;
- F1 chart.

Current snapshot:

- `1,966` reviewed pairs.
- Best model: `combined_name_embedding_year`.
- Best F1: `0.974026`.
- `name_similarity_only` F1: `0.950872`.
- Error-case rows: `35`.

Evidence:

- `embedding_model_comparison.csv`
- `embedding_threshold_eval.csv`
- `embedding_error_cases.csv`
- `embedding_model_f1.svg`

### 9. IGDB-Specific Matching Analysis

Message:

> IGDB is now a real search-based ER candidate source. Rank and confidence analysis
> show where IGDB retrieval is reliable and where lower-rank candidates should be
> treated as manual-review or negative examples.

Show:

- candidate and RAWG anchor counts;
- reviewed precision by IGDB search rank;
- enrichment coverage;
- high-risk reviewed negatives and likely positives.

Current snapshot:

- `10,730` IGDB search candidates.
- `10,344` staged IGDB games.
- `5,686` RAWG anchors with IGDB candidates.
- `1,637` reviewed IGDB pairs.
- Rank-1 reviewed precision: `0.928719`.
- Rank 2-3 reviewed precision: `0.052392`.

Evidence:

- `igdb_matching_summary.json`
- `igdb_review_precision_by_rank.csv`
- `igdb_enrichment_coverage.csv`
- `igdb_high_risk_reviewed_negatives.csv`
- `igdb_rank_distribution.svg`

### 10. Active Learning Casebook

Message:

> The model can drive the next manual-review iteration by selecting ambiguous or
> high-impact pairs.

Show examples:

- `Super Time Force` vs `Super Time Force Ultra`;
- `Quake III Arena` vs `Quake III: Team Arena`;
- `Remnant 2` vs `Remnant II`.

Evidence:

- `active_learning_candidates.csv`
- `defense_demo_cases.csv`

### 11. Recommendations As Secondary ML Block

Message:

> The recommendation layer is currently a content-based explainable baseline. It
> is useful for demonstrating the downstream value of canonical data, but it is
> not collaborative filtering because there are no user interactions.

Show:

- recommendation coverage;
- score distribution;
- shared-feature explanation examples;
- limitations where shared metadata creates high score but weak user value.

Evidence:

- `recommendation_examples.csv`
- `recommendation_score_distribution.csv`
- `charts/recommendation_score_distribution.svg`
- `dm.game_recommendations`

### 12. Bayesian Rating As Secondary Statistics Block

Message:

> Naive source ratings are useful but biased toward games with few votes. Bayesian
> adjustment shrinks low-vote outliers toward the global mean and gives a more
> stable ranking signal for canonical games.

Show:

- top Bayesian-adjusted games;
- low-vote shrinkage examples;
- source rating coverage by source/rating type;
- formula and prior choice.

Current snapshot:

- `24,344` vote-backed rating inputs.
- `14,468` canonical games with Bayesian ratings.
- Global weighted mean: `78.527138`.
- Prior votes: `50.0`.

Evidence:

- `bayesian_rating_summary.md`
- `canonical_bayesian_ratings.csv`
- `low_vote_shrinkage_examples.csv`
- `top_bayesian_ratings.svg`

### 13. Grounded RAG Explanations

Message:

> RAG/LLM is not used to decide matches or recommendations. The explanation layer
> only renders computed facts: ER features, model scores, manual labels, canonical
> facts and recommendation shared features.

Show:

- Russian match explanations;
- Russian recommendation explanations;
- grounded fact cards;
- grounding policy.

Current snapshot:

- `25` balanced match explanations.
- `25` recommendation explanations.
- `50` grounded fact cards.

Evidence:

- `rag_explanation_summary.json`
- `match_explanation_examples.csv`
- `recommendation_explanation_examples.csv`
- `grounded_fact_cards.csv`
- `rag_explanation_examples.md`

## Questions To Be Ready For

| Question | Short answer |
|---|---|
| Why not use model auto-merge directly? | Because ER errors are costly and transitive in canonical clusters; model outputs should be governed by thresholds and manual review. |
| Why are negative labels needed? | They teach the model franchise/remaster/DLC boundaries and prevent similar titles from being merged blindly. |
| Why graph analysis? | It reveals component-level and transitive merge risks that pair-level metrics can hide. |
| Why lightweight embeddings? | They show the value of vector similarity without requiring non-reproducible external model downloads. |
| Why IGDB analysis? | It proves IGDB search quality is rank-dependent and shows which enrichment fields justify keeping IGDB in the corpus. |
| Why Logistic Regression? | It is interpretable, fast, reproducible and sufficient for a strong baseline before neural embeddings. |
| Is recommendation ML complete? | It is a content-based baseline. Collaborative filtering is out of scope without user interaction data. |
| Why Bayesian rating? | It reduces ranking noise from low-vote source ratings and demonstrates a separate statistical ML block on top of canonical data. |
| Why RAG is safe here? | It only explains already computed facts; it does not decide matches, merges or recommendations. |
| What is next? | Multilingual neural embeddings, calibrated thresholds and optional LLM rendering over grounded facts. |

## Final Defense Claim

The strongest current claim:

> The project demonstrates a reproducible ML entity-resolution workflow with
> manual supervision, threshold governance, canonical catalog construction and
> downstream explainable recommendations. The model is not used as an unchecked
> source of truth; it is used as a controlled decision-support layer.
