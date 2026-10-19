# Standalone optimization patches

## New post-heap bottleneck patches (0004–0019)

**[Detailed Russian catalog and application choices](performance/README.md)** —
16 separate exports, including optional diagnostics and two deliberately opt-in
candidates with measured regressions. The conservative bundles exclude those
regressions; the memory variant trades another ≈35 KiB for cached heap priorities.

Base: current pinned master `0716b47` + 0003, **except 0019 also requires 0007**.
The `*-from-master` bundles already include 0003. Do not layer combined files or
reapply their individual components. Production source in this branch is still
the unpatched master, for reproducible A/B; use the exported patches explicitly.

[Three new original-KVM datasets and verification](../benchmarks/kvm/bottlenecks/README.md).
No new physical PSPKVM timing or full-game FPS is claimed.

## Heap patch for synchronized master

[0003-use-stable-heap-pathfinding.patch](0003-use-stable-heap-pathfinding.patch)
replaces only the pathfinding frontier with a stable FIFO binary min-heap.
It targets **`0716b47205e297375d7a3848d923d5ce916eba6d`** of `master`,
not the old baseline below. It preserves master's AI/lag counter, tile rendering,
and once-per-eight-ticks render sort. The heap patch is **not applied** to the
working `src/Game.java` so that master and heap can be tested separately.

See [HEAP.md](HEAP.md) for apply/reverse commands, memory cost, and fresh
Java/CLDC/KVM verification. Do not apply the two historical patches first.

## Historical render/list patches

Two independent `git apply` patches for the game source at baseline commit
`785ef001798fad8e4e9f2e21426e4c6d65875d33`:

1. [0001-optimize-render-sort.patch](0001-optimize-render-sort.patch) — replace
   the unconditional render-order bubble sort in `Game.tickMap()` with stable,
   allocation-free insertion sort. Preserve null barriers, equal-key order,
   stunned/lying priority, and sorting frequency.
2. [0002-optimize-pathfinding-queue.patch](0002-optimize-pathfinding-queue.patch)
   — optimize `Game.openAdd()` / `openRemove()` by caching array references and
   neighbor indices. Preserve the linked list and equal-cost FIFO tie-breaking.

Each patch changes **only `src/Game.java`**. They can be applied individually or
in either order. Together they reproduce exactly the production source used by
[the original-KVM benchmarks](../benchmarks/kvm/README.md); they do not include
the benchmark harness or results.

## Apply

Copy these files into a clean checkout of the baseline (or a compatible version)
and run from that checkout's repository root:

```sh
git apply --check patches/0001-optimize-render-sort.patch patches/0002-optimize-pathfinding-queue.patch
git apply patches/0001-optimize-render-sort.patch patches/0002-optimize-pathfinding-queue.patch
```

For just one optimization, pass only its patch filename to both commands.

**Do not apply these two historical exports on current master.** Upstream now
contains its own versions of the initial optimizations and additional changes.
These exports remain for the original baseline; they are not additional changes
to synchronized master. Use `0003` alone for the new heap experiment.

## Verify

The offline test suite checks each patch independently against the baseline,
both application orders, exact agreement with the optimized source, and reversal
back to the baseline. It uses isolated temporary Git indexes and does not alter
the working tree, current index, or branch:

```sh
python3 -m unittest discover -s benchmarks/kvm -p 'test_*.py' -v
```
