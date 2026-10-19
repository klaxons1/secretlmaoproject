# 0016 — Выключить debug logging в performance/release сборке

В текущем Constants LOGGING=true. Game/NPC могут печатать неудачные поиски и строить debugName/строки. Патч меняет только compile-time константу LOGGING=false: javac убирает соответствующие guarded blocks. Профилировочный HUD отдельного diagnostic-патча от этого не зависит.

Это сознательное изменение диагностического вывода, не алгоритма AI. Если ваш build pipeline уже выключает LOGGING, повторного выигрыша не будет. Нужные отладочные логи исчезнут; для разработки включайте обратно.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0016-release-logging-off.patch
git apply patches/performance/standalone/0016-release-logging-off.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Тайминг ускорения не заявляется: в headless kernels у всех вариантов общий no-op logger, а стоимость консоли PSPKVM агент не измерял. Есть полная сборка/preverification и сравнение размера классов. Обычные негардированные exception stack traces этим флагом не отключаются.

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0016-release-logging-off.patch
git apply --reverse patches/performance/standalone/0016-release-logging-off.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Размер CLDC-preverified классов, без ProGuard optimization/shrinking

- Game.class: 163754 → 163287 байт.
- NPC.class: 65332 → 63905 байт.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
