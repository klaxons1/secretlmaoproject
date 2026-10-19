# 0011 — Кеш повторных проверок зон конкретного NPC — опционально

NPC.isInZone хранит checked/found bitset для точных `(x+7,y+7)` и ссылки на текущий массив zones. Повторная проверка уже известного типа возвращается без обхода карты. При любом изменении позиции или замене массива карты маски сбрасываются. Неизвестные типы идут по прежнему пути.

Сохранения не меняются: кеш производный, не сериализуется. Полезен для стоящего персонажа/повторных вопросов охранников о том же игроке. В отличие от индекса типов это не бесплатное улучшение для любого движения.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0011-npc-zone-memo.patch
git apply patches/performance/standalone/0011-npc-zone-memo.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

**Не включён в conservative по измеренной moving-регрессии.** Около 20 байт полей на NPC при 32-битных ссылках, с оговоркой о VM alignment. В moving-контроле отдельный memo может замедляться: почти нет попаданий, а проверка тегов стоит времени. Обязательно сравнить этот патч отдельно и после zone-index; максимальный bundle — не универсально лучший набор.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:moving | 2.121 | 2.220 | 0.920× | 0.880–1.000 |
| irongate:stationary | 2.110 | 0.562 | 3.607× | 3.283–4.104 |
| jungle:moving | 2.388 | 2.647 | 0.914× | 0.814–1.010 |
| jungle:stationary | 2.403 | 0.586 | 4.076× | 3.140–4.482 |
| perks:moving | 2.232 | 2.548 | 0.877× | 0.844–0.921 |
| perks:stationary | 2.087 | 0.584 | 3.609× | 2.941–4.494 |
| sanpancho:moving | 1.774 | 2.373 | 0.829× | 0.712–0.890 |
| sanpancho:stationary | 1.862 | 0.563 | 3.345× | 3.128–3.878 |
| shanktonstatepen:moving | 1.930 | 2.159 | 0.881× | 0.844–0.934 |
| shanktonstatepen:stationary | 1.823 | 0.499 | 3.399× | 3.111–4.214 |
| stalagflucht:moving | 2.090 | 2.327 | 0.895× | 0.875–0.914 |
| stalagflucht:stationary | 1.984 | 0.469 | 4.230× | 4.031–4.480 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0011-npc-zone-memo.patch
git apply --reverse patches/performance/standalone/0011-npc-zone-memo.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
