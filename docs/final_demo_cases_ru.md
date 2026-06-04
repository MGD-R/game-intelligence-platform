# Final Demo Cases RU

Документ фиксирует проверенный набор демонстрационных кейсов для финальной защиты проекта.
Кейсы проверены через `app-dev` HTTP API на `localhost:8000`.

## Runtime Preconditions

Перед показом:

```bash
make up-dev
make ps
```

Ожидаемое состояние:

- `gip-postgres` запущен и `healthy`;
- `gip-app-dev` запущен и слушает `localhost:8000`;
- `gip-worker-dev` запущен для служебных команд;
- API endpoints работают в read-only режиме и не запускают внешние API downloads.

Важно: если `gip-app-dev` был остановлен, `curl`-часть demo script не будет работать,
хотя backend smoke через `TestClient` может проходить.

## Platform Snapshot

Проверенные команды:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/version
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Текущий snapshot:

| Метрика | Значение |
|---|---:|
| Source records | 31,462 |
| RAWG records | 10,039 |
| Wikidata records | 6,263 |
| Steam records | 4,816 |
| IGDB records | 10,344 |
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

## Catalog Cases

Проверенная команда:

```bash
curl "http://localhost:8000/games?limit=3&search=doom"
```

Кейсы:

| Case | UUID | Why Show |
|---|---|---|
| DOOM | `015078c4-059b-5a5f-ab7e-e8a43d3912eb` | canonical карточка с описанием, рейтингами, жанрами, платформами и source links |
| Akalabeth: World of Doom | `b46f754f-8334-560a-a3ad-fc7c5c5114c6` | пример игры, связанной из 4 источников |
| Bridge Constructor Portal | `7047f8a1-3ccc-51d0-9dc9-4c69cb864687` | пример multi-source карточки и хороших content recommendations |

Detail command:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb"
```

Что показать:

- canonical facts;
- source links;
- почему один catalog endpoint удобнее, чем просмотр RAWG/Wikidata/Steam/IGDB отдельно.

## Recommendation Cases

Проверенные команды:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=3"
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"seed_game_ids":["015078c4-059b-5a5f-ab7e-e8a43d3912eb"],"limit":3}'
```

Проверенные кейсы:

| Seed | Recommendation | Score | Why Show |
|---|---|---:|---|
| DOOM | DOOM II | 0.393643 | близкий жанр/серия/content features |
| DOOM | Doom 64 | 0.268882 | похожая franchise/genre логика |
| Bridge Constructor Portal | Bridge Constructor Stunts | 0.531429 | хороший пример content-based объяснимости |
| Bridge Constructor Portal | Bridge Constructor | 0.492958 | пример рекомендаций без user interactions |

Тезис:

- Это explainable content-based recommender.
- Он не заменяет collaborative filtering, потому что пользовательских интеракций в проекте нет.
- Для защиты это корректный baseline, так как он объясним и построен поверх canonical facts.

## Manual Review / ER Cases

Проверенная команда:

```bash
curl "http://localhost:8000/matches/review?limit=5&review_status=reviewed"
```

Кейсы:

| Pair ID | Pair | Label | Probability | Why Show |
|---|---|---:|---:|---|
| `d735ca21-ef72-49a6-a958-f12dd69dd87a` | DOOM <> Doom | false | 0.000028 | одинаковое имя, но разные годы/сущности |
| `880b5292-520b-4fcb-95cf-62075871dae4` | DIG DUG <> Dig Dug | false | 0.000048 | похожее имя не равно безопасному merge |
| `d31508d8-6307-4013-9d8b-f8ac1d233641` | Silent Hill 2 <> Silent Hill 2 | false | 0.000058 | показывает важность source/year/context signals |

Дополнительные defense cases из research artifacts:

| Type | Item A | Item B | Score | Why Show |
|---|---|---|---:|---|
| active learning | Remnant 2 | Remnant II | 0.500723 | high uncertainty pair для следующей ручной проверки |
| active learning | Quake III Arena | Quake III: Team Arena | 0.500612 | пример спорной boundary между игрой/аддоном |
| rejected risky match | The Jackbox Party Pack 4 | The Jackbox Party Pack | 0.838165 | похожее название, но разные сущности |
| rejected risky match | BioShock 2 Remastered | BioShock Remastered | 0.829243 | remaster/franchise confusion |

Тезис:

- ER-модель не должна быть слепым auto-merge механизмом.
- Ценность ML здесь в scoring, threshold policy, active learning и manual-review governance.
- Пары с одинаковыми названиями являются хорошим материалом для демонстрации ошибок
  простого rule-based подхода.

## Grounded Explanation Cases

Проверенные команды:

```bash
curl "http://localhost:8000/explain/recommendation?limit=2"
curl "http://localhost:8000/explain/match?limit=2"
```

Recommendation explanation cases:

| Seed | Recommendation | Why Show |
|---|---|---|
| 2010 FIFA World Cup South Africa | FIFA Soccer 11 | объяснение через общие признаки жанра, разработчика, издателя, платформы и decade |
| 2010 FIFA World Cup South Africa | Madden NFL 11 | ещё один пример sports/EA baseline recommendation |

Match explanation cases:

| Pair | Label | Probability | Why Show |
|---|---:|---:|---|
| Call of Duty: Modern Warfare (2019) <> Call of Duty: Modern Warfare - Season One | true | 0.500054 | сложный positive case, где модель осторожна |
| Spider-Man (2000) <> Spider-Man | true | 0.488211 | пример необходимости ручных labels и explanation layer |
| Disco Elysium: Final Cut <> Disco Elysium: The Final Cut Bundle | true | 0.514817 | edition/bundle boundary для обсуждения |

Тезис:

- Explanation layer не принимает решений.
- Он объясняет уже рассчитанные факты: features, model probability, manual label,
  recommendation shared factors.
- Это безопасная форма RAG/LLM-like объяснений для защиты.

## ML Research Materials

Проверенные материалы:

| Artifact | Status | Purpose |
|---|---|---|
| [notebooks/03_ml_research_defense_report.ipynb](../notebooks/03_ml_research_defense_report.ipynb) | exists, 56 cells | единый notebook для ML deep dive |
| [docs/ml_research_findings.md](ml_research_findings.md) | exists | выводы по ML-исследованиям |
| [docs/ml_research_defense_runbook.md](ml_research_defense_runbook.md) | exists | сценарий объяснения ML-части |
| [docs/model_card.md](model_card.md) | exists | model card |
| [docs/platform_analytics_ru.md](platform_analytics_ru.md) | exists | русское описание платформы |
| [docs/demo_script_ru.md](demo_script_ru.md) | exists | пошаговый demo script |

Readiness artifacts:

| Metric | Value |
|---|---:|
| Required artifacts | 10 |
| Missing required artifacts | 0 |
| Demo sequence steps | 9 |
| Metric count | 9 |
| Missing metrics | 0 |
| Overall status | ready |
| Defense demo cases | 14 |
| Active learning candidates | 250 |
| RAG fact cards | 50 |
| Match explanations | 25 |
| Recommendation explanations | 25 |

## Recommended Slide/Demo Order

1. Problem: разные источники дают разные записи об одних и тех же играх.
2. Architecture: ingestion -> raw/stg -> ER -> canonical -> recommendations -> explanations -> API.
3. Data snapshot: source counts, canonical count, recommendation rows.
4. Catalog API: `GET /games`, `GET /games/{id}`.
5. ER problem: похожие названия и разные сущности.
6. Manual review: positive/negative labels and why both are needed.
7. ER model metrics: F1/precision/recall/ROC-AUC/PR-AUC.
8. Threshold policy: why controlled hybrid is better than blind auto-merge.
9. Recommendations: content-based baseline and examples.
10. Grounded explanations: no LLM decisions, only fact-based explanations.
11. Readiness: artifacts/notebook/report/model card.
12. Next steps: improve embeddings, IGDB search matching, user interactions if available.

## Known Demo Notes

- `review_status=pending` can return zero rows because the current manual queue was already
  reviewed. Use `review_status=reviewed` or `review_status=all` for demo.
- Some duplicate-looking canonical entries still exist. This is acceptable for defense:
  it demonstrates why ER governance and future improvement matter.
- `games_with_ru_name = 0`; Russian UI/explanations are present, but canonical Russian aliases
  are not populated yet.
- Recommendation explanations come from prepared RAG explanation artifacts, while recommendation
  rankings come from `dm.game_recommendations`.
