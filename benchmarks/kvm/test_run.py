"""Fast, offline tests for extraction and the published calculation pipeline."""
import copy
import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import run


def row(sample, variant, iterations, elapsed=100):
    return dict(family="sort", scenario="fixture:sorted", variant=variant,
                sample=str(sample), order=str((sample & 1) if variant == "original" else 1 - (sample & 1)),
                iterations=str(iterations), operations=str(iterations), elapsed_ms=str(elapsed), checksum="123")


class CalculationTests(unittest.TestCase):
    def analyze(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            result = run.summarize(rows, Path(directory))
            self.assertTrue((Path(directory) / "calculations.md").exists())
            with (Path(directory) / "summary.csv").open() as data:
                self.assertEqual(len(list(csv.DictReader(data))), len(result))
            return result

    def test_paired_ratios_not_ratio_of_medians(self):
        rows = [row(0, "original", 10), row(0, "optimized", 20),
                row(1, "optimized", 50), row(1, "original", 100)]
        result = self.analyze(rows)[0]
        self.assertEqual(result["original_median_us"], 5500)
        self.assertEqual(result["optimized_median_us"], 3500)
        self.assertEqual(result["median_paired_speedup"], 1.25)
        self.assertAlmostEqual(result["median_paired_time_reduction_pct"], 20)
        self.assertEqual(result["min_paired_speedup"], 0.5)
        self.assertEqual(result["max_paired_speedup"], 2)

    def test_reject_empty_incomplete_and_duplicate(self):
        for rows in ([], [row(0, "original", 10)],
                     [row(0, "original", 10), row(0, "original", 10)],
                     [row(1, "original", 10), row(1, "optimized", 10)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.analyze(rows)

    def test_reject_invalid_normalization_and_order(self):
        good = [row(0, "original", 10), row(0, "optimized", 20)]
        for field, value in (("iterations", "0"), ("elapsed_ms", "0"), ("operations", "9"),
                             ("order", "1"), ("variant", "other"), ("family", "other")):
            rows = copy.deepcopy(good)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.analyze(rows)

    def test_reject_checksum_mismatch(self):
        rows = [row(0, "original", 10), row(0, "optimized", 20)]
        rows[1]["checksum"] = "456"
        with self.assertRaises(RuntimeError):
            self.analyze(rows)

    def test_path_batch_normalization(self):
        rows = [row(0, "original", 10), row(0, "optimized", 20)]
        for entry in rows:
            entry["family"] = "path"
            entry["operations"] = str(8 * int(entry["iterations"]))
        result = self.analyze(rows)[0]
        self.assertEqual(result["original_median_us"], 1250)
        self.assertEqual(result["optimized_median_us"], 625)


class SourceTests(unittest.TestCase):
    def test_brace_matching_ignores_comments_and_literals(self):
        body = 'void f() { /* } */ String s = "{"; char c = \'}\'; // }\n if (true) { } }'
        self.assertEqual(run.method("prefix\n" + body + "\nafter", "void f("), body)

    def test_unbalanced_source_fails(self):
        with self.assertRaises(RuntimeError):
            run.block("void f() { /* } */", 0)

    def test_baseline_exists_and_extracts(self):
        source = run.original_source()
        self.assertIn("while (i != -1)", run.method(source, "void openAdd("))
        self.assertIn("short[] next = openNodeNext", run.method((run.ROOT / "src/Game.java").read_text(), "void openRemove("))


class PatchTests(unittest.TestCase):
    def test_standalone_patches_and_both_application_orders(self):
        original = run.original_source().encode()
        current = (run.ROOT / "src/Game.java").read_bytes()
        marker = b"\t// region Pathfinding\n"
        old_prefix, old_path = original.split(marker)
        new_prefix, new_path = current.split(marker)
        render = run.ROOT / "patches/0001-optimize-render-sort.patch"
        queue = run.ROOT / "patches/0002-optimize-pathfinding-queue.patch"
        cases = [((render,), new_prefix + marker + old_path),
                 ((queue,), old_prefix + marker + new_path),
                 ((render, queue), current), ((queue, render), current)]
        for patches, expected in cases:
            with self.subTest(patches=[patch.name for patch in patches]), tempfile.TemporaryDirectory() as directory:
                env = os.environ.copy()
                env["GIT_INDEX_FILE"] = str(Path(directory) / "index")

                def git(*args):
                    return subprocess.check_output(["git"] + list(args), cwd=run.ROOT, env=env)

                git("read-tree", run.BASELINE)
                # --cached operates only on this temporary index, never the
                # user's source files, real index, or current branch.
                for patch in patches:
                    git("apply", "--cached", "--check", str(patch))
                    git("apply", "--cached", str(patch))
                self.assertEqual(git("show", ":src/Game.java"), expected)
                self.assertEqual(git("diff", "--cached", "--name-only", run.BASELINE), b"src/Game.java\n")
                for patch in reversed(patches):
                    git("apply", "--cached", "--reverse", "--check", str(patch))
                    git("apply", "--cached", "--reverse", str(patch))
                self.assertEqual(git("show", ":src/Game.java"), original)
                self.assertEqual(git("diff", "--cached", "--name-only", run.BASELINE), b"")


if __name__ == "__main__":
    unittest.main()
