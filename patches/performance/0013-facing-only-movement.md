# 0013 — Поворот с нулевой скоростью без sqrt и нормализации

moveTowards вызывается со speed=0, когда нужно только повернуться к противнику. При положительном конечном distanceSquared нормализованный вектор, умноженный на ноль, даёт только signed zero: sqrt и два деления не нужны. Обновление позиции сохраняет знак нуля.

Ненулевая скорость использует прежнюю математику. Нулевой/underflow distanceSquared, NaN и infinity уходят в старую ветку. Проверены 40 000 состояний, включая обычные координаты, -1 sentinel, +/-0, subnormal, infinity, NaN и отрицательную/ненулевую скорость. NaN сравнивается через канонизирующий Float.floatToIntBits.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0013-facing-only-movement.patch
git apply patches/performance/standalone/0013-facing-only-movement.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

**Не включён в conservative по измеренной регрессии обычного движения.** Дополнительной памяти нет. Обычное движение получает дополнительную проверку: move/mixed — обязательные отрицательные контроли. Не заменяется sqrt приблизительным L1-расстоянием и не меняется скорость/траектория AI.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| mixed | 2.392 | 2.472 | 0.937× | 0.795–1.194 |
| move | 2.327 | 2.594 | 0.920× | 0.830–0.970 |
| turn | 2.350 | 2.106 | 1.115× | 1.047–1.415 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0013-facing-only-movement.patch
git apply --reverse patches/performance/standalone/0013-facing-only-movement.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
