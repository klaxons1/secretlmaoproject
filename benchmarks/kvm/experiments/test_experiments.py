"""Offline guardrails: no downloads, VM runs, production edits, or Git writes."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze
import run_experiments as runner


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = (runner.ROOT / "src/Game.java").read_text()

    def test_heap_changes_only_pathfinding_region(self):
        new = runner.heap_game(self.current)
        before, after = "\t// region Pathfinding\n", "\t// endregion Pathfinding"
        self.assertEqual(self.current.split(before)[0], new.split(before)[0])
        self.assertEqual(self.current.split(after)[1], new.split(after)[1])
        region = new.split(before)[1].split(after)[0]
        self.assertNotIn("openNodePrev", region)
        self.assertNotIn("openNodeNext", region)
        self.assertIn("openHeapOrder = new int[size]", region)
        self.assertIn("openHeapPosition[n] == -1", region)
        self.assertIn("openHeapSize = openHeapSerial = 0", region)
        self.assertIn("int serial = openHeapSerial++", region)

    def test_tiles_do_not_modify_objects_or_other_methods(self):
        marker = "\n\t\tProfiler.beginRenderSection(Profiler.RENDER_OBJECTS);"
        for cull in (False, True):
            new = runner.tile_loop(self.current, cull)
            self.assertEqual(self.current.split(marker, 1)[1], new.split(marker, 1)[1])
            self.assertEqual(self.current.split("\tvoid paintMap(")[0], new.split("\tvoid paintMap(")[0])
            self.assertIn("viewX % TILE_SIZE", new)
            self.assertIn("viewY % TILE_SIZE", new)
            self.assertIn("g.drawRegion(tilesImg, (tile & 3) * TILE_SIZE, (tile >> 2) * TILE_SIZE", new)
            self.assertIn("solid[pos - width - 1]", new)
            self.assertEqual(cull, "int visibleCols =" in new)
        self.assertEqual(self.current, (runner.ROOT / "src/Game.java").read_text())

    def test_all_maps_and_separate_engines(self):
        scenarios = list(runner.scenarios())
        self.assertEqual(len(scenarios), len(set(scenarios)))
        self.assertEqual(96, len(scenarios))
        for name in runner.base.MAPS:
            self.assertIn(("original-kvm-1.1", "path", name + ":npc"), scenarios)
            self.assertIn(("desktop-awt-reference", "tiles", name + ":640x480:shadows"), scenarios)
        self.assertTrue(all(family == "tiles" for engine, family, scenario in scenarios if engine != "original-kvm-1.1"))


class AnalysisTests(unittest.TestCase):
    def rows(self):
        rows = []
        times = {"original": (100, 200, 300), "list": (100, 300, 100), "heap": (50, 60, 70)}
        names = analyze.names("path")
        for sample in range(3):
            for order, index in enumerate(analyze.ORDERS[sample]):
                variant = names[index]
                rows.append(dict(engine="original-kvm-1.1", family="path", scenario="fixture", variant=variant,
                                 sample=str(sample), order=str(order), iterations="1", operations="8",
                                 elapsed_ms=str(times[variant][sample]), checksum="-1987"))
        return rows

    def test_uses_median_of_paired_ratios(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = analyze.summarize(self.rows(), tmp, samples=3)
            row = next(row for row in summary if row["reference"] == "original" and row["candidate"] == "list")
            self.assertEqual(1.0, row["speedup_median"])
            self.assertEqual(2.0, row["reference_us_median"] / row["candidate_us_median"])
            self.assertEqual(0.0, row["time_reduction_percent"])

    def test_reanalysis_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            analyze.write_csv(tmp / "raw.csv", analyze.RAW_FIELDS, self.rows())
            analyze.summarize(self.rows(), tmp / "first", samples=3)
            analyze.reanalyze(tmp / "raw.csv", tmp / "second")
            for name in ("summary.csv", "paired.csv", "calculations.md"):
                self.assertEqual((tmp / "first" / name).read_bytes(), (tmp / "second" / name).read_bytes())

    def test_rejects_missing_duplicate_and_bad_order(self):
        rows = self.rows()
        bad_order = copy.deepcopy(rows)
        bad_order[0]["order"] = "2"
        for invalid in (rows[:-1], rows + [rows[0]], bad_order):
            with self.assertRaises(ValueError): analyze.validate(invalid, samples=3)

    def test_rejects_checksum_units_and_nonpositive_time(self):
        for field, value in (("checksum", "1"), ("operations", "16"), ("elapsed_ms", "0"), ("iterations", "-1"), ("sample", "4")):
            rows = self.rows()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): analyze.validate(rows, samples=3)

    def test_rejects_phone_claim_engine_or_mixed_schema(self):
        for field, value in (("engine", "phone-fps"), ("engine", "desktop-awt-reference"), ("variant", "quick-heap"), ("elapsed_ms", "0.5")):
            rows = self.rows()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): analyze.validate(rows, samples=3)
        rows = self.rows()
        rows[0]["unrecognized"] = "ignored?"
        with self.assertRaises(ValueError): analyze.validate(rows, samples=3)


if __name__ == "__main__":
    unittest.main()
