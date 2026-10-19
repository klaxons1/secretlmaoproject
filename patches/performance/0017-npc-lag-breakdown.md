# 0017 — Диагностика: из чего состоит именно пик NPC-pass

Отдельный патч, НЕ часть series.txt и НЕ оптимизация. Для одного и того же максимального NPC-pass сохраняются AI ms, суммарный pathfind ms, NPC.tick ms, число поисков/возвратов false и расширений A*. Это не независимые максимумы разных кадров.

HUD строка y=71: AI / pathfind / NPC.tick. Строка y=79: calls / false returns / expansions. Числа в колонках x=0/40/80. Сброс вместе с lag раз в пять секунд. pathfind-время вложено в AI: их нельзя складывать. False включает также недостаточный result buffer, а не только недостижимую цель.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/0017-npc-lag-breakdown.patch
git apply patches/performance/0017-npc-lag-breakdown.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Патч вызывает дополнительные currentTimeMillis для NPC и считает расширения; вносит заметную погрешность и не годится для честного A/B с обычной сборкой! Нужен, чтобы узнать долю поиска на PSPKVM. Применяется к heap или после всей серии; для измерения ускорения сначала откатить/пересобрать без него.

Пошаговая проверка на устройстве и чтение HUD: [PROFILE-GUIDE.md](PROFILE-GUIDE.md).

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/0017-npc-lag-breakdown.patch
git apply --reverse patches/performance/0017-npc-lag-breakdown.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
