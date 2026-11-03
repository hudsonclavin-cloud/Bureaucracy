import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import next_cycle  # noqa: E402


def numbers(eg=0, er=0, mg=0, mr=0, pg=0, pr=0):
    return {
        "evidence": {"organisations": 10, "sourced": 5, "gap": eg, "reach": er},
        "money": {"bare_estimates": mg, "named_in_a_held_document": mr, "explained_blanks": 0,
                  "committee_estimates": 0, "gap": mg, "reach": mr},
        "pay": {"positions": 10, "priced": 5, "gap": pg, "reach": pr},
    }


class PayGapIsTheDefinitionOfDonesTests(unittest.TestCase):
    """Criterion 2 (redefined 2026-11-03): a post is priced, carries an explained blank, or carries a terminal
    reason. The gap is the posts with none of those; reach is the open pay leads a person must decide."""

    GRAPH = Path(__file__).resolve().parents[1] / "output" / "graph.json"

    def test_the_gap_is_the_posts_with_no_blank_and_no_terminal_reason(self):
        if not self.GRAPH.exists():
            self.skipTest("no published graph")
        import report_unpriced_positions as unpriced
        graph = json.loads(self.GRAPH.read_text())
        now = next_cycle.measure(graph)["pay"]
        groups, positions, priced, _ = unpriced.collect(graph)
        rows = [row for group in groups.values() for row in group]
        expected = sum(1 for r in rows if r["reason"] not in next_cycle.TERMINAL_PAY_REASONS and r["blank"] is None)
        self.assertEqual(now["gap"], expected)
        self.assertEqual(now["gap"], 0)
        # a blank-carrying post is explained, not priced: the strict count is the rows, and the table says so
        self.assertEqual(positions - priced, len(rows))
        self.assertGreater(sum(1 for r in rows if r["blank"] is not None), 0)

    def test_reach_is_the_open_leads_and_a_decision_lowers_it(self):
        if not self.GRAPH.exists():
            self.skipTest("no published graph")
        import find_pay_leads as fpl
        graph = json.loads(self.GRAPH.read_text())
        before = next_cycle.open_pay_leads(graph)
        self.assertEqual(before, 109)
        first = None
        with mock.patch.object(fpl, "load_decisions") as decisions:
            export = fpl.load_plum_export()
            node_map, parent_map = fpl.index_tree(graph)
            found = fpl.find_leads(graph, export, fpl.load_alias_table(node_map=node_map, parent_map=parent_map))
            first = found[0]["nodeId"]
            decisions.return_value = {first: {"nodeId": first, "name": found[0]["name"], "kind": "not_this_post", "basis": "test"}}
            self.assertEqual(next_cycle.open_pay_leads(graph), before - 1)

    def test_a_post_with_neither_a_blank_nor_a_terminal_reason_is_a_gap(self):
        rows = [{"reason": "unreached", "blank": None}, {"reason": "unreached", "blank": {"checked": 6}},
                {"reason": "not_federally_paid", "blank": None}]
        with mock.patch("report_unpriced_positions.collect", return_value=({("p", "P"): rows}, 3, 0, 0)), \
                mock.patch.object(next_cycle, "open_pay_leads", return_value=0), \
                mock.patch.object(next_cycle.evidence, "collect", return_value={}), \
                mock.patch.object(next_cycle.cost, "collect", return_value={}):
            self.assertEqual(next_cycle.measure({})["pay"]["gap"], 1)


class PickTests(unittest.TestCase):
    def test_open_gap_beats_reach_and_follows_owner_order(self):
        self.assertEqual(next_cycle.pick_of(numbers(eg=0, er=9, mg=2, pg=5)), ("money", "gap"))
        self.assertEqual(next_cycle.pick_of(numbers(eg=1, mg=2, pg=5)), ("evidence", "gap"))

    def test_reach_only_when_every_gap_is_zero(self):
        self.assertEqual(next_cycle.pick_of(numbers(er=3, mr=2, pr=9)), ("evidence", "reach"))
        self.assertEqual(next_cycle.pick_of(numbers(mr=2, pr=9)), ("money", "reach"))

    def test_nothing_left(self):
        self.assertEqual(next_cycle.pick_of(numbers()), (None, "none"))


class CycleTests(unittest.TestCase):
    def run_cycle(self, now, log_lines):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "g.json").write_text("{}")
            log = d / "log.jsonl"
            if log_lines:
                log.write_text("\n".join(json.dumps(x) for x in log_lines) + "\n")
            out = d / "out.md"
            with mock.patch.object(next_cycle, "measure", return_value=now):
                next_cycle.main(["--graph", str(d / "g.json"), "--out", str(out), "--log", str(log),
                                 "--budget", str(d / "no_budget.json")])
            return out.read_text()

    @staticmethod
    def line(now, pick, metric, note="x"):
        return {"numbers": {k: {"gap": now[k]["gap"], "reach": now[k]["reach"]} for k in now},
                "pick": pick, "metric": metric, "note": note}

    def test_first_run_has_no_stop(self):
        text = self.run_cycle(numbers(er=4), None)
        self.assertIn("## This cycle: EVIDENCE (reach)", text)
        self.assertIn("IMPROVES", text)
        self.assertNotIn("## STOP", text)

    def test_stops_when_the_aimed_number_did_not_fall(self):
        now = numbers(er=4)
        text = self.run_cycle(now, [self.line(now, "evidence", "reach")])
        self.assertIn("## STOP", text)

    def test_continues_when_it_fell(self):
        was = numbers(er=9)
        text = self.run_cycle(numbers(er=4), [self.line(was, "evidence", "reach")])
        self.assertNotIn("## STOP", text)

    def test_baseline_never_triggers_stop(self):
        now = numbers(er=4)
        text = self.run_cycle(now, [self.line(now, "evidence", "reach", note="baseline")])
        self.assertNotIn("## STOP", text)

    def test_open_gap_says_it_closes_a_gap(self):
        text = self.run_cycle(numbers(mg=3), None)
        self.assertIn("## This cycle: MONEY (gap)", text)
        self.assertIn("closes an OPEN gap", text)

    def test_nothing_to_do(self):
        self.assertIn("## Nothing to do", self.run_cycle(numbers(), None))

    def test_record_appends_one_line_with_the_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "g.json").write_text("{}")
            with mock.patch.object(next_cycle, "measure", return_value=numbers(er=4)):
                next_cycle.main(["--graph", str(d / "g.json"), "--out", str(d / "o.md"),
                                 "--log", str(d / "l.jsonl"), "--record"])
            rows = [json.loads(x) for x in (d / "l.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["numbers"]["evidence"]["reach"], 4)


class RealGraphTests(unittest.TestCase):
    def test_measure_matches_the_repositorys_own_reports(self):
        import report_cost_coverage as cost
        import report_evidence_coverage as ev
        g = json.loads(next_cycle.GRAPH.read_text())
        m = next_cycle.measure(g)
        self.assertEqual(m["money"]["bare_estimates"], len(cost.collect(g).get("estimate", [])))
        self.assertEqual(m["evidence"]["gap"], sum(len(v) for c, v in ev.collect(g).items() if c in ev.GAP_CLASSES))
        self.assertEqual(m["evidence"]["organisations"], sum(len(v) for v in ev.collect(g).values()))


if __name__ == "__main__":
    unittest.main()


class LoopBudgetTests(unittest.TestCase):
    def go(self, d, reach, *args):
        (d / "g.json").write_text("{}")
        with mock.patch.object(next_cycle, "measure", return_value=numbers(er=reach)):
            next_cycle.main(["--graph", str(d / "g.json"), "--out", str(d / "o.md"), "--log", str(d / "l.jsonl"),
                             "--budget", str(d / "b.json"), *args])

    def test_loops_count_down_and_finish(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.go(d, 5, "--loops", "2")
            self.assertIn("Loop 1 of 2", (d / "o.md").read_text())
            self.go(d, 4, "--record", "--note", "first")
            self.assertEqual(json.loads((d / "b.json").read_text())["completed"], 1)
            self.assertIn("Loop 2 of 2", (d / "o.md").read_text())
            self.go(d, 3, "--record", "--note", "second")
            self.assertIn("All 2 requested loops are complete", (d / "o.md").read_text())

    def test_dry_run_and_baseline_do_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.go(d, 5, "--loops", "3", "--dry-run")
            self.assertFalse((d / "b.json").exists())
            self.go(d, 5, "--loops", "3")
            self.go(d, 5, "--record", "--note", "baseline")
            self.assertEqual(json.loads((d / "b.json").read_text())["completed"], 0)
