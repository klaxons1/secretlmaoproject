#!/usr/bin/env python3
"""Export and validate the stable-heap patch against the synchronized master.

No commits, branch changes, real-index writes, or production-source edits.
Historical benchmark inputs/results are not regenerated or overwritten.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import run as base

ROOT = base.ROOT
HERE = base.HERE
BASELINE = "0716b47205e297375d7a3848d923d5ce916eba6d"
HISTORICAL = base.BASELINE
WORK = base.WORK / "heap-patch"
RESULTS = HERE / "heap-patch-results"
DEFAULT_PATCH = ROOT / "patches/0003-use-stable-heap-pathfinding.patch"
BEGIN = "\t// region Pathfinding\n"
END = "\t// endregion Pathfinding"
LOG = []


def command(args, env=None):
    args = [str(arg) for arg in args]
    result = subprocess.run(args, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    output = result.stdout.decode()
    LOG.append("$ " + " ".join(args).replace(str(ROOT), "<repo>") + "\n" + output.replace(str(ROOT), "<repo>"))
    if result.returncode:
        print(output, end="", flush=True)
        raise RuntimeError("Command failed: " + args[0])
    return result.stdout


def git_source(revision):
    return subprocess.check_output(["git", "show", revision + ":src/Game.java"], cwd=ROOT).decode()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Unexpected pathfinding source shape: " + old[:100])
    return source.replace(old, new, 1)


def heap_source(source):
    """Replace only the pathfinding region; retain master's AI, lag and sort gate."""
    start, end = source.index(BEGIN), source.index(END)
    region = source[start:end]
    # Master now aliases the same array names in BOTH pathfind and openAdd.
    # Bound transformations to allocation/search, then replace queue methods.
    region = region.split("\t// sorted linked list functions\n", 1)[0]
    helper = (HERE / "experiments/HeapQueue.java.inc").read_text()
    fields, methods = helper.split("\tvoid openAdd(int n)", 1)
    methods = "\tvoid openAdd(int n)" + methods
    methods = re.sub(r"^\s*// HEAP_(?:COMPARE|PEAK)\n", "", methods, flags=re.M)
    region = once(region, "\t// linked list of open nodes\n\tshort[] openNodePrev;\n\tshort[] openNodeNext;", fields.rstrip())
    region = once(region, "\t\topenNodePrev = new short[size];\n\t\topenNodeNext = new short[size];",
                  "\t\topenHeap = new short[size];\n\t\topenHeapPosition = new short[size];\n\t\topenHeapOrder = new int[size];\n\t\topenHeapSize = openHeapSerial = 0;")
    region = once(region, "\t\t\topenNodePrev[i] = -1;\n\t\t\topenNodeNext[i] = -1;", "\t\t\topenHeapPosition[i] = -1;")
    region = once(region, "\t\tshort[] openNodePrev = this.openNodePrev;\n\t\tshort[] openNodeNext = this.openNodeNext;",
                  "\t\tshort[] openHeapPosition = this.openHeapPosition;")
    region = once(region, "\t\tint visited = 0;\n\t\tsortedNode = -1;",
                  "\t\tint visited = 0;\n\t\topenHeapSize = openHeapSerial = 0;\n\t\tsortedNode = -1;")
    region = once(region, "openNodePrev[n] == -1 && openNodeNext[n] == -1 && sortedNode != n", "openHeapPosition[n] == -1")
    region = once(region, "\t\t\topenNodePrev[n] = -1;\n\t\t\topenNodeNext[n] = -1;", "\t\t\topenHeapPosition[n] = -1;")
    region = once(region, "\n\t\treturn ret;\n\t}", "\n\t\topenHeapSize = openHeapSerial = 0;\n\t\treturn ret;\n\t}")
    return source[:start] + region + "\t// stable binary heap operations\n\n" + methods.rstrip() + "\n\n" + source[end:]


def blob_hash(source):
    data = source.encode()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def patch_text(original, candidate):
    diff = "".join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
                                        fromfile="a/src/Game.java", tofile="b/src/Game.java"))
    return ("Stable FIFO min-heap for pathfinding. Exported diff, not a new commit.\n"
            "Base-commit: " + BASELINE + "\n"
            "Changes only src/Game.java; no tile, sort-frequency, AI or lag-counter changes.\n\n"
            "diff --git a/src/Game.java b/src/Game.java\nindex " + blob_hash(original) + ".." + blob_hash(candidate) + " 100644\n" + diff)


def verify_patch(path, original, candidate):
    """Apply/check/reverse in a private index, never in the user's worktree."""
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=WORK) as directory:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(directory) / "index")
        command(["git", "read-tree", BASELINE], env)
        command(["git", "apply", "--cached", "--check", "--whitespace=error", path], env)
        command(["git", "apply", "--cached", path], env)
        actual = command(["git", "show", ":src/Game.java"], env).decode()
        if actual != candidate: raise ValueError("Applied patch differs from validated heap source")
        changed = command(["git", "diff", "--cached", "--name-only", BASELINE], env)
        if changed != b"src/Game.java\n": raise ValueError("Patch changes more than Game.java")
        command(["git", "apply", "--cached", "--reverse", "--check", path], env)
        command(["git", "apply", "--cached", "--reverse", path], env)
        if command(["git", "show", ":src/Game.java"], env).decode() != original: raise ValueError("Patch reversal failed")
    if original.split(BEGIN, 1)[0] != candidate.split(BEGIN, 1)[0] or original.split(END, 1)[1] != candidate.split(END, 1)[1]:
        raise ValueError("Code outside pathfinding was changed")


def generate_checks(master, heap):
    generated = WORK / "generated"
    if generated.exists(): shutil.rmtree(generated)
    generated.mkdir(parents=True)
    declarations = re.compile(r"^\t(?:short\[\]|byte\[\]|int) (?:nodeParent|nodeG, nodeH|openNodePrev|openNodeNext|sortedNode|visitedNodes|nodeDir, nodeX, nodeY);\n", re.M)
    for name, source, expected in (("OriginalKernel", git_source(HISTORICAL), 7),
                                   ("OptimizedKernel", master, 7), ("HeapKernel", heap, 5)):
        region = source.split(BEGIN, 1)[1].split(END, 1)[0]
        region, removed = declarations.subn("", region)
        if removed != expected: raise ValueError("Unexpected common kernel state")
        # This verifier checks queues/paths, not render sorting. Full production
        # builds retain and type-check the actual master sort unchanged.
        (generated / (name + ".java")).write_text("final class " + name + " extends Kernel {\nvoid sort(NPC[] chars) {}\n" + region + "\n}\n")
    collision = base.method(master, "static byte getTileCollision(") + "\n" + base.method(master, "static byte getObjectCollision(")
    (generated / "Collision.java").write_text("final class Collision implements Constants {\n" + collision.replace("Game.", "Collision.") + "\n}\n")
    checks = (HERE / "experiments/src/ExperimentChecks.java").read_text()
    checks = checks.split("    static TileKernel[] tileKernels(", 1)[0] + "}\n"
    checks = once(checks, "public final class ExperimentChecks", "public final class HeapPatchChecks")
    checks = once(checks, "        checkTiles();\n", "")
    checks = once(checks, '        System.out.println("CHECKS,three-way-visible-tile-traces," + tileFrames);\n', "")
    (generated / "HeapPatchChecks.java").write_text(checks)
    return generated


def preverify(raw, verified, libraries):
    if verified.exists(): shutil.rmtree(verified)
    args = [base.jdk("java"), "-jar", base.WORK / "suite/libs/proguard.jar", "-injars", raw, "-outjars", verified]
    for library in libraries: args += ["-libraryjars", library]
    command(args + ["-dontshrink", "-dontoptimize", "-dontobfuscate", "-microedition", "-target", "1.1"])


def verify_base_ancestry():
    """Artifact-only publication commits may follow the pinned master."""
    result = subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError("Pinned master must be an ancestor of HEAD; production-source guards still apply")


def build_and_check(path, original, candidate):
    base.bootstrap()
    verify_base_ancestry()
    if (ROOT / "src/Game.java").read_text() not in (original, candidate): raise ValueError("Unexpected local Game.java edits")
    other_changes = command(["git", "diff", "--name-only", BASELINE, "--", "src", "common"]).decode().splitlines()
    if any(name != "src/Game.java" for name in other_changes): raise ValueError("Other production files differ from the patch base")
    generated = generate_checks(original, candidate)
    raw, verified = WORK / "raw", WORK / "verified"
    if raw.exists(): shutil.rmtree(raw)
    raw.mkdir()
    api = base.WORK / "cldc/j2me_cldc/bin/common/api/classes"
    sources = [HERE / "src/Kernel.java", HERE / "src/Fixtures.java", HERE / "experiments/src/MapData.java",
               HERE / "experiments/src/TileKernel.java", ROOT / "common/src/Constants.java", ROOT / "common/src/Objects.java"]
    command([base.jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", api, "-d", raw] + sources + sorted(generated.glob("*.java")))
    preverify(raw, verified, [api])
    resources = list(base.MAPS) + [p.name for p in (ROOT / "res").glob("tiles_*.png")]
    resources += [p.name for p in (ROOT / "res").glob("ground_*.png")] + ["shadow.png"]
    for name in resources: shutil.copyfile(ROOT / "res" / name, verified / name)
    libraries = [base.WORK / "suite/uei" / name for name in ("cldc11.jar", "midp21.jar", "jsr135.jar", "jsr184.jar", "nokiaui.jar")]
    production = sorted((ROOT / "src").glob("*.java")) + sorted((ROOT / "common/src").glob("*.java"))
    footprints = {}
    for label, source in (("master", original), ("heap", candidate)):
        directory = WORK / ("game-" + label)
        (directory / "source").mkdir(parents=True, exist_ok=True)
        (directory / "source/Game.java").write_text(source)
        out = directory / "raw"
        if out.exists(): shutil.rmtree(out)
        out.mkdir()
        files = [p for p in production if p.name != "Game.java"] + [directory / "source/Game.java"]
        command([base.jdk("javac"), "-source", "1.3", "-target", "1.3", "-Xlint:-options", "-bootclasspath", libraries[0],
                 "-classpath", os.pathsep.join(str(p) for p in libraries[1:]), "-d", out] + files)
        preverify(out, directory / "verified", libraries)
        data = (directory / "verified/Game.class").read_bytes()
        if data[4:8] != b"\x00\x03\x00\x2d" or b"StackMap" not in data: raise ValueError("Not CLDC-preverified bytecode")
        footprints[label] = {"game_class_bytes":len(data), "game_class_sha256":base.sha(data)}
    outputs = []
    for engine, java in (("desktop Java", [base.jdk("java"), "-Xmx256m", "-cp", verified]),
                         ("original KVM 1.1", base.kvm_command()[:-1] + [verified])):
        print("Check", engine, flush=True)
        output = command(java + ["HeapPatchChecks"]).decode()
        if "CHECKS,PASS" not in output: raise ValueError("Missing correctness sentinel")
        print(output, end="", flush=True)
        outputs.append(engine + "\n" + output)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "validation.txt").write_text("\n".join(outputs))
    inputs = [Path(__file__), path, HERE / "experiments/HeapQueue.java.inc", HERE / "src/Kernel.java", HERE / "src/Fixtures.java",
              HERE / "experiments/src/ExperimentChecks.java", HERE / "experiments/src/MapData.java", HERE / "experiments/src/TileKernel.java"]
    metadata = {"base_commit":BASELINE, "comparison":"historical original / synchronized master / patched master",
                "base_game_sha256":base.sha(original.encode()), "patched_game_sha256":base.sha(candidate.encode()),
                "kvm_sha256":base.sha(base.kvm_binary().read_bytes()), "footprints":footprints,
                "input_sha256":{str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in inputs},
                "new_timing_run":False, "pspkvm_tested_here":False,
                "note":"Functional checks/builds only. No PSPKVM speedup is claimed for this patch."}
    (RESULTS / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (RESULTS / "commands.log").write_text("\n".join(LOG))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_PATCH)
    parser.add_argument("--check", action="store_true", help="Also build both complete games and run exact queue/path comparisons on Java and original KVM")
    args = parser.parse_args()
    original = git_source(BASELINE)
    candidate = heap_source(original)
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(patch_text(original, candidate))
    verify_patch(args.output, original, candidate)
    print("Exported and apply/reverse checked:", args.output.relative_to(ROOT), flush=True)
    if args.check: build_and_check(args.output, original, candidate)


if __name__ == "__main__":
    main()
