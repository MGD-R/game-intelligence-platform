# Финальная готовность проекта к защите

Дата: 2026-06-05.

## 1. Что реализовано

Проект готов как local/offline + FastAPI demo contour:

- Docker Compose контур: PostgreSQL, FastAPI app, worker, dev profile, notebook, optional UI,
  MLflow/MinIO и pgAdmin profiles.
- DWH-подобные слои PostgreSQL: `meta`, `raw`, `stg`, `ml`, `dm`.
- Ingestion для RAWG, Wikidata, Steam, Wikipedia и optional IGDB.
- Cache/log/quota/rate-limit/retry слой для API-загрузки.
- Data pack export/import/restore.
- Entity Resolution pipeline: candidate pairs, features, manual review, Logistic Regression,
  predictions, threshold policy, graph risk.
- Canonical catalog и canonical source links.
- Content-based recommendations и optional `hybrid_content_rating_v1` fallback layer.
- Bayesian rating analysis.
- Lightweight TF-IDF/SVD embedding research и optional neural embedding fallback.
- Grounded Russian explanations; optional `mode=llm` только переформулирует computed facts.
- FastAPI demo endpoints для catalog/recommendations/manual review/explanations/stats/readiness.
- Write endpoint для manual review: `PATCH /matches/review/{pair_id}`.
- Optional Streamlit UI: `make up-ui`.
- Defense notebooks, report docs и PPTX artifacts.

## 2. Что показывать на защите

Рекомендуемый порядок:

1. Архитектура: external APIs -> `raw/stg/ml/dm` -> FastAPI demo.
2. `/stats/readiness`, `/stats/catalog`, `/stats/ml` - масштаб и готовность данных.
3. `/games?search=doom` и `/games/{game_id}` - canonical catalog.
4. `/matches/review?review_status=reviewed` - ручная разметка и ER supervision.
5. ER metrics/model card - почему модель используется как scoring/governance layer.
6. `/games/{game_id}/similar` и `/recommend` - content-based recommendations.
7. `/explain/recommendation` и `/explain/match` - grounded explanations.
8. `/stats/graph` - graph risk analysis.
9. Notebook `notebooks/03_ml_research_defense_report.ipynb` - ML research details.
10. Optional UI на `http://localhost:8501`.

## 3. Как запустить demo

```bash
cp .env.example .env
cp .env.secrets.example .env.secrets
make build-dev
make up-dev
make demo-readiness
make api-smoke
make final-smoke
```

Проверить API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stats/readiness
curl "http://localhost:8000/games?search=doom&limit=5"
curl "http://localhost:8000/explain/recommendation?limit=2"
```

Optional UI:

```bash
make up-ui
```

Открыть:

```text
http://localhost:8501
```

## 4. Как восстановить data pack

Если локальная БД или artifacts отсутствуют:

```bash
make import-data-pack DATA_PACK=data_packs/gip_demo_local
make restore-from-files DATA_PACK=data_packs/gip_demo_local
make demo-readiness
```

Если data pack нужно пересобрать:

```bash
make export-data-pack
```

## 5. Как проверить готовность

Минимальный smoke:

```bash
make demo-readiness
make api-smoke
make notebook-check
make final-smoke
```

Полный pre-defense rebuild:

```bash
make ml-defense-all
make notebook-export
```

Code quality:

```bash
python -m compileall src tests
ruff check src tests
pytest
docker compose config -q
```

## 6. Новые финальные endpoints

| Endpoint | Назначение |
|---|---|
| `GET /stats/readiness` | readiness status, found/missing artifacts, recommended commands |
| `GET /stats/graph` | ER graph risk artifact summary |
| `PATCH /matches/review/{pair_id}` | update PostgreSQL manual review row |
| `GET /explain/recommendation?mode=llm` | optional LLM rendering over grounded facts |
| `GET /explain/match?mode=llm` | optional LLM rendering over grounded facts |

Manual review write endpoint обновляет только PostgreSQL. Artifact fallback остается read-only.
Если `GIP_WRITE_API_KEY` задан, передавать его нужно в `X-GIP-Write-API-Key`.

## 7. Ограничения, которые нужно проговорить честно

- Recommendations не являются collaborative filtering: user interaction data нет.
- `hybrid_content_rating_v1` сейчас безопасный baseline/fallback layer; полноценный hybrid
  reranking с learned weights остается следующим исследованием.
- LLM не принимает решений. Он может только переформулировать уже рассчитанные facts, а при
  отключенном provider возвращается template fallback.
- Neural embeddings optional: если `sentence-transformers` или модель недоступны, используется
  fallback report.
- `/stats/graph` показывает ER-risk graph, а полноценный product knowledge graph остается
  future work.
- API production hardening ограничен: нет полноценной авторизации для read endpoints,
  нет frontend production UX, нет CI/CD release pipeline.

## 8. Future work

1. Production UI или Streamlit dashboard polish.
2. Полноценный product knowledge graph: games-companies-genres-platforms-tags.
3. Neural multilingual embeddings как основной ER/recommendation feature.
4. Hybrid recommender с Bayesian rating, text embeddings и source coverage weights.
5. LLM rendering provider с groundedness verifier и traceable prompts.
6. CI workflow для lint/test/docker compose/api-smoke.
7. Data/model versioning через DVC или object storage.
