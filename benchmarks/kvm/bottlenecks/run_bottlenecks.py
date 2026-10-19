#!/usr/bin/env python3
"""Export, differentially verify, build and benchmark the post-heap patch series.

All production sources stay untouched. Original KVM 1.1; pinned tools from ../run.py.
New raw data goes to a separate directory; no historical result is overwritten.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

import candidates as c
base = c.base
ROOT, HERE = c.ROOT, c.HERE
WORK = base.WORK / "bottlenecks"
RESULTS = HERE / "results"
LOG = []

PATH_NAMES = ("heap", "heuristic", "diagonal", "stepcost", "decrease", "core")
NAMES = {
    "path": PATH_NAMES,
    "objects": ("heap", "objects", "core"),
    "zones": ("heap", "zones", "core"),
    "npc-zones": ("heap", "memo", "core"),
    "seats": ("heap", "seats", "core"),
    "vision": ("heap", "vision", "core"),
    "facing": ("heap", "facing", "core"),
    "tiles": ("heap", "tile-index", "tile-cull", "all"),
}
RAW_FIELDS = ("engine", "family", "scenario", "variant", "sample", "order", "iterations", "operations", "elapsed_ms", "checksum")
SUMMARY_FIELDS = ("family", "scenario", "reference", "candidate", "samples", "reference_us_median", "candidate_us_median", "speedup_median", "time_reduction_percent", "speedup_min", "speedup_max")


def command(args, accepted=(0,)):
    args = [str(a) for a in args]
    proc = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=1800)
    LOG.append("$ " + " ".join(args).replace(str(ROOT), "<repo>") + "\n" + proc.stdout.replace(str(ROOT), "<repo>"))
    if proc.returncode not in accepted:
        print(proc.stdout, end="", flush=True)
        raise RuntimeError("Command failed: " + args[0])
    return proc.stdout


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def cname(name): return name.replace("-", "_")


def order_for(sample, size):
    # Forward Latin rotations, then reversed Latin rotations. With 2*n samples
    # every candidate occupies every slot twice and every orientation is used.
    rotation = sample % size
    order = [(i + rotation) % size for i in range(size)]
    return order if sample % (size * 2) < size else list(reversed(order))


def validate(rows, samples=None):
    if not rows: raise ValueError("Empty timing data")
    groups = {}
    for row in rows:
        if set(row) != set(RAW_FIELDS): raise ValueError("Raw schema")
        if row["engine"] != "original-kvm-1.1" or row["family"] not in NAMES: raise ValueError("Engine/family")
        names = NAMES[row["family"]]
        if row["variant"] not in names or not row["scenario"]: raise ValueError("Variant/scenario")
        r = dict(row)
        for field in RAW_FIELDS[4:]: r[field] = int(r[field])
        if min(r["iterations"], r["operations"], r["elapsed_ms"]) <= 0 or r["operations"] % r["iterations"]: raise ValueError("Work/time")
        if r["sample"] < 0 or r["order"] < 0: raise ValueError("Negative trial/position")
        key = r["family"], r["scenario"]
        groups.setdefault(key, []).append(r)
    for (family, scenario), group in groups.items():
        names = NAMES[family]
        count = samples if samples is not None else max(r["sample"] for r in group) + 1
        if len(group) != count * len(names): raise ValueError("Missing or duplicated intervals")
        if len({(r["sample"], r["variant"]) for r in group}) != len(group): raise ValueError("Duplicate interval")
        if len({r["checksum"] for r in group}) != 1: raise ValueError("Checksum mismatch")
        if len({r["operations"] // r["iterations"] for r in group}) != 1: raise ValueError("Units mismatch")
        for sample in range(count):
            trial = sorted([r for r in group if r["sample"] == sample], key=lambda r:r["order"])
            if [r["order"] for r in trial] != list(range(len(names))): raise ValueError("Bad positions")
            if [r["variant"] for r in trial] != [names[i] for i in order_for(sample, len(names))]: raise ValueError("Bad rotation")
    return groups


def analyze(rows, destination, samples=None):
    groups = validate(rows, samples)
    destination.mkdir(parents=True, exist_ok=True)
    summary, paired, lines = [], [], ["# Paired original-KVM calculations", "", "us/op = elapsed_ms * 1000 / operations.", "Speedup = reference_us / candidate_us within the SAME sample.", "Reported speedup is median(paired ratios), NOT ratio(medians).", "Time reduction = 100 * (1 - 1 / speedup). Min/max are observed, not confidence intervals.", ""]
    for (family, scenario), group in sorted(groups.items()):
        by = {(r["variant"], r["sample"]):r for r in group}
        samples_here = len(group) // len(NAMES[family])
        def us(r): return r["elapsed_ms"] * 1000.0 / r["operations"]
        for name in NAMES[family][1:]:
            ref = [us(by[("heap", i)]) for i in range(samples_here)]
            cand = [us(by[(name, i)]) for i in range(samples_here)]
            ratios = [a/b for a,b in zip(ref, cand)]
            median = statistics.median(ratios)
            summary.append(dict(family=family, scenario=scenario, reference="heap", candidate=name, samples=samples_here,
                reference_us_median=statistics.median(ref), candidate_us_median=statistics.median(cand), speedup_median=median,
                time_reduction_percent=100*(1-1/median), speedup_min=min(ratios), speedup_max=max(ratios)))
            lines += ["## " + family + " " + scenario + " heap -> " + name, ""]
            for i, (a,b,ratio) in enumerate(zip(ref,cand,ratios)):
                paired.append(dict(family=family, scenario=scenario, candidate=name, sample=i, reference_us=a, candidate_us=b, speedup=ratio))
                lines.append("sample %d: %.9f / %.9f = %.9f" % (i,a,b,ratio))
            lines += ["median = %.9f; reduction = %.9f%%" % (median,100*(1-1/median)), ""]
    write_csv(destination/"summary.csv", SUMMARY_FIELDS, summary)
    write_csv(destination/"paired.csv", ("family","scenario","candidate","sample","reference_us","candidate_us","speedup"), paired)
    (destination/"calculations.md").write_text("\n".join(lines)+"\n")
    return summary


def verify_series(files):
    with tempfile.TemporaryDirectory(dir=WORK) as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory)/"index"))
        def git(*args):
            proc = subprocess.run(["git",*map(str,args)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return proc.stdout
        git("read-tree", c.MASTER)
        git("apply", "--cached", ROOT/"patches/0003-use-stable-heap-pathfinding.patch")
        for filename in files:
            git("apply", "--cached", "--check", "--whitespace=error", c.PATCHES/filename)
            git("apply", "--cached", c.PATCHES/filename)
        states = c.variants()
        for path in c.FILES:
            if git("show", ":"+path).decode() != states["all"][path]: raise ValueError("Series differs from prototype")
        for filename in reversed(files): git("apply", "--cached", "--reverse", c.PATCHES/filename)
        for path in c.FILES:
            if git("show", ":"+path).decode() != states["heap"][path]: raise ValueError("Series reversal")
        for filename, name in [(number+"-"+label+".patch",name) for number,label,name,fn in c.SPECS]:
            git("read-tree", c.MASTER);git("apply", "--cached", ROOT/"patches/0003-use-stable-heap-pathfinding.patch")
            git("apply", "--cached", "--check", "--whitespace=error", c.PATCHES/"standalone"/filename)
            git("apply", "--cached", c.PATCHES/"standalone"/filename)
            for path in c.FILES:
                if git("show", ":"+path).decode() != states[name][path]: raise ValueError("Standalone differs: "+name)
            git("apply", "--cached", "--reverse", c.PATCHES/"standalone"/filename)
        for filename, before in (("all-after-heap.patch", True), ("all-from-master.patch", False)):
            git("read-tree", c.MASTER)
            if before: git("apply", "--cached", ROOT/"patches/0003-use-stable-heap-pathfinding.patch")
            git("apply", "--cached", c.PATCHES/filename)
            for path in c.FILES:
                if git("show", ":"+path).decode() != states["all"][path]: raise ValueError("Combined differs")
        # Diagnostic applies both to the heap baseline and after the complete series.
        diagnostic = c.PATCHES/"0017-npc-lag-breakdown.patch"
        git("apply", "--cached", "--check", diagnostic)
        git("apply", "--cached", diagnostic)
        expected=dict(states["all"]);c.diagnostic(expected)
        for path in c.FILES:
            if git("show", ":"+path).decode() != expected[path]: raise ValueError("Diagnostic composition")
    print("All cumulative/standalone/combined patches apply and reverse in private indexes", flush=True)


def generate(states):
    generated = WORK/"generated"
    if generated.exists(): shutil.rmtree(generated)
    generated.mkdir(parents=True)
    names = [name for name in states if name != "diagnostic"]
    for name in names:
        game, npc = states[name][c.FILES[0]], states[name][c.FILES[1]]
        region = game.split("\t// region Pathfinding\n",1)[1].split("\t// endregion Pathfinding",1)[0]
        # All mutable path fields live in common headless state. Static tables
        # and complete production method bodies remain in each derived class.
        region = re.sub(r"^\t(?:private )?(?:short|byte|int)(?:\[\])? [\w, ]+;\n", "", region, flags=re.M)
        helpers = "\n".join(base.method(game, sig) for sig in ("int getObjectIdxAt(","int findObject(","int getSeatIndex(","boolean isInZone(int x,", "int findZone("))
        if "void ensureZoneIndex(" in game: helpers += "\n" + base.method(game,"void ensureZoneIndex(")
        text = "final class K_"+cname(name)+" extends PerfGame {\n"+region+"\n"+helpers+"\n}\n"
        (generated/("K_"+cname(name)+".java")).write_text(text)
        if name in PATH_NAMES:
            counted=text.replace("class K_"+cname(name),"class Counted_"+cname(name),1)
            counted=counted.replace("while (cur != -1) {", "while (cur != -1) { ++expanded;",1)
            counted=counted.replace("h = dx > dy ?", "++heuristics; h = dx > dy ?",1)
            counted=counted.replace("void openAdd(int n) {", "void openAdd(int n) { ++adds;",1)
            counted=counted.replace("void openRemove(int n) {", "void openRemove(int n) { ++removes;",1)
            counted=counted.replace("void openImprove(int n) {", "void openImprove(int n) { ++improves;",1)
            counted=counted.replace("int i = openHeapSize++;", "int i = openHeapSize++; if (openHeapSize > peak) peak = openHeapSize;",1)
            (generated/("Counted_"+cname(name)+".java")).write_text(counted)
        functions="\n".join(base.method(npc,sig) for sig in ("void moveTowards(","boolean isInZone(","boolean canSee(NPC ","boolean canSee(int "))
        body=base.method(npc,"void tickAI(")
        start=body.index("\t\t\tNPC[] chars = map.chars;")
        end_start=body.index("\t\t\tif (attack && found)",start)
        finish=end_start+len(base.block(body,end_start))
        functions += "\nvoid visionCandidates() {\n"+body[start:finish]+"\n}\n"
        functions=re.sub(r"\bNPC\b","Actor",functions).replace("Game.stringBuffer","PerfGame.stringBuffer")
        (generated/("A_"+cname(name)+".java")).write_text("final class A_"+cname(name)+" extends Actor {\n"+functions+"\n}\n")
    factories=["final class Factories {", "static final String[] PATH_NAMES = {"+",".join('"'+n+'"' for n in PATH_NAMES)+"};"]
    for typename,method,prefix in (("PerfGame","game","K_"),("Actor","actor","A_")):
        factories.append("static "+typename+" "+method+"(String name) {")
        for name in names: factories.append('if (name.equals("'+name+'")) return new '+prefix+cname(name)+'();')
        factories.append('throw new RuntimeException("Unknown variant: " + name); }')
    factories.append("static PerfGame counted(String name) {")
    for name in PATH_NAMES: factories.append('if (name.equals("'+name+'")) return new Counted_'+cname(name)+'();')
    factories.append('throw new RuntimeException("Unknown counted variant"); } }')
    (generated/"Factories.java").write_text("\n".join(factories)+"\n")
    collision=base.method(states["heap"][c.FILES[0]],"static byte getTileCollision(")+"\n"+base.method(states["heap"][c.FILES[0]],"static byte getObjectCollision(")
    (generated/"Collision.java").write_text("final class Collision implements Constants {\n"+collision.replace("Game.","Collision.")+"\n}\n")
    for classname,name in (("OriginalTiles","heap"),("IndexedTiles","tile-index"),("CulledTiles","all"),("CullOnlyTiles","tile-cull")):
        render=base.method(states[name][c.FILES[0]],"void paintMap(")
        render=render[:render.index("\n\t\tProfiler.beginRenderSection(Profiler.RENDER_OBJECTS);")]+"\n}\n"
        render=render.replace("void paintMap(","void render(",1).replace("Profiler.beginRenderSection(Profiler.RENDER_BG);","").replace("Profiler.beginRenderSection(Profiler.RENDER_TILES);","")
        (generated/(classname+".java")).write_text("final class "+classname+" extends TileKernel {\n"+render+"\n}\n")
    checks=(c.PARENT/"experiments/src/ExperimentChecks.java").read_text()
    tilepart=checks[checks.index("    static TileKernel[] tileKernels("):]
    tilepart=tilepart.replace("new OriginalTiles(), new IndexedTiles(), new CulledTiles()", "new OriginalTiles(), new IndexedTiles(), new CulledTiles(), new CullOnlyTiles()")
    tilepart=tilepart.replace("new TraceGraphics(width, height), new TraceGraphics(width, height), new TraceGraphics(width, height)", "new TraceGraphics(width, height), new TraceGraphics(width, height), new TraceGraphics(width, height), new TraceGraphics(width, height)")
    tilepart=tilepart.replace("new TraceGraphics(240, 320), new TraceGraphics(240, 320), new TraceGraphics(240, 320)", "new TraceGraphics(240, 320), new TraceGraphics(240, 320), new TraceGraphics(240, 320), new TraceGraphics(240, 320)")
    tilechecks=('public final class ExperimentChecks implements Constants {\nstatic int tileFrames, seed=1;\n'
        'static void require(boolean ok,String message){if(!ok)throw new RuntimeException(message);}\n'
        'static int random(int n){seed=seed*1664525+1013904223;return(seed>>>1)%n;}\n'
        'public static void main(String[] args)throws Exception{checkTiles();System.out.println("CHECKS,tile-traces,"+tileFrames);System.out.println("CHECKS,PASS");}\n'+tilepart)
    (generated/"ExperimentChecks.java").write_text(tilechecks)
    return generated


def preverify(raw, verified, libraries):
    if verified.exists(): shutil.rmtree(verified)
    args=[base.jdk("java"),"-jar",base.WORK/"suite/libs/proguard.jar","-injars",raw,"-outjars",verified]
    for library in libraries: args += ["-libraryjars",library]
    command(args+["-dontshrink","-dontoptimize","-dontobfuscate","-microedition","-target","1.1"])


def build(states, full=True):
    base.bootstrap()
    generated=generate(states)
    raw,verified=WORK/"raw",WORK/"verified"
    if raw.exists(): shutil.rmtree(raw)
    raw.mkdir()
    api=base.WORK/"cldc/j2me_cldc/bin/common/api/classes"
    sources=[c.PARENT/"src/Kernel.java",c.PARENT/"src/Fixtures.java",c.PARENT/"experiments/src/MapData.java",c.PARENT/"experiments/src/TileKernel.java",ROOT/"common/src/Constants.java",ROOT/"common/src/Objects.java"]
    sources+=sorted((HERE/"src").glob("*.java"))+sorted(generated.glob("*.java"))
    command([base.jdk("javac"),"-source","1.3","-target","1.3","-Xlint:-options","-bootclasspath",api,"-d",raw]+sources)
    preverify(raw,verified,[api])
    for p in (ROOT/"res").iterdir():
        if p.name in base.MAPS or p.suffix==".png": shutil.copyfile(p,verified/p.name)
    desktop=WORK/"desktop"
    if desktop.exists():shutil.rmtree(desktop)
    desktop.mkdir()
    desktop_source=WORK/"desktop-source"; desktop_source.mkdir(exist_ok=True)
    raster=(c.PARENT/"experiments/desktop/RasterChecks.java").read_text()
    raster=raster.replace("new RasterGraphics(width, height, textures), new RasterGraphics(width, height, textures)", "new RasterGraphics(width, height, textures), new RasterGraphics(width, height, textures), new RasterGraphics(width, height, textures)")
    raster=raster.replace("three-way-exact-ARGB-frames", "four-way-exact-ARGB-frames")
    (desktop_source/"RasterChecks.java").write_text(raster)
    command([base.jdk("javac"),"-source","1.3","-target","1.3","-Xlint:-options","-classpath",verified,"-d",desktop,c.PARENT/"experiments/desktop/RasterGraphics.java",desktop_source/"RasterChecks.java"])
    footprints={}
    if full:
        libs=[base.WORK/"suite/uei"/name for name in ("cldc11.jar","midp21.jar","jsr135.jar","jsr184.jar","nokiaui.jar")]
        original={p:c.source(c.MASTER,p) for p in c.FILES}
        # Each standalone candidate plus every cumulative prefix is type-checked.
        builds={"master":original,**states}
        running=dict(states["heap"])
        for number,label,name,fn in c.SPECS:
            fn(running);builds["series-"+number]=dict(running)
        diag=dict(states["all"]);c.diagnostic(diag);builds["all-diagnostic"]=diag
        common=sorted((ROOT/"src").glob("*.java"))+sorted((ROOT/"common/src").glob("*.java"))
        for label,state in builds.items():
            directory=WORK/("game-"+label); directory.mkdir(exist_ok=True)
            files=[]
            for path in common:
                relative=str(path.relative_to(ROOT))
                if relative in state:
                    target=directory/"source"/path.name;target.parent.mkdir(exist_ok=True);target.write_text(state[relative]);files.append(target)
                else:files.append(path)
            out=directory/"raw"
            if out.exists():shutil.rmtree(out)
            out.mkdir()
            print("Build full game:",label,flush=True)
            command([base.jdk("javac"),"-source","1.3","-target","1.3","-Xlint:-options","-bootclasspath",libs[0],"-classpath",os.pathsep.join(str(x) for x in libs[1:]),"-d",out]+files)
            preverify(out,directory/"verified",libs)
            values={}
            for name in ("Game","NPC","Constants"):
                data=(directory/"verified"/(name+".class")).read_bytes()
                if data[4:8]!=b"\x00\x03\x00\x2d" or (name != "Constants" and b"StackMap" not in data):raise ValueError("CLDC StackMap missing")
                values[name+"_bytes"]=len(data);values[name+"_sha256"]=base.sha(data)
            footprints[label]=values
    return footprints


def kvm(): return base.kvm_command()[:-1]+[str(WORK/"verified")]

def desktop(): return [base.jdk("java"),"-Xmx512m","-Djava.awt.headless=true","-cp",os.pathsep.join((str(WORK/"desktop"),str(WORK/"verified")))]


def checks(destination):
    results=[]
    for engine,args in (("desktop Java",desktop()),("original KVM 1.1",kvm())):
        for main in ("PerfChecks","ExperimentChecks"):
            print("Validate",engine,main,flush=True)
            output=command(args+[main])
            if "CHECKS,PASS" not in output: raise ValueError("Missing validation sentinel")
            print(output,end="",flush=True);results.append(engine+" "+main+"\n"+output)
    output=command(desktop()+["RasterChecks"])
    if "RASTER,PASS" not in output:raise ValueError("Missing raster sentinel")
    print(output,end="",flush=True);results.append("desktop AWT pixels\n"+output)
    (destination/"validation.txt").write_text("\n".join(results))


def scenarios():
    for name in base.MAPS:
        for distribution in ("npc","spread","local"):yield "path",name+":"+distribution
        for family in ("objects","zones","seats"):yield family,name
        for distribution in ("stationary","moving"):yield "npc-zones",name+":"+distribution
        for distribution in ("waypoint","guard"):yield "vision",name+":"+distribution
        yield "tiles",name+":240x320:shadows"
    for distribution in ("turn","move","mixed"):yield "facing",distribution


def collect(args):
    rows=[];counts=[]
    selected=[x for x in scenarios() if not args.filter or args.filter in (x[0]+" "+x[1])]
    for i,(family,scenario) in enumerate(selected):
        print("[%d/%d] %s %s"%(i+1,len(selected),family,scenario),flush=True)
        output=command(kvm()+["PerfBench",family,scenario,str(args.samples),str(args.min_ms)])
        new=[]
        for line in output.splitlines():
            fields=line.split(",")
            if fields[0]!="RESULT":continue
            if len(fields)!=len(RAW_FIELDS):raise ValueError("Timing output schema")
            new.append(dict(zip(RAW_FIELDS,["original-kvm-1.1"]+fields[1:])))
        validate(new,args.samples);rows+=new
        write_csv(args.results/"raw.csv",RAW_FIELDS,rows)
        if family=="path":
            profile=command(kvm()+["PerfProfile",scenario])
            for line in profile.splitlines():
                f=line.split(",")
                if f[0]=="COUNT":
                    if len(f)!=12:raise ValueError("Count schema")
                    counts.append(dict(zip(("scenario","variant","queries","expanded","heuristics","adds","removes","improves","peak","found","checksum"),f[1:])))
            write_csv(args.results/"operation-counts.csv",("scenario","variant","queries","expanded","heuristics","adds","removes","improves","peak","found","checksum"),counts)
        (args.results/"commands.log").write_text("\n".join(LOG))
    expected=args.samples*sum(len(NAMES[f]) for f,s in selected)
    if len(rows)!=expected:raise ValueError("Incomplete scenario list")
    analyze(rows,args.results,args.samples)


def metadata(args,states,footprints):
    inputs=sorted(HERE.glob("*.py"))+sorted((HERE/"src").glob("*.java"))
    inputs += [c.PARENT/"src/Kernel.java",c.PARENT/"src/Fixtures.java",c.PARENT/"run.py",c.PARENT/"experiments/run_experiments.py",c.PARENT/"experiments/TileLoop.java.inc",c.PARENT/"experiments/src/MapData.java",c.PARENT/"experiments/src/TileKernel.java",c.PARENT/"experiments/src/ExperimentChecks.java",c.PARENT/"experiments/desktop/RasterChecks.java",c.PARENT/"experiments/desktop/RasterGraphics.java"]
    inputs += sorted(c.PATCHES.glob("*.patch"))+sorted((c.PATCHES/"standalone").glob("*.patch"))
    return dict(recorded_utc=datetime.now(timezone.utc).isoformat(),host=platform.platform(),logical_cpus=os.cpu_count(),affinity=sorted(os.sched_getaffinity(0)),load=os.getloadavg(),
        git_head=command(["git","rev-parse","HEAD"]).strip(),base_master=c.MASTER,kvm_sha256=base.sha(base.kvm_binary().read_bytes()),kvm_heap_bytes=2*1024*1024,
        samples=args.samples,target_ms=args.min_ms,dependencies=base.DEPENDENCIES,footprints=footprints,
        input_sha256={str(p.relative_to(ROOT)):base.sha(p.read_bytes()) for p in inputs},
        resources_sha256={p.name:base.sha(p.read_bytes()) for p in sorted((ROOT/"res").iterdir()) if p.name in base.MAPS or p.suffix==".png"},
        prototype_sha256={name:{path:base.sha(text.encode()) for path,text in state.items()} for name,state in states.items()},
        generated_java_sha256={str(p.relative_to(WORK)):base.sha(p.read_bytes()) for directory in (WORK/"generated",WORK/"desktop-source") for p in sorted(directory.glob("*.java"))},
        headless_class_sha256={p.name:base.sha(p.read_bytes()) for p in sorted((WORK/"verified").glob("*.class"))},
        pspkvm_tested_here=False,whole_game_profile=False,
        caveats=["Source-extracted methods, not a full MIDP/PSPKVM run or FPS", "Path queries are synthetic spawn/waypoint or spatial fixtures on real maps", "No-op logger in path kernels; logging I/O/debug string removal is not timed", "Vision candidate block uses a heat-call recorder; RNG/state/call arguments and wall-detection side effects are compared", "KVM tiles only count commands; AWT pixel checks are a different graphics engine", "Common harness/checksum overhead is included in timed loops; allocation/setup/GC/output are excluded", "All candidates preserve zone contents only under existing immutable-after-load contract; replacing the array invalidates caches", "Float movement compares raw result bits including exceptional and underflow values"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-only",action="store_true")
    parser.add_argument("--check-only",action="store_true")
    parser.add_argument("--kernels-only",action="store_true",help="Skip repeated full game builds (development/pilots only)")
    parser.add_argument("--analyze",type=Path)
    parser.add_argument("--results",type=Path,default=RESULTS)
    parser.add_argument("--samples",type=int,default=12)
    parser.add_argument("--min-ms",type=int,default=200)
    parser.add_argument("--filter",default="")
    args=parser.parse_args()
    if args.samples<2 or args.min_ms<20:parser.error("samples >= 2 and min-ms >= 20")
    if args.analyze:
        with args.analyze.open() as stream:rows=list(csv.DictReader(stream))
        analyze(rows,args.results);return
    args.results=args.results.resolve()
    if args.results in ((c.PARENT/"results").resolve(),(c.PARENT/"experiments/results").resolve()):raise ValueError("Do not overwrite historical data")
    # Do not depend on HEAD being exactly master: artifact-only commits are fine.
    for path in c.FILES:
        if (ROOT/path).read_text()!=c.source(c.MASTER,path):raise ValueError("Keep production at the pinned master for controlled comparisons: "+path)
    WORK.mkdir(parents=True,exist_ok=True)
    files=c.export();verify_series(files)
    if args.export_only:return
    args.results.mkdir(parents=True,exist_ok=True)
    states=c.variants()
    footprints=build(states,not args.kernels_only)
    checks(args.results)
    (args.results/"environment.json").write_text(json.dumps(metadata(args,states,footprints),indent=2)+"\n")
    if not args.check_only:collect(args)
    (args.results/"commands.log").write_text("\n".join(LOG))
    print("PASS:",args.results.relative_to(ROOT),flush=True)


if __name__=="__main__":main()
