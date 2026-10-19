# 0008 — Не сканировать других NPC для пассивного заключённого

В npcVision вычисление `attack` и все предыдущие проверки игрока сохранены. Перебор остальных персонажей теперь выполняется только при `guard || attack`. У заключённого с attack=false результат found нигде не используется, а его canSee не имеет side effects. На AI_WAYPOINT/AI_SLEEP эта лишняя работа раньше выполнялась регулярно.

Охранники продолжают сканировать даже без драки: canSee обнаруживает COLL_DIGGED_WALL и выставляет причину solitary. Нельзя просто перенести фильтр other.fighting перед canSee. Также не меняется порядок RNG-вызовов до цикла и при выборе противника.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0008-passive-inmate-vision.patch
git apply patches/performance/standalone/0008-passive-inmate-vision.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Память не увеличивается. Таблица измеряет только извлечённый candidate-scan блок, не полный tickAI/NPC-цикл! Сценарий guard — отрицательный контроль, а большой коэффициент waypoint нельзя переносить на весь кадр или на пользовательские 917 мс.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:guard | 8.447 | 8.350 | 0.986× | 0.874–1.147 |
| irongate:waypoint | 7.194 | 0.484 | 14.817× | 13.647–16.269 |
| jungle:guard | 7.422 | 7.288 | 1.009× | 0.913–1.069 |
| jungle:waypoint | 6.812 | 0.609 | 11.374× | 10.941–12.891 |
| perks:guard | 6.799 | 7.129 | 0.993× | 0.866–1.034 |
| perks:waypoint | 5.579 | 0.473 | 11.742× | 9.542–14.297 |
| sanpancho:guard | 7.983 | 8.154 | 0.997× | 0.768–1.057 |
| sanpancho:waypoint | 8.285 | 0.544 | 15.187× | 13.799–17.195 |
| shanktonstatepen:guard | 9.741 | 9.399 | 1.005× | 0.867–1.237 |
| shanktonstatepen:waypoint | 10.132 | 0.500 | 20.748× | 17.116–22.588 |
| stalagflucht:guard | 4.944 | 5.005 | 0.985× | 0.879–1.154 |
| stalagflucht:waypoint | 6.006 | 0.493 | 11.766× | 10.840–12.645 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0008-passive-inmate-vision.patch
git apply --reverse patches/performance/standalone/0008-passive-inmate-vision.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
