#!/usr/bin/env python3
"""Build, check and benchmark source-extracted game kernels on unmodified KVM 1.1.

Requires Linux x86-64 with IA32 execution support, Python 3, git, and network
access to GitHub. All downloaded/generated binaries stay in ignored .work/.
"""
import argparse
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import tarfile
import urllib.request
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = HERE / ".work"
BASELINE = "785ef001798fad8e4e9f2e21426e4c6d65875d33"
DEPENDENCIES = {
    "cldc": ("klaxons1/j2me_cldc-1_1-fcs-src-winunix", "d924b6425fae9fb39387882ab6a86ae555cdcc90",
             "3b6ef960509c6e18718ae7ad11fea692059a8bc5f38c9b4238baae16f912849f"),
    "suite": ("klaxons1/LLM-J2ME-SUITE", "c4799767bf43c9a94d327f6394ef51445a2be807",
              "a61bc432db22fa456638bfc72b88b2a7e81075a393f91ac733f59c0ed62fa7de"),
    "jdk8": ("klaxons1/tools_linux_jdk8", "7be76e541810614e3627d42c68759fab16055b7b",
             "e197de355b091aab8b98b2e5da44f8c5371da8791a1b72e510958758b370044c"),
}
# Debian Wheezy i386 glibc 2.13 from a pinned Chromium sysroot. This lets
# the *original* dynamically linked KVM binary run without root/apt or VM patches.
GLIBC_REPO = "hanpfei/chromium-net"
GLIBC_COMMIT = "9df8ce98c2a14fb60c2f581853011e32eb4bed0f"
GLIBC_FILES = {
    "ld-2.13.so": ("31f9e5a1bcbe8bcaa04179fe99826d1908d93ed3", "898bd2ff11e1ba7fcc4eb672b23619b716dee96d95eeff03389dc21d3c6b6d73"),
    "libc-2.13.so": ("d81509e90df383f40e62a7459e2863e088d87c3d", "412d26f0e732e2f5ca81e6635e0ff13bb2d13e1d3bb3180941b7dc7f43c86829"),
    "libm-2.13.so": ("5a5fc9b07f25b6091bee3eb345f6c65cd1889b63", "f0359740af4d2091634354783c25c222cdd7ce33f75b88539c5928f5a769c155"),
    "libnsl-2.13.so": ("a1fc6f56ae1ca1ad47490bbc44f16f771bad054f", "33512249dfd0d7b0abc34a81088b6f6b52040fc8a6f7b410f932af2795e9599e"),
}
KVM_SHA256 = "917b17f278023670b9a5472d7740d12a5c7b1c6e3718196f828d4bed5de82e66"
MAPS = ("perks", "stalagflucht", "shanktonstatepen", "jungle", "sanpancho", "irongate")
LOG = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_hash(path, expected):
    actual = sha(path.read_bytes())
    if actual != expected:
        raise RuntimeError("SHA-256 mismatch for %s: %s != %s" % (path, actual, expected))


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "J2ME-KVM-benchmark", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def bootstrap():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise RuntimeError("The pinned original KVM/toolchain requires Linux x86-64 with IA32 support")
    WORK.mkdir(parents=True, exist_ok=True)
    for name, (repo, commit, expected) in DEPENDENCIES.items():
        archive = WORK / (name + ".tar.gz")
        if not archive.exists():
            print("Downloading", repo, commit, flush=True)
            archive.write_bytes(download("https://codeload.github.com/%s/tar.gz/%s" % (repo, commit)))
        check_hash(archive, expected)
        destination = WORK / name
        if not destination.exists():
            with tarfile.open(archive) as source:
                # Strip the single archive prefix; disallow escaping the cache.
                prefix = source.getmembers()[0].name.split("/")[0]
                for member in source.getmembers():
                    if member.name != prefix and not member.name.startswith(prefix + "/"):
                        raise RuntimeError("Unexpected archive prefix")
                    parts = Path(member.name).parts
                    if ".." in parts or Path(member.name).is_absolute():
                        raise RuntimeError("Unsafe archive member")
                source.extractall(WORK)
            (WORK / prefix).rename(destination)
    for directory in (WORK / "jdk8/bin", WORK / "jdk8/jre/bin"):
        for path in directory.iterdir():
            path.chmod(path.stat().st_mode | 0o111)
    runtime = WORK / "glibc32"
    runtime.mkdir(exist_ok=True)
    for name, (blob, expected) in GLIBC_FILES.items():
        path = runtime / name
        if not path.exists():
            print("Downloading pinned i386 runtime", name, flush=True)
            payload = json.loads(download("https://api.github.com/repos/%s/git/blobs/%s" % (GLIBC_REPO, blob)))
            path.write_bytes(base64.b64decode(payload["content"]))
        check_hash(path, expected)
        path.chmod(path.stat().st_mode | 0o111)
    for alias, target in (("libc.so.6", "libc-2.13.so"), ("libm.so.6", "libm-2.13.so"), ("libnsl.so.1", "libnsl-2.13.so")):
        path = runtime / alias
        if not path.is_symlink():
            path.symlink_to(target)
    check_hash(kvm_binary(), KVM_SHA256)


def jdk(tool):
    return str(WORK / "jdk8/bin" / tool)


def kvm_binary():
    return WORK / "cldc/j2me_cldc/bin/linux/kvm"


def kvm_command():
    return [str(WORK / "glibc32/ld-2.13.so"), "--library-path", str(WORK / "glibc32"), str(kvm_binary()),
            "-heapsize", "2M", "-classpath", str(WORK / "verified")]


def command(args, accepted_codes=(0,)):
    args = [str(arg) for arg in args]
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    LOG.append("$ " + " ".join(arg.replace(str(ROOT), "<repo>") for arg in args) + "\n" + result.stdout.replace(str(ROOT), "<repo>"))
    if result.returncode not in accepted_codes:
        print(result.stdout, flush=True)
        raise RuntimeError("Command failed (%d): %s" % (result.returncode, args[0]))
    return result.stdout


def original_source():
    return subprocess.check_output(["git", "show", BASELINE + ":src/Game.java"], cwd=ROOT, text=True)


# Mask comments and literals before brace matching, while preserving offsets.
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)


def block(source, start):
    masked = TOKEN.sub(lambda match: " " * len(match.group()), source)
    opening = masked.index("{", start)
    depth = 0
    for end in range(opening, len(masked)):
        if masked[end] == "{":
            depth += 1
        elif masked[end] == "}":
            depth -= 1
            if depth == 0:
                return source[start:end + 1]
    raise RuntimeError("Unbalanced source block")


def method(source, signature):
    return block(source, source.index(signature))


def generate_sources():
    baseline = original_source()
    current = (ROOT / "src/Game.java").read_text()
    generated = WORK / "generated"
    if generated.exists():
        shutil.rmtree(generated)
    generated.mkdir()
    hashes = {}
    # Extract the old sorting block verbatim, replacing only its enclosing
    # tick guard/array binding with the same callable signature as the new body.
    start = baseline.index("if ((tick & 3) == 0)", baseline.index("// sort characters for rendering"))
    old_sort = block(baseline, start)
    old_sort = old_sort[old_sort.index("{") + 1:old_sort.rindex("}")]
    old_sort = old_sort.replace("NPC[] sortedChars = this.renderChars;", "int n = sortedChars.length;")
    old_sort = "void sort(NPC[] sortedChars) {" + old_sort + "\n}"
    new_sort = method(current, "static void sortRenderChars(")
    new_sort = new_sort.replace("static void sortRenderChars(", "void sort(", 1)
    declarations = re.compile(r"^\t(?:short\[\]|byte\[\]|int) (?:nodeParent|nodeG, nodeH|openNodePrev|openNodeNext|sortedNode|visitedNodes|nodeDir, nodeX, nodeY);\n", re.M)
    for name, source, sort in (("OriginalKernel", baseline, old_sort), ("OptimizedKernel", current, new_sort)):
        region = source.split("// region Pathfinding\n", 1)[1].split("// endregion Pathfinding", 1)[0]
        region, removed = declarations.subn("", region)
        if removed != 7:
            raise RuntimeError("Unexpected pathfinding fields: %d (update extraction explicitly)" % removed)
        text = "// Generated from production sources; do not edit.\nfinal class %s extends Kernel {\n%s\n%s\n}\n" % (name, sort, region)
        (generated / (name + ".java")).write_text(text)
        hashes[name] = sha(text.encode())
        # A separate, untimed copy counts work to explain the bottleneck.
        counted = text.replace(name + " extends Kernel", "Counted" + name + " extends CountedKernel")
        counted = counted.replace("void openAdd(int n) {", "void openAdd(int n) { ++queueAdds;", 1)
        counted = counted.replace("void openRemove(int n) {", "void openRemove(int n) { ++queueRemoves;", 1)
        counted = counted.replace("while (cur != -1) {", "while (cur != -1) { ++expandedNodes;", 1)
        if name == "OriginalKernel":
            counted = counted.replace("for (int j = 0; j < n - i - 1; ++j) {",
                                      "for (int j = 0; j < n - i - 1; ++j) { ++sortAdjacentTests;", 1)
            counted = counted.replace("&& ((sortedChars[j].y", "&& countSortComparison() && ((sortedChars[j].y", 1)
            counted = counted.replace("int f2 = nodeG[i] + nodeH[i];", "++queueScanSteps; int f2 = nodeG[i] + nodeH[i];", 1)
        else:
            counted = counted.replace("while (j > 0) {", "while (j > 0) { ++sortAdjacentTests;", 1)
            counted = counted.replace("int prevY =", "++sortKeyComparisons; int prevY =", 1)
            counted = counted.replace("f >= nodeG[i] + nodeH[i]", "scan(f, nodeG[i] + nodeH[i])", 1)
        (generated / ("Counted" + name + ".java")).write_text(counted)
        hashes["Counted" + name] = sha(counted.encode())
    collision = method(current, "static byte getTileCollision(") + "\n" + method(current, "static byte getObjectCollision(")
    collision = "final class Collision implements Constants {\n" + collision.replace("Game.", "Collision.") + "\n}\n"
    (generated / "Collision.java").write_text(collision)
    hashes["Collision"] = sha(collision.encode())
    hashes["baseline_Game.java"] = sha(baseline.encode())
    hashes["current_Game.java"] = sha(current.encode())
    # Check the fixture's animation constants against production, not memory.
    npc = (ROOT / "src/NPC.java").read_text()
    for name, expected in (("ANIM_REGULAR", 0), ("ANIM_STUNNED", 3), ("ANIM_LYING", 5)):
        if not re.search(r"static final int " + name + r" = " + str(expected) + r";", npc):
            raise RuntimeError("Fixture animation constant has drifted: " + name)
    return hashes


def preverify(source, destination, libraries):
    if destination.exists():
        shutil.rmtree(destination)
    args = [jdk("java"), "-jar", WORK / "suite/libs/proguard.jar", "-injars", source, "-outjars", destination]
    for library in libraries:
        args += ["-libraryjars", library]
    args += ["-dontshrink", "-dontoptimize", "-dontobfuscate", "-microedition", "-target", "1.1"]
    command(args)


def build():
    hashes = generate_sources()
    raw = WORK / "raw"
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir()
    api = WORK / "cldc/j2me_cldc/bin/common/api/classes"
    sources = sorted((HERE / "src").glob("*.java")) + sorted((WORK / "generated").glob("*.java"))
    sources += [ROOT / "common/src/Constants.java", ROOT / "common/src/Objects.java"]
    command([jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", api, "-d", raw] + sources)
    preverify(raw, WORK / "verified", [api])
    for name in MAPS:
        shutil.copyfile(ROOT / "res" / name, WORK / "verified" / name)
    # Also compile and CLDC-preverify every production source against the
    # supplied Java ME APIs. This is a build/verifier check, not a phone run.
    libs = [WORK / "suite/uei" / name for name in ("cldc11.jar", "midp21.jar", "jsr135.jar", "jsr184.jar", "nokiaui.jar")]
    production = sorted((ROOT / "src").glob("*.java")) + sorted((ROOT / "common/src").glob("*.java"))
    for label, game_source in (("original", original_source()), ("optimized", (ROOT / "src/Game.java").read_text())):
        directory = WORK / ("game-" + label)
        if directory.exists():
            shutil.rmtree(directory)
        (directory / "source").mkdir(parents=True)
        (directory / "raw").mkdir()
        game = directory / "source/Game.java"
        game.write_text(game_source)
        files = [file for file in production if file.name != "Game.java"] + [game]
        command([jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", libs[0],
                 "-classpath", os.pathsep.join(str(lib) for lib in libs[1:]), "-d", directory / "raw"] + files)
        preverify(directory / "raw", directory / "verified", libs)
    print("Built/preverified original + optimized production and headless kernels", flush=True)
    return hashes


def validate():
    outputs = []
    for name, args in (("HotSpot correctness only", [jdk("java"), "-cp", WORK / "verified", "Checks"]),
                       ("Original KVM 1.1 correctness", kvm_command() + ["Checks"])):
        print("Checking:", name, flush=True)
        output = command(args)
        if "CHECKS,PASS" not in output:
            raise RuntimeError("Missing successful correctness sentinel: " + name)
        outputs.append(name + "\n" + output)
        print(output, end="", flush=True)
    return "\n".join(outputs)


def environment(args, hashes):
    cpu = "unknown"
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "baseline_commit": BASELINE,
        "branch": command(["git", "branch", "--show-current"]).strip(), "host": platform.platform(), "cpu": cpu,
        "python": platform.python_version(), "jdk_version": command([jdk("java"), "-version"]).strip(),
        "proguard_jar_sha256": sha((WORK / "suite/libs/proguard.jar").read_bytes()),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        # This historical CLI returns status 1 even for a successful -version.
        "kvm_version": command(kvm_command()[:4] + ["-version"], accepted_codes=(0, 1)).strip(), "kvm_sha256": KVM_SHA256,
        "kvm_modified": False, "kvm_heap_bytes": 2 * 1024 * 1024, "timer": "System.currentTimeMillis (integer milliseconds)",
        "samples": args.samples, "min_sample_ms": args.min_ms, "independent_variant_calibration": True,
        "warmup_batches": 2, "dependencies": {k: {"repository": v[0], "commit": v[1], "archive_sha256": v[2]} for k, v in DEPENDENCIES.items()},
        "glibc": {"repository": GLIBC_REPO, "commit": GLIBC_COMMIT, "files": GLIBC_FILES}, "sources_sha256": hashes,
        "map_sha256": {name: sha((ROOT / "res" / name).read_bytes()) for name in MAPS},
        "class_bytes": {label: {"Game.class": (WORK / ("game-" + label) / "verified/Game.class").stat().st_size,
                                "all_classes": sum(file.stat().st_size for file in (WORK / ("game-" + label) / "verified").glob("*.class"))}
                        for label in ("original", "optimized")},
    }
    for path in (Path("/sys/fs/cgroup/cpu.max"), Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")):
        if path.exists():
            result["cgroup_" + path.name] = path.read_text().strip()
    for directory in (HERE / "src", ROOT / "src", ROOT / "common/src"):
        for file in sorted(directory.glob("*.java")):
            result["sources_sha256"][str(file.relative_to(ROOT))] = sha(file.read_bytes())
    result["sources_sha256"]["benchmarks/kvm/run.py"] = sha(Path(__file__).read_bytes())
    return result


def scenarios():
    result = []
    for name in ("perks", "irongate", "shanktonstatepen"):
        for layout in ("spawn", "sorted", "near", "reverse"):
            result.append(("sort", name + ":" + layout))
    result += [("queue", "head:16"), ("queue", "ties:64"), ("queue", "mixed:256")]
    result += [("path", name) for name in MAPS]
    return result


def collect_metrics(destination, selected):
    fields = ["family", "scenario", "variant", "operations", "sort_adjacent_tests", "sort_key_comparisons",
              "queue_add_calls", "queue_scan_steps", "queue_remove_calls", "expanded_nodes", "checksum"]
    with (destination / "operation-counts.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(fields)
        for family, scenario in selected:
            output = command(kvm_command() + ["Profile", family, scenario])
            rows = [line.split(",")[1:] for line in output.splitlines() if line.startswith("METRIC,")]
            if len(rows) != 2 or any(len(row) != len(fields) for row in rows):
                raise RuntimeError("Missing operation counts: " + scenario)
            writer.writerows(rows)
    print("Collected separate, untimed operation counts", flush=True)


def summarize(rows, destination):
    if not rows:
        raise ValueError("No samples to analyze")
    groups = {}
    for row in rows:
        if row["family"] not in ("sort", "queue", "path") or row["variant"] not in ("original", "optimized"):
            raise ValueError("Unknown benchmark family/variant")
        for field in ("iterations", "operations", "elapsed_ms"):
            if int(row[field]) <= 0:
                raise ValueError("Nonpositive " + field)
        units = 8 if row["family"] == "path" else 1
        if int(row["operations"]) != units * int(row["iterations"]):
            raise ValueError("Incorrect operation normalization")
        sample = int(row["sample"])
        if sample < 0 or int(row["order"]) not in (0, 1):
            raise ValueError("Invalid sample/order")
        key = (row["family"], row["scenario"])
        variants = groups.setdefault(key, {}).setdefault(sample, {})
        if row["variant"] in variants:
            raise ValueError("Duplicate variant in sample pair")
        variants[row["variant"]] = row
    summaries = []
    for (family, scenario), samples in groups.items():
        pairs, baseline_us, optimized_us = [], [], []
        if sorted(samples) != list(range(len(samples))):
            raise ValueError("Noncontiguous sample indices")
        for sample, variants in sorted(samples.items()):
            if set(variants) != {"original", "optimized"}:
                raise ValueError("Incomplete sample pair")
            a, b = variants["original"], variants["optimized"]
            if int(a["order"]) != (sample & 1) or int(b["order"]) != 1 - (sample & 1):
                raise ValueError("Incorrect AB/BA order")
            if a["checksum"] != b["checksum"]:
                raise RuntimeError("Benchmark checksum mismatch: %s %s %d" % (family, scenario, sample))
            x = 1000 * int(a["elapsed_ms"]) / int(a["operations"])
            y = 1000 * int(b["elapsed_ms"]) / int(b["operations"])
            if x <= 0 or y <= 0:
                raise RuntimeError("Zero-duration sample; increase --min-ms")
            baseline_us.append(x)
            optimized_us.append(y)
            pairs.append(x / y)
        median_ratio = statistics.median(pairs)
        entry = {"family": family, "scenario": scenario, "pairs": len(pairs),
                 "original_median_us": statistics.median(baseline_us), "optimized_median_us": statistics.median(optimized_us),
                 "median_paired_speedup": median_ratio, "median_paired_time_reduction_pct": 100 * (1 - 1 / median_ratio),
                 "min_paired_speedup": min(pairs), "max_paired_speedup": max(pairs),
                 "original_min_ms": min(int(v["original"]["elapsed_ms"]) for v in samples.values()),
                 "optimized_min_ms": min(int(v["optimized"]["elapsed_ms"]) for v in samples.values())}
        summaries.append(entry)
    with (destination / "summary.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    lines = ["# Calculations from raw.csv", "", "Generated by `python3 benchmarks/kvm/run.py --analyze <results-dir>`.", "",
             "Each row is one timed interval *inside the original, unchanged KVM*. Warm-up, calibration, class loading, fixture allocation, and console output are not samples.", "",
             "For every variant/sample: `microseconds/operation = elapsed_ms × 1000 / operations`.",
             "For every matched pair: `speedup = original_us / optimized_us`; `time reduction = 100 × (1 − 1/speedup)`.",
             "Reported speedup is the **median of paired ratios**, not the ratio of medians. Range is min–max, not a confidence interval.", "",
             "| Family | Scenario | Original µs/op (median) | Optimized µs/op (median) | Paired speedup (median) | Time reduction | Speedup range |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in summaries:
        lines.append("| {family} | {scenario} | {original_median_us:.3f} | {optimized_median_us:.3f} | {median_paired_speedup:.2f}× | {median_paired_time_reduction_pct:.2f}% | {min_paired_speedup:.2f}–{max_paired_speedup:.2f}× |".format(**row))
    first = rows[0]
    lines += ["", "## Worked example", "", "First raw row: `%s / %s / %s / sample %s`: `%s × 1000 / %s = %.6f µs/op`." %
              (first["family"], first["scenario"], first["variant"], first["sample"], first["elapsed_ms"], first["operations"],
               int(first["elapsed_ms"]) * 1000 / int(first["operations"])), "",
              "Operations: one reset-and-sort for `sort`; one complete enqueue/drain of N nodes for `queue`; one path query for `path` (8 queries/batch).",
              "Sort timing includes a common `System.arraycopy` reset. Queue timing includes common initialization of its head and recording pop order. Path timing includes the full search, traceback, workspace cleanup, and a common result hash.", "",
              "Variant iteration counts are calibrated independently for timer precision, but each executes the same deterministic unit workload. Per-operation normalization accounts for unequal counts. Checksums are iteration-count-independent final-workload hashes.", "",
              "No device FPS, whole-game profile, or absolute handset latency is inferred from these headless host measurements.", ""]
    (destination / "calculations.md").write_text("\n".join(lines))
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "results")
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--min-ms", type=int, default=250)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--filter", default="", help="substring of family/scenario")
    parser.add_argument("--analyze", type=Path, help="recompute calculations without downloading/building/running")
    args = parser.parse_args()
    if args.analyze:
        with (args.analyze / "raw.csv").open(newline="") as data:
            summarize(list(csv.DictReader(data)), args.analyze)
        return
    if args.samples < 3 or args.min_ms < 20:
        parser.error("Use at least 3 sample pairs and 20 ms per interval")
    bootstrap()
    hashes = build()
    validation = validate()
    destination = args.results.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "validation.txt").write_text(validation)
    (destination / "environment.json").write_text(json.dumps(environment(args, hashes), indent=2) + "\n")
    if args.check_only:
        (destination / "commands.log").write_text("\n".join(LOG))
        return
    selected = [(family, scenario) for family, scenario in scenarios() if not args.filter or args.filter in family + "/" + scenario]
    if not selected:
        parser.error("--filter matched no benchmark scenarios")
    collect_metrics(destination, selected)
    fields = ["family", "scenario", "variant", "sample", "order", "iterations", "operations", "elapsed_ms", "checksum"]
    rows = []
    with (destination / "raw.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for family, scenario in selected:
            print("Benchmark:", family, scenario, flush=True)
            output = command(kvm_command() + ["Benchmark", family, scenario, str(args.samples), str(args.min_ms)])
            print(output, end="", flush=True)
            lines = [line.split(",")[1:] for line in output.splitlines() if line.startswith("RESULT,")]
            if len(lines) != 2 * args.samples or any(len(line) != len(fields) for line in lines):
                raise RuntimeError("Missing/malformed samples: " + scenario)
            for line in lines:
                row = dict(zip(fields, line))
                if row["family"] != family or row["scenario"] != scenario:
                    raise RuntimeError("Unexpected benchmark identity")
                rows.append(row)
                writer.writerow(row)
            out.flush()
    if not rows:
        raise RuntimeError("No benchmark rows collected")
    (destination / "commands.log").write_text("\n".join(LOG))
    summarize(rows, destination)
    print("Results:", destination, flush=True)


if __name__ == "__main__":
    main()
