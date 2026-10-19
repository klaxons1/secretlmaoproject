# 0007 — Decrease-key вместо удаления и повторной вставки

При `nodeG[n] > g` ключ действительно строго уменьшается: H не меняется. Старый код сначала ремонтировал heap после удаления, потом ещё раз поднимал заново вставленный узел. Новый openImprove обновляет существующее место и делает один sift-up.

Переоткрытие получает новый FIFO-ticket, как прежняя пара remove/add. Обычный openRemove остаётся универсальным и умеет удалять произвольный узел, в том числе при изменившемся ключе; быстрый метод вызывается только из доказанной ветки улучшения G.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0007-heap-decrease-key.patch
git apply patches/performance/standalone/0007-heap-decrease-key.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Новых массивов нет. Выигрыш зависит от числа релаксаций уже открытых узлов. Протестированы signed-short значения, равные приоритеты, membership, обратная position map и min/FIFO; нельзя использовать openImprove как универсальную замену remove/add при увеличении ключа.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:local | 15.991 | 15.991 | 1.019× | 0.911–1.251 |
| irongate:npc | 2167.969 | 2140.625 | 1.025× | 0.829–1.280 |
| irongate:spread | 11812.500 | 11750.000 | 0.987× | 0.777–1.320 |
| jungle:local | 16.571 | 16.418 | 1.019× | 0.863–1.277 |
| jungle:npc | 1871.094 | 1867.188 | 0.998× | 0.833–1.323 |
| jungle:spread | 12656.250 | 11781.250 | 1.043× | 0.956–1.692 |
| perks:local | 14.679 | 15.717 | 0.971× | 0.714–1.213 |
| perks:npc | 3734.375 | 3554.688 | 1.028× | 0.980–1.248 |
| perks:spread | 17937.500 | 17750.000 | 1.011× | 0.822–1.208 |
| sanpancho:local | 15.076 | 16.724 | 0.977× | 0.782–1.082 |
| sanpancho:npc | 2027.344 | 1964.844 | 1.027× | 0.882–1.209 |
| sanpancho:spread | 22625.000 | 22562.500 | 0.995× | 0.908–1.149 |
| shanktonstatepen:local | 12.329 | 14.587 | 1.004× | 0.706–1.106 |
| shanktonstatepen:npc | 6031.250 | 6187.500 | 1.018× | 0.821–1.211 |
| shanktonstatepen:spread | 14625.000 | 14656.250 | 0.987× | 0.779–1.196 |
| stalagflucht:local | 13.000 | 13.062 | 1.000× | 0.926–1.079 |
| stalagflucht:npc | 2539.062 | 2492.188 | 1.028× | 0.892–1.433 |
| stalagflucht:spread | 21125.000 | 20875.000 | 1.012× | 0.822–1.297 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0007-heap-decrease-key.patch
git apply --reverse patches/performance/standalone/0007-heap-decrease-key.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
