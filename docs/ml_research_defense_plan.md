# ML Research Defense Roadmap

## Summary

Основной фокус ближайшего цикла: **ER-first / Strong baseline / Notebook+report**.

Цель: превратить уже собранные данные, manual review, ER-модель, canonical catalog и
baseline-рекомендации в связное ML-исследование для защиты. Акцент делается не на одной
модели, а на end-to-end ML/data product:

```text
source data -> DQ -> candidate pairs -> manual review -> ER model
-> canonical catalog -> recommendations -> explainable research report
```

## Work Stages

1. **Baseline state**
   - Зафиксировать counts по `stg`, `ml`, `dm`.
   - Сохранить статистику manual review, model decisions, canonical layer и рекомендаций.
   - Подготовить единый notebook `notebooks/03_ml_research_defense_report.ipynb`.

2. **Entity Resolution research**
   - Сравнить rule baseline, Logistic Regression и weighted training `v3c`.
   - Показать threshold policy: `0.50`, `0.70`, `0.90`, `0.95`.
   - Добавить error analysis по false positives/false negatives.
   - Использовать merge strategy comparison:
     `canonical_v1_trusted`, `model_auto_095`, `model_auto_090`,
     `model_auto_070_research`, `hybrid_conservative_095`, `hybrid_safe_090`.

3. **Research analytics without heavy models**
   - Ablation study по группам признаков.
   - Calibration analysis: Brier score, probability bins, label distributions.
   - Active learning simulation для следующих manual-review кандидатов.
   - Data-quality impact через source coverage, missingness, conflicts и risky cases.
   - Graph analysis: connected components, same-source conflicts, source bridge edges,
     risky clusters and high-probability reviewed negatives.
   - Lightweight title embeddings: TF-IDF/SVD cosine similarities and Logistic Regression
     comparison against fuzzy `name_similarity`.
   - IGDB-specific matching analysis: retrieval rank precision, query strategies,
     high-risk negatives and enrichment coverage.

4. **Recommendations as secondary ML block**
   - Использовать `content_jaccard_v1` как explainable baseline.
   - Показать coverage, score distribution и shared-feature explanations.
   - Зафиксировать ограничение: нет user interactions, значит это не collaborative filtering.
   - Дополнить secondary ML/statistics блоком `Bayesian rating`: сравнить naive
     weighted ratings и Bayesian-adjusted ratings для canonical games с малым и большим
     числом голосов.

5. **Defense artifacts**
   - `docs/ml_research_findings.md`.
   - `docs/ml_research_defense_runbook.md`.
   - `docs/model_card.md`.
   - `notebooks/03_ml_research_defense_report.ipynb`.
   - `defense_demo_cases.csv` для live-сценария защиты.
   - `recommendation_score_distribution.csv` для анализа baseline-рекомендаций.
   - `graph_strategy_summary.csv`, `risky_components.csv`,
     `high_probability_reviewed_negatives.csv` и `same_source_duplicate_links.svg`
     для анализа transitive ER risk.
   - `embedding_model_comparison.csv`, `embedding_threshold_eval.csv`,
     `embedding_error_cases.csv` и `embedding_model_f1.svg` для title embedding
     research lane.
   - `igdb_matching_summary.json`, `igdb_review_precision_by_rank.csv`,
     `igdb_enrichment_coverage.csv` и `igdb_rank_distribution.svg` для IGDB
     search-lane analysis.
   - `bayesian_rating_summary.md`, `canonical_bayesian_ratings.csv`,
     `low_vote_shrinkage_examples.csv` и `top_bayesian_ratings.svg` для демонстрации
     naive-vs-Bayesian ranking.
   - SVG-графики для презентации: ablation, calibration, merge strategies,
     recommendation score distribution.
   - Runtime artifacts:
     `data/artifacts/reports/ml_research_defense/`.

## Reproducible Commands

```bash
make er-merge-strategy-comparison
make er-graph-analysis
make er-embedding-research
make igdb-matching-analysis
make ml-research-defense
make bayesian-rating
```

Direct module command:

```bash
python -m src.entity_resolution.build_research_defense_artifacts
python -m src.entity_resolution.build_graph_analysis
python -m src.entity_resolution.build_embedding_research
python -m src.entity_resolution.build_igdb_matching_analysis
python -m src.recommendations.build_bayesian_rating_analysis
```

## Assumptions

- Production `dm.canonical_*` не меняется модельными auto-merge без отдельного решения.
- Основной фокус - объяснимый ER baseline и сильный research narrative.
- Heavy neural embeddings/RAG остаются следующими направлениями; lightweight TF-IDF/SVD
  title embeddings and Bayesian rating реализованы как secondary research lanes.
- Сгенерированные data artifacts остаются вне Git.
