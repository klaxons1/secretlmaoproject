# 0012 — Один packed-key для поиска места

getSeatIndex сравнивает `(pos & 0xFFFF)` с заранее упакованным `x | (y << 8)`, вместо извлечения двух координат каждой записи. Координаты вне 0..255 сразу дают -1, как прежние сравнения с unsigned byte. Чтение positions[0] сохранено до раннего выхода.

Count, шаг по парам coordinate/occupant, порядок дубликатов и возвращаемый индекс не меняются. В тайминге используются таблицы из chair/training anchor реальных ресурсов; это не запись фактической занятости мест из игрового save.

## Применение отдельно для A/B

База — master `0716b47205e297375d7a3848d923d5ce916eba6d` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.

```sh
git apply --check patches/performance/standalone/0012-packed-seat-lookup.patch
git apply patches/performance/standalone/0012-packed-seat-lookup.patch
```

Для общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.

## Память, ограничения и регрессии

Новых полей/аллокаций нет. На коротких таблицах выигрыш мал и может теряться в разбросе. Это небольшой локальный вариант, не заявка на решение NPC-spike.

## Свежие замеры оригинального KVM 1.1

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate | 1.991 | 1.972 | 0.996× | 0.949–1.147 |
| jungle | 1.934 | 1.804 | 1.008× | 0.937–1.236 |
| perks | 2.411 | 2.205 | 1.037× | 0.983–1.223 |
| sanpancho | 1.854 | 1.812 | 1.019× | 0.784–1.092 |
| shanktonstatepen | 3.174 | 3.098 | 1.025× | 0.941–1.302 |
| stalagflucht | 1.728 | 1.736 | 0.996× | 0.962–1.016 |

## Откат того же standalone/diagnostic файла

```sh
git apply --reverse --check patches/performance/standalone/0012-packed-seat-lookup.patch
git apply --reverse patches/performance/standalone/0012-packed-seat-lookup.patch
```

Для cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.

## Доказательства и границы

[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).

Агент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.
