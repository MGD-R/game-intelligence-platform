# ML Research Findings

## Executive Summary

Проект готов к защите как **end-to-end ML/data product** с центральным исследованием
Entity Resolution. Уже есть достаточный корпус для strong baseline:

- `31,462` source records в staging: RAWG, Wikidata, Steam, IGDB.
- `17,320` ER candidate pairs.
- `1,966` reviewed manual labels: `1,029` positive и `937` negative.
- `20,613` canonical games.
- `147,254` baseline content recommendations.

Главный вывод: ML-модель не должна автоматически заменять trusted canonical logic. Она
лучше всего работает как **scoring/manual-review/controlled-hybrid layer**: помогает
приоритизировать спорные пары, оценивать риск auto-merge и расширять canonical catalog
после дополнительных проверок.

## Entity Resolution Results

Текущая weighted Logistic Regression `v3c` использует manual labels с весом `1.0`,
weak positives с весом `0.05` и показывает сильный baseline:

| Metric | Value |
|---|---:|
| Precision | `0.983242` |
| Recall | `0.916455` |
| F1 | `0.948675` |
| ROC-AUC | `0.957274` |
| PR-AUC | `0.994369` |
| Brier score | `0.080893` |

Manual-review holdout показывает, что модель хорошо отделяет positives и negatives, но
порог auto-merge должен быть консервативным:

| Threshold | Interpretation |
|---|---|
| `0.95` | Очень высокая precision, но почти нет recall; подходит только для самых безопасных auto-merge. |
| `0.90` | Хороший слой для model candidates и ручной проверки. |
| `0.70` | Research-only режим: высокий recall, но появляются false positives и risky clusters. |

## Merge Strategy Comparison

Shadow comparison не меняет `dm.canonical_*`, но показывает, что произойдёт при разных
merge-политиках:

| Strategy | Edges | Precision | Recall | F1 | Key interpretation |
|---|---:|---:|---:|---:|---|
| `canonical_v1_trusted` | `6,012` | `0.998060` | `1.000000` | `0.999029` | Текущий production-safe слой. |
| `model_auto_095` | `18` | `1.000000` | `0.013605` | `0.026846` | Слишком консервативно для расширения каталога. |
| `model_auto_090` | `3,183` | `1.000000` | `0.403304` | `0.574792` | Полезно как очередь high-confidence model candidates. |
| `model_auto_070_research` | `10,880` | `0.967022` | `0.968902` | `0.967961` | Хорошо для исследования риска, но не для production merge. |
| `hybrid_safe_090` | `6,229` | `0.998060` | `1.000000` | `0.999029` | Перспективный controlled-hybrid слой, но требует анализа same-source conflicts. |

## Ablation Study

Проверка “что будет, если убрать группы признаков” показывает, что название/alias -
ключевой источник качества, а часть metadata-признаков пока слабо влияет из-за
разреженности:

| Scenario | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| `all_features` | `0.983242` | `0.916455` | `0.948675` | `0.957274` |
| `without_name` | `0.959716` | `0.882673` | `0.919584` | `0.864896` |
| `without_year` | `0.981161` | `0.926989` | `0.953306` | `0.930256` |
| `without_companies` | `0.983236` | `0.916092` | `0.948477` | `0.957459` |
| `without_taxonomy` | `0.985530` | `0.915365` | `0.949153` | `0.956070` |
| `without_source_signal` | `0.987708` | `0.904831` | `0.944455` | `0.953876` |

Defense interpretation: текущая модель в первую очередь решает title/alias matching,
а дальнейший рост качества должен идти через richer aliases, better IGDB/Wikidata
metadata и embeddings.

## Error Analysis And Demo Cases

Successful merges:

| A | B | Probability |
|---|---|---:|
| Timelie | Timelie | `0.963393` |
| Super Killer Hornet: Resurrection | Super Killer Hornet: Resurrection | `0.962442` |
| Desert Ashes | Desert Ashes | `0.959803` |

Rejected / risky matches:

| A | B | Probability | Why useful |
|---|---|---:|---|
| The Jackbox Party Pack 4 | The Jackbox Party Pack | `0.838165` | Franchise/base-vs-sequel ambiguity. |
| BioShock Remastered | BioShock 2 Remastered | `0.829243` | Remaster names are similar but entities differ. |
| Crysis 2 Remastered | Crysis 3 Remastered | `0.825533` | Same series, different game. |

Active-learning candidates for next manual review:

| A | B | Probability | Bucket |
|---|---|---:|---|
| Super Time Force | Super Time Force Ultra | `0.500549` | High uncertainty. |
| Quake III Arena | Quake III: Team Arena | `0.500612` | Expansion/base-game ambiguity. |
| Remnant 2 | Remnant II | `0.500723` | Naming variant candidate. |

Generated casebook:

- `defense_demo_cases.csv` combines successful merges, rejected risky matches,
  active-learning candidates and recommendation examples.
- This file is intended as the live defense script: it gives concrete records to discuss
  without searching the database during presentation.

## Recommendations Baseline

`content_jaccard_v1` построен как explainable baseline без user interactions:

- `147,254` recommendation rows.
- `16,500` canonical games with recommendations.
- Score range: `0.150000` - `1.000000`.
- Average score: `0.374520`.
- Score distribution is generated in `recommendation_score_distribution.csv`.
- Curated recommendation examples are generated in `recommendation_examples.csv`.

Ограничение для защиты: это content-based recommender, а не collaborative filtering.
Некоторые примеры с высоким score выявляют ограничения feature baseline: e-reader cards,
однотипные платформы и QID-like names могут давать формально высокую похожесть, но слабую
пользовательскую ценность. Это хороший аргумент для следующего этапа: embeddings,
better canonical quality filters и richer recommendation features.

## What To Demonstrate On Defense

1. Data pipeline scale: source coverage, candidate pairs, manual labels, canonical games.
2. Manual review workflow: зачем нужны positive и negative labels.
3. ER model: features, weighted labels, metrics, threshold policy.
4. Merge strategies: почему model auto-merge нельзя слепо включать в canonical.
5. Error analysis: remaster, DLC, edition, franchise cases.
6. Active learning: как модель предлагает следующие пары для разметки.
7. Recommendations: explainable content baseline и его ограничения.
8. Next research directions: embeddings, calibration improvement, IGDB-specific matching,
   Bayesian rating, grounded RAG explanations.

## Runtime Artifacts

Generated by:

```bash
make ml-research-defense
```

Main outputs:

- `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`
- `data/artifacts/reports/ml_research_defense/ablation_study.csv`
- `data/artifacts/reports/ml_research_defense/calibration_bins.csv`
- `data/artifacts/reports/ml_research_defense/active_learning_candidates.csv`
- `data/artifacts/reports/ml_research_defense/defense_demo_cases.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_examples.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_score_distribution.csv`
