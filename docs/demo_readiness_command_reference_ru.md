# Справочник команд Demo Readiness

Этот файл поясняет команды, которые показываются в UI на странице
`Stats/readiness` и в ответе API `GET /stats/readiness`.

Назначение раздела readiness: быстро понять, какие локальные данные и
презентационные artifacts уже доступны, чего не хватает для демонстрации, и
какую команду нужно запустить для восстановления недостающей части.

## Где это используется

- UI: `http://localhost:8501`, страница `Stats/readiness`.
- API: `GET /stats/readiness`.
- CLI: `make demo-readiness`.

## Команды из readiness recommendations

| Команда | Для чего нужна | Что появится в результате | Меняет БД | Внешние API |
|---|---|---|---|---|
| `make ml-defense-all` | Полностью пересобрать research/defense package. | ER strategy reports, graph/embedding/IGDB analysis, ML research summary, Bayesian rating, RAG explanations, readiness summary, presentation outline. | Нет production-merge изменений; пишет отчеты/artifacts. | Нет. |
| `make ml-research-defense` | Построить центральный ML research report для защиты. | `data/artifacts/reports/ml_research_defense/ml_research_defense_summary.json`, ablation/calibration CSV, active-learning candidates, recommendation examples, SVG charts. | Нет. | Нет. |
| `make ml-defense-readiness` | Проверить, что ML/research artifacts готовы к защите. | `data/artifacts/reports/ml_defense_readiness/ml_defense_readiness_summary.json`, metric snapshot, demo sequence, artifact checklist. | Нет. | Нет. |
| `make er-review-queue` | Обновить очередь ручной проверки ER-кандидатов. | Pending/review candidates в БД и последующий материал для export. | Да, обновляет ML/manual-review слой. | Нет. |
| `make er-export-review-queue` | Выгрузить manual review queue в CSV для проверки и презентации. | `entity_resolution_manual_review_pending.csv`, `entity_resolution_manual_review_reviewed.csv`. | Нет, только экспортирует. | Нет. |
| `make recommendations` | Пересобрать content-based рекомендации. | Таблицы/слой рекомендаций и artifacts для похожих игр. | Да, обновляет recommendation слой. | Нет. |
| `make bayesian-rating` | Построить исследование Bayesian-adjusted rating. | `canonical_bayesian_ratings.csv`, shrinkage examples, summary markdown, chart. | Нет. | Нет. |
| `make rag-explanations` | Сгенерировать grounded explanations на русском языке. | Match/recommendation explanation examples и grounded fact cards. | Нет. | Нет. |
| `make export-data-pack` | Сформировать переносимый data pack для demo/restore. | `data_packs/gip_demo_local` с parquet/jsonl/reports/manifest. | Нет. | Нет. |
| `make restore-from-files DATA_PACK=data_packs/gip_demo_local` | Восстановить локальные data/artifacts из готового data pack без API-download. | Локальные `data/` и artifacts, пригодные для demo/API/UI. | Может восстановить/обновить локальные таблицы/файлы в зависимости от pack scripts. | Нет. |

## Проверочные команды

| Команда | Для чего нужна | Ожидаемый результат |
|---|---|---|
| `make demo-readiness` | Проверить наличие локальных demo data, report artifacts, explanations и data pack. | `Status: ok`, `warning` или `error`, список found/missing artifacts и команды восстановления. |
| `make api-smoke` | Проверить основные demo API endpoints. | Все ключевые endpoints возвращают `200`. |
| `make notebook-check` | Проверить, что defense notebooks существуют и parseable. | Notebook check проходит без ошибок. |
| `make final-smoke` | Запустить минимальную финальную проверку перед демонстрацией. | Последовательно проходят `demo-readiness`, `api-smoke`, `notebook-check`. |

## Запуск UI

| Команда | Когда использовать | Что запускает |
|---|---|---|
| `make up-ui` | Основной standalone demo UI. | `postgres`, runtime `app`, `ui`; UI доступен на `http://localhost:8501`, API на `http://localhost:8000`. |
| `make up-ui-dev` | Когда уже нужен dev app stack и UI должен ходить в `app-dev`. | `postgres`, `app-dev`, `worker-dev`, `ui` с `API_BASE_URL=http://app-dev:8000`. |

Важно: `make up-dev` и `make up-ui` не стоит запускать одновременно как два
независимых стека, потому что runtime `app` и `app-dev` используют один host
port `8000`. Для UI поверх dev-стенда используйте `make up-ui-dev`.

## Как читать поле `recommendation`

`recommendation` в readiness payload - это короткая подсказка для восстановления
конкретного artifact. Для подробностей используйте:

- поле `command` в той же строке UI;
- поле `result`, где описан ожидаемый итог;
- этот справочник;
- общий runbook [ml_research_defense_runbook.md](ml_research_defense_runbook.md).

Если artifact уже находится в `found_artifacts`, команду обычно не нужно
запускать повторно. Она показана как справочная информация: чем artifact
воспроизводится при необходимости.
