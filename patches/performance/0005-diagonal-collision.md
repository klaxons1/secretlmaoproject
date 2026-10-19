# 0005 — Одна проверка геометрии диагонали вместо четырёх веток

Вместо отдельных right-up/right-down/left-up/left-down блоков используются две соседние ортогональные клетки: `(nx, y)` и `(x, ny)`. Их COLL_BIT_SOLID_AI объединяется OR. Проверка выхода новых x/y за карту по-прежнему выполняется раньше обращений к массиву.

Правило обхода staff doors не меняется: для боковых клеток, как и раньше, проверяется именно solid-bit, а не полный запрет дверей. Стоимости диагоналей остаются прежними.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0005-diagonal-collision.patch
git apply patches/performance/standalone/0005-diagonal-collision.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Дополнительной памяти нет. OR читает обе клетки даже тогда, когда первая уже блокирует движение; это обмен short-circuit на меньшее число ветвлений. На плотных препятствиях отдельный вариант не обязан быть быстрее.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:local | 15.991 | 14.404 | 1.096× | 1.022–1.333 |
| irongate:npc | 2167.969 | 1949.219 | 1.099× | 0.861–1.321 |
| irongate:spread | 11812.500 | 10937.500 | 1.090× | 0.824–1.336 |
| jungle:local | 16.571 | 15.259 | 1.107× | 0.830–1.327 |
| jungle:npc | 1871.094 | 1703.125 | 1.075× | 0.891–1.347 |
| jungle:spread | 12656.250 | 11250.000 | 1.103× | 0.968–1.714 |
| perks:local | 14.679 | 14.008 | 1.055× | 0.869–1.272 |
| perks:npc | 3734.375 | 3437.500 | 1.085× | 0.866–1.194 |
| perks:spread | 17937.500 | 16781.250 | 1.073× | 0.842–1.279 |
| sanpancho:local | 15.076 | 13.428 | 1.062× | 0.852–1.371 |
| sanpancho:npc | 2027.344 | 1886.719 | 1.048× | 0.983–1.385 |
| sanpancho:spread | 22625.000 | 21250.000 | 1.088× | 0.814–1.350 |
| shanktonstatepen:local | 12.329 | 11.932 | 1.064× | 0.858–1.361 |
| shanktonstatepen:npc | 6031.250 | 4937.500 | 1.076× | 1.020–1.302 |
| shanktonstatepen:spread | 14625.000 | 13031.250 | 1.079× | 0.846–1.340 |
| stalagflucht:local | 13.000 | 12.238 | 1.065× | 1.023–1.120 |
| stalagflucht:npc | 2539.062 | 2339.844 | 1.078× | 1.016–1.510 |
| stalagflucht:spread | 21125.000 | 19875.000 | 1.084× | 0.837–1.377 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0005-diagonal-collision.patch
git apply --reverse patches/performance/standalone/0005-diagonal-collision.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
