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

## ER Graph Analysis

Graph analysis добавлен как отдельный risk-review слой поверх shadow merge strategies.
Он не меняет `dm.canonical_*`, а строит connected components и показывает, где merge
policy создает same-source conflicts, большие компоненты или ручные negative-пары внутри
одного компонента.

Текущий snapshot:

- `31,462` source records.
- `17,320` candidate pairs.
- `248` exported risky components across strategies.
- `28` high-probability reviewed negatives.

Ключевой результат:

| Strategy | Components | Multi-source | Max size | Same-source links | Risky components |
|---|---:|---:|---:|---:|---:|
| `canonical_v1_trusted` | `20,613` | `6,331` | `5` | `31` | `29` |
| `model_auto_090` | `23,441` | `5,854` | `5` | `31` | `30` |
| `model_auto_070_research` | `15,765` | `8,165` | `12` | `516` | `100` |
| `hybrid_safe_090` | `20,396` | `6,390` | `5` | `42` | `38` |

Defense interpretation:

- `model_auto_070_research` хорошо показывает transitive ER risk: высокий recall
  сопровождается резким ростом same-source duplicate links.
- `hybrid_safe_090` расширяет trusted graph аккуратнее, но все равно требует component-level
  risk review перед production merge.
- `high_probability_reviewed_negatives.csv` дает понятные примеры ошибок: remasters,
  sequels, editions, franchise/base-game cases.

## Lightweight Title Embedding Research

Embedding research lane добавлен без внешних загрузок моделей: используются локальные
TF-IDF/SVD title vectors и Logistic Regression. Это дает воспроизводимый способ показать,
что vector similarity может дополнять fuzzy title matching.

Текущий snapshot:

- Reviewed ER pairs used: `1,966`.
- Positive labels: `1,029`.
- Negative labels: `937`.
- Train/test split: `1,376` / `590`.
- Best model: `combined_name_embedding_year`.
- Best F1: `0.974026`.
- Error-case rows: `35`.

Сравнение моделей:

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| `combined_name_embedding_year` | `0.977199` | `0.970874` | `0.974026` | `0.989232` | `0.993470` |
| `word_tfidf_only` | `0.937500` | `0.970874` | `0.953895` | `0.963883` | `0.953786` |
| `embedding_stack` | `0.934579` | `0.970874` | `0.952381` | `0.965956` | `0.957829` |
| `name_similarity_only` | `0.931677` | `0.970874` | `0.950872` | `0.959610` | `0.945169` |

Defense interpretation:

- Lightweight embeddings improve the title-matching baseline without requiring
  sentence-transformer downloads.
- `embedding_error_cases.csv` is useful for explaining why embeddings still need manual
  review: remaster, sequel, edition and franchise titles remain difficult.
- This is a research feature lane; it does not change production canonical merge policy.

## IGDB-Specific Matching Analysis

IGDB теперь участвует как search-based candidate lane, а не только как источник по готовым
ID. Отдельный IGDB analysis показывает качество retrieval, ручную precision по rank/confidence
и enrichment coverage.

Текущий snapshot:

- `10,730` IGDB search candidates / candidate pairs.
- `10,344` staged IGDB games.
- `5,686` RAWG anchors with IGDB candidates.
- `1,637` reviewed IGDB pairs.
- Reviewed positives: `925`.
- Reviewed negatives: `712`.
- Overall reviewed precision: `0.565058`.
- High-risk reviewed negatives: `1`.
- Likely positive unreviewed candidates exported: `100`.

Rank-based reviewed precision:

| Rank bucket | Reviewed | Positive | Negative | Precision |
|---|---:|---:|---:|---:|
| `1` | `968` | `899` | `69` | `0.928719` |
| `2-3` | `439` | `23` | `416` | `0.052392` |
| `4-5` | `230` | `3` | `227` | `0.013043` |

IGDB enrichment coverage:

| Feature | Games | Coverage |
|---|---:|---:|
| `platforms` | `10,312` | `0.996906` |
| `descriptions` | `10,086` | `0.975058` |
| `genres` | `9,806` | `0.947989` |
| `urls` | `9,478` | `0.916280` |
| `companies` | `8,841` | `0.854698` |
| `themes` | `8,470` | `0.818832` |
| `aliases` | `6,663` | `0.644142` |
| `tags` | `6,352` | `0.614076` |
| `ratings` | `6,160` | `0.595514` |

Defense interpretation:

- Rank-1 IGDB search candidates are strong; lower ranks are mostly negative under current
  reviewed sampling.
- IGDB is valuable for enrichment because descriptions, platforms, genres, companies and
  themes are broadly populated.
- IGDB search should be controlled by rank/confidence/manual review/model scoring, not used
  as blind auto-merge.

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
- Presentation-ready SVG charts are generated under
  `data/artifacts/reports/ml_research_defense/charts/`.

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

## Bayesian Rating Analysis

Bayesian rating добавлен как вторичный research/statistics блок. Он сравнивает naive
weighted source rating и Bayesian-adjusted rating, чтобы показать, как можно снижать
риск переоценки игр с малым числом голосов.

Текущий snapshot:

- `24,344` vote-backed rating inputs из RAWG/IGDB rating rows.
- `14,468` canonical games with Bayesian ratings.
- Global weighted mean: `78.527138`.
- Prior votes: `50.0`.
- Total vote count: `2,803,272`.

Метод:

```text
bayesian_rating = (votes * naive_rating + prior_votes * global_mean)
                  / (votes + prior_votes)
```

Интерпретация для защиты:

- Naive rating полезен как прямой сигнал источников, но он шумный при малом числе голосов.
- Bayesian adjustment сдвигает маловотные high/low outliers к global mean и делает ranking
  устойчивее.
- Этот блок не заменяет recommendation model: он демонстрирует отдельную ML/statistics
  задачу ранжирования игр поверх canonical catalog.

Generated artifacts:

- `data/artifacts/reports/bayesian_rating/bayesian_rating_summary.json`
- `data/artifacts/reports/bayesian_rating/bayesian_rating_summary.md`
- `data/artifacts/reports/bayesian_rating/rating_source_summary.csv`
- `data/artifacts/reports/bayesian_rating/canonical_bayesian_ratings.csv`
- `data/artifacts/reports/bayesian_rating/low_vote_shrinkage_examples.csv`
- `data/artifacts/reports/bayesian_rating/top_bayesian_ratings.svg`

## What To Demonstrate On Defense

1. Data pipeline scale: source coverage, candidate pairs, manual labels, canonical games.
2. Manual review workflow: зачем нужны positive и negative labels.
3. ER model: features, weighted labels, metrics, threshold policy.
4. Merge strategies: почему model auto-merge нельзя слепо включать в canonical.
5. Error analysis: remaster, DLC, edition, franchise cases.
6. Graph analysis: same-source conflicts и transitive risk в merge components.
7. Lightweight embeddings: прирост TF-IDF/SVD title vectors над fuzzy-only baseline.
8. IGDB-specific matching: rank-based retrieval quality и enrichment coverage.
9. Active learning: как модель предлагает следующие пары для разметки.
10. Recommendations: explainable content baseline и его ограничения.
11. Bayesian rating: почему naive source ratings нужно корректировать числом голосов.
12. Next research directions: neural embeddings, calibration improvement,
   grounded RAG explanations.

## Runtime Artifacts

Generated by:

```bash
make ml-research-defense
make er-graph-analysis
make er-embedding-research
make igdb-matching-analysis
make bayesian-rating
```

Main outputs:

- `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`
- `data/artifacts/reports/ml_research_defense/ablation_study.csv`
- `data/artifacts/reports/ml_research_defense/calibration_bins.csv`
- `data/artifacts/reports/ml_research_defense/active_learning_candidates.csv`
- `data/artifacts/reports/ml_research_defense/defense_demo_cases.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_examples.csv`
- `data/artifacts/reports/ml_research_defense/recommendation_score_distribution.csv`
- `data/artifacts/reports/ml_research_defense/charts/ablation_f1.svg`
- `data/artifacts/reports/ml_research_defense/charts/calibration_bins.svg`
- `data/artifacts/reports/ml_research_defense/charts/merge_strategy_f1.svg`
- `data/artifacts/reports/ml_research_defense/charts/recommendation_score_distribution.svg`
- `data/artifacts/reports/graph_analysis/graph_analysis_summary.json`
- `data/artifacts/reports/graph_analysis/graph_strategy_summary.csv`
- `data/artifacts/reports/graph_analysis/risky_components.csv`
- `data/artifacts/reports/graph_analysis/high_probability_reviewed_negatives.csv`
- `data/artifacts/reports/graph_analysis/same_source_duplicate_links.svg`
- `data/artifacts/reports/embedding_research/embedding_research_summary.json`
- `data/artifacts/reports/embedding_research/embedding_model_comparison.csv`
- `data/artifacts/reports/embedding_research/embedding_threshold_eval.csv`
- `data/artifacts/reports/embedding_research/embedding_error_cases.csv`
- `data/artifacts/reports/embedding_research/embedding_model_f1.svg`
- `data/artifacts/reports/igdb_matching/igdb_matching_summary.json`
- `data/artifacts/reports/igdb_matching/igdb_review_precision_by_rank.csv`
- `data/artifacts/reports/igdb_matching/igdb_enrichment_coverage.csv`
- `data/artifacts/reports/igdb_matching/igdb_high_risk_reviewed_negatives.csv`
- `data/artifacts/reports/igdb_matching/igdb_rank_distribution.svg`
