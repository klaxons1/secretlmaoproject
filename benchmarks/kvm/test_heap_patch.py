"""Offline checks of the heap-only export for synchronized master."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import heap_patch


class HeapPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.master = heap_patch.git_source(heap_patch.BASELINE)
        cls.heap = heap_patch.heap_source(cls.master)

    def test_export_is_reproducible_and_applies_reversibly(self):
        path = heap_patch.DEFAULT_PATCH
        self.assertEqual(path.read_text(), heap_patch.patch_text(self.master, self.heap))
        game = heap_patch.ROOT / "src/Game.java"
        before = game.read_bytes()
        heap_patch.verify_patch(path, self.master, self.heap)
        self.assertEqual(game.read_bytes(), before)

    def test_everything_outside_pathfinding_is_byte_identical(self):
        self.assertEqual(self.master.split(heap_patch.BEGIN, 1)[0], self.heap.split(heap_patch.BEGIN, 1)[0])
        self.assertEqual(self.master.split(heap_patch.END, 1)[1], self.heap.split(heap_patch.END, 1)[1])
        self.assertIn("if ((tick & 7) == 0) sortRenderChars(renderChars);", self.heap)
        self.assertIn("if (l > lag) lag = (int) l;", self.heap)
        self.assertIn("private static void sortRenderChars", self.heap)

    def test_master_duplicate_aliases_are_not_ambiguous(self):
        region = self.master.split(heap_patch.BEGIN, 1)[1].split(heap_patch.END, 1)[0]
        aliases = "\t\tshort[] openNodePrev = this.openNodePrev;\n\t\tshort[] openNodeNext = this.openNodeNext;"
        self.assertEqual(region.count(aliases), 2)
        self.assertNotIn("openNodePrev", self.heap)
        self.assertNotIn("openNodeNext", self.heap)

    def test_heap_operations_match_previously_tested_prototype(self):
        helper = (heap_patch.HERE / "experiments/HeapQueue.java.inc").read_text()
        helper = re.sub(r"^\s*// HEAP_(?:COMPARE|PEAK)\n", "", helper, flags=re.M)
        for signature in ("void openAdd(", "void openRemove("):
            self.assertEqual(heap_patch.base.method(self.heap, signature), heap_patch.base.method(helper, signature))
        self.assertIn("int serial = openHeapSerial++;", self.heap)
        self.assertIn("serial >= order[other]", self.heap)
        self.assertIn("serial <= order[other]", self.heap)
        self.assertNotIn("HEAP_COMPARE", self.heap)

    def test_blob_hash_matches_git(self):
        expected = subprocess.check_output(["git", "hash-object", "--stdin"], input=self.heap.encode(), cwd=heap_patch.ROOT).decode().strip()
        self.assertEqual(heap_patch.blob_hash(self.heap), expected)

    def test_artifact_publication_commits_do_not_break_base_guard(self):
        heap_patch.verify_base_ancestry()

    def test_shape_guard_rejects_missing_or_duplicate_matches(self):
        for source in ("", "marker marker"):
            with self.assertRaises(ValueError): heap_patch.once(source, "marker", "replacement")


if __name__ == "__main__":
    unittest.main()
