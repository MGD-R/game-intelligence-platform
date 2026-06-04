# Demo Script RU

Этот сценарий предназначен для финальной демонстрации `Game Intelligence Platform` как
единой data/ML-платформы: источники -> staging -> entity resolution -> canonical catalog ->
recommendations -> grounded explanations -> FastAPI demo.

## 1. Подготовка окружения

Цель: показать, что проект воспроизводимо запускается локально через Docker Compose.

Команды:

```bash
make up-dev
make ps
```

Проверки:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/version
```

Что сказать:

- API работает как read-only demo layer.
- PostgreSQL содержит raw/staging/ml/dm слои.
- Demo endpoints не изменяют canonical catalog и не запускают внешние API-загрузки.

## 2. Общая статистика платформы

Команды:

```bash
curl http://localhost:8000/stats/catalog
curl http://localhost:8000/stats/ml
```

Ожидаемый смысл результата:

- `source_games` показывает общий объём записей из источников.
- `source_games_by_source` показывает вклад RAWG, Wikidata, Steam, IGDB.
- `canonical_games` показывает размер объединённого каталога.
- `recommendations_count` показывает объём построенного recommendation layer.
- `candidate_pairs`, `labeled_pairs`, `manual_positive_labels`,
  `manual_negative_labels` показывают базу для ER/ML-исследования.
- `entity_resolution_*` метрики показывают результат обучения и валидации модели.

Текущий локальный снимок, полученный через API:

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

## 3. Каталог игр

Команды:

```bash
curl "http://localhost:8000/games?limit=5&search=doom"
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb"
```

Если указанный UUID отсутствует в локальном окружении, сначала взять UUID из результата:

```bash
curl "http://localhost:8000/games?limit=3&search=doom"
```

Демонстрационные игры из текущей БД:

| Игра | UUID | Год | Источников |
|---|---|---:|---:|
| DOOM | `015078c4-059b-5a5f-ab7e-e8a43d3912eb` | 1993 | 2 |
| Akalabeth: World of Doom | `b46f754f-8334-560a-a3ad-fc7c5c5114c6` | 1979 | 4 |
| Bridge Constructor Portal | `7047f8a1-3ccc-51d0-9dc9-4c69cb864687` | 2017 | 4 |

Что показать:

- `GET /games` работает как searchable catalog.
- `GET /games/{game_id}` показывает canonical facts: имя, год, описание, жанры,
  платформы, ratings и source links.
- Source links демонстрируют, из каких систем была собрана canonical карточка.

## 4. Рекомендации

Команды:

```bash
curl "http://localhost:8000/games/015078c4-059b-5a5f-ab7e-e8a43d3912eb/similar?limit=5"
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"seed_game_ids":["015078c4-059b-5a5f-ab7e-e8a43d3912eb"],"limit":5}'
```

Примеры из текущей БД:

| Seed | Recommendation | Score |
|---|---|---:|
| DOOM | DOOM II | 0.393643 |
| DOOM | Doom 64 | 0.268882 |
| Bridge Constructor Portal | Bridge Constructor Stunts | 0.531429 |
| Bridge Constructor Portal | Bridge Constructor | 0.492958 |

Что сказать:

- Рекомендации сейчас являются explainable content-based baseline.
- Это не collaborative filtering, потому что в проекте нет user interaction данных.
- Score основан на пересечении content features: жанры, платформы, компании, decade и
  другие признаки.

## 5. Entity Resolution И Manual Review

Команды:

```bash
curl "http://localhost:8000/matches/review?limit=5&review_status=reviewed"
curl "http://localhost:8000/matches/review?limit=5&review_status=all"
```

Важно:

- `review_status=pending` может быть пустым, если текущая очередь уже размечена.
- Для демонстрации используйте `review_status=reviewed` или `review_status=all`.

Примеры reviewed-пар из текущей БД:

| Pair | Source A | Source B | Manual label | Model probability |
|---|---|---|---:|---:|
| `d735ca21-ef72-49a6-a958-f12dd69dd87a` | DOOM | Doom | false | 0.000028 |
| `880b5292-520b-4fcb-95cf-62075871dae4` | DIG DUG | Dig Dug | false | 0.000048 |
| `d31508d8-6307-4013-9d8b-f8ac1d233641` | Silent Hill 2 | Silent Hill 2 | false | 0.000058 |

Что сказать:

- Одинаковое или похожее название само по себе не гарантирует совпадение сущности.
- Разные годы, edition/remaster/DLC/franchise cases создают риск ложного merge.
- Manual review нужен не как ручная замена модели, а как источник качественных labels и
  контроль сложных границ.

## 6. Grounded Explanations

Команды:

```bash
curl "http://localhost:8000/explain/recommendation?limit=3"
curl "http://localhost:8000/explain/match?limit=3"
```

Примеры recommendation explanations:

| Seed | Recommendation | Score |
|---|---|---:|
| 2010 FIFA World Cup South Africa | FIFA Soccer 11 | 1.0 |
| 2010 FIFA World Cup South Africa | Madden NFL 11 | 1.0 |
| 2010 FIFA World Cup South Africa | Madden NFL 13 Social | 1.0 |

Примеры match explanations:

| Subject | Manual label | Model probability |
|---|---:|---:|
| Call of Duty: Modern Warfare (2019) <> Call of Duty: Modern Warfare - Season One | true | 0.500054 |
| Spider-Man (2000) <> Spider-Man | true | 0.488211 |
| Disco Elysium: Final Cut <> Disco Elysium: The Final Cut Bundle | true | 0.514817 |

Что сказать:

- Explanation layer не принимает решения.
- Объяснение строится поверх рассчитанных фактов: признаков пары, прогноза модели,
  ручной разметки и recommendation factors.
- Это безопаснее, чем использовать LLM как источник истины.

## 7. ML Research Deep Dive

Основные материалы:

- [ML research defense report](../notebooks/03_ml_research_defense_report.ipynb)
- [ML findings](ml_research_findings.md)
- [ML defense runbook](ml_research_defense_runbook.md)
- [Model card](model_card.md)
- [Platform analytics](platform_analytics_ru.md)

Что показать:

- дообучение ER на ручных positive/negative labels;
- confusion matrix и threshold policies;
- comparison rule baseline vs Logistic Regression vs weighted v3c;
- ablation study;
- calibration/Brier score;
- active learning candidates;
- canonical merge strategy comparison;
- graph analysis и risky clusters;
- recommendation baseline и grounded explanations.

## 8. Итоговый Вывод Для Защиты

Короткий тезис:

> Проект демонстрирует end-to-end data/ML platform, где внешние источники объединяются в
> canonical catalog, а ML используется как управляемый слой scoring/manual-review/controlled
> hybrid matching. Рекомендации и объяснения построены поверх canonical facts, поэтому demo
> показывает не только модель, но и полный инженерный контур данных.

Что уже готово:

- ingestion из нескольких источников;
- staging и canonical layers;
- entity resolution features, labels, model, metrics;
- recommendation baseline;
- grounded explanations;
- read-only FastAPI demo endpoints;
- notebook/report/model card/runbook.

Что остаётся до финальной защиты:

- пройти этот demo script на чистом локальном запуске;
- выбрать 10-12 окончательных слайдовых кейсов;
- проверить, что notebook открывается и все ключевые таблицы/графики доступны;
- при необходимости добавить 2-3 manual review кейса для спорных examples, если защита
  требует дополнительного пояснения ошибок модели.
