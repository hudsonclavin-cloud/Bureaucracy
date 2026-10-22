"""The update job (criterion 5): a fetched file that is not the document is
refused, the plan lists what the registry says is due, the clean-cycle streak
is counted as the definition requires, and the scheduled workflow runs the job
in hold mode and never pushes to main."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from scripts import update_cycle as uc  # noqa: E402

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "update_cycle.yml"
PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


class ContentCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = PROJECT_ROOT / "tests" / ".tmp"
        self.tmp.mkdir(exist_ok=True)

    def _file(self, name, body):
        path = self.tmp / name
        path.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
        return path

    def test_a_maintenance_page_a_small_file_and_a_wrong_type_are_refused(self):
        check = {"contentType": "html", "minBytes": 500, "mustContain": ["U.S.C."], "mustNotContain": ["Under Maintenance", "Request Access"]}
        page = self._file("maint.html", "<html><title>Under Maintenance</title>" + "x" * 600 + " U.S.C. </html>")
        problems = uc.content_check(page, {"content_type": "text/html"}, check, None)
        self.assertTrue(any("Under Maintenance" in p for p in problems), problems)
        small = self._file("small.html", "<html>U.S.C.</html>")
        self.assertTrue(any("under the floor" in p for p in uc.content_check(small, {"content_type": "text/html"}, check, None)))
        wrong = self._file("wrong.html", "x" * 600 + " U.S.C. ")
        self.assertTrue(any("not html" in p for p in uc.content_check(wrong, {"content_type": "application/pdf"}, check, None)))
        good = self._file("good.html", "<html>" + "x" * 600 + " 5 U.S.C. 5312 </html>")
        self.assertEqual(uc.content_check(good, {"content_type": "text/html; charset=utf-8"}, check, None), [])

    def test_a_statement_no_newer_than_the_copy_in_use_is_refused(self):
        check = {"contentType": "json", "minBytes": 10, "mustContain": ["record_date"], "parse": "x", "newerThanCopy": "record_date"}
        stale = self._file("stale.json", json.dumps({"data": [{"record_date": "2026-08-31"}]}))
        problems = uc.content_check(stale, {"content_type": "application/json"}, check, "2026-08-31")
        self.assertTrue(any("not newer than the copy in use" in p for p in problems), problems)
        newer = self._file("newer.json", json.dumps({"data": [{"record_date": "2026-09-30"}]}))
        self.assertEqual(uc.content_check(newer, {"content_type": "application/json"}, check, "2026-08-31"), [])
        broken = self._file("broken.json", "{not json")
        self.assertTrue(any("not JSON" in p for p in uc.content_check(broken, {"content_type": "application/json"}, {"contentType": "json", "parse": "x"}, None)))


class StreakTests(unittest.TestCase):
    def test_three_consecutive_clean_held_cycles_are_needed(self):
        self.assertEqual(uc.clean_streak([]), 0)
        clean = {"mode": "hold", "clean": True}
        held = {"mode": "hold", "clean": False}
        self.assertEqual(uc.clean_streak([clean, clean]), 2)
        self.assertEqual(uc.clean_streak([clean, clean, held]), 0)
        self.assertEqual(uc.clean_streak([held, clean, clean, clean]), 3)
        self.assertEqual(uc.CLEAN_CYCLES_BEFORE_PUBLISH, 3)
        self.assertEqual(uc.clean_streak([{"mode": "publish", "clean": True}, clean]), 1)


class PlanTests(unittest.TestCase):
    def test_the_plan_lists_what_the_registry_says_is_due_and_writes_nothing(self):
        if not PUBLISHED.is_file():
            self.skipTest("no published graph")
        before = {p: p.stat().st_mtime for p in (uc.REPORT, uc.CYCLES) if p.exists()}
        out = io.StringIO()
        with redirect_stdout(out):
            code = uc.main(["update_cycle", "--plan"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("source(s) due", text)
        self.assertIn("derive steps: {}".format(len(uc.DERIVE_STEPS)), text)
        for p, mtime in before.items():
            self.assertEqual(p.stat().st_mtime, mtime, "the plan wrote {}".format(p))

    def test_every_derive_and_report_step_exists(self):
        for script in uc.DERIVE_STEPS + uc.REPORT_STEPS:
            self.assertTrue((PROJECT_ROOT / "scripts" / script).is_file(), script)
        derive_scripts = sorted(p.name for p in (PROJECT_ROOT / "scripts").glob("derive_*_evidence.py"))
        self.assertEqual(sorted(uc.DERIVE_STEPS), derive_scripts, "a derive script the cycle does not run")


class WorkflowTests(unittest.TestCase):
    def test_the_workflow_runs_the_job_in_hold_mode_and_never_pushes_to_main(self):
        self.assertTrue(WORKFLOW.is_file())
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python scripts/update_cycle.py --hold", text)
        self.assertNotIn("python scripts/update_cycle.py --publish", text)
        self.assertIn("cron:", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn('git push -u origin "$BRANCH"', text)
        self.assertNotIn("push origin main", text)
        self.assertNotIn("push -f", text)
        self.assertIn("gh pr create", text)
        self.assertIn("update_cycle_report.json", text)
        try:
            import yaml  # noqa: F401
        except ImportError:
            return
        import yaml
        parsed = yaml.safe_load(text)
        self.assertEqual(parsed["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertIn("schedule", parsed[True] if True in parsed else parsed["on"])


class RebuildInputTests(unittest.TestCase):
    def test_a_cycle_that_fetched_nothing_still_rebuilds_from_the_newest_committed_statement(self):
        newest = uc.newest_committed_statement()
        self.assertIsNotNone(newest)
        self.assertRegex(newest.name, r"^mts_table5_\d{4}-\d{2}-\d{2}\.json$")
        import re
        dated = sorted(p.name for p in uc.FIXTURES.glob("mts_table5_*.json") if re.fullmatch(r"mts_table5_\d{4}-\d{2}-\d{2}\.json", p.name))
        self.assertEqual(newest.name, dated[-1])
        source = Path(uc.__file__).read_text(encoding="utf-8")
        self.assertIn("rebuild_from = new_statement or newest_committed_statement()", source)

    def test_the_workflow_does_not_fail_when_the_repository_forbids_opening_the_pull_request(self):
        text = (PROJECT_ROOT / ".github" / "workflows" / "update_cycle.yml").read_text(encoding="utf-8")
        self.assertIn("gh label create update-cycle", text)
        self.assertIn("compare/main...", text)
        self.assertIn("::warning::", text)


if __name__ == "__main__":
    unittest.main()
