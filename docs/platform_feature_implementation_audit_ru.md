# Аудит реализации функционала по `platform_analytics_ru.md`

Дата аудита: 2026-06-04.

Исходный файл для сравнения: `/Users/mgdr/Downloads/platform_analytics_ru.md`.

Цель документа - сверить аналитическое описание платформы с текущим состоянием проекта и
зафиксировать:

- что уже реализовано в коде, SQL, Makefile, API, tests и docs;
- что реализовано частично и требует аккуратного позиционирования на защите;
- что еще не реализовано, но может быть добавлено как следующий этап.

## 1. Главный вывод

Приложенный файл в целом правильно описывает проект как end-to-end data/ML-платформу, но
содержит несколько устаревших выводов. Самое важное расхождение: в приложенном файле FastAPI
business endpoints описаны как `501 Not Implemented`, тогда как текущий проект уже содержит
read-only demo API для каталога, рекомендаций, manual review, explanations и статистики.

Текущий проект готов демонстрироваться не только как offline research pipeline, но и как
локальный read-only data product:

```text
external APIs -> raw/cache/logging -> stg -> ml -> dm/canonical
              -> ER/manual review/model scoring
              -> recommendations/Bayesian rating/explanations
              -> FastAPI read-only demo endpoints
              -> notebooks/docs/PPTX defense artifacts
```

## 2. Проверенные источники фактов

Проверка проводилась по текущему рабочему дереву проекта:

| Область | Проверенные файлы / директории |
|---|---|
| API | `src/api/main.py`, `src/api/demo_readonly.py`, `tests/test_api.py` |
| Ingestion | `src/ingestion/`, `src/ingestion/jobs/`, `Makefile` |
| Preprocessing/DQ | `src/preprocessing/`, `sql/stg/`, `docker/postgres/init/005_create_stg_tables.sql` |
| Entity Resolution | `src/entity_resolution/`, `sql/ml/`, `docker/postgres/init/006_create_ml_tables.sql` |
| Recommendations | `src/recommendations/`, `sql/dm/`, `docker/postgres/init/007_create_dm_tables.sql` |
| RAG/explanations | `src/rag/`, `src/api/demo_readonly.py`, docs по defense/demo |
| Infrastructure | `docker-compose.yml`, Dockerfiles, `Makefile`, `.env.example` |
| Tests | `tests/`, особенно `tests/test_api.py` и ER/ingestion/preprocessing tests |
| Reports/docs | `README.md`, `docs/platform_analytics_ru.md`, `docs/ml_research_findings.md`, `docs/model_card.md` |

## 3. Статус функциональных блоков

| Блок | Статус | Комментарий |
|---|---|---|
| Docker/PostgreSQL/FastAPI/worker контур | реализовано | Compose содержит `postgres`, `app`, `worker`, dev-профили, optional `mlflow`, `minio`, `notebook`, `pgadmin`. |
| DWH-подобные слои `meta/raw/stg/ml/dm` | реализовано | Таблицы созданы в init SQL и дублируются в `sql/` как отдельные DDL. |
| Request cache/log/quota/retry/rate-limit | реализовано | Есть базовый HTTP-клиент, request hash/cache, quota, retry policy, redaction. |
| RAWG ingestion | реализовано | Есть check/reference/index/details/staging jobs и Makefile-команды. |
| Wikidata ingestion | реализовано | Есть targeted loading by RAWG IDs, identity/entities staging и external-id роль. |
| Steam enrichment | реализовано | Targeted appid selection, details loading, staging transform. |
| Wikipedia summaries | реализовано | Page selection, loading, staging transform для текстовых summary/explanations. |
| IGDB targeted/search lane | реализовано как optional | Есть auth/client/reference/games/search/staging/search-candidates/matching-analysis. |
| Data quality/anomaly/source coverage | реализовано | Есть DQ, anomaly reports, source coverage, validation commands. |
| Data pack export/import/restore | реализовано | Есть `export-data-pack`, `import-data-pack`, `restore-from-files`, `data-pack-check`. |
| Candidate generation для ER | реализовано | Есть blocking/candidate pairs: external IDs, normalized names, year+similarity, aliases, IGDB search candidates. |
| ER feature base | реализовано | Name/alias/year/external ID/company/platform/genre/tag/source-signal признаки. |
| Manual review в БД | реализовано | Есть таблица manual review, seed/queue/export scripts, views для анализа. |
| ER model training | реализовано | Logistic Regression baseline, weighted training, metrics, predictions, threshold policy. |
| Merge strategy comparison | реализовано | Есть comparison trusted/model/hybrid strategies. |
| Graph risk analysis | реализовано | Есть connected components/same-source conflict/risky cluster анализ. |
| Lightweight embedding research | реализовано | TF-IDF/SVD title-vector research lane. |
| IGDB matching analysis | реализовано | Есть rank/confidence/retrieval quality анализ search-based candidates. |
| Canonical catalog | реализовано | `dm.canonical_games`, source links, aliases, external IDs; build `canonical-v0/v1`. |
| Content-based recommendations | реализовано | `content_jaccard_v1`, `dm.game_recommendations`, API/отчеты. |
| Bayesian rating | реализовано | Есть отдельный анализ Bayesian-adjusted rating. |
| Grounded explanations | реализовано | Template-based Russian explanations from computed facts, без LLM decision-making. |
| Read-only demo API | реализовано | `/games`, `/recommend`, `/matches/review`, `/explain/*`, `/stats/*` возвращают `200` при наличии БД/артефактов. |
| Demo readiness checker | реализовано | `make demo-readiness` и `/stats/readiness` показывают found/missing artifacts и команды восстановления. |
| Manual review write API | реализовано | `PATCH /matches/review/{pair_id}` обновляет PostgreSQL manual review rows; artifact fallback read-only. |
| Optional Streamlit UI | реализовано как optional | `make up-ui`, UI читает FastAPI через `API_BASE_URL`. |
| Optional LLM rendering | реализовано как fallback layer | `mode=llm`, provider `none/mock`, verifier, template fallback. |
| Optional neural embeddings | реализовано как fallback lane | `make embeddings-research`; при отсутствии модели пишет TF-IDF fallback warning report. |
| Notebooks для защиты | реализовано | Есть `03_ml_research_defense_report.ipynb`, `04_live_demo_cases.ipynb`, ER training notebook. |
| Presentation artifacts | реализовано | Есть PPTX и scripts для readiness/presentation artifacts. |
| Tests | реализовано | Есть большой набор tests; `tests/test_api.py` покрывает 17 API smoke cases. |

## 4. Что в приложенном файле устарело

### 4.1. API больше не является `501 todo`

В приложенном файле API оценивается как главный gap: business endpoints якобы возвращают
`501 Not Implemented`. В текущей реализации это уже исправлено.

Фактические endpoints в `src/api/main.py`:

| Endpoint | Текущий статус | Источник данных |
|---|---|---|
| `GET /health` | реализовано | config/env |
| `GET /health/db` | реализовано | PostgreSQL connectivity |
| `GET /health/sources` | реализовано | source config без секретов |
| `GET /version` | реализовано | app config/env |
| `GET /games` | реализовано | `dm.canonical_games` или artifact fallback |
| `GET /games/{game_id}` | реализовано | canonical game card + sources/ratings |
| `GET /games/{game_id}/similar` | реализовано | `dm.game_recommendations` или artifacts |
| `POST /recommend` | реализовано | seed IDs / liked game names + recommendations |
| `GET /matches/review` | реализовано | `ml.v_entity_resolution_review_candidates` или artifacts |
| `GET /stats/catalog` | реализовано | `stg/dm` counts или artifacts |
| `GET /stats/ml` | реализовано | `ml` counts + metrics или artifacts |
| `GET /explain/recommendation` | реализовано | grounded explanation artifacts |
| `GET /explain/match` | реализовано | grounded explanation artifacts |

Важно: legacy `todo_response()` удалена из `src/api/main.py`; business endpoints больше не
имеют активного `501` fallback.

### 4.2. Документация уже обновлена относительно раннего scaffold-состояния

В приложенном файле есть замечание, что короткие docs выглядят как bootstrap/scaffold. В
текущей ветке README и ключевые docs уже обновлены:

- `README.md`;
- `docs/data_sources_api_methods.md`;
- `docs/demo_scenarios.md`;
- `docs/database_schema.md`;
- `docs/igdb_enrichment.md`;
- `docs/platform_analytics_ru.md`;
- `docs/final_defense_smoke_checklist_ru.md`.

Остались исторические runbooks, но они теперь в основном помечены как historical или first-run
context.

## 5. Реализованный функционал по направлениям

### 5.1. Data ingestion и источники

Реализованы все источники, описанные в аналитическом документе:

| Источник | Функционал | Статус |
|---|---|---|
| RAWG | discovery/reference/details/staging | реализовано |
| Wikidata | targeted identity by RAWG, QID, aliases, external IDs, sitelinks | реализовано |
| Steam | targeted enrichment by AppID | реализовано |
| Wikipedia | targeted pages/summaries for explanations | реализовано |
| IGDB | ID-based loading, reference loading, search-based candidates | реализовано как optional/advanced |

Что важно для защиты: IGDB используется не как гарантированный ID-join слой, а как отдельный
search-based retrieval/matching lane. Это позволяет демонстрировать ML/ER-задачу сопоставления
по названию, году, платформам, жанрам и другим признакам.

### 5.2. Хранилище и DWH-слои

Реализованы схемы:

- `meta` - request log, quota usage, pipeline logs, checkpoints;
- `raw` - raw API payloads;
- `stg` - source-centered normalized tables;
- `ml` - candidate pairs, features, predictions, manual review, IGDB candidates;
- `dm` - canonical catalog and recommendations.

Это полностью соответствует концепции платформы, описанной в `platform_analytics_ru.md`.

### 5.3. Entity Resolution

ER является самым зрелым ML-блоком проекта.

Реализовано:

- candidate generation;
- feature engineering;
- rule baseline;
- Logistic Regression training;
- weak/manual labels;
- manual review queue;
- predictions;
- threshold evaluation;
- merge strategy comparison;
- graph risk analysis;
- error analysis / defense artifacts;
- model card.

Текущие зафиксированные метрики из docs:

| Metric | Value |
|---|---:|
| Precision | `0.983242` |
| Recall | `0.916455` |
| F1 | `0.948675` |
| ROC-AUC | `0.957274` |
| PR-AUC | `0.994369` |
| Brier score | `0.080893` |

Вывод для защиты: модель работает не как слепой auto-merge, а как scoring/manual-review и
controlled-hybrid слой.

### 5.4. Manual review и supervised learning

Реализовано:

- таблица `ml.entity_resolution_manual_reviews`;
- review queue scripts;
- SQL/view для анализа review candidates;
- positive/negative labels;
- training dataset builder;
- reports по итерациям обучения.

По текущим docs зафиксированы:

| Показатель | Значение |
|---|---:|
| Reviewed manual labels | `1,966` |
| Manual positives | `1,029` |
| Manual negatives | `937` |

Это достаточная база для учебного supervised ER baseline. Для следующего уровня качества
можно расширять hard negative / ambiguous labels.

### 5.5. Recommendations

Реализован explainable content-based recommender:

- алгоритм `content_jaccard_v1`;
- признаки: genre, tag, platform, developer/publisher, release decade;
- таблица `dm.game_recommendations`;
- API `/games/{game_id}/similar` и `/recommend`;
- explanation factors.

Текущий статус корректно позиционировать как cold-start/content-based baseline. Это не
collaborative filtering, потому что в проекте нет user interaction данных.

### 5.6. Bayesian rating

Реализован отдельный статистический блок:

- Bayesian-adjusted rating;
- prior/global mean;
- сравнение naive vs adjusted rating;
- отчеты и defense examples.

Это хороший дополнительный ML/statistics блок, но не основная модель проекта.

### 5.7. Embeddings

Реализован lightweight embedding-style research:

- TF-IDF title vectors;
- SVD vectors;
- сравнение с fuzzy baseline;
- отчеты для защиты.

Не реализовано как production layer:

- multilingual neural sentence-transformers;
- embedding index/ANN search для каталога;
- semantic description embeddings для рекомендаций.

### 5.8. Graph analysis

Реализован graph/risk analysis для ER:

- connected components;
- same-source conflicts;
- risky components;
- сравнение graph risk при разных merge strategies.

Это не полноценный игровой knowledge graph, но это полезный и правильно примененный graph ML/data
quality блок.

### 5.9. RAG / explanations

Реализован grounded/template explanation layer:

- match explanations;
- recommendation explanations;
- grounded fact cards;
- русскоязычный текст;
- API endpoints `/explain/recommendation` и `/explain/match`.

Важное ограничение: это не интерактивный LangChain/LlamaIndex RAG-chat и не LLM decision maker.
LLM, если будет добавлен позже, должен только переформулировать уже вычисленные факты.

### 5.10. API и demo product

В отличие от приложенного файла, API-слой уже реализован как read-only demo product.

Сильные стороны:

- endpoints читают реальные `dm/ml/stg` таблицы;
- есть artifact fallback, поэтому demo может работать без полной БД;
- API tests покрывают catalog, recommendations, review queue, explanations and stats;
- secrets не отдаются в health/sources.

Ограничения:

- read endpoints остаются demo/read-only;
- write endpoint есть только для manual review и только PostgreSQL-backed;
- UI optional и не является production frontend;
- нет production auth/rate limiting;
- нет OpenAPI contract tests сверх smoke tests.

## 6. Частично реализовано: как правильно формулировать

| Направление | Что есть | Чего нет | Как говорить на защите |
|---|---|---|---|
| RAG/LLM | grounded fact cards и template explanations | interactive LLM/RAG chat | "LLM не принимает решения; сейчас реализован безопасный grounded explanation layer." |
| Embeddings | TF-IDF/SVD title-vector research | neural multilingual sentence-transformers | "Есть воспроизводимый lightweight embedding baseline; neural embeddings - следующий шаг." |
| Recommendations | content-based cold-start | collaborative filtering/ALS/SVD по users | "Нет user events, поэтому выбран explainable content baseline." |
| API | read-only demo endpoints | write API, auth, frontend | "API демонстрирует prepared data product, production write-layer остается future work." |
| IGDB | search/targeted candidates and analysis | trusted automatic merge by IGDB | "IGDB используется как retrieval/enrichment source, а не как безусловный source of truth." |
| MLflow/MLOps | optional profile and optional logging | обязательный experiment registry/release workflow | "Воспроизводимость обеспечена Makefile/data packs/docs; MLflow можно включить как advanced." |
| Graph | ER risk graph | full game knowledge graph | "Graph analysis используется для контроля ER merge risk." |

## 7. Не реализовано, но можно добавить

### P1. Write API для manual review

Что добавить:

- `PATCH /matches/review/{pair_id}`;
- body: `review_label`, `review_status`, `review_notes`, `reviewer`;
- audit timestamp;
- integration test.

Зачем:

- позволит размечать пары не через DBeaver/SQL, а через API;
- усилит demo как data product.

### P1. Frontend или lightweight Streamlit demo

Что добавить:

- экран каталога;
- карточка игры;
- рекомендации;
- manual review list;
- explanation view.

Зачем:

- защита станет визуально понятнее;
- API уже готов для такого слоя.

### P1. Neural multilingual embeddings

Что добавить:

- sentence-transformers для title/aliases/descriptions;
- cosine similarity features;
- сравнение fuzzy vs TF-IDF/SVD vs neural embeddings;
- отдельный notebook/report.

Зачем:

- усилит ML Advanced часть;
- лучше покрывает multilingual aliases и нестандартные названия.

### P2. LLM rendering over grounded facts

Что добавить:

- генерацию русскоязычного текста поверх `facts_used` / `sources_used`;
- strict prompt: LLM не добавляет факты;
- verifier, что output использует только переданные facts;
- fallback на template explanation.

Зачем:

- можно честно показать RAG/LLM layer без передачи LLM права принимать решения.

### P2. Hybrid recommender research

Что добавить:

- description embeddings;
- Bayesian rating as ranking prior;
- hybrid score: content similarity + rating prior + source confidence;
- offline examples and explanation table.

Зачем:

- усилит recommender block без необходимости user interactions.

### P2. Knowledge graph поверх canonical catalog

Что добавить:

- graph: games-companies-genres-platforms-tags;
- centrality/community analysis;
- graph-based similar games;
- сравнение с content Jaccard.

Зачем:

- расширит текущий graph analysis от ER-risk к product analytics.

### P2. Stronger model governance

Что добавить:

- calibration plot в API/report;
- threshold decision table in docs/API;
- drift/source coverage checks;
- model registry metadata.

Зачем:

- усилит аргументацию, почему model auto-merge контролируется.

### P3. Production hardening

Что добавить:

- auth for API;
- pagination contracts and schema models for all endpoints;
- background job orchestration;
- DVC or object-storage-based dataset versioning;
- CI pipeline for lint/tests/docker compose config.

Зачем:

- переведет учебный contour ближе к production-ready платформе.

## 8. Приоритетный следующий план

Рекомендуемый порядок после текущего состояния:

1. Закрепить текущую demo-ready версию в `develop`.
2. Добавить write API для manual review или lightweight UI, если нужен продуктовый demo.
3. Реализовать neural embeddings research как отдельный следующий ML-блок.
4. Добавить LLM rendering over grounded facts только после сохранения правила: LLM не принимает решений.
5. Расширить recommendations до hybrid content/rating/embedding model.
6. Добавить knowledge graph product analysis.
7. После этого заниматься production hardening: auth, CI, model/data versioning, orchestration.

## 9. Итоговая оценка

По сравнению с приложенным файлом проект находится в более продвинутом состоянии:

- API gap по `501` уже закрыт для read-only demo;
- docs приведены ближе к текущей реализации;
- текущая ветка содержит полноценный defense contour: data/ML/API/docs/notebooks/PPTX;
- основная ML-ценность остается ER/manual-review/controlled-merge, а рекомендации,
  Bayesian rating, embeddings, graph и grounded explanations служат дополнительными
  исследовательскими блоками.

Проект можно защищать как единую data/ML-платформу. Честная формулировка текущих границ:
это сильный local/offline + read-only API demo contour, но еще не production SaaS с frontend,
auth, write workflows, interactive RAG и collaborative recommender.
