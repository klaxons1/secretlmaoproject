"""Russian notes for the two separately measured post-freeze candidates."""
import csv
import json
from pathlib import Path
import candidates as c

HERE=c.HERE


def read_rows(directory,name='summary.csv'):
    with (directory/name).open() as stream:return list(csv.DictReader(stream))


def table(rows):
    text=['| Сценарий | База → кандидат | База, мкс | Кандидат, мкс | Медиана пар | Min–max пар |','|---|---|---:|---:|---:|---:|']
    for r in rows:
        text.append('| %s | %s → %s | %.3f | %.3f | %.3f× | %.3f–%.3f |'%(r['scenario'],r['reference'],r['candidate'],float(r['reference_us_median']),float(r['candidate_us_median']),float(r['speedup_median']),float(r['speedup_min']),float(r['speedup_max'])))
    return '\n'.join(text)


def render():
    fd=HERE/'fallback/results';pd=HERE/'priority/results';cd=HERE/'conservative-results'
    if not all((p/'environment.json').is_file() for p in (fd,pd,cd)):return False
    fs=read_rows(fd);ps=read_rows(pd);fc=read_rows(fd,'call-counts.csv')
    fe=json.loads((fd/'environment.json').read_text());pe=json.loads((pd/'environment.json').read_text());ce=json.loads((cd/'environment.json').read_text())
    fallback='''# 0018 — Не повторять идентичный неудачный поиск для non-inmate

## Найденный bottleneck

В **двух** caller-местах `NPC.tickAI` (roam и рабочий маршрут) есть:

```java
pathfind(..., inmate, path) || pathfind(..., false, path)
```

Для `inmate=false` первый false вызывает **тот же самый поиск второй раз**: та же цель, старт, направление, collision map, buffer и разрешённые двери. Между операндами игровое состояние не меняется; pathfinder синхронный и очищает scratch state. Второй запуск не может исправить результат первого.

Патч добавляет только условие:

```java
pathfind(..., inmate, path) || (inmate && pathfind(..., false, path))
```

У заключённого первый вызов может запрещать staff doors. Его fallback с разрешёнными staff doors **сохранён**. При успешном первом вызове short-circuit работает как раньше. Уменьшается число полных A* на неудачный non-inmate запрос с двух до одного; алгоритм самого A* не меняется. Новых полей/массивов, кешей или invalidation нет.

Это не доказательство того, что таких запросов много в пользовательском Lights Out → Rollcall. Обычный waypoint-код — другой caller; не объявляю каждый Rollcall-запрос ускоренным вдвое.

## Проверки

На desktop Java и оригинальном KVM каждый: **432** four-way случая (heap/core, старый/новый caller), в том числе **160** non-inmate false и **272** сохранённых контрольных случаев. Сравниваются boolean, весь частично/полностью заполненный result, parent/G/H, visited/nodeDir/nodeX/nodeY и **весь heap scratch** в паре одинаковых ядер. Есть null/пустые/короткие/400/1200-short buffers.

Отдельный синтетический коридор со staff door принудительно требует `true → false`: все четыре варианта успешно находят путь и делают ровно два вызова. Собраны/preverified две полные игры: heap+0018 и all+0018.

## Намеренно изменяемый диагностический вывод

Один лишний `NO PATH` лог исчезает вместе с поиском. Инструментальные call/false/expansion counts также уменьшаются. Это **не побайтно одинаковый debug transcript**. Игровые решения/буферы проверены отдельно; stdout-консоль PSPKVM не замерялась.

## Применение и откат

Нужен master `0716b47205e297375d7a3848d923d5ce916eba6d` + **0003**. Можно после 0004–0016/0017: изменены только две строки в NPC. Основная и standalone-копия здесь одинаковы.

```sh
git apply --check patches/performance/0018-avoid-identical-failed-fallback.patch
git apply patches/performance/0018-avoid-identical-failed-fallback.patch
# Откат того же файла:
git apply --reverse --check patches/performance/0018-avoid-identical-failed-fallback.patch
git apply --reverse patches/performance/0018-avoid-identical-failed-fallback.patch
```

Не накладывать отдельно, если уже выбран combined-файл с 0018. Изменений формата сохранений/частоты AI нет.

## Отдельная серия измерений

Одна операция — **полный caller-запрос NPC**, не один pathfind. Buffer **400 short**, как у NPC.path; false может означать как недостижимость, так и недостаток буфера. На каждой карте заранее выбираются 8 false-returning guard-запросов, 8 успешных и 8 inmate-policy контролей. Если в 128 spatial walkable-target кандидатах не хватает восьми false, недостающие дополняются **явно помеченными blocked-target стресс-контролями**: цель — существующая solid-клетка настоящей карты; геометрия не меняется. В опубликованной серии 42/48 failure-запросов имеют walkable-цель, 6/48 — специально заблокированную (Perks: 1, San Pancho: 5). Это не доказывает частоту такого случая в gameplay. [Разбивка отбора](../../benchmarks/kvm/bottlenecks/fallback/results/fixture-selection.csv), поле blocked_target в query-fixtures.csv. Это специально отобранные workload-ы, **не оценка их частоты в игре**. Исходные координаты: [query-fixtures.csv](../../benchmarks/kvm/bottlenecks/fallback/results/query-fixtures.csv).

`heap-original/heap-once` изолируют только 0018. `core-original/core-once` делают то же после CPU-набора. `heap-original → core-once` — свежая парная суммарная проверка, а не произведение медиан разных запусков.

'''+table(fs)+'''\n
## Независимые untimed call counts

| Сценарий | Вариант | Запросов | pathfind-вызовов |
|---|---|---:|---:|
'''
    for r in fc:
        fallback+='| '+r['scenario']+' | '+r['variant']+' | '+r['requests']+' | '+r['path_calls']+' |\n'
    fallback+='''
Счётчики собраны отдельными wrapper-классами **после** таймингов. 48 selected failure-fixtures дополнительно включены в four-way full-state проверки, помимо прежних 384 buffer/policy случаев. В timed wrappers исходное выражение вызывает map.pathfind напрямую.

[Raw](../../benchmarks/kvm/bottlenecks/fallback/results/raw.csv), [парные формулы](../../benchmarks/kvm/bottlenecks/fallback/results/calculations.md), [окружение/хеши](../../benchmarks/kvm/bottlenecks/fallback/results/environment.json), [полный вывод проверок](../../benchmarks/kvm/bottlenecks/fallback/results/validation.txt). Успешные проверки — ограниченное дифференциальное свидетельство, не полный физический gameplay/PSPKVM тест.
'''
    (c.PATCHES/'0018-avoid-identical-failed-fallback.md').write_text(fallback)
    priority='''# 0019 — Кешировать F-приоритет frontier: CPU в обмен на ещё ≈35 KiB

## Причина и алгоритм

Каждое сравнение heap повторяет `nodeG[id] + nodeH[id]`: две загрузки short-массивов, проверки индексов и сложение. При большом frontier один узел участвует во многих сравнениях. Добавляется **int[] openHeapPriority**; F обновляется на openAdd и openImprove и читается одной загрузкой при сравнении.

Ключ, signed арифметика, FIFO-ticket и порядок обработки не меняются. **Нельзя заменить int на short**: сумма двух signed short может выйти за диапазон short. После уменьшения G кеш обязательно обновляется до sift-up. При произвольном remove обновлённый ключ удаляемого элемента не нужен: ремонтируется перемещённый последний элемент. Неактивные записи могут быть старыми; перед каждым enqueue они перезаписываются, поэтому полного O(mapCells) обнуления после поиска нет.

## Память и ограничения

**Дополнительно 4 × 96 × 93 = 35 712 B payload**, около 34,88 KiB плюс заголовок массива/ссылка, **сверх** памяти уже установленного heap. Вместе это примерно ещё 70 KiB к исходной list-версии, а не «всё ещё 35 KiB». Аллокация одна на карту, не на запрос. Изменений save-формата нет.

Это опциональный memory/CPU trade-off. Проверяйте свободную heap на устройстве и GC в полной игре: стенд исключает setup/GC, не моделирует давление реальных текстур/аудио и не гарантирует выигрыш на phoneME. Для RAM-constrained телефона начинать без 0019.

## Обязательная зависимость

Нужны **0003 и 0007** (либо bundle/core, уже содержащий 0007). Нельзя накладывать на голый heap и потом добавлять старый openImprove: он не обновляет кеш и нарушит invariant. Это исключение из обычного правила standalone/+0003 — standalone-копия 0019 тоже требует 0007. Генератор отказывается работать без hook.

```sh
# При base master + 0003 сначала отдельно 0007:
git apply --check patches/performance/standalone/0007-heap-decrease-key.patch
git apply patches/performance/standalone/0007-heap-decrease-key.patch
# Если 0007 уже есть в выбранном пакете, НЕ применять его второй раз.
git apply --check patches/performance/0019-cache-heap-priorities.patch
git apply patches/performance/0019-cache-heap-priorities.patch
# Откат 0019 до отката его зависимости:
git apply --reverse --check patches/performance/0019-cache-heap-priorities.patch
git apply --reverse patches/performance/0019-cache-heap-priorities.patch
```

Применимость после all+0018 и conservative, а также обе combined-формы проверены по точному совпадению с прототипом. Не накладывать отдельный файл поверх memory-bundle.

## Дифференциальные проверки

На **каждой из двух VM**: **55 380** queue states, включая 30 000 произвольных изменений G/H + drain, равные и signed-overflow значения, decrease-key, удаление произвольного элемента, min/FIFO/membership/position-map и правильность кеша каждого активного узла. **1 232** five-way path cases с полным буфером, partial false, visited/expansion order, parent/G/H и cleanup. Общие 258 864 lookup, 40 000 movement, 5 400 vision/RNG checks также повторены.

Собраны три полных приложения: decrease+cache, core+cache и all+0018+cache. Отдельно полные conservative-memory и conservative-memory+diagnostic. Это не запуск игрового сеанса.

## Отдельный свежий KVM A/B

`heap` — только 0003, `decrease` — 0003+0007, `decrease-key` — предыдущий +0019. **Суффикс key в этом dataset означает priority cache, а не сам decrease-key 0007**. `core/core-key` изолирует кеш после всех CPU-правок. Строка `heap → core-key` измерена напрямую в той же серии, а не вычислена перемножением разных медиан.

Одна операция — полный pathfind с общим checksum-loop, buffer 1200 short, те же npc/spread/local геометрические fixtures, что в основной серии. Setup/GC/инициализация до таймера. 10 повторов = один полный цикл пяти прямых и пяти обратных ротаций, каждый кандидат дважды в каждом слоте.

'''+table(ps)+'''\n
[Raw](../../benchmarks/kvm/bottlenecks/priority/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/priority/results/calculations.md), [окружение/хеши/память](../../benchmarks/kvm/bottlenecks/priority/results/environment.json), [две VM](../../benchmarks/kvm/bottlenecks/priority/results/validation.txt). Физический PSPKVM, native graphics, FPS и полный NPC-pass агент не измерял.
'''
    (c.PATCHES/'0019-cache-heap-priorities.md').write_text(priority)
    bundle='''## Предпочтительный старт: без измеренных moving-регрессий

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

'''
    overview=c.PATCHES/'README.md';text=overview.read_text()
    newrows='| 0018 | Не повторять идентичный неудачный fallback | [описание](0018-avoid-identical-failed-fallback.md), [патч](0018-avoid-identical-failed-fallback.patch) |\n| 0019 | Кеш int-приоритетов heap, ещё ≈35 KiB | [описание](0019-cache-heap-priorities.md), [патч](0019-cache-heap-priorities.patch) |\n'
    text=text.replace('\n\n## Как применять\n','\n'+newrows+'\n'+bundle+'## Как применять\n',1)
    text=text.replace('### Максимальный набор после 0003','### Первоначальный frozen-набор 0004–0016 после 0003')
    text=text.replace('Для базы master + 0003 берите **standalone/**.','Для базы master + 0003 берите **standalone/**; исключение — 0019, ему также нужен 0007.')
    text+='\n## Поздние кандидаты без подмены основной серии\n\n0018 и 0019 обнаружены после фиксации основной серии. Их новые raw/counters/checks хранятся отдельно: [fallback](../../benchmarks/kvm/bottlenecks/fallback/README.md), [priority](../../benchmarks/kvm/bottlenecks/priority/README.md). Старые raw, источники и SHA основной серии не переписывались.\n'
    text+='\n[Отдельные коммиты каждого патча](COMMITS.md).\n\n## Быстрые ссылки на альтернативные conservative-файлы\n\n- После 0003: [conservative](conservative-after-heap.patch) **или** [conservative-memory](conservative-memory-after-heap.patch).\n- С чистого master: [conservative](conservative-from-master.patch) **или** [conservative-memory](conservative-memory-from-master.patch).\n- Как измерять на устройстве и читать 0017: [PROFILE-GUIDE.md](PROFILE-GUIDE.md).\n'
    overview.write_text(text)
    (c.PATCHES/'standalone/README.md').write_text('''# Standalone: сначала прочитать зависимости

- 0004–0016: база master `0716b47` + 0003, без cumulative-копии той же оптимизации.
- 0018: та же база; совместим после основной серии.
- **0019: 0003 + 0007 обязательны**, даже для standalone-файла. Не использовать старый openImprove без обновления priority cache.
- 0017 находится в родительском каталоге: отдельная диагностика с overhead, не часть runtime series.

Здесь не установщик всех файлов по wildcard. Для последовательной серии 0004–0016 брать родительские cumulative-файлы и series.txt; для одного A/B — подходящий standalone. Для рекомендованного opt-in набора без известных moving-регрессий: [общая инструкция](../README.md#предпочтительный-старт-без-измеренных-moving-регрессий).
''')
    for name,number,rows_,meta in (('fallback','0018',fs,fe),('priority','0019',ps,pe)):
        directory=HERE/name;raw=read_rows(directory/'results','raw.csv')
        minimum=min(int(r['elapsed_ms']) for r in raw);maximum=max(int(r['elapsed_ms']) for r in raw)
        script='run_'+name+'.py'
        readme='# '+number+' — отдельная дополнительная серия KVM\n\n'
        readme+='[Подробное описание патча](../../../../patches/performance/'+('0018-avoid-identical-failed-fallback' if name=='fallback' else '0019-cache-heap-priorities')+'.md). Не смешивать с primary-таблицами: это свой fresh paired A/B, та же неизменённая VM.\n\n'
        readme+='%d сценариев × %d вариантов × %d повторов = **%d интервалов**, target %d мс, фактически %d–%d мс.\n\n'%(18,4 if name=='fallback' else 5,meta['samples'],len(raw),meta['target_ms'],minimum,maximum)
        readme+='## Результаты\n\n'+table(rows_)+'\n\n'
        readme+='''## Целостность и воспроизведение

Сначала выполнить основной build/check на непатченом production source. Дополнительный runner проверяет хеши primary inputs/resources/generated Java/CLDC-классов и binary KVM перед копированием библиотеки; общие классы не пересобираются и primary `.work`/raw не меняются. Скомпилированы только новые source-extracted варианты. ProGuard получает non-public library members, без ignorewarnings. В environment.json также сохранены новые generated-source и headless-class hashes.

```sh
'''
        readme+='python3 benchmarks/kvm/bottlenecks/'+name+'/'+script+' --export-only\n'
        readme+='python3 benchmarks/kvm/bottlenecks/'+name+'/'+script+' --samples '+str(meta['samples'])+' --min-ms 150 \\\n  --results benchmarks/kvm/.work/'+name+'/my-run\n'
        readme+='python3 benchmarks/kvm/bottlenecks/'+name+'/'+script+' --analyze \\\n  benchmarks/kvm/bottlenecks/'+name+'/results/raw.csv --samples '+str(meta['samples'])+' \\\n  --results benchmarks/kvm/.work/'+name+'/reanalysis\n```\n\n'
        readme+='[raw.csv](results/raw.csv), [summary.csv](results/summary.csv), [paired.csv](results/paired.csv), [все формулы](results/calculations.md), [проверки обеих VM](results/validation.txt), [команды](results/commands.log), [хеши/ограничения](results/environment.json). Ни физического PSPKVM, ни полного gameplay/frame profile здесь нет.\n'
        (directory/'README.md').write_text(readme)
    main=HERE/'README.md';text=main.read_text()
    total=3204+len(read_rows(fd,'raw.csv'))+len(read_rows(pd,'raw.csv'))
    extra='''
## Поздние дополнительные исследования и исключённые регрессии

Основные **3 204** интервала выше не перезаписывались. После фиксации этой серии найдены и отдельно проверены:

- **0018:** два caller-места повторяют одинаковый failed поиск при inmate=false. Убран только дубликат, настоящий staff-door fallback сохранён; [отдельная серия](fallback/README.md).
- **0019:** повторные две short-загрузки G/H на каждое сравнение heap заменены int priority cache; ещё ≈35 KiB RAM; [отдельная серия](priority/README.md).

Все **44 offline Python-теста** пройдены; [аудит](results/audit.txt) сделал **1 635** проверок хешей, нормализации, классов и пересчётов с build cache.

Всего новые три серии: **%d интервалов** (3204 + %d + %d). Они хранятся раздельно, **не объединены в одну статистическую выборку**. Добавлены 2/3 полные сборки для новых патчей и 4 для conservative с/без diagnostic: вместе с основной серией **41 build/preverification записи**, а не запуск 41 игр на телефоне. [Conservative build evidence](conservative-results/environment.json), [лог](conservative-results/commands.log).

**Conservative** исключает 0011 memo и 0013 facing по реально измеренным регрессиям. Отдельный memo moving имеет медианы 0,829–0,920× (это **+8,7–20,6%% времени**, не «−8–17%%»); facing move 0,920× (примерно **+8,7%% времени**). Отрицательный time-reduction в summary сохранён. Максимальный набор не объявлен автоматически оптимальным.

%s

### Важное о vision fixtures

Геометрия и spawn XY читаются из настоящих ресурсов. Но `WorldData.actors` назначает роли inmate/guard **синтетически по индексу**, а AI_WAYPOINT, health/fighting и прочие поля задаются harness. Это **не точная реконструкция runtime списка NPC/их ролей и не replay save**. Поэтому waypoint/guard tables — сконструированные case studies извлечённого блока, не реальная доля затрат NPC-перехода. Differential checks относятся к перечисленным состояниям; принудительная проверка guard wall discovery остаётся обязательной.

### Дополнительное воспроизведение

```sh
# Все дополнительные offline проверки:
python3 -m unittest discover -s benchmarks/kvm/bottlenecks -p 'test_*.py' -v
# Export/build четырёх conservative конфигураций без переписывания публикации:
python3 benchmarks/kvm/bottlenecks/conservative.py \\
  --results benchmarks/kvm/.work/conservative/my-check
# Аудит сохранённых данных; с флагом также проверить ignored build cache:
python3 benchmarks/kvm/bottlenecks/audit.py --with-build-cache
# Пересоздать описания из сохранённых данных (без тайминга):
python3 benchmarks/kvm/bottlenecks/report.py
```

Как читать профиль устройства: [PROFILE-GUIDE.md](../../../patches/performance/PROFILE-GUIDE.md).

Свежий размер RAM/cache — цена выбранной реализации, не универсальный lower bound. Ни один коэффициент метода не переводится в пользовательские 917 мс без PSPKVM CPU-share и игрового A/B.
'''%(total,len(read_rows(fd,'raw.csv')),len(read_rows(pd,'raw.csv')),bundle)
    main.write_text(text+extra)
    return True
