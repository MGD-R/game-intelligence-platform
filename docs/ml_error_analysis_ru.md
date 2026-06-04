# ML Error Analysis RU

Документ закрывает P1-пункт финального плана: показать, где ER-модель ошибается или
остаётся неопределённой, почему это нормально для Entity Resolution и как threshold/manual
review governance снижает риск неправильного canonical merge.

## Контекст

Центральная ML-задача проекта — Entity Resolution: определить, описывают ли две записи из
разных источников одну и ту же игру.

Модель не используется как слепой auto-merge. Она выдаёт `same_game_probability`, после чего
применяется политика:

| Probability | Intended action |
|---:|---|
| `P >= 0.95` | очень консервативный auto-merge / trusted candidate |
| `0.70 <= P < 0.95` | manual review / controlled candidate |
| `P < 0.70` | no merge |

Практический вывод: основная ценность модели — scoring, prioritization и active/manual review,
а не безусловное объединение всех похожих названий.

## Текущая Разметка И Метрики

| Metric | Value |
|---|---:|
| Candidate pairs | 17,320 |
| Manual labels | 1,966 |
| Positive labels | 1,029 |
| Negative labels | 937 |
| ER F1 | 0.948675 |
| ER precision | 0.983242 |
| ER recall | 0.916455 |
| ER ROC-AUC | 0.957274 |
| ER PR-AUC | 0.994369 |
| Brier score | 0.080893 |

Обучающая выборка включает ручные labels и weak positive labels. Ручная разметка особенно
важна для negative examples: похожее название, remaster, DLC, edition или franchise не всегда
означают одну и ту же игру.

## Threshold Error Trade-Off

Manual threshold evaluation для `v3c`:

| Threshold | Predicted positive | TP | FP | FN | Precision | Recall |
|---:|---:|---:|---:|---:|---:|---:|
| `0.50` | 1,097 | 1,005 | 92 | 24 | 0.916135 | 0.976676 |
| `0.70` | 1,025 | 997 | 28 | 32 | 0.972683 | 0.968902 |
| `0.90` | 415 | 415 | 0 | 614 | 1.000000 | 0.403304 |
| `0.95` | 14 | 14 | 0 | 1,015 | 1.000000 | 0.013605 |
| `0.98` | 0 | 0 | 0 | 1,029 | - | 0.000000 |
| `0.99` | 0 | 0 | 0 | 1,029 | - | 0.000000 |

Интерпретация:

- `0.50` хорошо ловит совпадения, но даёт слишком много false positives для production merge.
- `0.70` выглядит сильным исследовательским threshold: высокий precision и высокий recall.
- `0.90` и `0.95` подходят для очень консервативного auto-merge, но резко теряют recall.
- Поэтому для защиты важно говорить не “модель всё объединяет”, а “модель помогает выбрать
  безопасную стратегию merge/manual review”.

## Типы Ошибок И Рисков

### 1. False Positive Risk: похожие названия, разные сущности

| Case | Score | Почему риск |
|---|---:|---|
| The Jackbox Party Pack 4 <> The Jackbox Party Pack | 0.838165 | Похожие franchise titles, но разные игры/части серии. |
| BioShock 2 Remastered <> BioShock Remastered | 0.829243 | Remaster/franchise confusion: разные игры внутри одной серии. |
| BioShock Remastered <> BioShock 2 Remastered | 0.829243 | Обратный порядок той же проблемы: title overlap слишком сильный. |

Что снижает риск:

- manual negative labels;
- release year difference;
- platform/genre/company context;
- threshold policy;
- graph risk analysis для контроля transitive merge effects.

### 2. False Negative / Low-Confidence Positive Risk

| Case | Probability | Почему сложно |
|---|---:|---|
| Call of Duty: Modern Warfare (2019) <> Call of Duty: Modern Warfare - Season One | 0.500054 | Season/edition naming сбивает модель; нужна ручная проверка. |
| Spider-Man (2000) <> Spider-Man | 0.488211 | Короткие названия и разные source conventions снижают уверенность. |
| Disco Elysium: Final Cut <> Disco Elysium: The Final Cut Bundle | 0.514817 | Bundle/edition boundary, сложно отличить entity от package. |

Что снижает риск:

- active learning по uncertainty zone около `0.5`;
- добавление aliases и external ids;
- ручная разметка positive examples для edition/bundle cases;
- future embeddings по title/description.

### 3. Ambiguous Manual Review Candidates

| Pair | Score | Почему полезно для следующей разметки |
|---|---:|---|
| Remnant 2 <> Remnant II | 0.500723 | Возможное совпадение с разным написанием номера. |
| Quake III Arena <> Quake III: Team Arena | 0.500612 | Игра vs expansion/team edition ambiguity. |
| Super Time Force <> Super Time Force Ultra | 0.500549 | Base game vs enhanced edition. |

Эти пары хороши для демонстрации active learning: модель сама подсказывает, где следующая
ручная метка наиболее полезна.

### 4. Same-Name Negative Controls

| Pair | Label | Probability | Почему важно |
|---|---:|---:|---|
| DOOM <> Doom | false | 0.000028 | Одинаковое normalized name, но разные годы/сущности. |
| DIG DUG <> Dig Dug | false | 0.000048 | Name-only matching дал бы ошибку. |
| Silent Hill 2 <> Silent Hill 2 | false | 0.000058 | Контекст источника/года важнее строки названия. |

Эти примеры показывают, почему простого fuzzy matching недостаточно.

## Calibration Notes

Калибровка показывает, что вероятность модели полезна для ранжирования и threshold policy, но
не должна трактоваться как абсолютная истина:

- bin `0.7-0.8`: positive rate около `0.956`;
- bin `0.8-0.9`: positive rate около `0.996`;
- bin `0.9-1.0`: positive rate `1.0` на текущей проверочной выборке;
- низкие bins всё ещё содержат часть positive labels, что объясняет false negative risk.

Вывод: высокие scores можно использовать для trusted candidates, средние scores — для manual
review, низкие scores — для no-merge с возможностью active-learning пересмотра.

## Что Показывать На Защите

1. Сначала показать, что name-only matching опасен.
2. Затем показать reviewed negative examples с похожими названиями.
3. После этого показать threshold table: чем выше threshold, тем безопаснее precision, но ниже recall.
4. Показать active learning candidates как следующий цикл улучшения модели.
5. Завершить тезисом: ER-модель — это управляемый scoring layer.

## Future Work

- Улучшить multilingual aliases и canonical RU labels.
- Добавить neural title/description embeddings как следующий research cycle.
- Развить active learning UI для ручной проверки.
- Улучшить calibration и threshold governance на новых manual labels.
- Отдельно анализировать DLC/remaster/edition/package cases.
