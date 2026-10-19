# Новые bottleneck-патчи после heap

## Сначала важное

**Исходники игры в ветке оставлены на master `0716b47`, без применённых heap/новых runtime-патчей.** Здесь лежат отдельные экспортированные `.patch`, их описания и воспроизводимые проверки. Все изменения вносятся `git apply`, не `git am`.

Пользовательский PSPKVM-результат: `1060 → 917 мс` с heap, то есть −143 мс/−13,49% к предыдущему результату. Это сообщение пользователя, а не наш замер. Для новых патчей **не заявлено время PSPKVM, FPS, батарея или доля метода в полном кадре**.

## Что установлено чтением кода и проверками

1. Пассивные заключённые выполняли неиспользуемый попарный vision-проход; охранникам он нужен для обнаружения проломов. Патч 0008 пропускает только действительно пустую ветку, не меняя RNG.
2. Поиск тратил CPU на повторную H, ветвления диагоналей/штрафов и remove+add при уменьшении ключа. Патчи 0004–0007 уменьшают цену того же поиска, не его качество/частоту.
3. Объекты и зоны сканировались линейно. Для объектов ускорен broad-phase без риска stale spatial cache; для неизменных зон построен маленький индекс.
4. Кеши и микроправки не универсальны: memo на постоянно меняющейся позиции, обычное движение с новым guard и guard-vision должны проверяться как отрицательные контроли.

## Серия и подробное описание каждого патча

| № | Изменение | Подробности |
|---|---|---|
| 0004 | Эвристика только при первом открытии узла | [описание](0004-discovery-heuristic.md), [патч](0004-discovery-heuristic.patch) |
| 0005 | Одна проверка геометрии диагонали вместо четырёх веток | [описание](0005-diagonal-collision.md), [патч](0005-diagonal-collision.patch) |
| 0006 | Таблица штрафов за направление движения | [описание](0006-movement-cost-table.md), [патч](0006-movement-cost-table.patch) |
| 0007 | Decrease-key вместо удаления и повторной вставки | [описание](0007-heap-decrease-key.md), [патч](0007-heap-decrease-key.patch) |
| 0008 | Не сканировать других NPC для пассивного заключённого | [описание](0008-passive-inmate-vision.md), [патч](0008-passive-inmate-vision.patch) |
| 0009 | Дешёвый broad-phase перед декодированием размеров объекта | [описание](0009-object-broad-phase.md), [патч](0009-object-broad-phase.patch) |
| 0010 | Индекс зон по типу вместо полного сканирования | [описание](0010-zone-type-index.md), [патч](0010-zone-type-index.patch) |
| 0011 | Кеш повторных проверок зон конкретного NPC — опционально | [описание](0011-npc-zone-memo.md), [патч](0011-npc-zone-memo.patch) |
| 0012 | Один packed-key для поиска места | [описание](0012-packed-seat-lookup.md), [патч](0012-packed-seat-lookup.patch) |
| 0013 | Поворот с нулевой скоростью без sqrt и нормализации | [описание](0013-facing-only-movement.md), [патч](0013-facing-only-movement.patch) |
| 0014 | Row strides и границы карты вне внутреннего tile-loop | [описание](0014-tile-row-strides.md), [патч](0014-tile-row-strides.patch) |
| 0015 | Не отправлять полностью невидимые tile/background команды | [описание](0015-clip-invisible-tiles.md), [патч](0015-clip-invisible-tiles.patch) |
| 0016 | Выключить debug logging в performance/release сборке | [описание](0016-release-logging-off.md), [патч](0016-release-logging-off.patch) |
| 0017 | Диагностика: из чего состоит именно пик NPC-pass | [описание](0017-npc-lag-breakdown.md), [патч](0017-npc-lag-breakdown.patch) |
| 0018 | Не повторять идентичный неудачный fallback | [описание](0018-avoid-identical-failed-fallback.md), [патч](0018-avoid-identical-failed-fallback.patch) |
| 0019 | Кеш int-приоритетов heap, ещё ≈35 KiB | [описание](0019-cache-heap-priorities.md), [патч](0019-cache-heap-priorities.patch) |

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

## Как применять

### Один вариант после вашего heap — лучший способ честного A/B

Для базы master + 0003 берите **standalone/**; исключение — 0019, ему также нужен 0007. Например:

```sh
git apply --check patches/performance/standalone/0008-passive-inmate-vision.patch
git apply patches/performance/standalone/0008-passive-inmate-vision.patch
```

Для отката: `git apply --reverse --check <тот-же-файл>` и затем `git apply --reverse <тот-же-файл>`. Если уже применены другие изменения, обязательно выполнить `--check`; не использовать принудительное применение/rejects.

### Первоначальный frozen-набор 0004–0016 после 0003

```sh
git apply --check patches/performance/all-after-heap.patch
git apply patches/performance/all-after-heap.patch
```

Это альтернатива последовательному `series.txt`, не дополнительный слой. Максимальный набор включает опциональный memo и отключение logging; он **не объявлен автоматически лучшим для каждого save/VM**.

### С чистого master

```sh
git apply --check patches/performance/all-from-master.patch
git apply patches/performance/all-from-master.patch
```

Этот файл уже включает heap. Не накладывать поверх 0003/других патчей. Старые 0001/0002 здесь не нужны.

### Последовательно, отдельными файлами

Начать с 0003, затем **по порядку** `series.txt` (0004–0016). Эти cumulative-файлы экспортированы относительно предыдущего шага. Standalone-копии имеют другую базу; не смешивайте две копии одной оптимизации.

**0017 — только диагностика**, не входит ни в `series.txt`, ни в combined-файлы. Его нужно снять перед сравнением скорости.

## Как выбирать, а не просто накладывать всё

- Для перехода Lights Out → Rollcall начать с 0004–0007 и 0008; это изменения поиска/AI, а не render FPS. Сравнить такой пакет с вашим heap-only 917 на том же save.
- 0009/0010 ускоряют независимые lookup-методы и не требуют больших spatial-массивов.
- 0011 оставить отдельным экспериментом: много попаданий у стоящего персонажа не доказывает пользу на ходу.
- 0012/0013 — небольшие локальные изменения; смотреть контрольные случаи.
- 0014/0015 относятся к render, вне текущего NPC-lag таймера.
- 0016 только если logging сейчас включён и вывод не нужен.
- 0017 нужен, чтобы перестать гадать о CPU-share на вашем PSPKVM. Пришлите обе строки HUD с того же перехода; AI и pathfind не складывать.

Полная новая методика, результаты и ограничения: [benchmarks/kvm/bottlenecks/README.md](../../benchmarks/kvm/bottlenecks/README.md).

## Поздние кандидаты без подмены основной серии

0018 и 0019 обнаружены после фиксации основной серии. Их новые raw/counters/checks хранятся отдельно: [fallback](../../benchmarks/kvm/bottlenecks/fallback/README.md), [priority](../../benchmarks/kvm/bottlenecks/priority/README.md). Старые raw, источники и SHA основной серии не переписывались.

[Отдельные коммиты каждого патча](COMMITS.md).

## Быстрые ссылки на альтернативные conservative-файлы

- После 0003: [conservative](conservative-after-heap.patch) **или** [conservative-memory](conservative-memory-after-heap.patch).
- С чистого master: [conservative](conservative-from-master.patch) **или** [conservative-memory](conservative-memory-from-master.patch).
- Как измерять на устройстве и читать 0017: [PROFILE-GUIDE.md](PROFILE-GUIDE.md).
