# Финальный review future work и границ реализации

Дата: 2026-06-05.

Основа анализа:

- `/Users/mgdr/Downloads/gip_future_work.md`;
- `/Users/mgdr/Downloads/gip_future_work_recomendation.md`;
- текущий код и документация проекта после финальных defense-ready доработок.

Главный вывод: большую часть небольших и безопасных доработок уже стоит считать закрытой как
`lightweight / optional / defense-ready` функционал. До защиты лучше не расширять проект
новыми крупными блоками, а стабилизировать demo-сценарий и четко объяснить границы:

```text
реализовано для защиты -> lightweight non-production extensions -> production-ready future work
```

## 1. Текущая реализация, которую можно защищать

Это функционал, который уже реализован и проверяется тестами/smoke-командами. Его можно
показывать как часть текущего проекта.

| Блок | Статус | Как формулировать |
|---|---|---|
| Data platform | done | External APIs -> `raw/stg/ml/dm` -> FastAPI demo. |
| Ingestion | done | RAWG, Wikidata, Steam, Wikipedia, optional IGDB; cache/log/quota/retry. |
| Data packs | done | Export/import/restore для воспроизводимости и защиты API-квот. |
| Entity Resolution | done | Candidate generation, features, manual labels, Logistic Regression, thresholds. |
| Manual review | done | Review queue, labels, SQL views, `PATCH /matches/review/{pair_id}`. |
| Canonical catalog | done | `dm.canonical_games` и source links. |
| Recommendations | done | `content_jaccard_v1` как explainable cold-start baseline. |
| Bayesian rating | done | Secondary statistics/ML block для устойчивого рейтинга. |
| Grounded explanations | done | Русскоязычные explanations по computed facts. |
| API demo | done | Catalog, recommendations, review, explanations, stats/readiness/graph. |
| Demo readiness | done | `make demo-readiness`, `/stats/readiness`. |
| API smoke | done | `make api-smoke`. |
| Notebook readiness/export | done | `make notebook-check`, `make notebook-export`. |
| Optional UI | done | `make up-ui`, lightweight Streamlit demo. |
| Model governance | done | Model card, threshold policy, `/stats/ml`, graph risk analysis. |

## 2. Промежуточные non-production реализации

Эти блоки уже есть, но их нельзя называть production-ready. Их лучше показывать как
исследовательские или демонстрационные расширения.

| Блок | Что реализовано | Почему non-production | Как говорить на защите |
|---|---|---|---|
| `hybrid_content_rating_v1` | Отдельный recommendation algorithm mode и Makefile target. | Это safe fallback/rule-style layer, не learned reranker. | "Explainable hybrid-style baseline; learned recommender требует user interactions." |
| Neural embeddings | `make embeddings-research`, optional `sentence-transformers`, TF-IDF fallback. | Нет production cache/versioning и интеграции в ER feature base. | "Optional research lane; production embeddings - следующий этап." |
| LLM rendering | `mode=llm`, provider `none/mock`, groundedness verifier, template fallback. | Нет реального provider trace, prompt logs, evaluation suite. | "LLM не принимает решений; только rendering over facts." |
| Streamlit UI | Optional dashboard поверх API. | Нет production UX/auth/state management. | "Lightweight demo UI для защиты." |
| `/stats/graph` | ER-risk graph summary. | Это не product knowledge graph каталога. | "Graph используется для governance ER, не для KG-рекомендаций." |
| Manual review write API | `PATCH /matches/review/{pair_id}`. | Только PostgreSQL-backed; artifact fallback read-only; auth минимальный. | "Feedback loop для ML review, не полный workflow management." |

## 3. Небольшие безопасные доработки, которые еще можно сделать

Это доработки с низким риском: они не требуют новой архитектуры, не ломают текущий pipeline и
не требуют внешних платных API. Их можно сделать, если остается время после стабилизации demo.

| Приоритет | Доработка | Польза | Риск |
|---|---|---|---|
| Done | Добавить короткий `docs/live_demo_script_final_ru.md` с пошаговыми curl/UI командами. | Упростит репетицию защиты. | Закрыто. |
| Done | Добавить `make final-smoke`, который последовательно запускает `demo-readiness`, `api-smoke`, `notebook-check`. | Один финальный вход для проверки. | Закрыто. |
| Done | Добавить больше examples в `docs/final_demo_cases_ru.md` под новые endpoints `/stats/readiness`, `/stats/graph`, `mode=llm`, `algorithm=hybrid_content_rating_v1`. | Улучшит демонстрацию. | Закрыто. |
| P1 optional | В Streamlit UI добавить форму PATCH manual review для одного выбранного `pair_id`. | Покажет feedback loop визуально. | Средний: write operation нужно показывать аккуратно. |
| P2 | Добавить static HTML landing page или README screenshot placeholders для UI. | Наглядность без запуска UI. | Низкий. |
| P2 | Добавить small report для optional neural embeddings fallback output. | Лучше объяснит, почему fallback допустим. | Низкий. |
| P2 | Добавить API response schemas для новых endpoints. | Улучшит OpenAPI. | Средний: может потребовать больше refactoring. |

Рекомендация: P1 docs/final-smoke/demo-case polish уже закрыт. Перед защитой не добавлять
новые ML-модели и не менять canonical/ER логику.

## 4. Что не стоит делать перед защитой

Эти задачи требуют отдельного проектного этапа. Быстрая реализация может снизить стабильность
и запутать границы проекта.

| Направление | Почему не сейчас |
|---|---|
| Learned recommender / collaborative filtering | Нет user interaction data; без него нельзя честно считать `Precision@K`, `Recall@K`, `NDCG@K`. |
| Full product knowledge graph | Нужно строить отдельный graph builder, similarity, reports, endpoint и сравнение с recommendations. |
| Production frontend | Требует UX, auth, state management, review workflow и регрессионных тестов. |
| Full online RAG-chat | Нужны provider, prompt tracing, groundedness evaluation, cost/security controls. |
| Production neural embeddings | Нужны batch cache, versioning, model availability, feature integration and threshold re-evaluation. |
| Alembic migrations / DVC / CI/CD | Это production engineering scope, не обязательный для финальной защиты ML/data project. |

## 5. Production-ready future work

### 5.1. Learned hybrid recommender

Что потребуется:

- источник user interactions: ratings, wishlist, playtime, likes или внешний benchmark;
- negative sampling;
- train/test split по пользователям;
- метрики `Precision@K`, `Recall@K`, `NDCG@K`, diversity, coverage;
- сравнение content-only, Bayesian/content hybrid, graph-based и learned reranker;
- model card для recommender.

### 5.2. Product knowledge graph

Что потребуется:

- graph builder: `game -> genre/platform/developer/publisher/tag/franchise`;
- GraphML/CSV exports;
- centrality/community analysis;
- graph-based similarity;
- endpoint `/stats/product-graph`;
- comparison report: graph recommendations vs content recommendations.

### 5.3. Production frontend

Что потребуется:

- полноценный UI flow: catalog, card, recommendations, ER review, explanations, readiness;
- form-based manual review updates;
- auth для write-действий;
- pagination/search/filter UX;
- smoke/e2e tests.

### 5.4. Production LLM/RAG rendering

Что потребуется:

- provider: OpenAI-compatible или local;
- prompt templates with strict groundedness constraints;
- prompt/input/output logs;
- verifier and fallback;
- tests for hallucination and missing facts;
- cost/security controls.

### 5.5. Production neural embeddings

Что потребуется:

- stable multilingual model;
- embedding cache and model version metadata;
- batch generation command;
- cosine similarity in ER feature base;
- threshold and calibration re-evaluation;
- comparison report against fuzzy/TF-IDF/SVD baselines.

### 5.6. Production hardening

Что потребуется:

- CI workflow: базовый GitHub Actions и `make ci-check` уже добавлены для `compileall`,
  `ruff`, `pytest`, `docker compose config`; `api-smoke` остаётся локальным pre-demo gate,
  потому что требует запущенного API и подготовленных artifacts.
- migrations instead of init-only SQL;
- response schemas and API contract tests;
- API auth policy: `PATCH /matches/review/{pair_id}` теперь требует `GIP_WRITE_API_KEY`
  вне local/demo окружения; полноценная user/session auth остаётся future work.
- strict DB mode: `GIP_STRICT_DB_MODE=true` отключает тихий artifact fallback и помогает
  ловить DB regressions в production-like проверках.
- DVC/object storage for data/model versioning;
- release workflow: feature branch -> `develop` -> `main` after approval.

## 6. Финальная рекомендация

Для защиты текущий проект уже достаточно насыщен. Наиболее рациональная стратегия:

1. Не добавлять крупные новые ML/production блоки до защиты.
2. Стабилизировать сценарий:
   `make up-dev -> make demo-readiness -> make api-smoke -> Swagger/UI -> notebook/PPTX`.
3. Подавать проект как strong local/offline + FastAPI demo ML platform.
4. Non-production extensions показывать как исследовательские и безопасные:
   `hybrid_content_rating_v1`, optional neural embeddings, safe LLM rendering, Streamlit UI.
5. Production-ready направления оставить в roadmap и честно объяснить, что для них нужны
   дополнительные данные, инфраструктура и evaluation.

Главная формулировка:

> Проект уже реализует end-to-end data/ML platform для мульти-источникового каталога игр.
> Оставшийся future work - это переход от учебного production-like контура к настоящему
> production/research продукту.
