# Final Defense Smoke Checklist RU

Финальный smoke checklist для проверки проекта перед защитой. Цель проверки — убедиться,
что проект демонстрируется как единая платформа: данные -> ER/ML -> canonical catalog ->
recommendations -> explanations -> FastAPI demo -> notebook/report/deck.

Дата последней проверки: 2026-06-04.

## 1. Runtime Stack

Команды:

```bash
make up-dev
make ps
```

Ожидаемый результат:

| Service | Expected |
|---|---|
| `gip-postgres` | `Up`, `healthy`, port `5432` |
| `gip-app-dev` | `Up`, `healthy`, port `8000` |
| `gip-worker-dev` | `Up` |

Фактический результат последней проверки:

- `gip-postgres`: `Up`, `healthy`;
- `gip-app-dev`: `Up`, `healthy`;
- `gip-worker-dev`: `Up`;
- `localhost:8000` доступен.

## 2. API Smoke

Команды:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/version
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Ожидаемый результат:

- `/health`: `{"status":"ok"}`;
- `/health/db`: `database reachable`;
- `/version`: `game-intelligence-platform`;
- `/stats/catalog`: `data_origin = database`;
- `/stats/ml`: `readiness_status = ready`.

Фактический snapshot:

| Metric | Value |
|---|---:|
| Source records | 31,462 |
| Canonical games | 20,613 |
| Canonical source links | 35,607 |
| Recommendation rows | 147,254 |
| Candidate pairs | 17,320 |
| Manual labels | 1,966 |
| Positive labels | 1,029 |
| Negative labels | 937 |
| ER F1 | 0.948675 |
| ER precision | 0.983242 |
| ER recall | 0.916455 |
| ER ROC-AUC | 0.957274 |
| ER PR-AUC | 0.994369 |

## 3. Demo Endpoint Smoke

Проверенные команды:

```bash
curl "http://localhost:8000/games?limit=3&search=doom"
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb"
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=3"
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"seed_game_ids":["015078c4-059b-5a5f-ab7e-e8a43d3912eb"],"limit":3}'
curl "http://localhost:8000/matches/review?limit=3&review_status=reviewed"
curl "http://localhost:8000/explain/recommendation?limit=2"
curl "http://localhost:8000/explain/match?limit=2"
```

Проверенный основной demo seed:

| Game | UUID | Expected Result |
|---|---|---|
| DOOM | `015078c4-059b-5a5f-ab7e-e8a43d3912eb` | detail endpoint returns canonical facts |

Проверенные рекомендации:

| Seed | Recommendation | Score |
|---|---|---:|
| DOOM | DOOM II | 0.393643 |
| DOOM | Doom 64 | 0.268882 |

Ожидаемые особенности:

- `review_status=pending` может вернуть `0`, потому что текущая очередь ручной проверки
  уже закрыта.
- Для демонстрации manual review использовать `review_status=reviewed` или
  `review_status=all`.
- Explanation endpoints читают подготовленные grounded explanation artifacts.

## 4. Code Quality Smoke

Команды:

```bash
python -m compileall src
ruff check src tests
pytest tests/test_api.py
docker compose config -q
```

Фактический результат последней проверки:

| Check | Status |
|---|---|
| `compileall src` | passed |
| `ruff check src tests` | passed |
| `pytest tests/test_api.py` | `14 passed` |
| `docker compose config -q` | passed |

## 5. Notebook Smoke

Проверенный notebook:

- [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb)

Структура:

- `56` cells;
- `14` логических разделов;
- notebook успешно выполнился через `nbconvert` в `/tmp` без записи больших outputs в Git.

Команда:

```bash
python3 -m nbconvert --execute --to notebook \
  --output /tmp/03_ml_research_defense_report.executed.ipynb \
  notebooks/03_ml_research_defense_report.ipynb
```

Фактический результат:

- execution passed;
- output written to `/tmp/03_ml_research_defense_report.executed.ipynb`;
- notebook cell ids нормализованы, `MissingIDFieldWarning` больше не появляется.

## 6. Defense Artifacts Smoke

Проверенные материалы:

| Artifact | Status | Purpose |
|---|---|---|
| [docs/platform_analytics_ru.md](platform_analytics_ru.md) | exists | полное русское описание платформы |
| [docs/final_plan_gap_analysis_ru.md](final_plan_gap_analysis_ru.md) | exists | сверка исходного плана и текущего состояния |
| [docs/ml_error_analysis_ru.md](ml_error_analysis_ru.md) | exists | анализ ошибок и threshold trade-off |
| [docs/future_work_ru.md](future_work_ru.md) | exists | отделение текущей реализации от future work |
| [docs/ml_research_findings.md](ml_research_findings.md) | exists | ML findings |
| [docs/ml_research_defense_runbook.md](ml_research_defense_runbook.md) | exists | сценарий объяснения ML-части |
| [docs/model_card.md](model_card.md) | exists | model card |
| [docs/demo_script_ru.md](demo_script_ru.md) | exists | live demo script |
| [docs/final_demo_cases_ru.md](final_demo_cases_ru.md) | exists | проверенные demo cases |
| [docs/timed_defense_rehearsal_ru.md](timed_defense_rehearsal_ru.md) | exists | тайминг репетиции защиты |
| [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx) | exists | 12-slide PPTX deck |
| [notebooks/04_live_demo_cases.ipynb](../notebooks/04_live_demo_cases.ipynb) | exists | offline backup demo notebook |

Readiness target:

```bash
make ml-defense-readiness
```

Фактический результат:

| Metric | Value |
|---|---:|
| Overall status | ready |
| Required artifacts | 10 |
| Missing required artifacts | 0 |
| Metric count | 9 |
| Missing metrics | 0 |
| Demo sequence steps | 9 |

Presentation target:

```bash
make ml-defense-presentation
```

Фактический результат:

| Metric | Value |
|---|---:|
| Readiness status | ready |
| Slide count | 12 |
| Metric count | 9 |
| Remaining step count | 5 |

## 7. Presentation Alignment

Текущий deck:

- [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx)
- `12` slides;
- generated narrative source:
  `data/artifacts/reports/ml_defense_presentation/`.

Рекомендуемый порядок защиты:

| Slide | Topic | Demo/Evidence |
|---:|---|---|
| 1 | Problem And Research Goal | project goal, ER-first hypothesis |
| 2 | Data Pipeline And Corpus Scale | `/stats/catalog`, `/stats/ml` |
| 3 | Manual Review As Supervision | `/matches/review?review_status=reviewed` |
| 4 | Explainable ER Baseline | notebook metrics, ablation/calibration |
| 5 | Merge Governance | merge strategy comparison |
| 6 | Graph Risk Analysis | graph analysis artifacts |
| 7 | Lightweight Title Embeddings | embedding research artifacts |
| 8 | IGDB Search Lane | IGDB matching summary |
| 9 | Content-Based Recommendations | `/games/{id}/similar`, `/recommend` |
| 10 | Bayesian Rating | Bayesian rating artifacts |
| 11 | Grounded RAG Explanations | `/explain/recommendation`, `/explain/match` |
| 12 | Conclusions And Next Research Steps | model card, limitations, next steps |

Внешний файл `/Users/mgdr/Downloads/presentation_plan_ru.md` содержит корректную структуру,
но его формулировка про “API желательно доработать” уже устарела: read-only business/demo
endpoints реализованы и проверены.

## 8. Known Limitations To Say Openly

- Нет user interaction data, поэтому recommender является content-based baseline, а не
  collaborative filtering.
- Explanation layer не принимает решений; он объясняет рассчитанные факты.
- `games_with_ru_name = 0`: русские explanations есть, но canonical RU aliases пока не
  заполнены.
- В canonical catalog ещё есть duplicate-looking cases. Это не скрывать: использовать как
  аргумент в пользу ER governance, graph risk analysis и будущих iterations.
- Полный `ml-defense-all` может быть длиннее lightweight smoke, потому что пересобирает
  несколько research blocks.

## 9. Final Go/No-Go

Статус по текущей проверке: `GO`.

Основание:

- runtime stack поднят;
- HTTP demo endpoints работают;
- API tests passed;
- notebook executes;
- readiness artifacts status = `ready`;
- PPTX deck exists and has 12 slides;
- final demo script and demo cases documented.
- timed defense rehearsal documented.

Перед самой защитой рекомендуется повторить:

```bash
make up-dev
make ps
curl http://localhost:8000/health
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
python3 -m nbconvert --execute --to notebook \
  --output /tmp/03_ml_research_defense_report.executed.ipynb \
  notebooks/03_ml_research_defense_report.ipynb
```
