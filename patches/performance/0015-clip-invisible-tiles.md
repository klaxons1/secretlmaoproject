# 0015 — Не отправлять полностью невидимые tile/background команды

Количество tile-строк/колонок ограничивается фактическим viewport; тот же принцип применяется к 48x48 фону. Caller уже устанавливает clip. Убираются только полностью невидимые вызовы; видимые команды сохраняют порядок, аргументы и графическое состояние.

Для NokiaUI triangle-shadow ветки tile-culling отключён, потому что примитив может выступать за свою клетку. Standalone-вариант применим без row-strides; cumulative — после него. Проверены и отдельный cull, и сочетание с index, включая отрицательные camera offsets и изменённые tiles.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0015-clip-invisible-tiles.patch
git apply patches/performance/standalone/0015-clip-invisible-tiles.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Дополнительной памяти нет. Compile-time-disabled NokiaUI/TiledLayer пути типизированы полной сборкой, но не исполнялись. Нативный PSPKVM/M3G/flush здесь не измерен; более редкие drawRegion не доказывают такой же процент FPS.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:240x320:shadows | 300.781 | 274.414 | 1.109× | 0.954–1.371 |
| jungle:240x320:shadows | 293.945 | 254.883 | 1.135× | 0.896–1.441 |
| perks:240x320:shadows | 207.031 | 181.641 | 1.140× | 1.082–1.227 |
| sanpancho:240x320:shadows | 263.184 | 230.957 | 1.154× | 0.978–1.294 |
| shanktonstatepen:240x320:shadows | 243.164 | 207.031 | 1.169× | 0.891–1.465 |
| stalagflucht:240x320:shadows | 267.578 | 219.238 | 1.124× | 1.049–1.410 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0015-clip-invisible-tiles.patch
git apply --reverse patches/performance/standalone/0015-clip-invisible-tiles.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
