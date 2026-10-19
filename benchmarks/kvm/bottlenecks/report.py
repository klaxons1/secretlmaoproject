#!/usr/bin/env python3
"""Render Russian patch notes from the separately retained raw-data analysis."""
import csv
import json
from pathlib import Path
import candidates as c

HERE=c.HERE
RESULTS=HERE/'results'

NOTES={
'heuristic':('path','Эвристика только при первом открытии узла',
'''Раньше octile H вычислялась для каждого допустимого ребра, даже когда сосед уже в frontier и кандидат не улучшает путь. Но H зависит только от координат соседа и цели, не от родителя или G. Расчёт перенесён внутрь ветки первого открытия. При улучшении G прежняя H сохраняется.

Стоимость подготовки H меняется с числа рассмотренных рёбер на число впервые открытых узлов. Это не сокращает число расширений A*: результат, родители, FIFO и порядок visited остаются прежними.''',
'Ноль новых массивов/полей. На коротком поиске работы мало, поэтому выигрыш может исчезнуть в общей цене вызова. Точное время следует брать из таблицы, а не приравнивать процент убранных вычислений H к ускорению всего поиска.'),
'diagonal':('path','Одна проверка геометрии диагонали вместо четырёх веток',
'''Вместо отдельных right-up/right-down/left-up/left-down блоков используются две соседние ортогональные клетки: `(nx, y)` и `(x, ny)`. Их COLL_BIT_SOLID_AI объединяется OR. Проверка выхода новых x/y за карту по-прежнему выполняется раньше обращений к массиву.

Правило обхода staff doors не меняется: для боковых клеток, как и раньше, проверяется именно solid-bit, а не полный запрет дверей. Стоимости диагоналей остаются прежними.''',
'Дополнительной памяти нет. OR читает обе клетки даже тогда, когда первая уже блокирует движение; это обмен short-circuit на меньшее число ветвлений. На плотных препятствиях отдельный вариант не обязан быть быстрее.'),
'stepcost':('path','Таблица штрафов за направление движения',
'''Сумма `10 + diagonal*4 + turn*4 + notStartFacing*2` одна и та же для ограниченного набора комбинаций. Вместо трёх условных веток на каждое ребро читается заранее подготовленный byte. Отдельный штраф +15 за COLL_BIT_AVOID_AI по-прежнему добавляется из текущей collision map.

Таблица содержит девятое состояние направления «другое»: оно сохраняет старую семантику отрицательных и произвольных startDir, а не вводит неверное ограничение только на 0..3. Приведение G к signed short и все сравнения сохранены.''',
'648 байт payload одной статической таблицы плюс заголовок/ссылка. Единовременное построение при загрузке класса не входит в таймер поиска. Это дополнительный вариант для A/B, не обещание одинакового выигрыша на любой VM.'),
'decrease':('path','Decrease-key вместо удаления и повторной вставки',
'''При `nodeG[n] > g` ключ действительно строго уменьшается: H не меняется. Старый код сначала ремонтировал heap после удаления, потом ещё раз поднимал заново вставленный узел. Новый openImprove обновляет существующее место и делает один sift-up.

Переоткрытие получает новый FIFO-ticket, как прежняя пара remove/add. Обычный openRemove остаётся универсальным и умеет удалять произвольный узел, в том числе при изменившемся ключе; быстрый метод вызывается только из доказанной ветки улучшения G.''',
'Новых массивов нет. Выигрыш зависит от числа релаксаций уже открытых узлов. Протестированы signed-short значения, равные приоритеты, membership, обратная position map и min/FIFO; нельзя использовать openImprove как универсальную замену remove/add при увеличении ключа.'),
'vision':('vision','Не сканировать других NPC для пассивного заключённого',
'''В npcVision вычисление `attack` и все предыдущие проверки игрока сохранены. Перебор остальных персонажей теперь выполняется только при `guard || attack`. У заключённого с attack=false результат found нигде не используется, а его canSee не имеет side effects. На AI_WAYPOINT/AI_SLEEP эта лишняя работа раньше выполнялась регулярно.

Охранники продолжают сканировать даже без драки: canSee обнаруживает COLL_DIGGED_WALL и выставляет причину solitary. Нельзя просто перенести фильтр other.fighting перед canSee. Также не меняется порядок RNG-вызовов до цикла и при выборе противника.''',
'Память не увеличивается. Таблица измеряет только извлечённый candidate-scan блок, не полный tickAI/NPC-цикл! Сценарий guard — отрицательный контроль, а большой коэффициент waypoint нельзя переносить на весь кадр или на пользовательские 917 мс.'),
'objects':('objects','Дешёвый broad-phase перед декодированием размеров объекта',
'''getObjectIdxAt раньше загружал sprite и раскодировал width/height у каждого объекта до проверки попадания. Теперь очевидные `x < ox` и `y > oy` отбрасываются раньше. Точное попадание в anchor обрабатывается до проверки размеров, включая нулевые размеры.

Порядок обхода/первое совпадение не меняются. Отрицательные координаты, null-слои, перекрывающиеся и нулевые объекты проверены. Это не spatial cache: перемещение/добавление объектов видно немедленно, invalidation не требуется.''',
'Дополнительной памяти и кеша нет. Сложность остаётся O(objects), сокращается цена непопавших объектов. Время включает общий цикл запросов; это не измерение всей коллизии NPC/дверей.'),
'zones':('zones','Индекс зон по типу вместо полного сканирования',
'''isInZone больше не перебирает зоны всех типов ради одного типа: short[] heads и short[] next образуют цепочки только соответствующих записей. findZone сразу возвращает первую запись. Индекс строится в обратном порядке, поэтому порядок дубликатов/первое совпадение совпадают с оригиналом.

Известные типы 0..ZONE_SAFE идут через индекс; неизвестные/отрицательные типы сохраняют старый scan. Координаты прямоугольников остаются включительными с обеих сторон. Первое построение ленивое, при замене zones на новую карту индекс перестраивается.''',
'Payload: 34 + 2*Nzones байт, плюс два заголовка массивов и ссылки. Контракт текущего кода: зоны неизменны после загрузки; grep всех записей в zones подтвердил запись только при загрузке. Если будущий редактор начнёт менять zones на месте, понадобится явная invalidation. Холодная аллокация не входит в steady-state тайминг.'),
'memo':('npc-zones','Кеш повторных проверок зон конкретного NPC — опционально',
'''NPC.isInZone хранит checked/found bitset для точных `(x+7,y+7)` и ссылки на текущий массив zones. Повторная проверка уже известного типа возвращается без обхода карты. При любом изменении позиции или замене массива карты маски сбрасываются. Неизвестные типы идут по прежнему пути.

Сохранения не меняются: кеш производный, не сериализуется. Полезен для стоящего персонажа/повторных вопросов охранников о том же игроке. В отличие от индекса типов это не бесплатное улучшение для любого движения.''',
'**Не включён в conservative по измеренной moving-регрессии.** Около 20 байт полей на NPC при 32-битных ссылках, с оговоркой о VM alignment. В moving-контроле отдельный memo может замедляться: почти нет попаданий, а проверка тегов стоит времени. Обязательно сравнить этот патч отдельно и после zone-index; максимальный bundle — не универсально лучший набор.'),
'seats':('seats','Один packed-key для поиска места',
'''getSeatIndex сравнивает `(pos & 0xFFFF)` с заранее упакованным `x | (y << 8)`, вместо извлечения двух координат каждой записи. Координаты вне 0..255 сразу дают -1, как прежние сравнения с unsigned byte. Чтение positions[0] сохранено до раннего выхода.

Count, шаг по парам coordinate/occupant, порядок дубликатов и возвращаемый индекс не меняются. В тайминге используются таблицы из chair/training anchor реальных ресурсов; это не запись фактической занятости мест из игрового save.''',
'Новых полей/аллокаций нет. На коротких таблицах выигрыш мал и может теряться в разбросе. Это небольшой локальный вариант, не заявка на решение NPC-spike.'),
'facing':('facing','Поворот с нулевой скоростью без sqrt и нормализации',
'''moveTowards вызывается со speed=0, когда нужно только повернуться к противнику. При положительном конечном distanceSquared нормализованный вектор, умноженный на ноль, даёт только signed zero: sqrt и два деления не нужны. Обновление позиции сохраняет знак нуля.

Ненулевая скорость использует прежнюю математику. Нулевой/underflow distanceSquared, NaN и infinity уходят в старую ветку. Проверены 40 000 состояний, включая обычные координаты, -1 sentinel, +/-0, subnormal, infinity, NaN и отрицательную/ненулевую скорость. NaN сравнивается через канонизирующий Float.floatToIntBits.''',
'**Не включён в conservative по измеренной регрессии обычного движения.** Дополнительной памяти нет. Обычное движение получает дополнительную проверку: move/mixed — обязательные отрицательные контроли. Не заменяется sqrt приблизительным L1-расстоянием и не меняется скорость/траектория AI.'),
 'tile-index':('tiles','Row strides и границы карты вне внутреннего tile-loop',
'''Пересечение видимой сетки с границами карты считается заранее, индекс клетки продвигается инкрементом, соседние collision cells берутся как pos-width/pos-1. Для положительного tile ID деление/остаток по 4 заменены сдвигом/маской.

Все графические вызовы, включая полностью клиппированные, остаются в том же порядке и с теми же аргументами. Это повторно проверенный перенос прежнего прототипа на новую серию после master+heap, не изменение частоты render/tick.''',
'Новых массивов нет. KVM измеряет Java-подготовку команд с тестовым sink, не нативные пиксели/MIDP. AWT использован только для отдельной проверки точных ARGB-пикселей. Этот патч вне замеряемого NPC-участка и не должен напрямую уменьшать показатель 917 мс.'),
 'tile-cull':('tiles','Не отправлять полностью невидимые tile/background команды',
'''Количество tile-строк/колонок ограничивается фактическим viewport; тот же принцип применяется к 48x48 фону. Caller уже устанавливает clip. Убираются только полностью невидимые вызовы; видимые команды сохраняют порядок, аргументы и графическое состояние.

Для NokiaUI triangle-shadow ветки tile-culling отключён, потому что примитив может выступать за свою клетку. Standalone-вариант применим без row-strides; cumulative — после него. Проверены и отдельный cull, и сочетание с index, включая отрицательные camera offsets и изменённые tiles.''',
'Дополнительной памяти нет. Compile-time-disabled NokiaUI/TiledLayer пути типизированы полной сборкой, но не исполнялись. Нативный PSPKVM/M3G/flush здесь не измерен; более редкие drawRegion не доказывают такой же процент FPS.'),
 'release':(None,'Выключить debug logging в performance/release сборке',
'''В текущем Constants LOGGING=true. Game/NPC могут печатать неудачные поиски и строить debugName/строки. Патч меняет только compile-time константу LOGGING=false: javac убирает соответствующие guarded blocks. Профилировочный HUD отдельного diagnostic-патча от этого не зависит.

Это сознательное изменение диагностического вывода, не алгоритма AI. Если ваш build pipeline уже выключает LOGGING, повторного выигрыша не будет. Нужные отладочные логи исчезнут; для разработки включайте обратно.''',
'Тайминг ускорения не заявляется: в headless kernels у всех вариантов общий no-op logger, а стоимость консоли PSPKVM агент не измерял. Есть полная сборка/preverification и сравнение размера классов. Обычные негардированные exception stack traces этим флагом не отключаются.'),
 'diagnostic':(None,'Диагностика: из чего состоит именно пик NPC-pass',
'''Отдельный патч, НЕ часть series.txt и НЕ оптимизация. Для одного и того же максимального NPC-pass сохраняются AI ms, суммарный pathfind ms, NPC.tick ms, число поисков/возвратов false и расширений A*. Это не независимые максимумы разных кадров.

HUD строка y=71: AI / pathfind / NPC.tick. Строка y=79: calls / false returns / expansions. Числа в колонках x=0/40/80. Сброс вместе с lag раз в пять секунд. pathfind-время вложено в AI: их нельзя складывать. False включает также недостаточный result buffer, а не только недостижимую цель.''',
'Патч вызывает дополнительные currentTimeMillis для NPC и считает расширения; вносит заметную погрешность и не годится для честного A/B с обычной сборкой! Нужен, чтобы узнать долю поиска на PSPKVM. Применяется к heap или после всей серии; для измерения ускорения сначала откатить/пересобрать без него.'),
}


def table(rows):
    out=['| Сценарий | Heap, мкс/op | Кандидат, мкс/op | Медиана пар | Диапазон пар |','|---|---:|---:|---:|---:|']
    for r in rows:
        out.append('| %s | %.3f | %.3f | %.3f× | %.3f–%.3f |' % (r['scenario'],float(r['reference_us_median']),float(r['candidate_us_median']),float(r['speedup_median']),float(r['speedup_min']),float(r['speedup_max'])))
    return '\n'.join(out)


def main():
    summary=list(csv.DictReader((RESULTS/'summary.csv').open()))
    raw=list(csv.DictReader((RESULTS/'raw.csv').open()))
    env=json.loads((RESULTS/'environment.json').read_text())
    counts=list(csv.DictReader((RESULTS/'operation-counts.csv').open()))
    docs=[]
    for number,label,name,fn in c.SPECS+[c.DIAGNOSTIC]:
        family,title,body,limits=NOTES[name]
        filename=number+'-'+label
        selected=[r for r in summary if r['family']==family and r['candidate']==name]
        if name=='diagnostic':commands='git apply --check patches/performance/'+filename+'.patch\ngit apply patches/performance/'+filename+'.patch'
        else:commands='git apply --check patches/performance/standalone/'+filename+'.patch\ngit apply patches/performance/standalone/'+filename+'.patch'
        text='# '+number+' — '+title+'\n\n'+body+'\n\n## Применение отдельно для A/B\n\nБаза — master `'+c.MASTER+'` с уже применённым **0003**. Heap в исходники ветки автоматически не внесён.\n\n```sh\n'+commands+'\n```\n\nДля общей последовательной серии используйте файл из родительского каталога, а не его standalone-копию. Одну оптимизацию нельзя накладывать дважды.\n\n## Память, ограничения и регрессии\n\n'+limits+'\n\n'
        if selected:text+='## Свежие замеры оригинального KVM 1.1\n\n'+table(selected)+'\n\n'
        if name=='diagnostic':text+='Пошаговая проверка на устройстве и чтение HUD: [PROFILE-GUIDE.md](PROFILE-GUIDE.md).\n\n'
        reverse_path='patches/performance/'+('' if name=='diagnostic' else 'standalone/')+filename+'.patch'
        text+='## Откат того же standalone/diagnostic файла\n\n```sh\ngit apply --reverse --check '+reverse_path+'\ngit apply --reverse '+reverse_path+'\n```\n\nДля cumulative откатывать тот же cumulative-файл в обратном порядке зависимостей. Если выбран combined, откатывать его целиком; не смешивать эти формы.\n\n'
        if name=='release':
            footprint=env['footprints'];a=footprint['heap'];b=footprint['release']
            text+='## Размер CLDC-preverified классов, без ProGuard optimization/shrinking\n\n- Game.class: %d → %d байт.\n- NPC.class: %d → %d байт.\n\n'%(a['Game_bytes'],b['Game_bytes'],a['NPC_bytes'],b['NPC_bytes'])
        text+='## Доказательства и границы\n\n[Общая проверка](../../benchmarks/kvm/bottlenecks/results/validation.txt), [сырые интервалы](../../benchmarks/kvm/bottlenecks/results/raw.csv), [все парные расчёты](../../benchmarks/kvm/bottlenecks/results/calculations.md), [окружение/хеши/полные сборки](../../benchmarks/kvm/bottlenecks/results/environment.json). Методика и смысл единиц: [подробный отчёт](../../benchmarks/kvm/bottlenecks/README.md).\n\nАгент не запускал PSPKVM/полный игровой сеанс. Unit/differential проверки не являются доказательством отсутствия любых возможных игровых регрессий.\n'
        (c.PATCHES/(filename+'.md')).write_text(text)
        docs.append((number,title,filename,name))
    overview=['# Новые bottleneck-патчи после heap','',
        '## Сначала важное','',
        '**Исходники игры в ветке оставлены на master `0716b47`, без применённых heap/новых runtime-патчей.** Здесь лежат отдельные экспортированные `.patch`, их описания и воспроизводимые проверки. Все изменения вносятся `git apply`, не `git am`.', '',
        'Пользовательский PSPKVM-результат: `1060 → 917 мс` с heap, то есть −143 мс/−13,49% к предыдущему результату. Это сообщение пользователя, а не наш замер. Для новых патчей **не заявлено время PSPKVM, FPS, батарея или доля метода в полном кадре**.', '',
        '## Что установлено чтением кода и проверками','',
        '1. Пассивные заключённые выполняли неиспользуемый попарный vision-проход; охранникам он нужен для обнаружения проломов. Патч 0008 пропускает только действительно пустую ветку, не меняя RNG.',
        '2. Поиск тратил CPU на повторную H, ветвления диагоналей/штрафов и remove+add при уменьшении ключа. Патчи 0004–0007 уменьшают цену того же поиска, не его качество/частоту.',
        '3. Объекты и зоны сканировались линейно. Для объектов ускорен broad-phase без риска stale spatial cache; для неизменных зон построен маленький индекс.',
        '4. Кеши и микроправки не универсальны: memo на постоянно меняющейся позиции, обычное движение с новым guard и guard-vision должны проверяться как отрицательные контроли.', '',
        '## Серия и подробное описание каждого патча','',
        '| № | Изменение | Подробности |','|---|---|---|']
    for number,title,filename,name in docs:overview.append('| '+number+' | '+title+' | [описание]('+filename+'.md), [патч]('+filename+'.patch) |')
    overview += ['', '## Как применять', '',
        '### Один вариант после вашего heap — лучший способ честного A/B', '',
        'Для базы master + 0003 берите **standalone/**. Например:', '',
        '```sh\ngit apply --check patches/performance/standalone/0008-passive-inmate-vision.patch\ngit apply patches/performance/standalone/0008-passive-inmate-vision.patch\n```', '',
        'Для отката: `git apply --reverse --check <тот-же-файл>` и затем `git apply --reverse <тот-же-файл>`. Если уже применены другие изменения, обязательно выполнить `--check`; не использовать принудительное применение/rejects.', '',
        '### Максимальный набор после 0003', '',
        '```sh\ngit apply --check patches/performance/all-after-heap.patch\ngit apply patches/performance/all-after-heap.patch\n```', '',
        'Это альтернатива последовательному `series.txt`, не дополнительный слой. Максимальный набор включает опциональный memo и отключение logging; он **не объявлен автоматически лучшим для каждого save/VM**.', '',
        '### С чистого master', '',
        '```sh\ngit apply --check patches/performance/all-from-master.patch\ngit apply patches/performance/all-from-master.patch\n```', '',
        'Этот файл уже включает heap. Не накладывать поверх 0003/других патчей. Старые 0001/0002 здесь не нужны.', '',
        '### Последовательно, отдельными файлами', '',
        'Начать с 0003, затем **по порядку** `series.txt` (0004–0016). Эти cumulative-файлы экспортированы относительно предыдущего шага. Standalone-копии имеют другую базу; не смешивайте две копии одной оптимизации.', '',
        '**0017 — только диагностика**, не входит ни в `series.txt`, ни в combined-файлы. Его нужно снять перед сравнением скорости.', '',
        '## Как выбирать, а не просто накладывать всё', '',
        '- Для перехода Lights Out → Rollcall начать с 0004–0007 и 0008; это изменения поиска/AI, а не render FPS. Сравнить такой пакет с вашим heap-only 917 на том же save.',
        '- 0009/0010 ускоряют независимые lookup-методы и не требуют больших spatial-массивов.',
        '- 0011 оставить отдельным экспериментом: много попаданий у стоящего персонажа не доказывает пользу на ходу.',
        '- 0012/0013 — небольшие локальные изменения; смотреть контрольные случаи.',
        '- 0014/0015 относятся к render, вне текущего NPC-lag таймера.',
        '- 0016 только если logging сейчас включён и вывод не нужен.',
        '- 0017 нужен, чтобы перестать гадать о CPU-share на вашем PSPKVM. Пришлите обе строки HUD с того же перехода; AI и pathfind не складывать.', '',
        'Полная новая методика, результаты и ограничения: [benchmarks/kvm/bottlenecks/README.md](../../benchmarks/kvm/bottlenecks/README.md).']
    (c.PATCHES/'README.md').write_text('\n'.join(overview)+'\n')
    groups=len({(r['family'],r['scenario']) for r in raw})
    timings=[int(r['elapsed_ms']) for r in raw]
    report=['# Проверка bottleneck-оптимизаций после heap','',
        'База: master **`'+c.MASTER+'` + стабильный FIFO heap 0003**. Исторические серии в соседних каталогах не смешиваются с этой. Исходники Game/NPC/Constants в рабочем дереве не патчились автоматически.', '',
        '## Результат пользователя, отдельно от наших данных','',
        'PSPKVM, phoneME/CLDC HI interpreter, Perks Lights Out → Rollcall: сначала 1390 → 1060 мс **без heap**, затем **917 мс с heap**. Последний шаг −143 мс/−13,49%, 1,156× к 1060. Все три числа сообщил пользователь; одинаковые условия последнего шага предполагаются, нами не воспроизводились.', '',
        '## Найденные лишние затраты','',
        'Это не flame graph целого PSPKVM: ниже подтверждены конкретные повторные операции в исходниках и ускорение извлечённых методов на оригинальном KVM. Главный bottleneck полного устройства нельзя установить по микробенчмарку. Для этого добавлен 0017 с коррелированным breakdown одного NPC-spike.', '',
        '- H для уже открытых соседей не зависит от нового пути и считалась зря.',
        '- Диагонали/штрафы направления разбирались ветвлениями на каждом ребре.',
        '- При снижении G heap удалял и заново вставлял узел вместо одного decrease-key.',
        '- При attack=false заключённые всё равно делали попарный vision-scan; результат не использовался. У guard canSee имеет side effect, поэтому guard-проход сохранён.',
        '- Зоны перебирались всеми типами, размеры всех объектов декодировались до дешёвого геометрического reject.', '',
        '## Новая серия','',
        '**%d сценариев, %d интервалов, %d повторов, target %d мс**. Фактические интервалы: %d–%d мс. Не считать calibration target гарантированным минимумом.'%(groups,len(raw),env['samples'],env['target_ms'],min(timings),max(timings)), '',
        'Семейства: path (npc/spread/local на шести картах); objects; zones; npc-zones (stationary/moving); seats; vision (waypoint/guard); facing (turn/move/mixed); tiles. Для path 6 вариантов, для большинства helper-методов 3, для tiles 4.', '',
        '### Поиск: heap → все CPU-патчи core', '',table([r for r in summary if r['family']=='path' and r['candidate']=='core']), '',
        'В path-таблице core реально исполняет 0004–0007; остальные CPU-изменения набора не вызываются этим workload. `npc` — достижимые синтетические пары spawn/waypoint на настоящей collision map, не запись перехода пользователя. `spread` содержит неудачные поиски; `local` — очень короткие запросы. Это три разных распределения, не одно среднее.', '',
        '### Vision: только candidate-scan, не весь AI', '',table([r for r in summary if r['family']=='vision' and r['candidate']=='vision']), '',
        'Роли в vision fixtures синтетически назначены по индексу, а не точно восстановлены из runtime NPC constructor/save. Waypoint моделирует пассивных заключённых, guard — сохранённый проход охраны. Большой локальный коэффициент не означает такой же выигрыш tickAI или 917 мс. В блоке heat заменён recorder-методом; сравниваются полные аргументы вызова, количество, состояние, выбор цели, wall-detection и следующий RNG value.', '',
        '### Объекты и зоны', '',table([r for r in summary if (r['family']=='objects' and r['candidate']=='objects') or (r['family']=='zones' and r['candidate']=='zones')]), '',
        '### Кеш зон NPC: полезный случай и отрицательный контроль', '',table([r for r in summary if r['family']=='npc-zones' and r['candidate'] in ('memo','core')]), '',
        'Memo может проигрывать на смене позиции: это явно опциональный патч. Core одновременно содержит индекс типов, поэтому его moving-результат нельзя приписать самому memo.', '',
        '### Небольшие изменения: места и facing', '',table([r for r in summary if (r['family']=='seats' and r['candidate']=='seats') or (r['family']=='facing' and r['candidate']=='facing')]), '',
        '### Tiles: Java-команды, не native MIDP/M3G', '',table([r for r in summary if r['family']=='tiles']), '',
        'Все tile-варианты проверены на точный видимый command stream и ARGB в desktop AWT. AWT здесь используется только для корректности, **не для новой серии таймингов**. Compile-disabled NokiaUI/TiledLayer ветки не исполнены; нет измерения native drawRegion/M3G/flush/PSP framebuffer.', '',
        '## Почему счётчики операций не равны коэффициенту ускорения', '',
        'Perks:npc, один batch = 16 запросов:', '',
        '| Вариант | Expansions | H calculations | Adds | Removes | Improves | Peak frontier |','|---|---:|---:|---:|---:|---:|---:|']
    for r in counts:
        if r['scenario']=='perks:npc':report.append('| '+r['variant']+' | '+' | '.join(r[k] for k in ('expanded','heuristics','adds','removes','improves','peak'))+' |')
    report += ['', 'Расширения/пути сохранены. Убирается цена вычислений и обслуживания очереди, а не вся работа A*. Из уменьшения числа H нельзя выводить такое же уменьшение полного tick.', '',
        '## Корректность и полные сборки','',
        'На desktop Java и оригинальном KVM каждый: **25 187** queue states, **1 232** six-way exact paths, **258 864** lookup cases, **40 000** float-movement cases, **5 400** vision/RNG cases. Каждый — также **3 264** tile frames. Desktop AWT: **1 920** кадров, четыре renderer-варианта с точными ARGB. Полный вывод: [validation.txt](results/validation.txt).', '',
        'Path сравнивается по return, всему result buffer (в том числе частично заполненному при false), visited/expansion order, parent/G/H и cleanup/positions. Null/короткие/полные буферы, start=target, невозможный путь, staff doors, signed-short queue costs и произвольный startDir включены. Физическое расположение элементов в валидном heap не является наблюдаемым результатом.', '',
        'Float проверяется по integer positions/direction и Float.floatToIntBits (канонический NaN), включая +/-0, subnormal, NaN/Inf. Vision проверяет RNG consumption/выбор цели/heat arguments/guard wall alerts; неизменённая остальная часть tickAI не эмулируется.', '',
        'Собраны и CLDC-preverified master, heap, каждый standalone-кандидат, каждый cumulative prefix, core/all, diagnostic и all+diagnostic: **%d полных сборок**. Java 1.3, target CLDC 45.3 + StackMap для исполняемых Game/NPC; Constants-интерфейс без методов не требует StackMap. Размеры и SHA-256 каждого класса в [environment.json](results/environment.json).'%(len(env['footprints'])), '',
        'Патчи применялись/откатывались в изолированных Git indexes; проверены обе combined-формы и diagnostic поверх всей серии. Реальный index и исходники не меняются. [Offline tests](results/offline-tests.txt) и [итоговый аудит](results/audit.txt). Это дифференциальное свидетельство на перечисленных случаях, не гарантия отсутствия любых игровых регрессий.', '',
        '## Память и холодный запуск','',
        '- Уже установленный heap: примерно +35 KiB массивов к master, как описано у 0003.',
        '- Таблица движения: 648 B payload + заголовок/ссылка на весь Game class, не на NPC.',
        '- Индекс зон: 34 + 2*Nzones B payload, два массива/три ссылки.',
        '- Memo зон: около 20 B полей на NPC (32-битные ссылки; alignment VM может отличаться).',
        '- Остальные новые CPU/render-патчи не добавляют рабочих массивов. Диагностика добавляет счётчики/часы.',
        '- Таблица/индекс строятся до steady-state замера. Это не бесплатный cold-start: начальная инициализация/аллокация не измеряется в опубликованном us/op.', '',
        '## Методика','',
        'Неизменённый original KVM 1.1, heap 2 MiB, SHA-256 `'+env['kvm_sha256']+'`. Поставленный pinned JDK 8/suite, Linux x86-64 с локальным i386 loader; VM не пересобиралась. Сравниваются source-extracted production bodies в общих headless-классах.', '',
        'Все варианты прогреваются и калибруются; перед измеряемым интервалом — новый подготовленный state, GC и два warm-up batch, вне таймера. Статические таблицы/индекс прогреты. Внутри таймера только run-loop с одинаковым checksum/общим harness overhead. Нет аллокаций на каждый path query. Инструментированные счётчики собраны отдельным PerfProfile и не участвуют в таймингах.', '',
        'Ротация — Latin shifts и обратные shifts. За 12 path-повторов каждый из шести вариантов занимает каждый слот дважды. Данные одной пары относятся к одному sample. Медиана пар `ref_us/candidate_us`, не отношение медиан. Диапазоны — наблюдаемые min/max, не confidence intervals. Фоновая нагрузка хоста/шум не исключены.', '',
        'Источник LOGGING для headless kernels — общий no-op Profiler; стоимость stdout/строк полного NPC не измерена. Поэтому 0016 имеет build/size evidence, **без придуманного timing speedup**.', '',
        '## Воспроизведение','',
        '```sh\n# Git/Python, без Java/загрузок, не трогает реальный index/source\npython3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --export-only\npython3 -m unittest discover -s benchmarks/kvm/bottlenecks -p \'test_*.py\' -v\n\n# Полные сборки + проверки Java/KVM/ARGB\npython3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --check-only \\\n  --results benchmarks/kvm/.work/bottlenecks/my-check\n\n# Полный новый замер: отдельный каталог, не переписывать опубликованные данные\npython3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --samples 12 --min-ms 150 \\\n  --results benchmarks/kvm/.work/bottlenecks/my-run\n\n# Полностью offline пересчитать опубликованный raw\npython3 benchmarks/kvm/bottlenecks/run_bottlenecks.py --analyze \\\n  benchmarks/kvm/bottlenecks/results/raw.csv \\\n  --results benchmarks/kvm/.work/bottlenecks/reanalysis\n```', '',
        'Полный runner ожидает production sources ровно от pinned master: patch-only commits поверх него допустимы. После применения патчей запускать проверку в контрольном checkout с непатченым production source. Генератор берёт master и 0003 по фиксированной базе, а не молча использует изменённый файл пользователя.', '',
        '## Что отвергнуто как небезопасное «ускорение»','',
        '- Пропуск guard vision до canSee: теряет обнаружение проломленных стен.',
        '- Сокращение частоты AI/pathfinding или time-slicing перехода: меняет моменты реакции/маршруты, не эквивалентная оптимизация.',
        '- Кеш collision/connectivity/spatial map без invalidation: двери, разрушения, переносимые объекты делают данные устаревшими. В этой серии такого кеша нет.',
        '- Замена евклидова движения приближённой нормой: меняет траекторию/округление.',
        '- Объявлять локальный vision/tile коэффициент ускорением NPC/FPS или переводить KVM us/op в PSP ms.', '',
        '## Следующий эксперимент на PSPKVM','',
        'Сохранить heap-only 917 как контроль; по очереди добавить независимые standalone-патчи, не менять save/settings, выполнить несколько одинаковых переходов. Для оценки CPU-share отдельно включить 0017, записать обе строки HUD и снять его перед A/B. Использовать максимум в одном 5-секундном окне, а не сравнивать свежий пик с давно накопленным.', '',
        'Файлы: [каталог патчей и инструкции](../../../patches/performance/README.md), [raw.csv](results/raw.csv), [summary.csv](results/summary.csv), [paired.csv](results/paired.csv), [все формулы](results/calculations.md), [counts](results/operation-counts.csv), [полные команды](results/commands.log), [окружение](results/environment.json).']
    (HERE/'README.md').write_text('\n'.join(report)+'\n')
    import supplement_reports
    extra=supplement_reports.render()
    print('Rendered overview, '+('16' if extra else '14')+' detailed patch notes and benchmark report')


if __name__=='__main__':main()
