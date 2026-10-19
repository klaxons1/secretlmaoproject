# Исторические функциональные проверки 0003 против master 0716b47

Здесь сохранён прежний вывод full-game build/preverification и queue/path проверок heap-патча: **20 644** состояния очереди и **656** точных путей на desktop Java и original KVM. Это **не timing dataset** и не физический PSPKVM-результат.

Вместе с новым исследованием публикуются ранее локальные `heap_patch.py`, его tests и эти неизменённые результаты. В tooling исправлен только guard полного `--check`: вместо требования `HEAD == 0716b47` разрешены artifact-only commits после pinned master; ancestry и проверки production source остаются. Алгоритм, экспорт 0003 и его SHA-256 не изменились. Поэтому старый environment.json намеренно сохраняет SHA wrapper-файла на момент того запуска, до исправления guard; это не заявка на совпадение всей текущей обёртки с историческим хешем.

Свежие post-heap проверки и три отдельные timing-серии: [bottlenecks/README.md](../bottlenecks/README.md). Старые raw timing files не подменялись новыми.

Чтобы перепроверять 0003 без перезаписи этого снимка, из корня на контрольном production source:

```sh
python3 - <<'PY'
import sys
sys.path.insert(0, 'benchmarks/kvm')
import heap_patch as h
h.RESULTS = h.WORK / 'my-check'
original = h.git_source(h.BASELINE)
heap = h.heap_source(original)
h.verify_patch(h.DEFAULT_PATCH, original, heap)
h.build_and_check(h.DEFAULT_PATCH, original, heap)
PY
```

`--check` обычного CLI по-прежнему пишет в его default results; для архива предпочитать отдельный каталог, как выше.
