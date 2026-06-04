# Future Work RU

Документ отделяет текущую защищаемую реализацию от направлений развития после сдачи.

## Текущая Защищаемая Версия

Сейчас проект готов как `ER-first` end-to-end data/ML platform:

- multi-source ingestion и staging;
- canonical catalog;
- Entity Resolution model и manual review;
- threshold/merge governance;
- graph risk analysis;
- IGDB search/enrichment lane;
- content-based recommendations;
- Bayesian rating analysis;
- grounded Russian explanations;
- read-only FastAPI demo endpoints;
- notebook/report/model card/PPTX/checklist.

## Что Не Является Текущим MVP

Эти пункты не надо обещать как реализованные:

- collaborative filtering;
- production frontend;
- Airflow как обязательный orchestration contour;
- online LLM/RAG decision-making;
- real-time recommendation service;
- model registry as production MLflow workflow;
- full active-learning UI.

## Приоритеты Развития

### 1. Neural Embeddings For ER

Добавить multilingual title/description embeddings и сравнить их с текущим TF-IDF/SVD и
fuzzy-title baseline.

Ожидаемая польза:

- лучше ловить renamed/localized titles;
- улучшить recall для low-confidence positives;
- расширить notebook/research comparison.

### 2. Active Learning UI

Сделать простой UI/API для ручной проверки:

- high-uncertainty pairs;
- risky positives;
- same-name negative controls;
- IGDB lower-rank candidates.

Ожидаемая польза:

- быстрее добирать manual labels;
- контролировать качество canonical merge;
- показывать практический ML feedback loop.

### 3. IGDB Search Matching Calibration

Развить IGDB lane:

- rank-based precision;
- query strategy comparison;
- title/year/platform/company feature impact;
- separate policy for IGDB enrichment vs canonical merge.

Ожидаемая польза:

- IGDB станет не только enrichment source, но и полноценным matching research source.

### 4. Recommendation Model Expansion

Текущий recommender — content-based baseline. Следующие шаги:

- добавить user interaction data, если появятся;
- после этого сравнить collaborative filtering, hybrid reranking и content-only baseline;
- добавить offline ranking metrics.

Ожидаемая польза:

- перейти от cold-start content recommendations к полноценной recommendation research задаче.

### 5. LLM Rendering Over Grounded Facts

Текущий слой explanations не принимает решений. Следующий шаг:

- LLM генерирует только текст объяснения;
- вход — canonical facts, ER features, predictions, recommendation factors;
- output проверяется на groundedness.

Ожидаемая польза:

- улучшить читаемость русскоязычных объяснений без риска hallucination-based decisions.

### 6. Orchestration And MLOps

После защиты можно усилить production-like контур:

- MLflow model registry;
- DVC/data versioning;
- Airflow/Prefect as optional orchestration;
- scheduled ingestion jobs;
- run history dashboard.

Ожидаемая польза:

- лучше воспроизводить research cycles и data refresh.

### 7. Frontend Demo

Добавить лёгкий UI:

- catalog search;
- game card;
- similar games;
- review candidates;
- explanation cards.

Ожидаемая польза:

- сделать demo доступнее для нетехнической аудитории.

## Что Делать В Первую Очередь После Защиты

1. Смержить текущую ветку в `develop`.
2. Запустить следующий data refresh, если нужны свежие источники.
3. Добрать manual labels через active-learning queue.
4. Добавить neural embedding comparison.
5. После появления interactions перейти к recommendation research beyond content-based baseline.
