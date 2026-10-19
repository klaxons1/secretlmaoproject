# Game hot-path benchmarks on the original KVM 1.1

> **Historical measurement snapshot.** These timings describe the earlier measured source, not the newly synchronized master. For the heap-only patch against master `0716b47` and its fresh build/KVM checks, see [patches/HEAP.md](../../patches/HEAP.md). No historical timing samples were replaced.

This change optimizes two sources of avoidable interpreter work in `src/Game.java`:

- **Render ordering in `tickMap()` → `sortRenderChars()`**: replace an unconditional bubble sort with a stable, allocation-free insertion sort. Already/nearly sorted character lists are the important case because the previous render order is retained between updates.
- **Pathfinding's `openAdd()` / `openRemove()`**: cache array references and neighbor indices in locals, and consolidate list insertion. This reduces interpreted field/array loads without changing the linked-list algorithm, priority calculation, or FIFO ordering of equal-cost nodes.

Standalone exports of the two production fixes are available in
[`patches/`](../../patches/README.md). They apply independently to the baseline;
the fixes are already included in this branch.

These are **game-method optimizations, not modifications to the VM**. Every published timing runs both implementations on the exact same **unmodified Linux/i386 KVM 1.1 executable** supplied by [the CLDC repository](https://github.com/klaxons1/j2me_cldc-1_1-fcs-src-winunix). Its SHA-256 is:

```
917b17f278023670b9a5472d7740d12a5c7b1c6e3718196f828d4bed5de82e66
```

“Original” means game source at commit `785ef001798fad8e4e9f2e21426e4c6d65875d33`; “optimized” means the working source whose hash is recorded in `results/environment.json`. Neither column is a desktop-Java performance measurement.

## Results and calculations

Measured on 2026-10-16 on an Intel Xeon x86-64 host at 2.60 GHz: **21 scenarios × 9 paired samples = 378 timed intervals**. Actual sample intervals were 234–508 ms. These are headless KVM measurements, not phone FPS.

| Workload | Median paired speedup across the measured scenarios |
|---|---:|
| Already sorted render order | **16.40–23.18×** |
| Nearly sorted render order (exactly 3 inversions) | **15.25–21.95×** |
| Initial map spawn order | **3.62–7.74×** |
| Reversed live prefix | **2.53–2.97×** |
| Equal-cost / mixed frontier enqueue + drain | **1.62–1.75×** |
| Full pathfinding, all six map fixtures | **1.29–1.55×** |
| 16-node head-only frontier enqueue + drain | **0.97×** (about 3% slower) |

The ranges above are ranges of scenario medians, not confidence intervals. The short head-insertion case is an explicit trade-off: local-reference setup offers little benefit when every insertion stops immediately. It is retained in the results; all six full pathfinding fixtures improve despite this case.

The preverified, unoptimized `Game.class` grows from 161,858 to 161,990 bytes: **+132 bytes (+0.082%)**. No additional persistent fields, per-map arrays, or per-sort allocations are introduced; the queue uses additional stack locals.

- [All results, formulas, and a worked calculation](results/calculations.md)
- [Every timed interval](results/raw.csv), including iteration counts, AB/BA order, integer milliseconds, and checksums
- [Machine-readable summary](results/summary.csv)
- [Separate, untimed operation counts](results/operation-counts.csv)
- [Host, exact dependencies, source/resource hashes, and compiled class sizes](results/environment.json)
- [Correctness results](results/validation.txt) and [exact build/run command log](results/commands.log)

The measurements cover all six committed map geometries, three real character-array sizes, initial spawn order, already sorted order, three adjacent swaps, reversed live prefixes, and head/equal-cost/mixed queue insertion. Adverse cases are retained, not discarded.

## Why these methods?

### Render ordering

`tickMap()` sorts every fourth tick. At the configured 30 ticks/second this is 7.5 sorts/second. The original loops perform **`n × (n − 1) / 2` adjacent-slot tests on every invocation**, including an already sorted array and unused null suffix:

| Representative map | Array slots | Live characters at load | Old adjacent-slot tests/sort |
|---|---:|---:|---:|
| Perks | 31 | 21 | 465 |
| Irongate | 41 | 30 | 820 |
| Shankton State Pen | 46 | 36 | 1,035 |

Insertion sort scans an already sorted live prefix once: respectively 20, 29, and 35 key comparisons. The separate instrumented run records actual comparison counts for every layout. Insertion sort is `O(n + inversions)` for these lists, remains `O(n²)` in the reverse-order worst case, and allocates no objects or arrays.

Ordering semantics are unchanged:

- same `y − 10000` priority for stunned/lying characters;
- equal keys retain **object-identity order**, not merely equal numeric values;
- null slots remain **barriers**, including internal holes, rather than being compacted;
- same once-per-four-ticks scheduling and same array shared with rendering.

### Pathfinding frontier

`openAdd()` scans a sorted linked list and is called for newly discovered nodes and decrease-key reinsertion. The untimed profile records queue additions, actual cost comparisons, removals, and expanded search nodes on the real map collision grids. Original and optimized searches retain the same expansion order and queue-scan counts: the improvement here is **less interpreter work per operation**, not a claim of a better asymptotic algorithm.

The optimized queue still inserts **after** existing equal-cost nodes. A heap or a different A* heuristic could alter path tie-breaking and require additional per-map memory, so neither is introduced. `pathfind()` itself, collision checks, traceback, costs, and cleanup remain unchanged. No additional per-map storage is added.

This is targeted hot-path analysis, **not a whole-game CPU profile**. These headless measurements identify avoidable work and quantify the local improvements; they do not establish which subsystem dominates every handset/frame.

## Reproduce

Requirements: Linux x86-64 with kernel IA32 execution support, Python 3, `git`, and access to GitHub. No installed Java, root permissions, apt packages, display server, or external game assets are required.

From the repository root:

```sh
# Fast, offline checks of extraction and calculation logic.
python3 -m unittest discover -s benchmarks/kvm -p 'test_*.py' -v

# Download pinned dependencies, compile and CLDC-preverify both full game
# versions and benchmark kernels, then run correctness checks on both VMs.
python3 benchmarks/kvm/run.py --check-only \
  --results benchmarks/kvm/.work/check-results

# Complete benchmark: 9 paired samples/scenario, calibration target >=250 ms.
# Use a new results directory so the checked-in run remains intact.
python3 benchmarks/kvm/run.py --samples 9 --min-ms 250 \
  --results benchmarks/kvm/.work/my-results

# Recompute the published summaries without downloading or running anything.
python3 benchmarks/kvm/run.py --analyze benchmarks/kvm/results

# Optional subset; other families are 'sort' and 'queue'.
python3 benchmarks/kvm/run.py --filter path --samples 9 --min-ms 250 \
  --results benchmarks/kvm/.work/path-results
```

Run timings on an otherwise idle host. Do not run multiple benchmark processes concurrently. The runner fails on compile/preverification failures, semantic mismatches, missing samples, invalid normalization/order, or checksum mismatches. It does not make noisy timing thresholds into correctness tests.

### Downloaded tools

All dependencies are commit-pinned and downloaded archives/binaries are SHA-256 checked. Downloads and generated classes remain under ignored `.work/`; **no third-party binaries or large archives are committed**.

| Dependency | Pinned commit | Purpose |
|---|---|---|
| [`LLM-J2ME-SUITE`](https://github.com/klaxons1/LLM-J2ME-SUITE) | `c4799767bf43c9a94d327f6394ef51445a2be807` | Java ME API jars and ProGuard 6.2.2 |
| [`j2me_cldc-1_1-fcs-src-winunix`](https://github.com/klaxons1/j2me_cldc-1_1-fcs-src-winunix) | `d924b6425fae9fb39387882ab6a86ae555cdcc90` | Original KVM executable and actual CLDC API classes |
| [`tools_linux_jdk8`](https://github.com/klaxons1/tools_linux_jdk8) | `7be76e541810614e3627d42c68759fab16055b7b` | JDK 8 compiler, as recommended by the suite |
| [`chromium-net` sysroot](https://github.com/hanpfei/chromium-net/tree/9df8ce98c2a14fb60c2f581853011e32eb4bed0f/build/linux/debian_wheezy_i386-sysroot/lib/i386-linux-gnu) | `9df8ce98c2a14fb60c2f581853011e32eb4bed0f` | Four pinned Debian i386 glibc 2.13 files needed to run the old binary without system installation |

The old glibc is used only by the local, offline benchmark process. Do not use this historical runtime for network-facing services. Upstream tools retain their upstream licenses; downloading them does not relicense them under this project's MIT license.

## Methodology and safeguards

1. **Extract, don't hand-reimplement.** `run.py` obtains the baseline with `git show <baseline>:src/Game.java` and reads the optimized working source. It extracts the actual sorting and complete pathfinding method bodies into headless classes. Only the enclosing callable signature/receiver and field ownership are adapted to a common test fixture. Sorting's original tick guard is moved outside the measured kernel. Both callable sort kernels have the same harness dispatch overhead; production now has one additional helper call at its original call site.
2. **Use the original interpreter.** There are no C patches, native algorithm replacements, emulator timing substitutes, or VM rebuilds. The executable is launched directly through a pinned i386 dynamic loader with a 2 MiB Java heap. No QEMU is involved.
3. **Use CLDC-compatible bytecode.** Compile with `javac -source 1.3 -target 1.3` against the real CLDC classes. ProGuard uses `-microedition -target 1.1 -dontshrink -dontoptimize -dontobfuscate` to generate CLDC `StackMap` attributes. Both full production versions are also compiled and preverified against the suite's CLDC/MIDP/MMAPI/M3G/Nokia APIs. No ProGuard optimization changes the compared algorithms.
4. **Separate setup and profiling.** Class loading, fixture allocation, warm-up, calibration, explicit GC, console output, and the final checksum are outside each timed interval. Kernels allocate nothing during timing. Instrumented `Counted*Kernel` classes are used only for operation counts; they are never timed.
5. **Make small methods measurable.** Each variant is calibrated independently to a target interval of at least 250 ms and normalized by its exact operation count. This avoids either sub-millisecond optimized samples or excessively long baseline batches. Both variants repeat the same deterministic unit workload. Each has two untimed warm-up batches before calibration; the sample order alternates AB/BA.
6. **Account for common harness costs.** Sort intervals include a native `System.arraycopy` fixture reset before each call. Queue intervals enqueue and drain the whole frontier and record pop order. Path intervals execute eight queries/batch, including normal search, traceback, cleanup, and common result hashing. These common costs are included, **not subtracted**. Thus queue timings describe `openAdd`+`openRemove` together, not individually isolated calls.
7. **Record raw data.** Timers are `System.currentTimeMillis()` inside KVM. Summaries use microseconds/operation and the median of paired original/optimized ratios; the reported time reduction is `100 × (1 − 1 / median_speedup)`. Min–max ranges describe observed variability, not confidence intervals. Different variants' iteration counts are explicit in `raw.csv`. Checksums describe one final workload, so they remain comparable across iteration counts.

### Map fixture boundaries

`Fixtures.java` reads the committed version-5 map format through the NPC records. Collision lookup method bodies are extracted from production; tile and object collision overlays follow `initMap()`. All six maps are 96×93. The fixtures retain all stash objects (no day-zero random deletion) and do not include saves, moved desks, runtime tile damage, dynamic NPC updates, textures, or MIDP graphics calls. Path endpoints are deterministic walkable cells across each real grid, with both staff-door policies; they are not a recorded player session or a real NPC path-request distribution.

The sorting `NPC` fixture supplies only fields the method reads, plus identity/position for fixtures. Both versions use an identical no-op logger to keep console I/O out of no-path searches. Benchmark dispatch and smaller fixture objects can affect absolute host costs; the full game and proprietary handset VM are not claimed to have identical timing.

## Correctness coverage

Each complete run verifies:

- **101,674 sorting cases**: every sequence of length 0–7 over five null/key/animation symbols; 4,000 deterministic randomized arrays up to 96 slots; all six actual initial map populations; all 12 timed sort fixtures. Checks include ties, stunned/lying priority, internal nulls, empty/all-null inputs, repeated object references, unusual animation values, and integer-limit coordinates. Each nearly-sorted fixture is independently checked to contain exactly three inversions, rather than accidental swaps of equal keys.
- **10,772 queue-state checks**: empty/not-enqueued start removal, equal-priority FIFO, all endpoint positions, 10,000 deterministic mixed add/remove/decrease-key steps, signed-short costs, forward/back-link invariants, and exact agreement with the baseline queue.
- **416 pathfinding comparisons**: all six map geometries plus synthetic disconnected/door/avoid/corner-blocking grids; both door policies; start=target; no-path and buffer-exhaustion behavior; null, empty, tiny, and normal output buffers. The entire result buffer, expansion/visited order, and workspace cleanup must match, not just reachability.

The same checks run on desktop Java for a second execution engine **and on the original KVM**. Desktop Java timings are never reported as KVM results. The full game is compiled/preverified, but its MIDP rendering and gameplay have **not** been exercised on a physical phone. Device profiling remains the next step before translating local speedups into FPS or battery-life claims.
