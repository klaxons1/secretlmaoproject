# 0014 — Row strides и границы карты вне внутреннего tile-loop

Пересечение видимой сетки с границами карты считается заранее, индекс клетки продвигается инкрементом, соседние collision cells берутся как pos-width/pos-1. Для положительного tile ID деление/остаток по 4 заменены сдвигом/маской.

Все графические вызовы, включая полностью клиппированные, остаются в том же порядке и с теми же аргументами. Это повторно проверенный перенос прежнего прототипа на новую серию после master+heap, не изменение частоты render/tick.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0014-tile-row-strides.patch
git apply patches/performance/standalone/0014-tile-row-strides.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Новых массивов нет. KVM измеряет Java-подготовку команд с тестовым sink, не нативные пиксели/MIDP. AWT использован только для отдельной проверки точных ARGB-пикселей. Этот патч вне замеряемого NPC-участка и не должен напрямую уменьшать показатель 917 мс.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:240x320:shadows | 300.781 | 254.395 | 1.187× | 1.042–1.447 |
| jungle:240x320:shadows | 293.945 | 235.352 | 1.234× | 0.964–1.508 |
| perks:240x320:shadows | 207.031 | 163.086 | 1.269× | 1.256–1.345 |
| sanpancho:240x320:shadows | 263.184 | 206.055 | 1.286× | 1.165–1.364 |
| shanktonstatepen:240x320:shadows | 243.164 | 198.242 | 1.218× | 1.061–1.542 |
| stalagflucht:240x320:shadows | 267.578 | 188.965 | 1.261× | 1.248–1.554 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0014-tile-row-strides.patch
git apply --reverse patches/performance/standalone/0014-tile-row-strides.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
