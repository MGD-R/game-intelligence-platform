# ML Research Defense Runbook

## Purpose

This runbook is the practical defense script for the current ML research stage. It
uses the existing ER-first strong baseline and generated artifacts. The goal is to
show a coherent ML/data-product story, not just isolated model metrics.

## Pre-Demo Checklist

Run these commands before the defense rehearsal:

```bash
make er-merge-strategy-comparison
make ml-research-defense
```

Expected generated artifacts:

- `data/artifacts/reports/entity_resolution/merge_strategies/merge_strategy_comparison.csv`
- `data/artifacts/reports/entity_resolution/merge_strategies/model_auto_merge_candidates.csv`
- `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`
- `data/artifacts/reports/ml_research_defense/ablation_study.csv`
- `data/artifacts/reports/ml_research_defense/calibration_bins.csv`
- `data/artifacts/reports/ml_research_defense/defense_demo_cases.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_examples.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_score_distribution.csv`

Open for presentation:

- `notebooks/03_ml_research_defense_report.ipynb`
- `docs/ml_research_findings.md`
- `docs/model_card.md`

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

### 7. Active Learning Casebook

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

### 8. Recommendations As Secondary ML Block

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
- `dm.game_recommendations`

## Questions To Be Ready For

| Question | Short answer |
|---|---|
| Why not use model auto-merge directly? | Because ER errors are costly and transitive in canonical clusters; model outputs should be governed by thresholds and manual review. |
| Why are negative labels needed? | They teach the model franchise/remaster/DLC boundaries and prevent similar titles from being merged blindly. |
| Why Logistic Regression? | It is interpretable, fast, reproducible and sufficient for a strong baseline before embeddings. |
| Is recommendation ML complete? | It is a content-based baseline. Collaborative filtering is out of scope without user interaction data. |
| What is next? | Multilingual embeddings, better IGDB candidate quality, calibrated thresholds, Bayesian rating and grounded RAG explanations. |

## Final Defense Claim

The strongest current claim:

> The project demonstrates a reproducible ML entity-resolution workflow with
> manual supervision, threshold governance, canonical catalog construction and
> downstream explainable recommendations. The model is not used as an unchecked
> source of truth; it is used as a controlled decision-support layer.
