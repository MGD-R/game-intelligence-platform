# Timed Defense Rehearsal RU

Сценарий репетиции защиты на 7-10 минут. Цель — показать проект как единую
data/ML-платформу, а не набор разрозненных скриптов.

## Перед Репетицией

Запустить стек:

```bash
make up-dev
make ps
```

Проверить API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Открыть заранее:

- [docs/presentations/game-intelligence-ml-defense.pptx](presentations/game-intelligence-ml-defense.pptx)
- [docs/final_demo_cases_ru.md](final_demo_cases_ru.md)
- [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb)
- Swagger UI: `http://localhost:8000/docs`

## Основной Тайминг На 10 Минут

| Time | Slide/Block | What To Show | Key Message |
|---:|---|---|---|
| 0:00-0:40 | 1. Problem | title + problem framing | Проект решает задачу построения canonical game catalog из разнородных источников. |
| 0:40-1:20 | 2. Data Pipeline | `/stats/catalog`, `/stats/ml` | Данные прошли ingestion/staging/ML/canonical слои, а не просто загружены в CSV. |
| 1:20-2:00 | 3. Manual Review | `/matches/review?review_status=reviewed` | Для ER нужны и positive, и negative labels; похожее имя не равно same game. |
| 2:00-3:10 | 4. ER Baseline | notebook metrics section | Logistic Regression baseline даёт сильные метрики и остаётся объяснимым. |
| 3:10-4:00 | 5. Merge Governance | threshold/merge strategy artifacts | Модель используется как controlled scoring layer, а не blind auto-merge. |
| 4:00-4:50 | 6. Graph Risk | graph analysis summary | Ошибка одной пары может испортить компонент, поэтому нужен graph risk контроль. |
| 4:50-5:30 | 7. Embeddings | embedding comparison | Lightweight title embeddings показывают развитие baseline без тяжёлых внешних моделей. |
| 5:30-6:10 | 8. IGDB Lane | IGDB matching summary | IGDB полезен как ranked candidate/enrichment source, но требует review governance. |
| 6:10-7:10 | 9. Recommendations | `/games/{DOOM}/similar`, `/recommend` | Рекомендации — explainable content-based baseline без user interactions. |
| 7:10-7:50 | 10. Bayesian Rating | Bayesian rating examples | Bayesian adjustment снижает шум оценок при малом числе голосов. |
| 7:50-8:40 | 11. Explanations | `/explain/recommendation`, `/explain/match` | Explanation layer объясняет рассчитанные факты и не принимает ML-решения. |
| 8:40-10:00 | 12. Conclusions | checklist + limitations | Проект готов как ER-first end-to-end data/ML platform; future work честно отделён. |

## Сокращённый Тайминг На 7 Минут

Если времени мало, объединить блоки:

| Time | Block | Action |
|---:|---|---|
| 0:00-0:45 | Problem + architecture | Один тезис: multi-source canonical catalog. |
| 0:45-1:30 | Data snapshot | Быстро показать `/stats/catalog` и `/stats/ml`. |
| 1:30-3:00 | ER + manual review | Показать reviewed pair и метрики ER. |
| 3:00-4:00 | Governance | Объяснить threshold policy и graph risk без подробных графиков. |
| 4:00-5:00 | Recommendations | Показать DOOM -> DOOM II через `/similar`. |
| 5:00-5:50 | Explanations | Показать `/explain/match` или `/explain/recommendation`. |
| 5:50-7:00 | Conclusions | GO checklist, ограничения, next steps. |

## Live API Команды

Health/statistics:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Catalog:

```bash
curl "http://localhost:8000/games?limit=3&search=doom"
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb"
```

Recommendations:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=3"
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"seed_game_ids":["015078c4-059b-5a5f-ab7e-e8a43d3912eb"],"limit":3}'
```

Manual review:

```bash
curl "http://localhost:8000/matches/review?limit=3&review_status=reviewed"
```

Explanations:

```bash
curl "http://localhost:8000/explain/recommendation?limit=2"
curl "http://localhost:8000/explain/match?limit=2"
```

## Что Сказать На Сложные Вопросы

### Почему не collaborative filtering?

В проекте нет user interaction data: просмотров, покупок, лайков, playtime. Поэтому
корректный MVP — content-based recommender по canonical features. Collaborative filtering
можно добавить только после появления пользовательских событий.

### Почему Logistic Regression, а не тяжёлая модель?

Для ER-first защиты важна explainability: признаки, коэффициенты, threshold policy,
manual review и controlled merge governance. Logistic Regression даёт сильный baseline и
позволяет понятно объяснить решения. Более тяжёлые модели — следующий цикл.

### Почему остаются duplicate-looking canonical entries?

Это ожидаемая часть ER-задачи. Проект не скрывает такие кейсы, а показывает механизмы
контроля: manual review, graph risk analysis, threshold policies и future iterations.

### LLM принимает решения?

Нет. Explanation/RAG-like слой только объясняет уже рассчитанные факты: признаки,
вероятности, ручные labels, shared recommendation factors. Решения принимаются
ER/recommendation pipeline.

### Зачем IGDB, если нет полного id matching?

IGDB используется как ranked search/enrichment lane. Он расширяет coverage и даёт материал
для ML matching research, но lower-rank candidates требуют manual review governance.

## Fallback Если Live API Не Работает

Если `localhost:8000` недоступен:

1. Показать [docs/final_demo_cases_ru.md](final_demo_cases_ru.md).
2. Показать [docs/final_defense_smoke_checklist_ru.md](final_defense_smoke_checklist_ru.md).
3. Открыть notebook [03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb).
4. Использовать artifacts:
   - `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`
   - `data/artifacts/reports/ml_defense_presentation/ml_defense_speaker_notes.md`
   - `data/artifacts/reports/rag_explanations/match_explanation_examples.csv`
   - `data/artifacts/reports/rag_explanations/recommendation_explanation_examples.csv`

Формулировка:

> Live API является read-only demo layer поверх уже подготовленного DWH/ML контура. Если
> сервис недоступен, результаты всё равно воспроизводимы через notebook, reports и artifacts.

## Финальная Фраза

> Главный результат проекта — не одна модель, а воспроизводимая data/ML-платформа:
> внешние источники нормализуются в canonical catalog, Entity Resolution управляется через
> ML scoring и manual review, а рекомендации и объяснения строятся поверх проверенных
> canonical facts.
