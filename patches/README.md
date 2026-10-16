# Standalone optimization patches

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

**The optimizations are already present in this PR's branch. Do not apply them
again here.** These files are exports for applying the fixes to the original
source elsewhere, not additional changes to the optimized game.

## Verify

The offline test suite checks each patch independently against the baseline,
both application orders, exact agreement with the optimized source, and reversal
back to the baseline. It uses isolated temporary Git indexes and does not alter
the working tree, current index, or branch:

```sh
python3 -m unittest discover -s benchmarks/kvm -p 'test_*.py' -v
```
