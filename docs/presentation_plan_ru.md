# План презентации защиты

Цель: показать `Game Intelligence Platform` как единую data/ML-платформу, а не только
отдельную модель.

## Структура

| Блок | Что показать | Evidence |
|---|---|---|
| 1. Проблема | Разные источники игр дают разные ID, названия, годы, платформы | architecture + source examples |
| 2. Data platform | `raw -> stg -> ml -> dm` | `docs/database_schema.md`, `/stats/catalog` |
| 3. Readiness | Данные и artifacts готовы к demo | `make demo-readiness`, `/stats/readiness` |
| 4. Entity Resolution | Candidate pairs, features, manual labels, Logistic Regression | `docs/model_card.md`, notebook |
| 5. Governance | Thresholds, manual review, graph risk | `/stats/ml`, `/stats/graph` |
| 6. Manual review | Reviewed pairs и write endpoint | `/matches/review`, `PATCH /matches/review/{pair_id}` |
| 7. Catalog | Canonical catalog карточки игр | `/games`, `/games/{game_id}` |
| 8. Recommendations | Content-based и hybrid fallback baseline | `/games/{id}/similar`, `/recommend` |
| 9. Explanations | Grounded Russian explanations, optional LLM rendering fallback | `/explain/recommendation`, `/explain/match` |
| 10. Engineering | Docker, Makefile, tests, notebooks, UI | `make api-smoke`, `make notebook-check`, `make up-ui` |
| 11. Ограничения | No collaborative filtering, no LLM decisions, optional neural embeddings | `docs/final_project_readiness_ru.md` |
| 12. Future work | Product KG, neural embeddings, hybrid reranking, CI/CD | roadmap/future work |

## Live Demo Команды

```bash
make up-dev
make demo-readiness
make api-smoke
make notebook-check
```

Optional:

```bash
make up-ui
make notebook-export
```

## Что Не Обещать

- LLM не принимает решений.
- Recommendations не являются collaborative filtering.
- `hybrid_content_rating_v1` является explainable fallback/research layer, а не production
  learned recommender.
- `/stats/graph` сейчас ER-risk graph, не полный product knowledge graph.
