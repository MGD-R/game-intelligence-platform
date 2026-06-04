# Финальный execution plan до защищаемого demo-продукта

Источник: `/Users/mgdr/Downloads/final_project_implementation_plan_ru.md`.

Цель ближайшего цикла - не добавлять тяжелые новые ML-исследования, а собрать уже
реализованную data/ML-логику в демонстрируемую платформу:

```text
multi-source data -> raw/staging -> ER -> canonical catalog
-> recommendations -> explanations -> FastAPI demo -> ML notebook deep dive
```

## Текущее состояние после аудита

### Уже есть

- Docker Compose, PostgreSQL, FastAPI, worker, Makefile.
- Слои БД: `raw`, `stg`, `ml`, `dm`, `meta`.
- Ingestion/staging/jobs для RAWG, Wikidata, Steam, Wikipedia, IGDB.
- ML-ready datasets, ER baseline, manual review, canonical catalog.
- Research artifacts: ER, graph, embeddings, IGDB matching, recommendations,
  Bayesian rating, grounded RAG explanations.
- Notebook для защиты ML-исследований:
  `notebooks/03_ml_research_defense_report.ipynb`.
- PPTX deck:
  `docs/presentations/game-intelligence-ml-defense.pptx`.
- Readiness gate:
  `make ml-defense-all`.

### Главный P0-разрыв

FastAPI был главным слабым местом demo-интерфейса. На текущем шаге P0 read-only слой
закрыт:

- `/health`, `/health/db`, `/health/sources`, `/version` работают.
- `/games`, `/games/{game_id}`, `/games/{game_id}/similar`, `/recommend`,
  `/matches/review`, `/explain/recommendation`, `/explain/match` реализованы как
  read-only demo endpoints.
- `/stats/catalog` и `/stats/ml` реализованы.
- endpoints читают PostgreSQL при доступности и используют подготовленные research artifacts
  как fallback там, где это уместно для demo/research слоя.

## Этапы работ

### Этап 1. P0 Audit And Planning

Результат:

- этот execution plan;
- список текущих API-заглушек;
- подтверждение доступных `dm/ml/stg` таблиц и generated artifacts.

Acceptance criteria:

- `docs/final_project_execution_plan_ru.md` есть в репозитории;
- README ссылается на итоговую русскоязычную аналитику;
- текущие API gaps явно описаны.

### Этап 2. P0 Read-only API Demo Layer

Реализовать endpoints, которые читают уже подготовленные данные и не запускают тяжелые
вычисления онлайн.

Порядок:

1. `GET /stats/catalog`
2. `GET /stats/ml`
3. `GET /games`
4. `GET /games/{game_id}`
5. `GET /games/{game_id}/similar`
6. `POST /recommend`
7. `GET /matches/review`
8. `GET /explain/recommendation`
9. `GET /explain/match`

Design:

- primary path: PostgreSQL `dm/ml/stg` tables;
- fallback path: generated artifacts under `data/artifacts/reports`;
- API must not expose secrets;
- API must not retrain models or call external APIs.

Acceptance criteria:

- endpoints return `200`, not `501`;
- empty DB does not crash demo endpoints;
- fallback responses include `data_origin`;
- unit tests cover no-DB/no-artifact-safe behavior.

### Этап 3. P0 Stable Demo Cases

Подготовить 5-7 проверенных cases:

- уверенное объединение;
- ложнопохожая пара;
- спорный match/manual review;
- рекомендация по одной игре;
- рекомендация по списку любимых игр;
- Bayesian rating example;
- grounded explanation example.

Acceptance criteria:

- `docs/demo_cases_ru.md` описывает cases;
- cases доступны через API или notebook/artifact;
- для каждого case есть тезис, который он доказывает.

### Этап 4. P1 Notebook Deep Dive

Доработать `notebooks/03_ml_research_defense_report.ipynb`:

- русские пояснения для ключевых блоков;
- demo case selector;
- threshold selector;
- recommendation selector;
- без онлайн-загрузок и долгого обучения.

Acceptance criteria:

- notebook открывается после `make ml-defense-all`;
- читает готовые CSV/JSON/SVG;
- не требует API calls или model training в live demo.

### Этап 5. P1/P2 ML Explanation Polish

Усилить уже реализованные исследования:

- `docs/ml_error_analysis_ru.md`;
- threshold policy notes;
- recommendation factors in API;
- Bayesian rating examples;
- grounded explanations with `facts_used` and `sources_used`.

Acceptance criteria:

- проверяющий видит, где именно находится ML;
- ограничения и future work отделены от текущей реализации.

### Этап 6. P0/P1 Demo Documentation

Документы:

- `docs/demo_script_ru.md`;
- README block `Demo для защиты`;
- при необходимости `docs/future_work_ru.md`.

Acceptance criteria:

- есть последовательность запуска и показа demo;
- Swagger UI, notebook и PPTX связаны в один сценарий.

### Этап 7. P0 Final Checks

Проверки:

```bash
make ml-defense-all
python -m compileall src
ruff check src tests
pytest
docker compose config -q
curl http://localhost:8000/health
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Acceptance criteria:

- проект запускается;
- API demo работает;
- notebook demo работает;
- README команды актуальны;
- известные ограничения описаны.

## Текущий спринт

Начальный P0 API-блок:

1. `GET /stats/catalog` - реализовано.
2. `GET /stats/ml` - реализовано.
3. `GET /games` - реализовано.
4. `GET /games/{game_id}` - реализовано.
5. `GET /games/{game_id}/similar` - реализовано.
6. `POST /recommend` - реализовано.
7. `GET /matches/review` - реализовано.
8. `GET /explain/recommendation` - реализовано.
9. `GET /explain/match` - реализовано.
10. tests for P0 API demo endpoints - реализовано.
11. docs update - реализовано.

Следующий P0-шаг:

1. Выбрать стабильные demo cases: 3-5 игр, 3 рекомендации, 3 match explanations,
   3 manual review examples - реализовано.
2. Сформировать `docs/demo_script_ru.md` - реализовано.
3. Сформировать `docs/final_demo_cases_ru.md` - реализовано.
4. Проверить demo script через реальный `localhost:8000` - реализовано.

Следующий шаг:

1. Проверить notebook/report/model card/presentation materials как единый комплект защиты -
   реализовано.
2. Сформировать финальный smoke checklist для защиты - реализовано:
   `docs/final_defense_smoke_checklist_ru.md`.
3. При необходимости обновить presentation outline на основе выбранных demo cases -
   следующий optional шаг.

Текущий статус: `GO` для финального demo smoke. Следующий practical step: либо обновить PPTX
под новые API/demo cases, либо зафиксировать изменения коммитом.
