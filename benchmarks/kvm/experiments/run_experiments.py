#!/usr/bin/env python3
"""Historical experiment: stable heap frontier and tile command generation.

Does not edit production sources, publish commits, or overwrite the earlier
benchmark results. KVM command-generation and desktop AWT raster timings are
strictly separate engines; neither is physical-phone FPS.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import run as base

ROOT = base.ROOT
WORK = base.WORK / "experiments"
LOG = []


def command(args, accepted=(0,)):
    args = [str(arg) for arg in args]
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    LOG.append("$ " + " ".join(args).replace(str(ROOT), "<repo>") + "\n" + result.stdout.replace(str(ROOT), "<repo>"))
    if result.returncode not in accepted:
        print(result.stdout, flush=True)
        raise RuntimeError("Command failed: " + args[0])
    return result.stdout


def replace_one(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected source shape: " + old[:100])
    return source.replace(old, new, 1)


def heap_game(source):
    start = source.index("\t// region Pathfinding\n")
    end = source.index("\t// endregion Pathfinding", start)
    region = source[start:end]
    region = replace_one(region, "// linked list of open nodes", "// stable binary heap of open nodes")
    helper = (HERE / "HeapQueue.java.inc").read_text()
    fields, methods = helper.split("\tvoid openAdd(int n)", 1)
    methods = "\tvoid openAdd(int n)" + methods
    region = replace_one(region, "\tshort[] openNodePrev;\n\tshort[] openNodeNext;", fields.rstrip())
    region = replace_one(region, "\t\topenNodePrev = new short[size];\n\t\topenNodeNext = new short[size];",
                         "\t\topenHeap = new short[size];\n\t\topenHeapPosition = new short[size];\n\t\topenHeapOrder = new int[size];\n\t\topenHeapSize = openHeapSerial = 0;")
    region = replace_one(region, "\t\t\topenNodePrev[i] = -1;\n\t\t\topenNodeNext[i] = -1;", "\t\t\topenHeapPosition[i] = -1;")
    # Newer master also uses these aliases inside openAdd, which is replaced
    # below. Restrict this edit to the search portion; old generated output is
    # unchanged and duplicate aliases in upstream queue code are unambiguous.
    queue_start = region.index("\t// sorted linked list functions")
    search = replace_one(region[:queue_start], "\t\tshort[] openNodePrev = this.openNodePrev;\n\t\tshort[] openNodeNext = this.openNodeNext;",
                         "\t\tshort[] openHeapPosition = this.openHeapPosition;")
    region = search + region[queue_start:]
    region = replace_one(region, "\t\tint visited = 0;\n\t\tsortedNode = -1;",
                         "\t\tint visited = 0;\n\t\topenHeapSize = openHeapSerial = 0;\n\t\tsortedNode = -1;")
    region = replace_one(region, "openNodePrev[n] == -1 && openNodeNext[n] == -1 && sortedNode != n", "openHeapPosition[n] == -1")
    region = replace_one(region, "\t\t\topenNodePrev[n] = -1;\n\t\t\topenNodeNext[n] = -1;", "\t\t\topenHeapPosition[n] = -1;")
    region = replace_one(region, "\t\treturn ret;\n\t}\n\n\t// sorted linked list functions", "\t\topenHeapSize = openHeapSerial = 0;\n\t\treturn ret;\n\t}\n\n\t// sorted linked list functions")
    region = region.split("\t// sorted linked list functions", 1)[0] + methods + "\n"
    return source[:start] + region + source[end:]


def tile_loop(source, cull):
    method = base.method(source, "void paintMap(")
    start = method.index("\t\t\t// tiles\n\t\t\tint y = -yr;")
    loop_start = method.index("for (int i = 0; i < viewRows; ++i)", start)
    old_loop = method[start:loop_start] + base.block(method, loop_start)
    cell_start = method.index("x: {", loop_start)
    cell = base.block(method, cell_start)
    cell = cell[cell.index("{") + 1:cell.rindex("}")]
    cell = replace_one(cell, "\n\t\t\t\t\t\t\tif (j + xoff < 0 || j + xoff >= width) break x;", "")
    cell = cell.replace("solid[j + xoff + (i + yoff - 1) * width]", "solid[pos - width]")
    cell = cell.replace("solid[j + xoff - 1 + (i + yoff) * width]", "solid[pos - 1]")
    cell = cell.replace("solid[j + xoff - 1 + (i + yoff - 1) * width]", "solid[pos - width - 1]")
    cell = cell.replace("i + yoff", "mapY").replace("j + xoff", "mapX")
    cell = cell.replace("(tile % 4) * TILE_SIZE", "(tile & 3) * TILE_SIZE")
    cell = cell.replace("(tile / 4) * TILE_SIZE", "(tile >> 2) * TILE_SIZE")
    # Align the transplanted cell body with the new two-loop driver.
    lines = cell.strip("\n").splitlines()
    cell = "\n".join(line[2:] if line.startswith("\t\t") else line for line in lines) + "\n"
    driver = (HERE / "TileLoop.java.inc").read_text()
    driver = replace_one(driver, "// TILE_BODY\n", cell)
    if cull:
        driver = replace_one(driver, "\t\t\t// CULL_LIMITS\n", "\t\t\t// The callers clip drawing to this viewport. Skip wholly invisible cells.\n\t\t\tif (!NOKIAUI_SHADOWS) {\n\t\t\tint visibleCols = (viewWidth + xr + TILE_SIZE - 1) / TILE_SIZE;\n\t\t\tint visibleRows = (viewHeight + yr + TILE_SIZE - 1) / TILE_SIZE;\n\t\t\tif (lastCol > visibleCols) lastCol = visibleCols;\n\t\t\tif (lastRow > visibleRows) lastRow = visibleRows;\n\t\t\t}\n")
    updated = replace_one(source, old_loop, driver.rstrip())
    if cull:
        # Same clipping argument for the 48x48 background, without changing
        # the order of the surviving image draws.
        updated = replace_one(updated, "int y0 = viewHeight / (TILE_SIZE * 3) + 1;", "int y0 = (viewHeight + yr + TILE_SIZE * 3 - 1) / (TILE_SIZE * 3) - 1;")
        updated = replace_one(updated, "for (int x = viewWidth / (TILE_SIZE * 3) + 1; x >= 0; --x)",
                              "for (int x = (viewWidth + xr + TILE_SIZE * 3 - 1) / (TILE_SIZE * 3) - 1; x >= 0; --x)")
    return updated


def generate():
    hashes = base.generate_sources()
    current = (ROOT / "src/Game.java").read_text()
    original = base.original_source()
    if base.method(original, "void paintMap(") != base.method(current, "void paintMap("):
        raise ValueError("Original/current tile baseline differs; update experiment explicitly")
    generated = WORK / "generated"
    if generated.exists(): shutil.rmtree(generated)
    generated.mkdir(parents=True)
    heap = heap_game(current)
    region = heap.split("// region Pathfinding\n", 1)[1].split("// endregion Pathfinding", 1)[0]
    import re
    region, removed = re.subn(r"^\t(?:short\[\]|byte\[\]|int) (?:nodeParent|nodeG, nodeH|sortedNode|visitedNodes|nodeDir, nodeX, nodeY);\n", "", region, flags=re.M)
    if removed != 5: raise ValueError("Unexpected heap common state")
    sort = base.method(current, "static void sortRenderChars(").replace("static void sortRenderChars(", "void sort(", 1)
    text = "final class HeapKernel extends Kernel {\n" + sort + "\n" + region + "\n}\n"
    (generated / "HeapKernel.java").write_text(text)
    counted = text.replace("class HeapKernel", "class CountedHeapKernel", 1)
    counted = counted.replace("extends Kernel {", "extends Kernel {\nint heapComparisons, queueAdds, queueRemoves, expandedNodes, peak;", 1)
    counted = counted.replace("// HEAP_COMPARE", "++heapComparisons;")
    counted = counted.replace("// HEAP_PEAK", "if (openHeapSize > peak) peak = openHeapSize;")
    counted = counted.replace("void openAdd(int n) {", "void openAdd(int n) { ++queueAdds;", 1)
    counted = counted.replace("void openRemove(int n) {", "void openRemove(int n) { ++queueRemoves;", 1)
    counted = counted.replace("while (cur != -1) {", "while (cur != -1) { ++expandedNodes;", 1)
    (generated / "CountedHeapKernel.java").write_text(counted)
    candidates = {"heap": heap, "tile-index": tile_loop(current, False), "tile-cull": tile_loop(current, True),
                  "heap-tile-cull": heap_game(tile_loop(current, True))}
    for label, source in candidates.items():
        directory = WORK / ("game-" + label) / "source"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "Game.java").write_text(source)
        hashes["game-" + label] = base.sha(source.encode())
    for name, source in (("OriginalTiles", current), ("IndexedTiles", candidates["tile-index"]), ("CulledTiles", candidates["tile-cull"])):
        phase = base.method(source, "void paintMap(")
        phase = phase[:phase.index("\n\t\tProfiler.beginRenderSection(Profiler.RENDER_OBJECTS);")] + "\n}\n"
        phase = phase.replace("void paintMap(", "void render(", 1)
        phase = phase.replace("Profiler.beginRenderSection(Profiler.RENDER_BG);", "")
        phase = phase.replace("Profiler.beginRenderSection(Profiler.RENDER_TILES);", "")
        (generated / (name + ".java")).write_text("final class " + name + " extends TileKernel {\n" + phase + "}\n")
    for path in generated.glob("*.java"): hashes[path.name] = base.sha(path.read_bytes())
    return hashes, candidates


def preverify(raw, verified, libs):
    if verified.exists(): shutil.rmtree(verified)
    args = [base.jdk("java"), "-jar", base.WORK / "suite/libs/proguard.jar", "-injars", raw, "-outjars", verified]
    for library in libs: args += ["-libraryjars", library]
    command(args + ["-dontshrink", "-dontoptimize", "-dontobfuscate", "-microedition", "-target", "1.1"])


def build():
    base.bootstrap()
    WORK.mkdir(parents=True, exist_ok=True)
    hashes, candidates = generate()
    raw = WORK / "raw"
    if raw.exists(): shutil.rmtree(raw)
    raw.mkdir()
    api = base.WORK / "cldc/j2me_cldc/bin/common/api/classes"
    sources = sorted((PARENT / "src").glob("*.java")) + sorted((base.WORK / "generated").glob("*.java"))
    sources += sorted((HERE / "src").glob("*.java")) + sorted((WORK / "generated").glob("*.java"))
    sources += [ROOT / "common/src/Constants.java", ROOT / "common/src/Objects.java"]
    command([base.jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", api, "-d", raw] + sources)
    preverify(raw, WORK / "verified", [api])
    resources = list(base.MAPS) + [p.name for p in (ROOT / "res").glob("tiles_*.png")]
    resources += [p.name for p in (ROOT / "res").glob("ground_*.png")] + ["shadow.png"]
    for name in resources: shutil.copyfile(ROOT / "res" / name, WORK / "verified" / name)
    libs = [base.WORK / "suite/uei" / name for name in ("cldc11.jar", "midp21.jar", "jsr135.jar", "jsr184.jar", "nokiaui.jar")]
    production = sorted((ROOT / "src").glob("*.java")) + sorted((ROOT / "common/src").glob("*.java"))
    full_sources = {"original": base.original_source(), "list": (ROOT / "src/Game.java").read_text()}
    full_sources.update(candidates)
    for label, source in full_sources.items():
        directory = WORK / ("game-" + label)
        (directory / "source").mkdir(parents=True, exist_ok=True)
        (directory / "source/Game.java").write_text(source)
        out = directory / "raw"
        if out.exists(): shutil.rmtree(out)
        out.mkdir()
        files = [path for path in production if path.name != "Game.java"] + [directory / "source/Game.java"]
        command([base.jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", libs[0],
                 "-classpath", os.pathsep.join(str(lib) for lib in libs[1:]), "-d", out] + files)
        preverify(out, directory / "verified", libs)
    desktop_sources = sorted((HERE / "desktop").glob("*.java"))
    if desktop_sources:
        desktop = WORK / "desktop"
        if desktop.exists(): shutil.rmtree(desktop)
        desktop.mkdir()
        command([base.jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-classpath", WORK / "verified", "-d", desktop] + desktop_sources)
    print("Experiment kernels, original/current games and four full prototypes compiled/preverified", flush=True)
    return hashes


def java_command():
    return [base.jdk("java"), "-Djava.awt.headless=true", "-Xmx512m", "-cp", os.pathsep.join([str(WORK / "desktop"), str(WORK / "verified")])]


def kvm_command():
    return base.kvm_command()[:-1] + [str(WORK / "verified")]


def validate():
    outputs = []
    for engine, args in (("desktop-correctness", java_command()), ("original-kvm-1.1", kvm_command())):
        for main in ("Checks", "ExperimentChecks"):
            print("Validate:", engine, main, flush=True)
            output = command(args + [main])
            if "CHECKS,PASS" not in output: raise RuntimeError("Missing correctness sentinel")
            print(output, end="", flush=True)
            outputs.append(engine + " " + main + "\n" + output)
    if (HERE / "desktop/RasterChecks.java").exists():
        output = command(java_command() + ["RasterChecks"])
        if "RASTER,PASS" not in output: raise RuntimeError("Missing raster sentinel")
        print(output, end="", flush=True)
        outputs.append("desktop-AWT-reference\n" + output)
    return "\n".join(outputs)


RAW_FIELDS = ("engine", "family", "scenario", "variant", "sample", "order", "iterations", "operations", "elapsed_ms", "checksum")
METRIC_FIELDS = ("engine", "family", "scenario", "variant", "operations", "queue_adds", "priority_comparisons", "queue_removes", "expanded_nodes",
                 "peak_frontier", "raw_regions", "raw_rects", "visible_regions", "visible_rects", "checksum", "found_queries", "result_nodes")
QUERY_FIELDS = ("scenario", "query", "start_x", "start_y", "start_direction", "target_x", "target_y", "no_staff_doors", "found", "result_nodes",
                "expanded_nodes", "queue_adds", "heap_comparisons", "peak_frontier")


def scenarios():
    for map_name in ("perks", "irongate", "shanktonstatepen"):
        for layout in ("spawn", "sorted", "near", "reverse"):
            yield "original-kvm-1.1", "sort", map_name + ":" + layout
    for scenario in ("head:16", "mixed:16", "mixed:64", "ties:64", "mixed:256", "ties:256"):
        yield "original-kvm-1.1", "queue", scenario
    for map_name in base.MAPS:
        for distribution in ("spread", "npc", "local"):
            yield "original-kvm-1.1", "path", map_name + ":" + distribution
    for map_name in base.MAPS:
        for size in ("176x220", "240x320", "640x480"):
            for shadows in ("plain", "shadows"):
                yield "original-kvm-1.1", "tiles", map_name + ":" + size + ":" + shadows
        for size in ("240x320", "640x480"):
            for shadows in ("plain", "shadows"):
                yield "desktop-awt-reference", "tiles", map_name + ":" + size + ":" + shadows


def collect(args, selected):
    from analyze import write_csv, validate as validate_raw, names
    raw, metrics, queries = [], [], []
    for index, (engine, family, scenario) in enumerate(selected):
        print("[%d/%d] %s %s %s" % (index + 1, len(selected), engine, family, scenario), flush=True)
        if engine == "original-kvm-1.1" and family != "sort":
            output = command(kvm_command() + ["ExperimentProfile", family, scenario])
            for line in output.splitlines():
                fields = line.split(",")
                if fields[0] == "METRIC":
                    if len(fields) != len(METRIC_FIELDS): raise ValueError("Metric schema")
                    metrics.append(dict(zip(METRIC_FIELDS, [engine] + fields[1:])))
                elif fields[0] == "QUERY":
                    if len(fields) - 1 != len(QUERY_FIELDS): raise ValueError("Query schema")
                    queries.append(dict(zip(QUERY_FIELDS, fields[1:])))
        if engine == "original-kvm-1.1":
            output = command(kvm_command() + ["ExperimentBenchmark", family, scenario, args.samples, args.min_ms])
        else:
            output = command(java_command() + ["RasterBenchmark", scenario, args.samples, max(100, args.min_ms // 2)])
        new_rows = []
        for line in output.splitlines():
            fields = line.split(",")
            if fields[0] != "RESULT": continue
            if len(fields) != len(RAW_FIELDS): raise ValueError("Timing schema")
            row = dict(zip(RAW_FIELDS, [engine] + fields[1:]))
            if row["family"] != family or row["scenario"] != scenario: raise ValueError("Unexpected scenario")
            new_rows.append(row)
        validate_raw(new_rows, args.samples)
        raw.extend(new_rows)
        write_csv(args.results / "raw.csv", RAW_FIELDS, raw)
        write_csv(args.results / "operation-counts.csv", METRIC_FIELDS, metrics)
        write_csv(args.results / "queries.csv", QUERY_FIELDS, queries)
        (args.results / "commands.log").write_text("\n".join(LOG))
    validate_raw(raw, args.samples)
    expected_rows = args.samples * sum(len(names(family)) for engine, family, scenario in selected)
    if len(raw) != expected_rows: raise ValueError("Missing scenarios")
    return raw


def memory_results(destination):
    from analyze import write_csv
    rows = []
    for variant in ("original", "list", "heap"):
        output = command(kvm_command() + ["MemoryProbe", variant])
        for line in output.splitlines():
            fields = line.split(",")
            if fields[0] != "MEMORY" or fields[1] == "variant": continue
            if len(fields) != 6: raise ValueError("Memory schema")
            rows.append(dict(zip(("variant", "sample", "width", "height", "allocated_bytes"), fields[1:])))
    if len(rows) != 15: raise ValueError("Missing memory samples")
    write_csv(destination / "memory.csv", ("variant", "sample", "width", "height", "allocated_bytes"), rows)
    return rows


def metadata(args, hashes):
    import re
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "unknown")
    sources = {}
    paths = list((HERE).rglob("*.java")) + list(HERE.glob("*.py")) + list(HERE.glob("*.inc"))
    paths += list((PARENT / "src").glob("*.java")) + [PARENT / "run.py", ROOT / "src/Game.java", ROOT / "src/NPC.java",
                                                         ROOT / "common/src/Constants.java", ROOT / "common/src/Objects.java"]
    for path in paths: sources[str(path.relative_to(ROOT))] = base.sha(path.read_bytes())
    resources = {}
    for path in sorted((WORK / "verified").iterdir()):
        if path.suffix == ".png" or path.name in base.MAPS: resources[path.name] = base.sha(path.read_bytes())
    footprints = {}
    for label in ("original", "list", "heap", "tile-index", "tile-cull", "heap-tile-cull"):
        classes = list((WORK / ("game-" + label) / "verified").rglob("*.class"))
        game = WORK / ("game-" + label) / "verified/Game.class"
        data = game.read_bytes()
        if int.from_bytes(data[4:6], "big") != 3 or int.from_bytes(data[6:8], "big") != 45 or b"StackMap" not in data:
            raise ValueError("Not a CLDC 45.3/StackMap game")
        footprints[label] = dict(game_class_bytes=len(data), all_class_bytes=sum(path.stat().st_size for path in classes), game_class_sha256=base.sha(data),
                                 major_version=45, minor_version=3, stackmap=True)
    constants = (ROOT / "common/src/Constants.java").read_text()
    flags = {}
    for name in ("TILE_SIZE", "DRAW_SHADOWS", "NOKIAUI_SHADOWS", "USE_TILED_LAYER", "USE_M3G", "DRAW_LIGHTS"):
        flags[name] = re.search(r"^\s*static final (?:boolean|int) " + name + r" = ([^;]+);", constants, flags=re.M).group(1)
    return dict(recorded_utc=datetime.now(timezone.utc).isoformat(), host=platform.platform(), cpu=cpu,
                logical_cpus=os.cpu_count(), affinity=sorted(os.sched_getaffinity(0)), load_before=os.getloadavg(),
                git_head=command(["git", "rev-parse", "HEAD"]).strip(), branch=command(["git", "branch", "--show-current"]).strip(),
                baseline=base.BASELINE, dependencies=base.DEPENDENCIES, kvm_sha256=base.sha(base.kvm_binary().read_bytes()),
                kvm_version=command(kvm_command()[:-2] + ["-version"], accepted=(0, 1)),
                java_version=command([base.jdk("java"), "-version"]), kvm_heap_bytes=2 * 1024 * 1024,
                samples=args.samples, target_kvm_ms=args.min_ms, target_awt_ms=max(100, args.min_ms // 2),
                source_hashes=hashes, input_source_hashes=sources, resource_hashes=resources, footprints=footprints, flags=flags,
                limitations=["Hosted x86 timing, not a physical phone", "KVM graphics sink only clips/counts commands; no pixels or native MIDP",
                             "Desktop AWT reference is software ARGB on HotSpot, not MIDP or M3G", "NPC endpoints are synthetic reachable spawn/waypoint fixtures, not a captured play session",
                             "No whole-game CPU-share, FPS or battery profiling", "Compile-time-disabled NokiaUI/TiledLayer branches are not exercised"])


def main():
    from analyze import reanalyze, summarize
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--analyze", type=Path, help="Offline: recalculate a raw.csv into --results without building")
    parser.add_argument("--results", type=Path, default=HERE / "results")
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--min-ms", type=int, default=200)
    parser.add_argument("--filter", default="")
    args = parser.parse_args()
    protected = (PARENT / "results").resolve()
    target = args.results.resolve()
    if target == protected or protected in target.parents: raise ValueError("Historical published results are protected")
    if args.samples < 1 or args.min_ms < 20: raise ValueError("Invalid sample count/target interval")
    if args.analyze:
        reanalyze(args.analyze, args.results)
        print("Offline calculations regenerated", flush=True)
        return
    hashes = build()
    if args.build_only: return
    args.results.mkdir(parents=True, exist_ok=True)
    output = validate()
    (args.results / "validation.txt").write_text(output)
    environment = metadata(args, hashes)
    environment["memory_samples"] = memory_results(args.results)
    (args.results / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (args.results / "commands.log").write_text("\n".join(LOG))
    if args.check_only: return
    selected = [case for case in scenarios() if args.filter in "/".join(case)]
    if not selected: raise ValueError("No matching scenarios")
    rows = collect(args, selected)
    summarize(rows, args.results, args.samples)
    environment["finished_utc"] = datetime.now(timezone.utc).isoformat()
    environment["load_after"] = os.getloadavg()
    environment["scenario_count"] = len(selected)
    environment["interval_count"] = len(rows)
    (args.results / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (args.results / "commands.log").write_text("\n".join(LOG))
    print("DONE: %d scenarios, %d intervals; %s" % (len(selected), len(rows), args.results), flush=True)


if __name__ == "__main__":
    main()
