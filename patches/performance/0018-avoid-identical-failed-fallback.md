# 0018 — Не повторять идентичный неудачный поиск для non-inmate

## Найденный bottleneck

В **двух** caller-местах `NPC.tickAI` (roam и рабочий маршрут) есть:

```java
pathfind(..., inmate, path) || pathfind(..., false, path)
```

Для `inmate=false` первый false вызывает **тот же самый поиск второй раз**: та же цель, старт, направление, collision map, buffer и разрешённые двери. Между операндами игровое состояние не меняется; pathfinder синхронный и очищает scratch state. Второй запуск не может исправить результат первого.

Патч добавляет только условие:

```java
pathfind(..., inmate, path) || (inmate && pathfind(..., false, path))
```

У заключённого первый вызов может запрещать staff doors. Его fallback с разрешёнными staff doors **сохранён**. При успешном первом вызове short-circuit работает как раньше. Уменьшается число полных A* на неудачный non-inmate запрос с двух до одного; алгоритм самого A* не меняется. Новых полей/массивов, кешей или invalidation нет.

Это не доказательство того, что таких запросов много в пользовательском Lights Out → Rollcall. Обычный waypoint-код — другой caller; не объявляю каждый Rollcall-запрос ускоренным вдвое.

## Проверки

На desktop Java и оригинальном KVM каждый: **432** four-way случая (heap/core, старый/новый caller), в том числе **160** non-inmate false и **272** сохранённых контрольных случаев. Сравниваются boolean, весь частично/полностью заполненный result, parent/G/H, visited/nodeDir/nodeX/nodeY и **весь heap scratch** в паре одинаковых ядер. Есть null/пустые/короткие/400/1200-short buffers.

Отдельный синтетический коридор со staff door принудительно требует `true → false`: все четыре варианта успешно находят путь и делают ровно два вызова. Собраны/preverified две полные игры: heap+0018 и all+0018.

## Намеренно изменяемый диагностический вывод

Один лишний `NO PATH` лог исчезает вместе с поиском. Инструментальные call/false/expansion counts также уменьшаются. Это **не побайтно одинаковый debug transcript**. Игровые решения/буферы проверены отдельно; stdout-консоль PSPKVM не замерялась.

## Применение и откат

Нужен master `0716b47205e297375d7a3848d923d5ce916eba6d` + **0003**. Можно после 0004–0016/0017: изменены только две строки в NPC. Основная и standalone-копия здесь одинаковы.

```sh
git apply --check patches/performance/0018-avoid-identical-failed-fallback.patch
git apply patches/performance/0018-avoid-identical-failed-fallback.patch
# Откат того же файла:
git apply --reverse --check patches/performance/0018-avoid-identical-failed-fallback.patch
git apply --reverse patches/performance/0018-avoid-identical-failed-fallback.patch
```

Не накладывать отдельно, если уже выбран combined-файл с 0018. Изменений формата сохранений/частоты AI нет.

## Отдельная серия измерений

Одна операция — **полный caller-запрос NPC**, не один pathfind. Buffer **400 short**, как у NPC.path; false может означать как недостижимость, так и недостаток буфера. На каждой карте заранее выбираются 8 false-returning guard-запросов, 8 успешных и 8 inmate-policy контролей. Если в 128 spatial walkable-target кандидатах не хватает восьми false, недостающие дополняются **явно помеченными blocked-target стресс-контролями**: цель — существующая solid-клетка настоящей карты; геометрия не меняется. В опубликованной серии 42/48 failure-запросов имеют walkable-цель, 6/48 — специально заблокированную (Perks: 1, San Pancho: 5). Это не доказывает частоту такого случая в gameplay. [Разбивка отбора](../../benchmarks/kvm/bottlenecks/fallback/results/fixture-selection.csv), поле blocked_target в query-fixtures.csv. Это специально отобранные workload-ы, **не оценка их частоты в игре**. Исходные координаты: [query-fixtures.csv](../../benchmarks/kvm/bottlenecks/fallback/results/query-fixtures.csv).

`heap-original/heap-once` изолируют только 0018. `core-original/core-once` делают то же после CPU-набора. `heap-original → core-once` — свежая парная суммарная проверка, а не произведение медиан разных запусков.

| Сценарий | База → кандидат | База, мкс | Кандидат, мкс | Медиана пар | Min–max пар |
|---|---|---:|---:|---:|---:|
| irongate:guard-failure | heap-original → heap-once | 58750.000 | 29062.500 | 1.994× | 1.679–2.599 |
| irongate:guard-failure | core-original → core-once | 50687.500 | 23500.000 | 2.152× | 1.740–2.668 |
| irongate:guard-failure | heap-original → core-once | 58750.000 | 23500.000 | 2.434× | 1.889–3.062 |
| irongate:guard-success | heap-original → heap-once | 10187.500 | 10625.000 | 1.001× | 0.829–1.121 |
| irongate:guard-success | core-original → core-once | 9593.750 | 8812.500 | 1.030× | 0.869–1.259 |
| irongate:guard-success | heap-original → core-once | 10187.500 | 8812.500 | 1.195× | 0.987–1.339 |
| irongate:inmate-policy | heap-original → heap-once | 24562.500 | 25250.000 | 0.991× | 0.778–1.278 |
| irongate:inmate-policy | core-original → core-once | 21843.750 | 21656.250 | 1.016× | 0.740–1.284 |
| irongate:inmate-policy | heap-original → core-once | 24562.500 | 21656.250 | 1.156× | 1.000–1.307 |
| jungle:guard-failure | heap-original → heap-once | 46062.500 | 22687.500 | 2.030× | 1.623–2.542 |
| jungle:guard-failure | core-original → core-once | 39562.500 | 19781.250 | 2.016× | 1.570–2.326 |
| jungle:guard-failure | heap-original → core-once | 46062.500 | 19781.250 | 2.356× | 1.886–2.679 |
| jungle:guard-success | heap-original → heap-once | 7312.500 | 8375.000 | 0.998× | 0.782–1.170 |
| jungle:guard-success | core-original → core-once | 7156.250 | 6875.000 | 0.997× | 0.800–1.288 |
| jungle:guard-success | heap-original → core-once | 7312.500 | 6875.000 | 1.199× | 0.935–1.260 |
| jungle:inmate-policy | heap-original → heap-once | 22562.500 | 19937.500 | 1.026× | 0.784–1.301 |
| jungle:inmate-policy | core-original → core-once | 18125.000 | 17312.500 | 1.004× | 0.812–1.301 |
| jungle:inmate-policy | heap-original → core-once | 22562.500 | 17312.500 | 1.209× | 1.042–1.482 |
| perks:guard-failure | heap-original → heap-once | 79500.000 | 40437.500 | 2.022× | 1.604–2.534 |
| perks:guard-failure | core-original → core-once | 66937.500 | 34312.500 | 1.982× | 1.526–2.197 |
| perks:guard-failure | heap-original → core-once | 79500.000 | 34312.500 | 2.379× | 1.948–2.905 |
| perks:guard-success | heap-original → heap-once | 12250.000 | 13468.750 | 1.000× | 0.773–1.005 |
| perks:guard-success | core-original → core-once | 10375.000 | 10375.000 | 0.998× | 0.788–1.218 |
| perks:guard-success | heap-original → core-once | 12250.000 | 10375.000 | 1.178× | 0.924–1.485 |
| perks:inmate-policy | heap-original → heap-once | 38125.000 | 37937.500 | 1.007× | 0.946–1.092 |
| perks:inmate-policy | core-original → core-once | 32687.500 | 31687.500 | 1.020× | 0.939–1.212 |
| perks:inmate-policy | heap-original → core-once | 38125.000 | 31687.500 | 1.189× | 1.122–1.425 |
| sanpancho:guard-failure | heap-original → heap-once | 112375.000 | 55812.500 | 2.021× | 1.556–2.596 |
| sanpancho:guard-failure | core-original → core-once | 86187.500 | 39250.000 | 2.014× | 1.784–2.593 |
| sanpancho:guard-failure | heap-original → core-once | 112375.000 | 39250.000 | 2.862× | 1.992–3.086 |
| sanpancho:guard-success | heap-original → heap-once | 15437.500 | 17937.500 | 0.966× | 0.752–1.076 |
| sanpancho:guard-success | core-original → core-once | 13187.500 | 13125.000 | 1.004× | 0.776–1.236 |
| sanpancho:guard-success | heap-original → core-once | 15437.500 | 13125.000 | 1.182× | 0.931–1.527 |
| sanpancho:inmate-policy | heap-original → heap-once | 40125.000 | 42875.000 | 0.990× | 0.784–1.235 |
| sanpancho:inmate-policy | core-original → core-once | 35687.500 | 36375.000 | 0.976× | 0.801–1.200 |
| sanpancho:inmate-policy | heap-original → core-once | 40125.000 | 36375.000 | 1.157× | 0.933–1.511 |
| shanktonstatepen:guard-failure | heap-original → heap-once | 52812.500 | 22375.000 | 2.013× | 1.849–2.571 |
| shanktonstatepen:guard-failure | core-original → core-once | 40750.000 | 21687.500 | 1.959× | 1.524–2.690 |
| shanktonstatepen:guard-failure | heap-original → core-once | 52812.500 | 21687.500 | 2.336× | 2.211–2.897 |
| shanktonstatepen:guard-success | heap-original → heap-once | 16312.500 | 16406.250 | 0.998× | 0.752–1.294 |
| shanktonstatepen:guard-success | core-original → core-once | 14687.500 | 14593.750 | 1.019× | 0.914–1.251 |
| shanktonstatepen:guard-success | heap-original → core-once | 16312.500 | 14593.750 | 1.170× | 0.893–1.342 |
| shanktonstatepen:inmate-policy | heap-original → heap-once | 30250.000 | 25812.500 | 1.006× | 0.914–1.299 |
| shanktonstatepen:inmate-policy | core-original → core-once | 25500.000 | 23562.500 | 1.017× | 0.806–1.405 |
| shanktonstatepen:inmate-policy | heap-original → core-once | 30250.000 | 23562.500 | 1.172× | 1.009–1.527 |
| stalagflucht:guard-failure | heap-original → heap-once | 86000.000 | 44625.000 | 1.997× | 1.712–2.241 |
| stalagflucht:guard-failure | core-original → core-once | 74500.000 | 37500.000 | 1.991× | 1.594–2.045 |
| stalagflucht:guard-failure | heap-original → core-once | 86000.000 | 37500.000 | 2.298× | 1.914–2.834 |
| stalagflucht:guard-success | heap-original → heap-once | 22687.500 | 23500.000 | 0.962× | 0.789–1.028 |
| stalagflucht:guard-success | core-original → core-once | 19312.500 | 19437.500 | 1.004× | 0.853–1.076 |
| stalagflucht:guard-success | heap-original → core-once | 22687.500 | 19437.500 | 1.186× | 0.956–1.429 |
| stalagflucht:inmate-policy | heap-original → heap-once | 45000.000 | 46562.500 | 0.987× | 0.787–1.164 |
| stalagflucht:inmate-policy | core-original → core-once | 36437.500 | 36750.000 | 1.002× | 0.802–1.250 |
| stalagflucht:inmate-policy | heap-original → core-once | 45000.000 | 36750.000 | 1.177× | 1.051–1.409 |

## Независимые untimed call counts

| Сценарий | Вариант | Запросов | pathfind-вызовов |
|---|---|---:|---:|
| perks:guard-failure | heap-original | 8 | 16 |
| perks:guard-failure | heap-once | 8 | 8 |
| perks:guard-failure | core-original | 8 | 16 |
| perks:guard-failure | core-once | 8 | 8 |
| perks:guard-success | heap-original | 8 | 8 |
| perks:guard-success | heap-once | 8 | 8 |
| perks:guard-success | core-original | 8 | 8 |
| perks:guard-success | core-once | 8 | 8 |
| perks:inmate-policy | heap-original | 8 | 15 |
| perks:inmate-policy | heap-once | 8 | 15 |
| perks:inmate-policy | core-original | 8 | 15 |
| perks:inmate-policy | core-once | 8 | 15 |
| stalagflucht:guard-failure | heap-original | 8 | 16 |
| stalagflucht:guard-failure | heap-once | 8 | 8 |
| stalagflucht:guard-failure | core-original | 8 | 16 |
| stalagflucht:guard-failure | core-once | 8 | 8 |
| stalagflucht:guard-success | heap-original | 8 | 8 |
| stalagflucht:guard-success | heap-once | 8 | 8 |
| stalagflucht:guard-success | core-original | 8 | 8 |
| stalagflucht:guard-success | core-once | 8 | 8 |
| stalagflucht:inmate-policy | heap-original | 8 | 16 |
| stalagflucht:inmate-policy | heap-once | 8 | 16 |
| stalagflucht:inmate-policy | core-original | 8 | 16 |
| stalagflucht:inmate-policy | core-once | 8 | 16 |
| shanktonstatepen:guard-failure | heap-original | 8 | 16 |
| shanktonstatepen:guard-failure | heap-once | 8 | 8 |
| shanktonstatepen:guard-failure | core-original | 8 | 16 |
| shanktonstatepen:guard-failure | core-once | 8 | 8 |
| shanktonstatepen:guard-success | heap-original | 8 | 8 |
| shanktonstatepen:guard-success | heap-once | 8 | 8 |
| shanktonstatepen:guard-success | core-original | 8 | 8 |
| shanktonstatepen:guard-success | core-once | 8 | 8 |
| shanktonstatepen:inmate-policy | heap-original | 8 | 15 |
| shanktonstatepen:inmate-policy | heap-once | 8 | 15 |
| shanktonstatepen:inmate-policy | core-original | 8 | 15 |
| shanktonstatepen:inmate-policy | core-once | 8 | 15 |
| jungle:guard-failure | heap-original | 8 | 16 |
| jungle:guard-failure | heap-once | 8 | 8 |
| jungle:guard-failure | core-original | 8 | 16 |
| jungle:guard-failure | core-once | 8 | 8 |
| jungle:guard-success | heap-original | 8 | 8 |
| jungle:guard-success | heap-once | 8 | 8 |
| jungle:guard-success | core-original | 8 | 8 |
| jungle:guard-success | core-once | 8 | 8 |
| jungle:inmate-policy | heap-original | 8 | 13 |
| jungle:inmate-policy | heap-once | 8 | 13 |
| jungle:inmate-policy | core-original | 8 | 13 |
| jungle:inmate-policy | core-once | 8 | 13 |
| sanpancho:guard-failure | heap-original | 8 | 16 |
| sanpancho:guard-failure | heap-once | 8 | 8 |
| sanpancho:guard-failure | core-original | 8 | 16 |
| sanpancho:guard-failure | core-once | 8 | 8 |
| sanpancho:guard-success | heap-original | 8 | 8 |
| sanpancho:guard-success | heap-once | 8 | 8 |
| sanpancho:guard-success | core-original | 8 | 8 |
| sanpancho:guard-success | core-once | 8 | 8 |
| sanpancho:inmate-policy | heap-original | 8 | 12 |
| sanpancho:inmate-policy | heap-once | 8 | 12 |
| sanpancho:inmate-policy | core-original | 8 | 12 |
| sanpancho:inmate-policy | core-once | 8 | 12 |
| irongate:guard-failure | heap-original | 8 | 16 |
| irongate:guard-failure | heap-once | 8 | 8 |
| irongate:guard-failure | core-original | 8 | 16 |
| irongate:guard-failure | core-once | 8 | 8 |
| irongate:guard-success | heap-original | 8 | 8 |
| irongate:guard-success | heap-once | 8 | 8 |
| irongate:guard-success | core-original | 8 | 8 |
| irongate:guard-success | core-once | 8 | 8 |
| irongate:inmate-policy | heap-original | 8 | 16 |
| irongate:inmate-policy | heap-once | 8 | 16 |
| irongate:inmate-policy | core-original | 8 | 16 |
| irongate:inmate-policy | core-once | 8 | 16 |

Счётчики собраны отдельными wrapper-классами **после** таймингов. 48 selected failure-fixtures дополнительно включены в four-way full-state проверки, помимо прежних 384 buffer/policy случаев. В timed wrappers исходное выражение вызывает map.pathfind напрямую.

[Raw](../../benchmarks/kvm/bottlenecks/fallback/results/raw.csv), [парные формулы](../../benchmarks/kvm/bottlenecks/fallback/results/calculations.md), [окружение/хеши](../../benchmarks/kvm/bottlenecks/fallback/results/environment.json), [полный вывод проверок](../../benchmarks/kvm/bottlenecks/fallback/results/validation.txt). Успешные проверки — ограниченное дифференциальное свидетельство, не полный физический gameplay/PSPKVM тест.
