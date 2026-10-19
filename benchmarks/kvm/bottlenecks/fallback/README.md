# 0018 — отдельная дополнительная серия KVM

[Подробное описание патча](../../../../patches/performance/0018-avoid-identical-failed-fallback.md). Не смешивать с primary-таблицами: это свой fresh paired A/B, та же неизменённая VM.

18 сценариев × 4 вариантов × 12 повторов = **864 интервалов**, target 150 мс, фактически 120–937 мс.

## Результаты

| Сценарий | База → кандидат | База, мкс | Кандидат, мкс | Медиана пар | Min–max пар |
|---|---|---:|---:|---:|---:|
| irongate:guard-failure | heap-original → heap-once | 58750.000 | 29062.500 | 1.994× | 1.679–2.599 |
| irongate:guard-failure | core-original → core-once | 50687.500 | 23500.000 | 2.152× | 1.740–2.668 |
| irongate:guard-failure | heap-original → core-once | 58750.000 | 23500.000 | 2.434× | 1.889–3.062 |
| irongate:guard-success | heap-original → heap-once | 10187.500 | 10625.000 | 1.001× | 0.829–1.121 |
| irongate:guard-success | core-original → core-once | 9593.750 | 8812.500 | 1.030× | 0.869–1.259 |
| irongate:guard-success | heap-original → core-once | 10187.500 | 8812.500 | 1.195× | 0.987–1.339 |
| irongate:inmate-policy | heap-original → heap-once | 24562.500 | 25250.000 | 0.991× | 0.778–1.278 |
| irongate:inmate-policy | core-original → core-once | 21843.750 | 21656.250 | 1.016× | 0.740–1.284 |
| irongate:inmate-policy | heap-original → core-once | 24562.500 | 21656.250 | 1.156× | 1.000–1.307 |
| jungle:guard-failure | heap-original → heap-once | 46062.500 | 22687.500 | 2.030× | 1.623–2.542 |
| jungle:guard-failure | core-original → core-once | 39562.500 | 19781.250 | 2.016× | 1.570–2.326 |
| jungle:guard-failure | heap-original → core-once | 46062.500 | 19781.250 | 2.356× | 1.886–2.679 |
| jungle:guard-success | heap-original → heap-once | 7312.500 | 8375.000 | 0.998× | 0.782–1.170 |
| jungle:guard-success | core-original → core-once | 7156.250 | 6875.000 | 0.997× | 0.800–1.288 |
| jungle:guard-success | heap-original → core-once | 7312.500 | 6875.000 | 1.199× | 0.935–1.260 |
| jungle:inmate-policy | heap-original → heap-once | 22562.500 | 19937.500 | 1.026× | 0.784–1.301 |
| jungle:inmate-policy | core-original → core-once | 18125.000 | 17312.500 | 1.004× | 0.812–1.301 |
| jungle:inmate-policy | heap-original → core-once | 22562.500 | 17312.500 | 1.209× | 1.042–1.482 |
| perks:guard-failure | heap-original → heap-once | 79500.000 | 40437.500 | 2.022× | 1.604–2.534 |
| perks:guard-failure | core-original → core-once | 66937.500 | 34312.500 | 1.982× | 1.526–2.197 |
| perks:guard-failure | heap-original → core-once | 79500.000 | 34312.500 | 2.379× | 1.948–2.905 |
| perks:guard-success | heap-original → heap-once | 12250.000 | 13468.750 | 1.000× | 0.773–1.005 |
| perks:guard-success | core-original → core-once | 10375.000 | 10375.000 | 0.998× | 0.788–1.218 |
| perks:guard-success | heap-original → core-once | 12250.000 | 10375.000 | 1.178× | 0.924–1.485 |
| perks:inmate-policy | heap-original → heap-once | 38125.000 | 37937.500 | 1.007× | 0.946–1.092 |
| perks:inmate-policy | core-original → core-once | 32687.500 | 31687.500 | 1.020× | 0.939–1.212 |
| perks:inmate-policy | heap-original → core-once | 38125.000 | 31687.500 | 1.189× | 1.122–1.425 |
| sanpancho:guard-failure | heap-original → heap-once | 112375.000 | 55812.500 | 2.021× | 1.556–2.596 |
| sanpancho:guard-failure | core-original → core-once | 86187.500 | 39250.000 | 2.014× | 1.784–2.593 |
| sanpancho:guard-failure | heap-original → core-once | 112375.000 | 39250.000 | 2.862× | 1.992–3.086 |
| sanpancho:guard-success | heap-original → heap-once | 15437.500 | 17937.500 | 0.966× | 0.752–1.076 |
| sanpancho:guard-success | core-original → core-once | 13187.500 | 13125.000 | 1.004× | 0.776–1.236 |
| sanpancho:guard-success | heap-original → core-once | 15437.500 | 13125.000 | 1.182× | 0.931–1.527 |
| sanpancho:inmate-policy | heap-original → heap-once | 40125.000 | 42875.000 | 0.990× | 0.784–1.235 |
| sanpancho:inmate-policy | core-original → core-once | 35687.500 | 36375.000 | 0.976× | 0.801–1.200 |
| sanpancho:inmate-policy | heap-original → core-once | 40125.000 | 36375.000 | 1.157× | 0.933–1.511 |
| shanktonstatepen:guard-failure | heap-original → heap-once | 52812.500 | 22375.000 | 2.013× | 1.849–2.571 |
| shanktonstatepen:guard-failure | core-original → core-once | 40750.000 | 21687.500 | 1.959× | 1.524–2.690 |
| shanktonstatepen:guard-failure | heap-original → core-once | 52812.500 | 21687.500 | 2.336× | 2.211–2.897 |
| shanktonstatepen:guard-success | heap-original → heap-once | 16312.500 | 16406.250 | 0.998× | 0.752–1.294 |
| shanktonstatepen:guard-success | core-original → core-once | 14687.500 | 14593.750 | 1.019× | 0.914–1.251 |
| shanktonstatepen:guard-success | heap-original → core-once | 16312.500 | 14593.750 | 1.170× | 0.893–1.342 |
| shanktonstatepen:inmate-policy | heap-original → heap-once | 30250.000 | 25812.500 | 1.006× | 0.914–1.299 |
| shanktonstatepen:inmate-policy | core-original → core-once | 25500.000 | 23562.500 | 1.017× | 0.806–1.405 |
| shanktonstatepen:inmate-policy | heap-original → core-once | 30250.000 | 23562.500 | 1.172× | 1.009–1.527 |
| stalagflucht:guard-failure | heap-original → heap-once | 86000.000 | 44625.000 | 1.997× | 1.712–2.241 |
| stalagflucht:guard-failure | core-original → core-once | 74500.000 | 37500.000 | 1.991× | 1.594–2.045 |
| stalagflucht:guard-failure | heap-original → core-once | 86000.000 | 37500.000 | 2.298× | 1.914–2.834 |
| stalagflucht:guard-success | heap-original → heap-once | 22687.500 | 23500.000 | 0.962× | 0.789–1.028 |
| stalagflucht:guard-success | core-original → core-once | 19312.500 | 19437.500 | 1.004× | 0.853–1.076 |
| stalagflucht:guard-success | heap-original → core-once | 22687.500 | 19437.500 | 1.186× | 0.956–1.429 |
| stalagflucht:inmate-policy | heap-original → heap-once | 45000.000 | 46562.500 | 0.987× | 0.787–1.164 |
| stalagflucht:inmate-policy | core-original → core-once | 36437.500 | 36750.000 | 1.002× | 0.802–1.250 |
| stalagflucht:inmate-policy | heap-original → core-once | 45000.000 | 36750.000 | 1.177× | 1.051–1.409 |

## Целостность и воспроизведение

Сначала выполнить основной build/check на непатченом production source. Дополнительный runner проверяет хеши primary inputs/resources/generated Java/CLDC-классов и binary KVM перед копированием библиотеки; общие классы не пересобираются и primary `.work`/raw не меняются. Скомпилированы только новые source-extracted варианты. ProGuard получает non-public library members, без ignorewarnings. В environment.json также сохранены новые generated-source и headless-class hashes.

```sh
python3 benchmarks/kvm/bottlenecks/fallback/run_fallback.py --export-only
python3 benchmarks/kvm/bottlenecks/fallback/run_fallback.py --samples 12 --min-ms 150 \
  --results benchmarks/kvm/.work/fallback/my-run
python3 benchmarks/kvm/bottlenecks/fallback/run_fallback.py --analyze \
  benchmarks/kvm/bottlenecks/fallback/results/raw.csv --samples 12 \
  --results benchmarks/kvm/.work/fallback/reanalysis
```

[raw.csv](results/raw.csv), [summary.csv](results/summary.csv), [paired.csv](results/paired.csv), [все формулы](results/calculations.md), [проверки обеих VM](results/validation.txt), [команды](results/commands.log), [хеши/ограничения](results/environment.json). Ни физического PSPKVM, ни полного gameplay/frame profile здесь нет.
