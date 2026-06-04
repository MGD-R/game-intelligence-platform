# Game Intelligence Platform: подробная аналитика проекта

## 1. Краткое резюме

`Game Intelligence Platform` - это учебная end-to-end data/ML-платформа для сбора,
нормализации, сопоставления и дальнейшего использования данных о видеоиграх из нескольких
внешних источников.

Проект не ограничивается ML-моделью. ML-исследования являются центральной аналитической
частью, но вся система шире:

1. подключение внешних API;
2. безопасная загрузка и кеширование сырых ответов;
3. PostgreSQL-хранилище с DWH-подобными слоями;
4. нормализация данных в staging;
5. data quality и anomaly reports;
6. entity resolution для объединения записей из разных источников;
7. canonical catalog;
8. рекомендации;
9. grounded RAG/explanation layer;
10. FastAPI/Docker/Makefile-инфраструктура;
11. notebook/report/deck для защиты результатов.

Текущее состояние: платформа готова к демонстрации как исследовательский data/ML product.
Основной production-safe слой canonical catalog не меняется моделью вслепую. ML используется
как scoring/manual-review/controlled-hybrid layer.

Ключевые текущие числа:

| Блок | Значение |
|---|---:|
| Source records в staging | `31,462` |
| ER candidate pairs | `17,320` |
| Reviewed manual labels | `1,966` |
| Manual positives | `1,029` |
| Manual negatives | `937` |
| Canonical games | `20,613` |
| Canonical source links | `35,607` |
| Recommendation rows | `147,254` |
| ER weighted baseline F1 | `0.948675` |
| Lightweight embedding best F1 | `0.974026` |
| IGDB rank-1 reviewed precision | `0.928719` |
| Grounded explanation examples | `50` |

Готовые связанные документы:

- [README.md](../README.md)
- [docs/architecture.md](architecture.md)
- [docs/database_schema.md](database_schema.md)
- [docs/ml_research_findings.md](ml_research_findings.md)
- [docs/model_card.md](model_card.md)
- [docs/ml_research_defense_runbook.md](ml_research_defense_runbook.md)
- [docs/ml_defense_remaining_steps.md](ml_defense_remaining_steps.md)

Готовые notebook:

- [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb)
- [notebooks/entity_resolution_training_report.ipynb](../notebooks/entity_resolution_training_report.ipynb)

Готовая презентация:

- [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx)

## 2. Из чего состоит проект

### 2.1. Инфраструктура

Основной runtime:

- Docker Compose;
- PostgreSQL;
- FastAPI app;
- worker container для ingestion/preprocessing/ML jobs;
- Makefile как единая точка запуска пайплайнов.

См.:

- [docs/deployment_environment.md](deployment_environment.md)
- [docs/docker_db_bootstrap.md](docker_db_bootstrap.md)
- [README.md](../README.md)

Ключевые команды:

```bash
make up-dev
make db-check
make check-sources
make ml-ready-data
make er-baseline
make ml-defense-all
```

### 2.2. Хранилище

PostgreSQL организован по слоям:

| Слой | Назначение |
|---|---|
| `meta` | request log, quota usage, pipeline logs, checkpoints |
| `raw` | исходные JSON/API payloads и технические признаки загрузки |
| `stg` | нормализованные source-centered таблицы |
| `ml` | candidate pairs, features, labels, predictions, manual review |
| `dm` | canonical catalog, canonical source links, recommendations |

См.:

- [docs/database_schema.md](database_schema.md)

### 2.3. Источники данных

| Источник | Роль в системе |
|---|---|
| RAWG | широкий discovery/index источник, стартовая база игр |
| Wikidata | identity hub: QID, external IDs, aliases, sitelinks |
| Steam | targeted enrichment по Steam AppID |
| Wikipedia | текстовые summary для grounded explanations |
| IGDB | search-based candidate lane и enrichment источник |

См.:

- [docs/data_sources_api_methods.md](data_sources_api_methods.md)
- [docs/rawg_ingestion.md](rawg_ingestion.md)
- [docs/wikidata_ingestion.md](wikidata_ingestion.md)
- [docs/steam_enrichment.md](steam_enrichment.md)
- [docs/wikipedia_summaries.md](wikipedia_summaries.md)
- [docs/igdb_enrichment.md](igdb_enrichment.md)
- [docs/igdb_ml_matching_research_plan.md](igdb_ml_matching_research_plan.md)

### 2.4. Data pipeline

Пайплайн устроен так:

```text
External APIs
-> raw storage/cache/logging
-> staging normalization
-> DQ/anomaly reports
-> external ID matching
-> candidate pairs
-> feature base
-> manual review
-> ER model/predictions
-> canonical catalog
-> recommendations
-> grounded explanations
-> reports/notebooks/deck/API
```

См.:

- [docs/ingestion_framework.md](ingestion_framework.md)
- [docs/staging_data_quality.md](staging_data_quality.md)
- [docs/ml_ready_datasets.md](ml_ready_datasets.md)
- [docs/external_id_matching.md](external_id_matching.md)

## 3. Что было сделано

### 3.1. Bootstrap и инфраструктура

Сделано:

- создана структура проекта;
- настроены Docker Compose services;
- поднят PostgreSQL с нужными схемами;
- создан FastAPI skeleton;
- добавлены Makefile-команды для всех этапов;
- настроены `.env.example`, `.env.secrets.example`;
- добавлены базовые smoke tests и code quality checks.

Что важно: проект запускается как локальный reproducible contour. Команды пайплайна
выполняются через worker container, а не зависят от случайного Python окружения на машине.

### 3.2. Ingestion и загрузка данных

Реализованы ingestion-клиенты и jobs для:

- RAWG discovery/details;
- Wikidata targeted queries by RAWG;
- Steam targeted enrichment;
- Wikipedia targeted summaries;
- IGDB search/details/staging.

Реализованы:

- request cache;
- request logging;
- quota usage tracking;
- retries/timeouts;
- source-specific rate-limit hardening;
- data-pack export/import/restore dry-run.

См.:

- [docs/full_data_download_strategy.md](full_data_download_strategy.md)
- [docs/full_data_download_report.md](full_data_download_report.md)
- [docs/pre_api_download_readiness.md](pre_api_download_readiness.md)

### 3.3. Staging и ML-ready данные

Сделано:

- нормализованы source games;
- вынесены aliases, external IDs, genres/tags/platforms/companies/descriptions/ratings;
- построены candidate pairs;
- построена feature base;
- сформированы parquet snapshots;
- сформированы DQ/anomaly reports;
- подготовлена manual review queue.

См.:

- [docs/ml_ready_datasets.md](ml_ready_datasets.md)
- [docs/staging_data_quality.md](staging_data_quality.md)

### 3.4. Entity Resolution и canonical catalog

Сделано:

- построены weak labels по deterministic external IDs;
- создана таблица ручных проверок `ml.entity_resolution_manual_reviews`;
- добавлена view для анализа review-кандидатов;
- проведена ручная разметка положительных и отрицательных пар;
- обучен baseline ER model;
- построены predictions;
- построены threshold reports;
- построен canonical catalog;
- проведено сравнение merge strategies.

См.:

- [docs/entity_resolution_baseline.md](entity_resolution_baseline.md)
- [docs/manual_review_workflow.md](manual_review_workflow.md)
- [docs/model_card.md](model_card.md)
- [notebooks/entity_resolution_training_report.ipynb](../notebooks/entity_resolution_training_report.ipynb)

### 3.5. Рекомендации и объяснения

Сделано:

- построен content-based recommender `content_jaccard_v1`;
- сформировано `147,254` recommendation rows;
- добавлен Bayesian rating analysis;
- добавлен grounded RAG explanation layer;
- сформированы русскоязычные match/recommendation explanations.

См.:

- [docs/ml_research_findings.md](ml_research_findings.md)
- [docs/model_card.md](model_card.md)

### 3.6. Research/readiness/reporting слой

Сделано:

- `make ml-research-defense`;
- `make er-graph-analysis`;
- `make er-embedding-research`;
- `make igdb-matching-analysis`;
- `make bayesian-rating`;
- `make rag-explanations`;
- `make ml-defense-readiness`;
- `make ml-defense-presentation`;
- `make ml-defense-all`.

Готовы:

- единый research report;
- model card;
- runbook;
- notebook;
- slide outline;
- PPTX deck.

См.:

- [docs/ml_research_defense_plan.md](ml_research_defense_plan.md)
- [docs/ml_research_findings.md](ml_research_findings.md)
- [docs/ml_research_defense_runbook.md](ml_research_defense_runbook.md)
- [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb)
- [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx)

## 4. Какие данные получены и как

### 4.1. Текущий staging snapshot

| Source | Source games |
|---|---:|
| IGDB | `10,344` |
| RAWG | `10,039` |
| Wikidata | `6,263` |
| Steam | `4,816` |
| Total | `31,462` |

Интерпретация:

- RAWG дал широкий discovery corpus.
- Wikidata дал identity layer и external IDs.
- Steam дал targeted enrichment по найденным Steam AppID.
- IGDB стал полноценным search-based candidate/enrichment источником.
- Wikipedia используется как текстовый слой для summaries/explanations, а не как source of truth
  для identity.

### 4.2. Candidate pairs

| Candidate source | Rows |
|---|---:|
| `igdb_search` | `10,730` |
| `external_id` | `6,263` |
| `same_release_year_and_similar_name` | `204` |
| `same_normalized_name` | `123` |
| Total | `17,320` |

Интерпретация:

- `external_id` пары - наиболее надежная deterministic база.
- `igdb_search` пары - исследовательский lane: много кандидатов, но качество зависит от rank/confidence.
- name/year эвристики дают небольшой набор дополнительных кандидатов.

### 4.3. Canonical/data mart слой

| Object | Rows |
|---|---:|
| `dm.canonical_games` | `20,613` |
| `dm.canonical_game_sources` | `35,607` |
| `dm.game_recommendations` | `147,254` |

Интерпретация:

- canonical layer уже построен и связывает source records в единые игровые сущности;
- модельный auto-merge не включен как blind production policy;
- рекомендации строятся поверх canonical layer.

### 4.4. Data packs и воспроизводимость

Были сформированы data packs:

- `data_packs/gip_full_rawg_v1`
- `data_packs/gip_full_rawg_wikidata_v1`
- `data_packs/gip_full_steam_v1`
- `data_packs/gip_full_wikipedia_v1`
- `data_packs/gip_full_rawg_details_v1`
- `data_packs/gip_full_ml_ready_v1`

Они не коммитятся в Git, но нужны для локального восстановления без повторного расхода API-квот.

См.:

- [docs/full_data_download_report.md](full_data_download_report.md)

## 5. Качество данных и насколько источники соотносятся между собой

### 5.1. Общая оценка

Данные пригодны для research/demo и для построения strong baseline. При этом они не являются
идеально чистыми и не должны объединяться простым join по названию.

Основные проблемы:

- разные источники используют разные названия;
- есть remasters, DLC, editions, sequels, localized titles;
- часть Wikidata records может иметь QID-like или низкокачественные labels;
- metadata features разрежены;
- source ratings и vote counts не одинаково калиброваны между источниками;
- IGDB lower-rank search candidates часто являются отрицательными примерами.

### 5.2. Как источники связаны

Связи строятся несколькими способами:

1. deterministic external IDs;
2. normalized title matching;
3. similar title + release year blocking;
4. IGDB search candidates by RAWG anchors;
5. manual review labels;
6. ML same_game_probability.

Это важно: система не предполагает, что одна база данных является истиной. Истина собирается
из комбинации source facts, deterministic IDs, ручной проверки и ML scoring.

### 5.3. IGDB quality

IGDB search lane показал сильную зависимость качества от rank:

| Rank bucket | Reviewed | Positive | Negative | Precision |
|---|---:|---:|---:|---:|
| `1` | `968` | `899` | `69` | `0.928719` |
| `2-3` | `439` | `23` | `416` | `0.052392` |
| `4-5` | `230` | `3` | `227` | `0.013043` |

Вывод:

- rank-1 IGDB search candidates можно использовать как сильный candidate signal;
- lower ranks полезны для hard negatives и ambiguity analysis;
- IGDB нельзя использовать как blind merge source;
- IGDB полезен как enrichment источник.

IGDB enrichment coverage:

| Feature | Coverage |
|---|---:|
| platforms | `0.996906` |
| descriptions | `0.975058` |
| genres | `0.947989` |
| companies | `0.854698` |
| themes | `0.818832` |
| aliases | `0.644142` |
| tags | `0.614076` |
| ratings | `0.595514` |

### 5.4. Graph quality

Graph analysis показывает, что pair-level качество не гарантирует безопасный canonical merge.

| Strategy | Components | Same-source links | Risky components |
|---|---:|---:|---:|
| `canonical_v1_trusted` | `20,613` | `31` | `29` |
| `model_auto_090` | `23,441` | `31` | `30` |
| `model_auto_070_research` | `15,765` | `516` | `100` |
| `hybrid_safe_090` | `20,396` | `42` | `38` |

Вывод:

- threshold `0.70` хорошо показывает исследовательский риск, но не годится для production merge;
- `0.90` и hybrid policy выглядят перспективно, но требуют component-level review;
- canonical production layer должен оставаться conservative.

## 6. Какие исследования можно провести и какие уже проведены

### 6.1. Уже проведено

| Исследование | Статус | Назначение |
|---|---|---|
| ER baseline | done | модель same-game probability |
| Manual review | done | supervised labels для positives/negatives |
| Threshold analysis | done | политика auto/manual/no merge |
| Merge strategy comparison | done | сравнение trusted/model/hybrid policies |
| Graph analysis | done | transitive risk и risky components |
| Ablation study | done | какие группы признаков важны |
| Calibration analysis | done | насколько вероятности пригодны для threshold policy |
| Active learning simulation | done | какие пары модель предложит разметить дальше |
| Lightweight embeddings | done | TF-IDF/SVD title vectors против fuzzy matching |
| IGDB matching analysis | done | rank/confidence/retrieval quality |
| Content recommendations | done | explainable baseline |
| Bayesian rating | done | ranking under sparse vote counts |
| Grounded RAG explanations | done | русскоязычные объяснения на computed facts |

### 6.2. ER model results

Weighted Logistic Regression `v3c`:

| Metric | Value |
|---|---:|
| Precision | `0.983242` |
| Recall | `0.916455` |
| F1 | `0.948675` |
| ROC-AUC | `0.957274` |
| PR-AUC | `0.994369` |
| Brier score | `0.080893` |

Вывод:

- модель сильная как baseline;
- ручные labels улучшили надежность оценки;
- модель нельзя использовать как единственный источник truth;
- модель полезна для приоритизации manual review и controlled hybrid merge.

### 6.3. Ablation results

| Scenario | F1 | Вывод |
|---|---:|---|
| all_features | `0.948675` | базовое качество |
| without_name | `0.919584` | title/alias признаки критичны |
| without_year | `0.953306` | year сам по себе не главный фактор |
| without_companies | `0.948477` | company metadata пока sparse |
| without_taxonomy | `0.949153` | genre/platform/tag не дают большой прирост |
| without_source_signal | `0.944455` | source signal полезен, но не главный |

Вывод:

- сейчас модель в основном решает задачу name/alias matching;
- дальнейший рост качества должен идти через aliases, richer metadata, IGDB/Wikidata cleanup и embeddings.

### 6.4. Lightweight embeddings

| Model | F1 |
|---|---:|
| `combined_name_embedding_year` | `0.974026` |
| `word_tfidf_only` | `0.953895` |
| `embedding_stack` | `0.952381` |
| `name_similarity_only` | `0.950872` |
| `char_tfidf_only` | `0.937107` |
| `svd_title_only` | `0.869440` |

Вывод:

- embedding-style признаки улучшают baseline;
- даже lightweight TF-IDF/SVD уже полезны;
- следующий сильный исследовательский шаг - multilingual neural embeddings.

### 6.5. Bayesian rating

Сделан вторичный статистический блок:

```text
bayesian_rating = (votes * naive_rating + prior_votes * global_mean)
                  / (votes + prior_votes)
```

Текущие числа:

| Metric | Value |
|---|---:|
| Rating inputs | `24,344` |
| Canonical games with Bayesian ratings | `14,468` |
| Global weighted mean | `78.527138` |
| Prior votes | `50.0` |
| Total vote count | `2,803,272` |

Вывод:

- naive rating шумный при малом числе голосов;
- Bayesian adjustment делает ranking устойчивее;
- это отдельный explainable ML/statistics блок, не ER-модель.

### 6.6. Grounded RAG

Сделано:

- `25` match explanations;
- `25` recommendation explanations;
- `50` grounded fact cards;
- язык: русский.

Принцип:

- LLM/RAG не принимает решение;
- он только объясняет уже вычисленные факты;
- решение принимается ER/recommendation pipeline.

Это важно для защиты: объяснение не подменяет модель и не создает новые основания для merge.

## 7. Какое обучение проведено

### 7.1. Что обучали

Обучалась модель Entity Resolution:

```text
pair(source_game_a, source_game_b) -> same_game_probability
```

Модель:

- Logistic Regression;
- median imputation;
- balanced class weights;
- sample weights:
  - manual review: `1.0`;
  - weak positive: `0.05`;
  - synthetic negative: `0.5`.

### 7.2. На каких данных обучали

Training frame:

| Metric | Value |
|---|---:|
| Total rows | `7,817` |
| Positive labels | `6,881` |
| Negative labels | `936` |

Источники labels:

1. manual review labels;
2. weak positives from external IDs;
3. synthetic negatives.

Manual labels:

| Label type | Count |
|---|---:|
| Reviewed positives | `1,029` |
| Reviewed negatives | `937` |
| Skipped/uncertain | `152` |

См.:

- [docs/manual_review_workflow.md](manual_review_workflow.md)
- [docs/model_card.md](model_card.md)

### 7.3. На каких ручных сопоставлениях

Ручная разметка проводилась по candidate pairs из:

- external ID matching;
- IGDB search candidates;
- suspicious auto-merge candidates;
- likely positives;
- high uncertainty / active learning candidates;
- risky franchise/remaster/edition cases.

Хранилище ручной разметки:

- `ml.entity_resolution_manual_reviews`

Контекстная view:

- `ml.v_entity_resolution_review_candidates`
- `ml.v_igdb_manual_review_queue`

Ручной столбец:

- `review_label = TRUE` - одна и та же игра;
- `review_label = FALSE` - разные игры;
- `review_label = NULL` - не проверено или uncertain;
- `review_status = reviewed/unsure/pending`.

### 7.4. Как ручная разметка улучшила результат

До ручной разметки система могла опираться в основном на weak positives и эвристики.
Это создавало риск:

- переоценить пары с похожими названиями;
- пропустить hard negatives;
- считать remaster/DLC/edition одной игрой;
- получить слишком оптимистичную оценку качества.

После ручной разметки:

- появились реальные negative examples;
- модель научилась лучше отличать похожие, но разные игры;
- появилась возможность проверить threshold policy;
- появилась база для active learning;
- появилась возможность сравнивать model-only и trusted/hybrid merge strategies.

Итог: manual review не просто улучшил метрику. Он сделал оценку качества модели защищаемой.

## 8. Что сделали далее после обучения

После обучения были построены дополнительные слои:

1. Predictions:
   - `auto_merge`;
   - `manual_review`;
   - `no_merge`.
2. Threshold analysis:
   - `0.95`;
   - `0.90`;
   - `0.70`.
3. Merge strategy comparison:
   - trusted canonical;
   - model-only;
   - hybrid policies.
4. Graph analysis:
   - same-source conflicts;
   - risky components;
   - high-probability reviewed negatives.
5. Canonical catalog:
   - `20,613` canonical games.
6. Recommendations:
   - `147,254` recommendation rows.
7. Bayesian rating:
   - robust rating under sparse vote counts.
8. Grounded explanations:
   - Russian explanations from computed facts.
9. Readiness layer:
   - artifact checklist;
   - metric snapshot;
   - demo sequence.
10. Presentation layer:
   - slide outline;
   - speaker notes;
   - PPTX deck.

## 9. Что означает презентационная часть

Презентация не является отдельной частью платформы и не является ML-моделью.

Она нужна для защиты как производный артефакт:

```text
reports + notebooks + readiness metrics -> speaker notes -> PPTX deck
```

То есть презентация собирает уже полученные результаты в понятный сценарий:

1. зачем нужна платформа;
2. какие источники подключены;
3. какой объем данных собран;
4. почему нужна ручная разметка;
5. как обучалась ER-модель;
6. какие метрики получились;
7. почему blind auto-merge опасен;
8. что дает graph analysis;
9. что дает IGDB;
10. как работают рекомендации/Bayesian/RAG;
11. что осталось сделать.

Готовый PPTX:

- [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx)

Если презентационная часть пока не понятна, ее можно рассматривать не как «часть системы», а как
упаковку результатов для защиты. Основные рабочие артефакты остаются в коде, БД, reports и notebooks.

## 10. Готовые документы по пунктам

| Тема | Документ |
|---|---|
| Общий README и команды | [README.md](../README.md) |
| Архитектура | [docs/architecture.md](architecture.md) |
| Схема БД | [docs/database_schema.md](database_schema.md) |
| Источники API | [docs/data_sources_api_methods.md](data_sources_api_methods.md) |
| Ingestion framework | [docs/ingestion_framework.md](ingestion_framework.md) |
| Полная загрузка данных | [docs/full_data_download_report.md](full_data_download_report.md) |
| ML-ready datasets | [docs/ml_ready_datasets.md](ml_ready_datasets.md) |
| Manual review | [docs/manual_review_workflow.md](manual_review_workflow.md) |
| Entity Resolution baseline | [docs/entity_resolution_baseline.md](entity_resolution_baseline.md) |
| Model card | [docs/model_card.md](model_card.md) |
| ML research findings | [docs/ml_research_findings.md](ml_research_findings.md) |
| Defense runbook | [docs/ml_research_defense_runbook.md](ml_research_defense_runbook.md) |
| IGDB research | [docs/igdb_ml_matching_research_plan.md](igdb_ml_matching_research_plan.md) |
| Remaining steps | [docs/ml_defense_remaining_steps.md](ml_defense_remaining_steps.md) |

## 11. Готовые notebook

| Notebook | Назначение |
|---|---|
| [notebooks/entity_resolution_training_report.ipynb](../notebooks/entity_resolution_training_report.ipynb) | обучение/оценка ER baseline |
| [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb) | единый notebook для защиты ML-исследований |

## 12. Что еще необходимо для финальной работы

### 12.1. Для защиты

1. Провести timed rehearsal по PPTX и notebook.
2. Понять лимит времени защиты и сократить deck под этот лимит.
3. Выбрать 5-7 live demo artifacts, которые будут открываться на защите.
4. Подготовить короткий устный сценарий:
   - 2 минуты про платформу;
   - 3-5 минут про данные;
   - 5-7 минут про ER/ML;
   - 2-3 минуты про рекомендации/RAG;
   - 2 минуты про ограничения и future work.

### 12.2. Для платформы как продукта

1. Довести FastAPI endpoints от placeholder/demo логики до чтения реальных `dm`/`ml` таблиц:
   - `/games`;
   - `/games/{game_id}`;
   - `/games/{game_id}/similar`;
   - `/recommend`;
   - `/matches/review`;
   - `/explain/recommendation`;
   - `/explain/match`.
2. Добавить API demo scenario и smoke/integration tests.
3. Зафиксировать contract для canonical catalog API.
4. Добавить простой UI или Swagger demo script, если это нужно для защиты.

### 12.3. Для данных

1. Продолжать очищать low-quality names и QID-like labels.
2. Увеличить долю ручных labels в hard cases.
3. Провести дополнительный IGDB sampling:
   - rank-1 positives;
   - lower-rank negatives;
   - ambiguous franchise/remaster/edition cases.
4. Пересобрать canonical catalog после утверждения controlled hybrid policy.

### 12.4. Для ML-исследований

1. Добавить multilingual neural embeddings.
2. Сравнить neural embeddings с текущими TF-IDF/SVD title vectors.
3. Улучшить calibration и threshold governance.
4. Провести более строгую holdout evaluation для IGDB search lane.
5. Рассмотреть MLflow/experiment registry, если требуется формальная демонстрация экспериментов.

### 12.5. Для RAG/explanations

1. Текущий слой template-based, не interactive RAG chat.
2. Следующий шаг - LLM rendering over grounded fact cards.
3. Важно сохранить правило: LLM объясняет, но не принимает решение.

### 12.6. Для Git/release

1. После согласования материалов выполнить merge `feature/igdb-search-lane` в `develop`.
2. Запустить `make ml-defense-all`.
3. Запустить code quality checks.
4. Merge в `main` делать только после явного подтверждения.

## 13. Итоговая формулировка для защиты

Проект можно представить так:

> Мы построили end-to-end data/ML-платформу для видеоигр. Она собирает данные из RAWG,
> Wikidata, Steam, Wikipedia и IGDB, сохраняет raw/staging/ML/canonical слои в PostgreSQL,
> формирует candidate pairs, использует ручную разметку и ML-модель Entity Resolution для
> оценки совпадения игр, строит canonical catalog, рекомендации, Bayesian rating и grounded
> объяснения. Главный исследовательский результат: модель полезна не как blind auto-merge,
> а как управляемый scoring/manual-review/controlled-hybrid слой. Такой подход позволяет
> улучшать качество объединения данных из разных систем и при этом контролировать риск
> ошибочных объединений.
