# Final Plan Gap Analysis RU

Сверка исходного плана `/Users/mgdr/Downloads/final_project_implementation_plan_ru.md`
с текущим состоянием проекта.

## Summary

Текущий статус: `GO` для защиты как read-only FastAPI + ER-first ML/data platform demo.

Критические P0-пункты закрыты:

- FastAPI запускается через Docker Compose.
- Swagger UI показывает основные demo endpoints.
- `/games`, `/games/{id}`, `/games/{id}/similar`, `/recommend`, `/matches/review`,
  `/explain/recommendation`, `/explain/match`, `/stats/catalog`, `/stats/ml` работают.
- Есть стабильные demo cases.
- Notebook выполняется.
- README/docs связаны с demo script, final cases, smoke checklist и timed rehearsal.

## Status By Stage

| Stage | Status | Evidence |
|---|---|---|
| 1. Audit | done | [docs/final_project_execution_plan_ru.md](final_project_execution_plan_ru.md) |
| 2. Read-only API | done | [src/api/main.py](../src/api/main.py), [src/api/demo_readonly.py](../src/api/demo_readonly.py) |
| 3. Demo cases | done | [docs/final_demo_cases_ru.md](final_demo_cases_ru.md) |
| 4. Notebook deep dive | mostly done | [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb) |
| 5. ML polish | mostly done | [docs/ml_error_analysis_ru.md](ml_error_analysis_ru.md), [docs/model_card.md](model_card.md) |
| 6. Docs/demo script | done | [docs/demo_script_ru.md](demo_script_ru.md), [docs/timed_defense_rehearsal_ru.md](timed_defense_rehearsal_ru.md) |
| 7. Final checks | done/lightweight | [docs/final_defense_smoke_checklist_ru.md](final_defense_smoke_checklist_ru.md) |

## Endpoint Coverage

| Endpoint | Status | Notes |
|---|---|---|
| `GET /health` | done | returns app/env/status |
| `GET /health/db` | done | checks PostgreSQL without exposing secrets |
| `GET /version` | done | returns app metadata |
| `GET /games` | done | supports `limit`, `offset`, `search` |
| `GET /games/{game_id}` | done | returns canonical card and source links |
| `GET /games/{game_id}/similar` | done | reads `dm.game_recommendations` |
| `POST /recommend` | done | supports `seed_game_ids` and `liked_games` |
| `GET /matches/review` | done | supports `review_status` and `decision` filters |
| `GET /explain/recommendation` | done | supports DB-first `game_id`, artifact fallback, grounded metadata |
| `GET /explain/match` | done | supports `pair_id`, grounded metadata |
| `GET /stats/catalog` | done | DB-first with artifact fallback |
| `GET /stats/ml` | done | DB-first counts plus ER metrics |

## Remaining Items From Original Plan

### P1. Notebook interactivity

Original plan asked for:

- demo case selector;
- threshold selector;
- recommendation selector;
- optional `notebooks/04_live_demo_cases.ipynb`.

Current state:

- main notebook executes and has all core ML sections;
- backup notebook [notebooks/04_live_demo_cases.ipynb](../notebooks/04_live_demo_cases.ipynb)
  exists and reads prepared demo artifacts;
- it is not a widget-driven selector notebook because `ipywidgets` is not required for the
  project runtime.

Decision:

- not blocking for defense because FastAPI is now the primary demo interface;
- backup notebook covers offline fallback without adding widget dependencies.

### P1. Future work document

Status: done.

Evidence:

- [docs/future_work_ru.md](future_work_ru.md)

### P1/P2. Full HTML notebook export

Original plan suggested executed copy or HTML export.

Current state:

- notebook executes via `nbconvert` to `/tmp`;
- executed artifact is intentionally not committed to Git.

Decision:

- not blocking;
- optional export can be generated before defense and kept outside Git.

### P2. Stronger RAG/LLM rendering

Original plan explicitly says not to build heavy LangChain/RAG before defense.

Current state:

- grounded template explanations exist;
- API returns `explanation_ru`, `facts_used`, `sources_used`;
- LLM does not make decisions.

Decision:

- keep as future work.

## Recommended Next Sequential Work

1. Optionally generate HTML export of `03_ml_research_defense_report.ipynb` outside Git.
2. Run full `make ml-defense-all` if time allows.
3. Push branch and merge into `develop` when user confirms.

## Current Non-Blocking Limitations

- `games_with_ru_name = 0`: Russian explanations exist, but canonical RU aliases are not
  populated.
- Some duplicate-looking canonical rows remain; this is documented as ER future work.
- Recommendation model is content-based, not collaborative filtering.
- The notebook has no widget selectors yet; live API covers the interactive demo role.
