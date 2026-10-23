"""Offline regression tests for documented R1 accounting and drift detection."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_creative_research_status as status


class StatusCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(status.ROOT / status.PROJECT, self.root / status.PROJECT)

    def path(self, name):
        return self.root / status.PROJECT / name

    def replace(self, name, old, new):
        path = self.path(name)
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_current_repository_and_write_idempotence(self):
        before = {p: p.read_bytes() for p in (self.root / status.PROJECT).rglob("*.md")}
        with redirect_stdout(StringIO()):
            snapshot = status.check(self.root, write=True)
        self.assertEqual(snapshot["count"] + snapshot["remaining"], 200)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_each_current_page_rejects_drift_and_can_be_repaired(self):
        for name in status.CURRENT:
            with self.subTest(page=name):
                original = self.path(name).read_bytes()
                self.replace(name, "153 / 200 (76.5%)", "73 / 200 (36.5%)")
                with self.assertRaises(ValueError):
                    status.check(self.root)
                with redirect_stdout(StringIO()):
                    status.check(self.root, write=True)
                self.assertEqual(original, self.path(name).read_bytes())

    def test_invalid_milestone_accounting_is_rejected(self):
        original = self.path("MILESTONES.md").read_text(encoding="utf-8")
        mutations = [
            ("**47**", "**127**"),
            ("153 / 200 (76.5%)", "153 / 200 (36.5%)"),
            ("153 / 200 (76.5%)", "242 / 200 (121.0%)"),
            ("**89 / 89**, tracked separately", "**89 / 200**, tracked separately"),
            ("B04–B12: **36**", "B04–B12: **32**"),
            ("B04–B12: **36**", "B04–B13: **40**"),
            ("- 150-case Coverage Map", "- 200-case Coverage Map"),
            ("Status: **Complete**", "Status: **Pending**"),
        ]
        for old, new in mutations:
            with self.subTest(change=new):
                self.path("MILESTONES.md").write_text(original, encoding="utf-8")
                self.replace("MILESTONES.md", old, new)
                with self.assertRaises(ValueError):
                    status.check(self.root)

    def test_candidate_change_cannot_silently_leave_old_summaries(self):
        self.replace("MILESTONES.md", "E-P04 Incentive Rewire → Strong Candidate", "E-P04 Incentive Rewire → Candidate")
        with self.assertRaises(ValueError):
            status.check(self.root)

    def test_conflicting_claims_outside_generated_block_are_rejected(self):
        original = self.path("STATUS.md").read_text(encoding="utf-8")
        for claim in ["Current: 73 / 200", "remaining **127**", "32 primitives",
                      "Canon promotions: **1**",
                      "**E-P04 Incentive Rewire → Priority Candidate**"]:
            with self.subTest(claim=claim):
                self.path("STATUS.md").write_text(original + "\n" + claim + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    status.check(self.root)

    def test_historical_batch_counts_and_tasks_are_not_rewritten(self):
        historical = self.path("progress/R1_BATCH_01.md")
        before = historical.read_bytes()
        self.assertIn(b"33 / 200", before)
        self.replace("STATUS.md", "153 / 200 (76.5%)", "73 / 200 (36.5%)")
        with redirect_stdout(StringIO()):
            status.check(self.root, write=True)
        self.assertEqual(historical.read_bytes(), before)

    def test_missing_duplicate_or_reversed_markers_are_rejected(self):
        original = self.path("STATUS.md").read_text(encoding="utf-8")
        for modified in [original.replace(status.BEGIN, ""),
                         original + status.END,
                         original.replace(status.BEGIN, "TEMP").replace(status.END, status.BEGIN).replace("TEMP", status.END)]:
            self.path("STATUS.md").write_text(modified, encoding="utf-8")
            with self.assertRaises(ValueError):
                status.check(self.root)


if __name__ == "__main__":
    unittest.main()
