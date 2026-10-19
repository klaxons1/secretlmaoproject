"""Strict, offline analysis of the three-way experiment's raw intervals."""
import csv
from collections import defaultdict
from pathlib import Path
import statistics

RAW_FIELDS = ("engine", "family", "scenario", "variant", "sample", "order", "iterations", "operations", "elapsed_ms", "checksum")
SUMMARY_FIELDS = ("engine", "family", "scenario", "reference", "candidate", "pairs", "reference_us_median", "candidate_us_median",
                  "speedup_median", "time_reduction_percent", "speedup_min", "speedup_max")
ORDERS = ((0, 1, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0), (1, 0, 2), (0, 2, 1))


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def names(family):
    if family == "sort": return ("original", "list")
    if family in ("queue", "path"): return ("original", "list", "heap")
    if family == "tiles": return ("original", "index", "cull")
    raise ValueError("Unknown family: " + family)


def validate(rows, samples=None):
    if not rows: raise ValueError("Empty raw dataset")
    groups = defaultdict(list)
    seen = set()
    normalized = []
    for row in rows:
        if set(row) != set(RAW_FIELDS): raise ValueError("Unexpected raw schema")
        row = dict(row)
        if row["engine"] not in ("original-kvm-1.1", "desktop-awt-reference"): raise ValueError("Unknown engine")
        if row["engine"] == "desktop-awt-reference" and row["family"] != "tiles": raise ValueError("Invalid engine/family")
        variants = names(row["family"])
        if row["variant"] not in variants or not row["scenario"]: raise ValueError("Unknown variant/empty scenario")
        for field in RAW_FIELDS[4:]:
            try: row[field] = int(row[field])
            except (TypeError, ValueError): raise ValueError("Noninteger " + field)
        if min(row["iterations"], row["operations"], row["elapsed_ms"]) <= 0: raise ValueError("Nonpositive work/time")
        if row["sample"] < 0 or row["order"] < 0: raise ValueError("Negative sample/order")
        if row["operations"] % row["iterations"]: raise ValueError("Fractional operations per iteration")
        key = tuple(row[field] for field in ("engine", "family", "scenario", "sample", "variant"))
        if key in seen: raise ValueError("Duplicate raw interval")
        seen.add(key)
        groups[key[:3]].append(row)
        normalized.append(row)
    for key, group in groups.items():
        variants = names(key[1])
        count = samples if samples is not None else max(row["sample"] for row in group) + 1
        if len(group) != count * len(variants): raise ValueError("Missing interval(s)")
        if {row["sample"] for row in group} != set(range(count)): raise ValueError("Noncontiguous samples")
        if len({row["checksum"] for row in group}) != 1: raise ValueError("Checksum mismatch")
        if len({row["operations"] // row["iterations"] for row in group}) != 1: raise ValueError("Inconsistent units")
        for sample in range(count):
            trial = sorted((row for row in group if row["sample"] == sample), key=lambda row: row["order"])
            if [row["order"] for row in trial] != list(range(len(variants))): raise ValueError("Invalid within-trial order")
            order = ORDERS[sample % len(ORDERS)] if len(variants) == 3 else ((0, 1) if sample % 2 == 0 else (1, 0))
            if [row["variant"] for row in trial] != [variants[i] for i in order]: raise ValueError("Wrong rotation")
    return normalized


def summarize(rows, destination, samples=None):
    rows = validate(rows, samples)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(dict)
    for row in rows:
        key = tuple(row[field] for field in ("engine", "family", "scenario"))
        groups[key][(row["sample"], row["variant"])] = row
    summary, paired, details = [], [], []
    for key, group in sorted(groups.items()):
        engine, family, scenario = key
        variants = names(family)
        comparisons = [(variants[0], variants[1])]
        if len(variants) == 3: comparisons += [(variants[0], variants[2]), (variants[1], variants[2])]
        trial_ids = sorted({sample for sample, variant in group})
        for reference, candidate in comparisons:
            ratios, old_times, new_times = [], [], []
            for sample in trial_ids:
                old, new = group[(sample, reference)], group[(sample, candidate)]
                old_us = old["elapsed_ms"] * 1000.0 / old["operations"]
                new_us = new["elapsed_ms"] * 1000.0 / new["operations"]
                ratio = old_us / new_us
                ratios.append(ratio); old_times.append(old_us); new_times.append(new_us)
                paired.append(dict(engine=engine, family=family, scenario=scenario, reference=reference, candidate=candidate,
                                   sample=sample, reference_us=old_us, candidate_us=new_us, speedup=ratio))
            speedup = statistics.median(ratios)
            summary.append(dict(engine=engine, family=family, scenario=scenario, reference=reference, candidate=candidate,
                                pairs=len(trial_ids), reference_us_median=statistics.median(old_times), candidate_us_median=statistics.median(new_times),
                                speedup_median=speedup, time_reduction_percent=100 * (1 - 1 / speedup), speedup_min=min(ratios), speedup_max=max(ratios)))
            details.append("| %s | %s | %s | %s → %s | %.3f | %.3f | %.4f× | %.2f%% | %.4f–%.4f | %s |" %
                           (engine, family, scenario, reference, candidate, statistics.median(old_times), statistics.median(new_times), speedup,
                            100 * (1 - 1 / speedup), min(ratios), max(ratios), ", ".join("%.5f" % r for r in ratios)))
    write_csv(destination / "summary.csv", SUMMARY_FIELDS, summary)
    write_csv(destination / "paired.csv", ("engine", "family", "scenario", "reference", "candidate", "sample", "reference_us", "candidate_us", "speedup"), paired)
    text = """# All experiment calculations

The KVM and desktop AWT engines must not be combined into a phone/FPS claim.
A tile operation is one background + tiles + wall-shadows phase, not a full game frame.
A queue operation is a complete enqueue/drain batch; a path operation is one query.

- `us/op = elapsed_ms * 1000 / operations`.
- `speedup_sample = reference_us_sample / candidate_us_sample` for the same trial.
- Reported speedup is the **median of paired ratios**, not the ratio of medians.
- `time reduction (%) = 100 * (1 - 1 / median_speedup)`; negative means slower.
- Ranges are observed paired min–max, **not confidence intervals**.
- All fixed-batch checksums, trial rotations, units and missing/duplicate rows are validated.

| Engine | Family | Scenario | Comparison | Reference µs/op | Candidate µs/op | Paired median | Time reduction | Observed range | Every paired ratio |
|---|---|---|---|---:|---:|---:|---:|---|---|
"""
    (destination / "calculations.md").write_text(text + "\n".join(details) + "\n")
    return summary


def reanalyze(source, destination):
    with Path(source).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    return summarize(rows, destination)
