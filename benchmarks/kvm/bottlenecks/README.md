# Проверка bottleneck-оптимизаций после heap

База: master **`0716b47205e297375d7a3848d923d5ce916eba6d` + стабильный FIFO heap 0003**. Исторические серии в соседних каталогах не смешиваются с этой. Исходники Game/NPC/Constants в рабочем дереве не патчились автоматически.

## Результат пользователя, отдельно от наших данных

PSPKVM, phoneME/CLDC HI interpreter, Perks Lights Out → Rollcall: сначала 1390 → 1060 мс **без heap**, затем **917 мс с heap**. Последний шаг −143 мс/−13,49%, 1,156× к 1060. Все три числа сообщил пользователь; одинаковые условия последнего шага предполагаются, нами не воспроизводились.

## Найденные лишние затраты

Это не flame graph целого PSPKVM: ниже подтверждены конкретные повторные операции в исходниках и ускорение извлечённых методов на оригинальном KVM. Главный bottleneck полного устройства нельзя установить по микробенчмарку. Для этого добавлен 0017 с коррелированным breakdown одного NPC-spike.

- H для уже открытых соседей не зависит от нового пути и считалась зря.
- Диагонали/штрафы направления разбирались ветвлениями на каждом ребре.
- При снижении G heap удалял и заново вставлял узел вместо одного decrease-key.
- При attack=false заключённые всё равно делали попарный vision-scan; результат не использовался. У guard canSee имеет side effect, поэтому guard-проход сохранён.
- Зоны перебирались всеми типами, размеры всех объектов декодировались до дешёвого геометрического reject.

## Новая серия

**69 сценариев, 3204 интервалов, 12 повторов, target 150 мс**. Фактические интервалы: 100–415 мс. Не считать calibration target гарантированным минимумом.

Семейства: path (npc/spread/local на шести картах); objects; zones; npc-zones (stationary/moving); seats; vision (waypoint/guard); facing (turn/move/mixed); tiles. Для path 6 вариантов, для большинства helper-методов 3, для tiles 4.

### Поиск: heap → все CPU-патчи core

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:local | 15.991 | 14.526 | 1.130× | 0.963–1.316 |
| irongate:npc | 2167.969 | 1824.219 | 1.177× | 1.094–1.322 |
| irongate:spread | 11812.500 | 10000.000 | 1.164× | 0.940–1.560 |
| jungle:local | 16.571 | 14.832 | 1.099× | 1.044–1.327 |
| jungle:npc | 1871.094 | 1593.750 | 1.190× | 0.961–1.422 |
| jungle:spread | 12656.250 | 10531.250 | 1.209× | 1.127–1.794 |
| perks:local | 14.679 | 14.435 | 1.070× | 0.904–1.154 |
| perks:npc | 3734.375 | 3039.062 | 1.184× | 1.117–1.275 |
| perks:spread | 17937.500 | 15250.000 | 1.185× | 0.911–1.407 |
| sanpancho:local | 15.076 | 14.862 | 1.078× | 0.913–1.191 |
| sanpancho:npc | 2027.344 | 1773.438 | 1.184× | 1.039–1.339 |
| sanpancho:spread | 22625.000 | 19000.000 | 1.185× | 1.037–1.341 |
| shanktonstatepen:local | 12.329 | 12.024 | 1.091× | 0.970–1.187 |
| shanktonstatepen:npc | 6031.250 | 5265.625 | 1.178× | 1.067–1.233 |
| shanktonstatepen:spread | 14625.000 | 12625.000 | 1.154× | 1.042–1.196 |
| stalagflucht:local | 13.000 | 12.238 | 1.086× | 1.030–1.148 |
| stalagflucht:npc | 2539.062 | 2265.625 | 1.199× | 1.057–1.376 |
| stalagflucht:spread | 21125.000 | 18156.250 | 1.184× | 0.952–1.252 |

В path-таблице core реально исполняет 0004–0007; остальные CPU-изменения набора не вызываются этим workload. `npc` — достижимые синтетические пары spawn/waypoint на настоящей collision map, не запись перехода пользователя. `spread` содержит неудачные поиски; `local` — очень короткие запросы. Это три разных распределения, не одно среднее.

### Vision: только candidate-scan, не весь AI

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:guard | 8.447 | 8.350 | 0.986× | 0.874–1.147 |
| irongate:waypoint | 7.194 | 0.484 | 14.817× | 13.647–16.269 |
| jungle:guard | 7.422 | 7.288 | 1.009× | 0.913–1.069 |
| jungle:waypoint | 6.812 | 0.609 | 11.374× | 10.941–12.891 |
| perks:guard | 6.799 | 7.129 | 0.993× | 0.866–1.034 |
| perks:waypoint | 5.579 | 0.473 | 11.742× | 9.542–14.297 |
| sanpancho:guard | 7.983 | 8.154 | 0.997× | 0.768–1.057 |
| sanpancho:waypoint | 8.285 | 0.544 | 15.187× | 13.799–17.195 |
| shanktonstatepen:guard | 9.741 | 9.399 | 1.005× | 0.867–1.237 |
| shanktonstatepen:waypoint | 10.132 | 0.500 | 20.748× | 17.116–22.588 |
| stalagflucht:guard | 4.944 | 5.005 | 0.985× | 0.879–1.154 |
| stalagflucht:waypoint | 6.006 | 0.493 | 11.766× | 10.840–12.645 |

Роли в vision fixtures синтетически назначены по индексу, а не точно восстановлены из runtime NPC constructor/save. Waypoint моделирует пассивных заключённых, guard — сохранённый проход охраны. Большой локальный коэффициент не означает такой же выигрыш tickAI или 917 мс. В блоке heat заменён recorder-методом; сравниваются полные аргументы вызова, количество, состояние, выбор цели, wall-detection и следующий RNG value.

### Объекты и зоны

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate | 15.686 | 10.529 | 1.477× | 1.400–1.669 |
| jungle | 7.385 | 4.883 | 1.517× | 1.457–1.786 |
| perks | 13.794 | 9.064 | 1.539× | 1.463–1.884 |
| sanpancho | 8.987 | 6.165 | 1.508× | 1.332–1.676 |
| shanktonstatepen | 22.644 | 14.984 | 1.480× | 1.248–1.793 |
| stalagflucht | 9.109 | 6.226 | 1.502× | 1.279–1.563 |
| irongate | 1.717 | 0.388 | 4.315× | 3.727–6.135 |
| jungle | 2.182 | 0.475 | 4.652× | 4.154–5.275 |
| perks | 1.621 | 0.400 | 4.269× | 3.312–4.897 |
| sanpancho | 1.671 | 0.416 | 3.979× | 3.712–4.185 |
| shanktonstatepen | 1.938 | 0.460 | 4.078× | 3.962–4.851 |
| stalagflucht | 2.026 | 0.469 | 4.792× | 3.919–5.366 |

### Кеш зон NPC: полезный случай и отрицательный контроль

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:moving | 2.121 | 2.220 | 0.920× | 0.880–1.000 |
| irongate:moving | 2.121 | 0.938 | 2.215× | 2.049–2.509 |
| irongate:stationary | 2.110 | 0.562 | 3.607× | 3.283–4.104 |
| irongate:stationary | 2.110 | 0.573 | 3.583× | 3.303–3.931 |
| jungle:moving | 2.388 | 2.647 | 0.914× | 0.814–1.010 |
| jungle:moving | 2.388 | 0.984 | 2.411× | 2.294–2.907 |
| jungle:stationary | 2.403 | 0.586 | 4.076× | 3.140–4.482 |
| jungle:stationary | 2.403 | 0.595 | 4.010× | 3.375–4.976 |
| perks:moving | 2.232 | 2.548 | 0.877× | 0.844–0.921 |
| perks:moving | 2.232 | 1.026 | 2.170× | 2.042–2.274 |
| perks:stationary | 2.087 | 0.584 | 3.609× | 2.941–4.494 |
| perks:stationary | 2.087 | 0.547 | 3.622× | 3.431–4.806 |
| sanpancho:moving | 1.774 | 2.373 | 0.829× | 0.712–0.890 |
| sanpancho:moving | 1.774 | 0.937 | 1.969× | 1.613–2.409 |
| sanpancho:stationary | 1.862 | 0.563 | 3.345× | 3.128–3.878 |
| sanpancho:stationary | 1.862 | 0.553 | 3.355× | 3.175–3.853 |
| shanktonstatepen:moving | 1.930 | 2.159 | 0.881× | 0.844–0.934 |
| shanktonstatepen:moving | 1.930 | 0.933 | 2.100× | 2.000–2.308 |
| shanktonstatepen:stationary | 1.823 | 0.499 | 3.399× | 3.111–4.214 |
| shanktonstatepen:stationary | 1.823 | 0.513 | 3.480× | 2.800–4.132 |
| stalagflucht:moving | 2.090 | 2.327 | 0.895× | 0.875–0.914 |
| stalagflucht:moving | 2.090 | 0.841 | 2.473× | 2.439–2.500 |
| stalagflucht:stationary | 1.984 | 0.469 | 4.230× | 4.031–4.480 |
| stalagflucht:stationary | 1.984 | 0.467 | 4.236× | 4.062–4.375 |

Memo может проигрывать на смене позиции: это явно опциональный патч. Core одновременно содержит индекс типов, поэтому его moving-результат нельзя приписать самому memo.

### Небольшие изменения: места и facing

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| mixed | 2.392 | 2.472 | 0.937× | 0.795–1.194 |
| move | 2.327 | 2.594 | 0.920× | 0.830–0.970 |
| turn | 2.350 | 2.106 | 1.115× | 1.047–1.415 |
| irongate | 1.991 | 1.972 | 0.996× | 0.949–1.147 |
| jungle | 1.934 | 1.804 | 1.008× | 0.937–1.236 |
| perks | 2.411 | 2.205 | 1.037× | 0.983–1.223 |
| sanpancho | 1.854 | 1.812 | 1.019× | 0.784–1.092 |
| shanktonstatepen | 3.174 | 3.098 | 1.025× | 0.941–1.302 |
| stalagflucht | 1.728 | 1.736 | 0.996× | 0.962–1.016 |

### Tiles: Java-команды, не native MIDP/M3G

| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |
|---|---:|---:|---:|---:|
| irongate:240x320:shadows | 300.781 | 254.395 | 1.187× | 1.042–1.447 |
| irongate:240x320:shadows | 300.781 | 274.414 | 1.109× | 0.954–1.371 |
| irongate:240x320:shadows | 300.781 | 219.727 | 1.377× | 1.227–1.697 |
| jungle:240x320:shadows | 293.945 | 235.352 | 1.234× | 0.964–1.508 |
| jungle:240x320:shadows | 293.945 | 254.883 | 1.135× | 0.896–1.441 |
| jungle:240x320:shadows | 293.945 | 208.496 | 1.395× | 1.174–1.634 |
| perks:240x320:shadows | 207.031 | 163.086 | 1.269× | 1.256–1.345 |
| perks:240x320:shadows | 207.031 | 181.641 | 1.140× | 1.082–1.227 |
| perks:240x320:shadows | 207.031 | 144.043 | 1.437× | 1.137–1.589 |
| sanpancho:240x320:shadows | 263.184 | 206.055 | 1.286× | 1.165–1.364 |
| sanpancho:240x320:shadows | 263.184 | 230.957 | 1.154× | 0.978–1.294 |
| sanpancho:240x320:shadows | 263.184 | 180.176 | 1.422× | 1.275–1.580 |
| shanktonstatepen:240x320:shadows | 243.164 | 198.242 | 1.218× | 1.061–1.542 |
| shanktonstatepen:240x320:shadows | 243.164 | 207.031 | 1.169× | 0.891–1.465 |
| shanktonstatepen:240x320:shadows | 243.164 | 171.875 | 1.423× | 1.105–1.731 |
| stalagflucht:240x320:shadows | 267.578 | 188.965 | 1.261× | 1.248–1.554 |
| stalagflucht:240x320:shadows | 267.578 | 219.238 | 1.124× | 1.049–1.410 |
| stalagflucht:240x320:shadows | 267.578 | 176.270 | 1.405× | 1.322–1.741 |

Все tile-варианты проверены на точный видимый command stream и ARGB в desktop AWT. AWT здесь используется только для корректности, **не для новой серии таймингов**. Compile-disabled NokiaUI/TiledLayer ветки не исполнены; нет измерения native drawRegion/M3G/flush/PSP framebuffer.

## Почему счётчики операций не равны коэффициенту ускорения

Perks:npc, один batch = 16 запросов:

| Вариант | Expansions | H calculations | Adds | Removes | Improves | Peak frontier |
|---|---:|---:|---:|---:|---:|---:|
| heap | 7312 | 24343 | 9843 | 8996 | 0 | 124 |
| heuristic | 7312 | 8159 | 9843 | 8996 | 0 | 124 |
| diagonal | 7312 | 24343 | 9843 | 8996 | 0 | 124 |
| stepcost | 7312 | 24343 | 9843 | 8996 | 0 | 124 |
| decrease | 7312 | 24343 | 8159 | 7312 | 1684 | 124 |
| core | 7312 | 8159 | 8159 | 7312 | 1684 | 124 |

Расширения/пути сохранены. Убирается цена вычислений и обслуживания очереди, а не вся работа A*. Из уменьшения числа H нельзя выводить такое же уменьшение полного tick.

## Корректность и полные сборки

На desktop Java и оригинальном KVM каждый: **25 187** queue states, **1 232** six-way exact paths, **258 864** lookup cases, **40 000** float-movement cases, **5 400** vision/RNG cases. Каждый — также **3 264** tile frames. Desktop AWT: **1 920** кадров, четыре renderer-варианта с точными ARGB. Полный вывод: [validation.txt](results/validation.txt).

Path сравнивается по return, всему result buffer (в том числе частично заполненному при false), visited/expansion order, parent/G/H и cleanup/positions. Null/короткие/полные буферы, start=target, невозможный путь, staff doors, signed-short queue costs и произвольный startDir включены. Физическое расположение элементов в валидном heap не является наблюдаемым результатом.

Float проверяется по integer positions/direction и Float.floatToIntBits (канонический NaN), включая +/-0, subnormal, NaN/Inf. Vision проверяет RNG consumption/выбор цели/heat arguments/guard wall alerts; неизменённая остальная часть tickAI не эмулируется.

Собраны и CLDC-preverified master, heap, каждый standalone-кандидат, каждый cumulative prefix, core/all, diagnostic и all+diagnostic: **32 полных сборок**. Java 1.3, target CLDC 45.3 + StackMap для исполняемых Game/NPC; Constants-интерфейс без методов не требует StackMap. Размеры и SHA-256 каждого класса в [environment.json](results/environment.json).

Патчи применялись/откатывались в изолированных Git indexes; проверены обе combined-формы и diagnostic поверх всей серии. Реальный index и исходники не меняются. [Offline tests](results/offline-tests.txt) и [итоговый аудит](results/audit.txt). Это дифференциальное свидетельство на перечисленных случаях, не гарантия отсутствия любых игровых регрессий.

## Память и холодный запуск

- Уже установленный heap: примерно +35 KiB массивов к master, как описано у 0003.
- Таблица движения: 648 B payload + заголовок/ссылка на весь Game class, не на NPC.
- Индекс зон: 34 + 2*Nzones B payload, два массива/три ссылки.
- Memo зон: около 20 B полей на NPC (32-битные ссылки; alignment VM может отличаться).
- Остальные новые CPU/render-патчи не добавляют рабочих массивов. Диагностика добавляет счётчики/часы.
- Таблица/индекс строятся до steady-state замера. Это не бесплатный cold-start: начальная инициализация/аллокация не измеряется в опубликованном us/op.

## Методика

Неизменённый original KVM 1.1, heap 2 MiB, SHA-256 `917b17f278023670b9a5472d7740d12a5c7b1c6e3718196f828d4bed5de82e66`. Поставленный pinned JDK 8/suite, Linux x86-64 с локальным i386 loader; VM не пересобиралась. Сравниваются source-extracted production bodies в общих headless-классах.

Все варианты прогреваются и калибруются; перед измеряемым интервалом — новый подготовленный state, GC и два warm-up batch, вне таймера. Статические таблицы/индекс прогреты. Внутри таймера только run-loop с одинаковым checksum/общим harness overhead. Нет аллокаций на каждый path query. Инструментированные счётчики собраны отдельным PerfProfile и не участвуют в таймингах.

Ротация — Latin shifts и обратные shifts. За 12 path-повторов каждый из шести вариантов занимает каждый слот дважды. Данные одной пары относятся к одному sample. Медиана пар `ref_us/candidate_us`, не отношение медиан. Диапазоны — наблюдаемые min/max, не confidence intervals. Фоновая нагрузка хоста/шум не исключены.

Источник LOGGING для headless kernels — общий no-op Profiler; стоимость stdout/строк полного NPC не измерена. Поэтому 0016 имеет build/size evidence, **без придуманного timing speedup**.

## Воспроизведение

```sh
# Git/Python, без Java/загрузок, не трогает реальный index/source
python3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --export-only
python3 -m unittest discover -s benchmarks/kvm/bottlenecks -p 'test_*.py' -v

# Полные сборки + проверки Java/KVM/ARGB
python3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --check-only \
  --results benchmarks/kvm/.work/bottlenecks/my-check

# Полный новый замер: отдельный каталог, не переписывать опубликованные данные
python3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --samples 12 --min-ms 150 \
  --results benchmarks/kvm/.work/bottlenecks/my-run

# Полностью offline пересчитать опубликованный raw
python3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --analyze \
  benchmarks/kvm/bottlenecks/results/raw.csv \
  --results benchmarks/kvm/.work/bottlenecks/reanalysis
```

Полный runner ожидает production sources ровно от pinned master: patch-only commits поверх него допустимы. После применения патчей запускать проверку в контрольном checkout с непатченым production source. Генератор берёт master и 0003 по фиксированной базе, а не молча использует изменённый файл пользователя.

## Что отвергнуто как небезопасное «ускорение»

- Пропуск guard vision до canSee: теряет обнаружение проломленных стен.
- Сокращение частоты AI/pathfinding или time-slicing перехода: меняет моменты реакции/маршруты, не эквивалентная оптимизация.
- Кеш collision/connectivity/spatial map без invalidation: двери, разрушения, переносимые объекты делают данные устаревшими. В этой серии такого кеша нет.
- Замена евклидова движения приближённой нормой: меняет траекторию/округление.
- Объявлять локальный vision/tile коэффициент ускорением NPC/FPS или переводить KVM us/op в PSP ms.

## Следующий эксперимент на PSPKVM

Сохранить heap-only 917 как контроль; по очереди добавить независимые standalone-патчи, не менять save/settings, выполнить несколько одинаковых переходов. Для оценки CPU-share отдельно включить 0017, записать обе строки HUD и снять его перед A/B. Использовать максимум в одном 5-секундном окне, а не сравнивать свежий пик с давно накопленным.

Файлы: [каталог патчей и инструкции](../../../patches/performance/README.md), [raw.csv](results/raw.csv), [summary.csv](results/summary.csv), [paired.csv](results/paired.csv), [все формулы](results/calculations.md), [counts](results/operation-counts.csv), [полные команды](results/commands.log), [окружение](results/environment.json).

## Поздние дополнительные исследования и исключённые регрессии

Основные **3 204** интервала выше не перезаписывались. После фиксации этой серии найдены и отдельно проверены:

- **0018:** два caller-места повторяют одинаковый failed поиск при inmate=false. Убран только дубликат, настоящий staff-door fallback сохранён; [отдельная серия](fallback/README.md).
- **0019:** повторные две short-загрузки G/H на каждое сравнение heap заменены int priority cache; ещё ≈35 KiB RAM; [отдельная серия](priority/README.md).

Все **44 offline Python-теста** пройдены; [аудит](results/audit.txt) сделал **1 635** проверок хешей, нормализации, классов и пересчётов с build cache.

Всего новые три серии: **4968 интервалов** (3204 + 864 + 900). Они хранятся раздельно, **не объединены в одну статистическую выборку**. Добавлены 2/3 полные сборки для новых патчей и 4 для conservative с/без diagnostic: вместе с основной серией **41 build/preverification записи**, а не запуск 41 игр на телефоне. [Conservative build evidence](conservative-results/environment.json), [лог](conservative-results/commands.log).

**Conservative** исключает 0011 memo и 0013 facing по реально измеренным регрессиям. Отдельный memo moving имеет медианы 0,829–0,920× (это **+8,7–20,6% времени**, не «−8–17%»); facing move 0,920× (примерно **+8,7% времени**). Отрицательный time-reduction в summary сохранён. Максимальный набор не объявлен автоматически оптимальным.

## Предпочтительный старт: без измеренных moving-регрессий

Все файлы ниже — **альтернативы**, не слои. `*-after-heap` требует только 0003; `*-from-master` уже включает 0003. Не смешивать их и не добавлять поверх них те же отдельные патчи.

| Prefix | Состав после 0003 | Намеренно исключено | Доп. priority RAM |
|---|---|---|---:|
| **conservative** | 0004–0010, 0012, 0014–0016, 0018 | 0011/0013, 0017, 0019 | 0 |
| **conservative-memory** | conservative + 0019 | 0011/0013, 0017 | ≈35 KiB |
| all-plus-fallback | вся 0004–0016 + 0018 | 0017, 0019 | 0 |
| all-memory | вся 0004–0016 + 0018/0019 | 0017 | ≈35 KiB |
| all (первоначальный frozen набор) | только 0004–0016 | 0017/0018/0019 | 0 |

Для твоей heap-сборки разумно начать так:

```sh
git apply --check patches/performance/conservative-after-heap.patch
git apply patches/performance/conservative-after-heap.patch
```

Или выбрать **вместо него** `conservative-memory-after-heap.patch`, если сознательно готов отдать ещё ≈35 KiB. Для чистого pinned master использовать соответствующий `*-from-master.patch`. Пакеты conservative **собраны и preverified с/без 0017**, но их полный игровой runtime не замерялся: набор выбран по компонентным A/B и известным регрессиям, не по придуманному full-game результату.

Почему не просто «всё»: 0011 отдельно замедляет moving-lookup, 0013 замедляет обычное движение. Они остаются подробными opt-in A/B-кандидатами, но **не входят в conservative**. Все пакеты включают 0016 (logging off); если отладочные логи нужны, выбирай отдельные patches без 0016 или подготовь свой набор по генератору. 0018 сам по себе всё равно убирает один дублирующий NO PATH лог.

Откат combined: `git apply --reverse --check <тот-же-combined-файл>` и `git apply --reverse <тот-же-combined-файл>`. Если после него был добавлен 0017/другой патч — сначала снять последний слой. Нельзя откатывать пакет отдельными standalone-файлами с другой базой.

**0019 требует 0007 даже в standalone/**. Это не дополнительный патч к memory-bundle: он там уже есть.



### Важное о vision fixtures

Геометрия и spawn XY читаются из настоящих ресурсов. Но `WorldData.actors` назначает роли inmate/guard **синтетически по индексу**, а AI_WAYPOINT, health/fighting и прочие поля задаются harness. Это **не точная реконструкция runtime списка NPC/их ролей и не replay save**. Поэтому waypoint/guard tables — сконструированные case studies извлечённого блока, не реальная доля затрат NPC-перехода. Differential checks относятся к перечисленным состояниям; принудительная проверка guard wall discovery остаётся обязательной.

### Дополнительное воспроизведение

```sh
# Все дополнительные offline проверки:
python3 -m unittest discover -s benchmarks/kvm/bottlenecks -p 'test_*.py' -v
# Export/build четырёх conservative конфигураций без переписывания публикации:
python3 benchmarks/kvm/bottlenecks/conservative.py \
  --results benchmarks/kvm/.work/conservative/my-check
# Аудит сохранённых данных; с флагом также проверить ignored build cache:
python3 benchmarks/kvm/bottlenecks/audit.py --with-build-cache
# Пересоздать описания из сохранённых данных (без тайминга):
python3 benchmarks/kvm/bottlenecks/report.py
```

Как читать профиль устройства: [PROFILE-GUIDE.md](../../../patches/performance/PROFILE-GUIDE.md).

Свежий размер RAM/cache — цена выбранной реализации, не универсальный lower bound. Ни один коэффициент метода не переводится в пользовательские 917 мс без PSPKVM CPU-share и игрового A/B.
