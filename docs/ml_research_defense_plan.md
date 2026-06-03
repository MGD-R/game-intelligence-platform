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

4. **Recommendations as secondary ML block**
   - Использовать `content_jaccard_v1` как explainable baseline.
   - Показать coverage, score distribution и shared-feature explanations.
   - Зафиксировать ограничение: нет user interactions, значит это не collaborative filtering.

5. **Defense artifacts**
   - `docs/ml_research_findings.md`.
   - `docs/ml_research_defense_runbook.md`.
   - `docs/model_card.md`.
   - `notebooks/03_ml_research_defense_report.ipynb`.
   - `defense_demo_cases.csv` для live-сценария защиты.
   - `recommendation_score_distribution.csv` для анализа baseline-рекомендаций.
   - SVG-графики для презентации: ablation, calibration, merge strategies,
     recommendation score distribution.
   - Runtime artifacts:
     `data/artifacts/reports/ml_research_defense/`.

## Reproducible Commands

```bash
make er-merge-strategy-comparison
make ml-research-defense
```

Direct module command:

```bash
python -m src.entity_resolution.build_research_defense_artifacts
```

## Assumptions

- Production `dm.canonical_*` не меняется модельными auto-merge без отдельного решения.
- Основной фокус - объяснимый ER baseline и сильный research narrative.
- Heavy embeddings/RAG/Bayesian rating остаются следующими направлениями.
- Сгенерированные data artifacts остаются вне Git.
