#!/usr/bin/env python3
"""Confirm noisy desktop raster timings without replacing the primary dataset.

Same original/index/cull render methods, all six maps at 240x320 with shadows.
Longer intervals, synchronous JIT, Serial GC, all variants warmed before
calibration. Still hosted desktop AWT, NOT phone/MIDP performance.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import run_experiments as runner
import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=runner.HERE / "results/awt-controlled")
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--min-ms", type=int, default=500)
    args = parser.parse_args()
    protected = [(runner.PARENT / "results").resolve(), (runner.HERE / "results").resolve()]
    target = args.results.resolve()
    if target == protected[1] or target == protected[0] or protected[0] in target.parents:
        raise ValueError("Primary and historical results must not be overwritten")
    if args.samples < 1 or args.min_ms < 100: raise ValueError("Invalid samples/interval")
    primary = runner.HERE / "results/raw.csv"
    primary_hash = runner.base.sha(primary.read_bytes()) if primary.exists() else None
    old_environment = runner.HERE / "results/environment.json"
    if old_environment.exists():
        for path, expected in json.loads(old_environment.read_text())["input_source_hashes"].items():
            if runner.base.sha((runner.ROOT / path).read_bytes()) != expected: raise ValueError("Primary benchmark source changed: " + path)
    hashes = runner.build()
    args.results.mkdir(parents=True, exist_ok=True)
    java = [runner.base.jdk("java"), "-Djava.awt.headless=true", "-Xms512m", "-Xmx512m", "-XX:+UseSerialGC", "-Xbatch", "-XX:CICompilerCount=2",
            "-cp", os.pathsep.join([str(runner.WORK / "desktop"), str(runner.WORK / "verified")])]
    validation = runner.command(java + ["RasterChecks"])
    if "RASTER,PASS" not in validation: raise ValueError("Missing raster validation")
    (args.results / "validation.txt").write_text(validation)
    metadata = dict(started_utc=datetime.now(timezone.utc).isoformat(), engine="desktop-awt-reference",
                    series="long-interval-confirmatory", java_command=[str(arg) for arg in java], samples=args.samples,
                    target_ms=args.min_ms, clock="System.nanoTime (elapsed converted to integer ms)",
                    warmup="3 rounds x 256 batches x 8 phases per variant, all variants before calibration",
                    primary_raw_sha256=primary_hash, generated_source_hashes=hashes,
                    script_sha256=runner.base.sha(Path(__file__).read_bytes()),
                    controlled_java_sha256=runner.base.sha((runner.HERE / "desktop/ControlledRasterBenchmark.java").read_bytes()),
                    comparison="same six maps, 240x320, bitmap shadows on; source kernels unchanged", load_before=os.getloadavg())
    rows = []
    for index, map_name in enumerate(runner.base.MAPS):
        scenario = map_name + ":240x320:shadows"
        print("[%d/6] Confirm raster %s" % (index + 1, scenario), flush=True)
        output = runner.command(java + ["ControlledRasterBenchmark", scenario, args.samples, args.min_ms])
        batch = []
        for line in output.splitlines():
            fields = line.split(",")
            if fields[0] != "RESULT": continue
            if len(fields) != len(analyze.RAW_FIELDS): raise ValueError("Timing schema")
            row = dict(zip(analyze.RAW_FIELDS, ["desktop-awt-reference"] + fields[1:]))
            if row["family"] != "tiles" or row["scenario"] != scenario: raise ValueError("Unexpected scenario")
            batch.append(row)
        analyze.validate(batch, args.samples)
        rows.extend(batch)
        analyze.write_csv(args.results / "raw.csv", analyze.RAW_FIELDS, rows)
        (args.results / "commands.log").write_text("\n".join(runner.LOG))
    analyze.summarize(rows, args.results, args.samples)
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["load_after"] = os.getloadavg()
    metadata["interval_count"] = len(rows)
    (args.results / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (args.results / "commands.log").write_text("\n".join(runner.LOG))
    if primary_hash and runner.base.sha(primary.read_bytes()) != primary_hash: raise ValueError("Primary timings were overwritten")
    print("Controlled raster complete: %d intervals; primary raw.csv unchanged" % len(rows), flush=True)


if __name__ == "__main__":
    main()
