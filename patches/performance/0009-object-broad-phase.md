# 0009 — Дешёвый broad-phase перед декодированием размеров объекта

getObjectIdxAt раньше загружал sprite и раскодировал width/height у каждого объекта до проверки попадания. Теперь очевидные `x < ox` и `y > oy` отбрасываются раньше. Точное попадание в anchor обрабатывается до проверки размеров, включая нулевые размеры.

Порядок обхода/первое совпадение не меняются. Отрицательные координаты, null-слои, перекрывающиеся и нулевые объекты проверены. Это не spatial cache: перемещение/добавление объектов видно немедленно, invalidation не требуется.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0009-object-broad-phase.patch
git apply patches/performance/standalone/0009-object-broad-phase.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Дополнительной памяти и кеша нет. Сложность остаётся O(objects), сокращается цена непопавших объектов. Время включает общий цикл запросов; это не измерение всей коллизии NPC/дверей.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate | 15.686 | 10.529 | 1.477× | 1.400–1.669 |
| jungle | 7.385 | 4.883 | 1.517× | 1.457–1.786 |
| perks | 13.794 | 9.064 | 1.539× | 1.463–1.884 |
| sanpancho | 8.987 | 6.165 | 1.508× | 1.332–1.676 |
| shanktonstatepen | 22.644 | 14.984 | 1.480× | 1.248–1.793 |
| stalagflucht | 9.109 | 6.226 | 1.502× | 1.279–1.563 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0009-object-broad-phase.patch
git apply --reverse patches/performance/standalone/0009-object-broad-phase.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
