# 0019 — Кешировать F-приоритет frontier: CPU в обмен на ещё ≈35 KiB

## Причина и алгоритм

Каждое сравнение heap повторяет `nodeG[id] + nodeH[id]`: две загрузки short-массивов, проверки индексов и сложение. При большом frontier один узел участвует во многих сравнениях. Добавляется **int[] openHeapPriority**; F обновляется на openAdd и openImprove и читается одной загрузкой при сравнении.

Ключ, signed арифметика, FIFO-ticket и порядок обработки не меняются. **Нельзя заменить int на short**: сумма двух signed short может выйти за диапазон short. После уменьшения G кеш обязательно обновляется до sift-up. При произвольном remove обновлённый ключ удаляемого элемента не нужен: ремонтируется перемещённый последний элемент. Неактивные записи могут быть старыми; перед каждым enqueue они перезаписываются, поэтому полного O(mapCells) обнуления после поиска нет.

## Память и ограничения

**Дополнительно 4 × 96 × 93 = 35 712 B payload**, около 34,88 KiB плюс заголовок массива/ссылка, **сверх** памяти уже установленного heap. Вместе это примерно ещё 70 KiB к исходной list-версии, а не «всё ещё 35 KiB». Аллокация одна на карту, не на запрос. Изменений save-формата нет.

Это опциональный memory/CPU trade-off. Проверяйте свободную heap на устройстве и GC в полной игре: стенд исключает setup/GC, не моделирует давление реальных текстур/аудио и не гарантирует выигрыш на phoneME. Для RAM-constrained телефона начинать без 0019.

## Обязательная зависимость

Нужны **0003 и 0007** (либо bundle/core, уже содержащий 0007). Нельзя накладывать на голый heap и потом добавлять старый openImprove: он не обновляет кеш и нарушит invariant. Это исключение из обычного правила standalone/+0003 — standalone-копия 0019 тоже требует 0007. Генератор отказывается работать без hook.

```sh
# При base master + 0003 сначала отдельно 0007:
git apply --check patches/performance/standalone/0007-heap-decrease-key.patch
git apply patches/performance/standalone/0007-heap-decrease-key.patch
# Если 0007 уже есть в выбранном пакете, НЕ применять его второй раз.
git apply --check patches/performance/0019-cache-heap-priorities.patch
git apply patches/performance/0019-cache-heap-priorities.patch
# Откат 0019 до отката его зависимости:
git apply --reverse --check patches/performance/0019-cache-heap-priorities.patch
git apply --reverse patches/performance/0019-cache-heap-priorities.patch
```

Применимость после all+0018 и conservative, а также обе combined-формы проверены по точному совпадению с прототипом. Не накладывать отдельный файл поверх memory-bundle.

## Дифференциальные проверки

На **каждой из двух VM**: **55 380** queue states, включая 30 000 произвольных изменений G/H + drain, равные и signed-overflow значения, decrease-key, удаление произвольного элемента, min/FIFO/membership/position-map и правильность кеша каждого активного узла. **1 232** five-way path cases с полным буфером, partial false, visited/expansion order, parent/G/H и cleanup. Общие 258 864 lookup, 40 000 movement, 5 400 vision/RNG checks также повторены.

Собраны три полных приложения: decrease+cache, core+cache и all+0018+cache. Отдельно полные conservative-memory и conservative-memory+diagnostic. Это не запуск игрового сеанса.

## Отдельный свежий KVM A/B

`heap` — только 0003, `decrease` — 0003+0007, `decrease-key` — предыдущий +0019. **Суффикс key в этом dataset означает priority cache, а не сам decrease-key 0007**. `core/core-key` изолирует кеш после всех CPU-правок. Строка `heap → core-key` измерена напрямую в той же серии, а не вычислена перемножением разных медиан.

Одна операция — полный pathfind с общим checksum-loop, buffer 1200 short, те же npc/spread/local геометрические fixtures, что в основной серии. Setup/GC/инициализация до таймера. 10 повторов = один полный цикл пяти прямых и пяти обратных ротаций, каждый кандидат дважды в каждом слоте.

| Сценарий | База → кандидат | База, мкс | Кандидат, мкс | Медиана пар | Min–max пар |
|---|---|---:|---:|---:|---:|
| irongate:local | decrease → decrease-key | 12.390 | 12.207 | 1.015× | 0.990–1.020 |
| irongate:local | core → core-key | 11.353 | 11.292 | 1.005× | 0.986–1.076 |
| irongate:local | heap → core-key | 12.390 | 11.292 | 1.097× | 1.091–1.324 |
| irongate:npc | decrease → decrease-key | 1742.188 | 1652.344 | 1.034× | 0.958–1.138 |
| irongate:npc | core → core-key | 1609.375 | 1453.125 | 1.024× | 0.947–1.243 |
| irongate:npc | heap → core-key | 1855.469 | 1453.125 | 1.211× | 1.030–1.399 |
| irongate:spread | decrease → decrease-key | 10687.500 | 9468.750 | 1.042× | 0.977–1.246 |
| irongate:spread | core → core-key | 9187.500 | 8187.500 | 1.031× | 0.992–1.269 |
| irongate:spread | heap → core-key | 10875.000 | 8187.500 | 1.232× | 1.205–1.471 |
| jungle:local | decrease → decrease-key | 16.235 | 15.594 | 1.025× | 1.004–1.092 |
| jungle:local | core → core-key | 14.465 | 14.496 | 1.004× | 0.951–1.205 |
| jungle:local | heap → core-key | 15.869 | 14.496 | 1.098× | 1.062–1.328 |
| jungle:npc | decrease → decrease-key | 2136.719 | 2097.656 | 1.023× | 0.996–1.296 |
| jungle:npc | core → core-key | 1859.375 | 1796.875 | 1.044× | 0.996–1.118 |
| jungle:npc | heap → core-key | 2175.781 | 1796.875 | 1.227× | 1.164–1.270 |
| jungle:spread | decrease → decrease-key | 14437.500 | 14156.250 | 1.036× | 0.767–1.069 |
| jungle:spread | core → core-key | 11500.000 | 11718.750 | 1.034× | 0.827–1.150 |
| jungle:spread | heap → core-key | 14343.750 | 11718.750 | 1.220× | 1.096–1.479 |
| perks:local | decrease → decrease-key | 14.404 | 14.008 | 1.023× | 0.995–1.091 |
| perks:local | core → core-key | 12.054 | 11.780 | 1.016× | 1.004–1.086 |
| perks:local | heap → core-key | 16.052 | 11.780 | 1.093× | 1.071–1.448 |
| perks:npc | decrease → decrease-key | 3687.500 | 3515.625 | 1.039× | 0.799–1.293 |
| perks:npc | core → core-key | 3164.062 | 3046.875 | 1.038× | 0.837–1.177 |
| perks:npc | heap → core-key | 3718.750 | 3046.875 | 1.213× | 1.127–1.330 |
| perks:spread | decrease → decrease-key | 21875.000 | 21375.000 | 1.041× | 0.767–1.348 |
| perks:spread | core → core-key | 16125.000 | 16750.000 | 1.050× | 0.791–1.115 |
| perks:spread | heap → core-key | 19812.500 | 16750.000 | 1.225× | 0.933–1.513 |
| sanpancho:local | decrease → decrease-key | 16.541 | 15.656 | 1.015× | 0.877–1.288 |
| sanpancho:local | core → core-key | 15.472 | 14.343 | 1.010× | 0.977–1.261 |
| sanpancho:local | heap → core-key | 15.045 | 14.343 | 1.088× | 0.922–1.281 |
| sanpancho:npc | decrease → decrease-key | 2074.219 | 1878.906 | 1.031× | 0.849–1.300 |
| sanpancho:npc | core → core-key | 1488.281 | 1406.250 | 1.025× | 0.905–1.068 |
| sanpancho:npc | heap → core-key | 1953.125 | 1406.250 | 1.220× | 1.199–1.573 |
| sanpancho:spread | decrease → decrease-key | 21531.250 | 20812.500 | 1.021× | 0.817–1.243 |
| sanpancho:spread | core → core-key | 18031.250 | 17656.250 | 1.012× | 0.852–1.256 |
| sanpancho:spread | heap → core-key | 21187.500 | 17656.250 | 1.219× | 0.973–1.547 |
| shanktonstatepen:local | decrease → decrease-key | 13.794 | 11.932 | 1.027× | 0.996–1.204 |
| shanktonstatepen:local | core → core-key | 11.597 | 12.695 | 0.985× | 0.896–1.037 |
| shanktonstatepen:local | heap → core-key | 14.465 | 12.695 | 1.113× | 1.054–1.328 |
| shanktonstatepen:npc | decrease → decrease-key | 6171.875 | 5718.750 | 1.055× | 0.843–1.362 |
| shanktonstatepen:npc | core → core-key | 5343.750 | 4609.375 | 1.029× | 0.944–1.199 |
| shanktonstatepen:npc | heap → core-key | 6468.750 | 4609.375 | 1.268× | 1.140–1.667 |
| shanktonstatepen:spread | decrease → decrease-key | 13968.750 | 13187.500 | 1.020× | 0.779–1.149 |
| shanktonstatepen:spread | core → core-key | 11625.000 | 11250.000 | 1.028× | 1.005–1.266 |
| shanktonstatepen:spread | heap → core-key | 13718.750 | 11250.000 | 1.209× | 1.009–1.279 |
| stalagflucht:local | decrease → decrease-key | 13.092 | 12.939 | 1.019× | 0.981–1.089 |
| stalagflucht:local | core → core-key | 13.153 | 13.367 | 1.005× | 0.785–1.207 |
| stalagflucht:local | heap → core-key | 13.306 | 13.367 | 1.077× | 0.902–1.105 |
| stalagflucht:npc | decrease → decrease-key | 3031.250 | 2789.062 | 1.038× | 1.000–1.307 |
| stalagflucht:npc | core → core-key | 2429.688 | 2531.250 | 1.008× | 0.821–1.085 |
| stalagflucht:npc | heap → core-key | 3125.000 | 2531.250 | 1.234× | 1.165–1.527 |
| stalagflucht:spread | decrease → decrease-key | 21031.250 | 21187.500 | 1.021× | 0.777–1.258 |
| stalagflucht:spread | core → core-key | 18218.750 | 17906.250 | 1.023× | 0.776–1.180 |
| stalagflucht:spread | heap → core-key | 21218.750 | 17906.250 | 1.195× | 0.984–1.265 |

[Raw](../../benchmarks/kvm/bottlenecks/priority/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/priority/results/calculations.md), [окружение/хеши/память](../../benchmarks/kvm/bottlenecks/priority/results/environment.json), [две VM](../../benchmarks/kvm/bottlenecks/priority/results/validation.txt). Физический PSPKVM, native graphics, FPS и полный NPC-pass агент не измерял.
