# Финальный live-demo script

Дата: 2026-06-05.

Цель: пройти защитный demo-сценарий без внешних API-загрузок и без изменения canonical
catalog. Скрипт показывает готовность данных, FastAPI endpoints, manual-review feedback loop,
recommendations, grounded explanations, graph governance и optional UI.

## 1. Старт контура

```bash
make up-dev
make final-smoke
```

Ожидаемо:

- `demo-readiness`: `Status: ok`;
- `api-smoke`: все основные endpoints возвращают `200`;
- `notebook-check`: ключевые notebooks существуют и parseable.

Если `final-smoke` падает:

```bash
make ps
make logs
make demo-readiness
```

## 2. Readiness и масштаб данных

```bash
curl http://localhost:8000/stats/readiness
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
curl http://localhost:8000/stats/graph
```

Что сказать:

- `/stats/readiness` доказывает наличие demo artifacts и data pack;
- `/stats/catalog` показывает масштаб multi-source каталога;
- `/stats/ml` показывает manual labels, model metrics и threshold policy;
- `/stats/graph` показывает ER-risk graph, а не product KG.

## 3. Каталог

```bash
curl "http://localhost:8000/games?limit=5&search=doom"
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb"
```

Что сказать:

- catalog endpoint читает canonical layer;
- карточка игры показывает facts, ratings, source links;
- external APIs во время demo не вызываются.

## 4. Recommendations

Content baseline:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=3&algorithm=content_jaccard_v1"
```

Hybrid-style fallback:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=3&algorithm=hybrid_content_rating_v1"
```

POST flow:

```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"liked_games":["DOOM"],"limit":3,"algorithm":"content_jaccard_v1"}'
```

Что сказать:

- `content_jaccard_v1` - основной explainable cold-start recommender;
- `hybrid_content_rating_v1` - lightweight non-production extension;
- collaborative filtering не заявляется, потому что нет user interactions.

## 5. Manual review и write feedback loop

Read:

```bash
curl "http://localhost:8000/matches/review?limit=5&review_status=reviewed"
curl "http://localhost:8000/matches/review?limit=5&review_status=all"
```

Write endpoint демонстрировать только на заранее выбранной безопасной test-паре:

```bash
curl -X PATCH "http://localhost:8000/matches/review/<pair_id>" \
  -H "Content-Type: application/json" \
  -H "X-GIP-Write-API-Key: <optional-if-configured>" \
  -d '{"review_label":"same_game","review_status":"reviewed","review_notes":"demo check","reviewer":"defense-demo","confidence":0.9}'
```

Что сказать:

- write endpoint обновляет только PostgreSQL manual review row;
- artifact fallback read-only;
- это feedback loop для ML governance, не полноценный review-management UI.

## 6. Grounded explanations и optional LLM mode

Template mode:

```bash
curl "http://localhost:8000/explain/recommendation?limit=2&mode=template"
curl "http://localhost:8000/explain/match?limit=2&mode=template"
```

LLM mode fallback:

```bash
curl "http://localhost:8000/explain/recommendation?limit=2&mode=llm"
curl "http://localhost:8000/explain/match?limit=2&mode=llm"
```

Что сказать:

- LLM не принимает решений;
- при `LLM_PROVIDER=none` возвращается template grounded explanation с warning;
- provider `mock` используется только для tests/demo логики.

## 7. Optional UI

```bash
make up-ui
```

Открыть:

```text
http://localhost:8501
```

Что показать:

- Stats/readiness page;
- catalog search;
- similar games;
- manual review queue;
- explanations.

Если UI не стартует, основной demo остается через FastAPI `/docs` и curl.

## 8. Notebook/PPTX backup

```bash
make notebook-check
make notebook-export
```

Открыть:

- `notebooks/03_ml_research_defense_report.ipynb`;
- `notebooks/04_live_demo_cases.ipynb`;
- `data/artifacts/reports/notebooks_html/03_ml_research_defense_report.html`.

## 9. Короткая финальная формулировка

> Game Intelligence Platform - это end-to-end local/offline + FastAPI demo ML platform.
> Главный ML-блок - Entity Resolution с manual review, threshold governance и graph risk.
> Recommendations, Bayesian rating, grounded explanations, optional UI и readiness checks
> показывают, что модель встроена в полноценный data product contour.
