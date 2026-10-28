import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import next_cycle  # noqa: E402


def graph(verified=1, unverified=2, bare=1):
    kids = [{"id": f"v{i}", "type": "Agency", "verificationMethod": "m", "cost_status": "official"} for i in range(verified)]
    kids += [{"id": f"u{i}", "type": "Agency", "cost_status": "official"} for i in range(unverified)]
    kids += [{"id": f"b{i}", "type": "Division", "cost_status": "allocated"} for i in range(bare)]
    kids.append({"id": "p1", "type": "Position", "cost_status": "unavailable"})
    return {"id": "root", "type": "Constitution", "children": kids}


class MeasureTests(unittest.TestCase):
    def test_counts_exclude_root_and_posts(self):
        m = next_cycle.measure(graph(verified=3, unverified=2, bare=4))
        self.assertEqual(m["evidence"]["organisations"], 9)
        self.assertEqual(m["evidence"]["gap"], 2 + 4)  # the bare estimates are unverified organisations too
        self.assertEqual(m["money"]["bare_estimates"], 4)
        self.assertEqual(m["pay"]["positions"], 1)
        self.assertEqual(m["pay"]["gap"], 1)


class CycleTests(unittest.TestCase):
    def run_cycle(self, g, log_lines):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "g.json").write_text(json.dumps(g))
            log = d / "log.jsonl"
            if log_lines:
                log.write_text("\n".join(json.dumps(x) for x in log_lines) + "\n")
            out = d / "out.md"
            next_cycle.main(["--graph", str(d / "g.json"), "--out", str(out), "--log", str(log)])
            return out.read_text(), log

    def test_first_run_picks_evidence(self):
        text, _ = self.run_cycle(graph(), None)
        self.assertIn("## This cycle: EVIDENCE", text)
        self.assertNotIn("## STOP", text)

    def test_stops_when_the_picked_gap_did_not_fall(self):
        before = {"evidence": 3, "money": 1, "pay": 1}
        g = graph()
        gap_now = next_cycle.measure(g)["evidence"]["gap"]
        text, _ = self.run_cycle(g, [{"gaps": {**before, "evidence": gap_now}, "pick": "evidence", "note": "x"}])
        self.assertIn("## STOP", text)

    def test_continues_when_the_picked_gap_fell(self):
        g = graph()
        gap_now = next_cycle.measure(g)["evidence"]["gap"]
        text, _ = self.run_cycle(g, [{"gaps": {"evidence": gap_now + 5, "money": 1, "pay": 1}, "pick": "evidence", "note": "x"}])
        self.assertNotIn("## STOP", text)

    def test_baseline_line_never_triggers_stop(self):
        g = graph()
        gap_now = next_cycle.measure(g)["evidence"]["gap"]
        text, _ = self.run_cycle(g, [{"gaps": {"evidence": gap_now, "money": 1, "pay": 1}, "pick": "evidence", "note": "baseline"}])
        self.assertNotIn("## STOP", text)

    def test_moves_to_money_when_evidence_is_closed(self):
        g = graph(unverified=0, bare=0)
        g["children"].append({"id": "b9", "type": "Division", "cost_status": "allocated", "verificationMethod": "m"})
        text, _ = self.run_cycle(g, None)
        self.assertIn("## This cycle: MONEY", text)

    def test_record_appends_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "g.json").write_text(json.dumps(graph()))
            next_cycle.main(["--graph", str(d / "g.json"), "--out", str(d / "o.md"), "--log", str(d / "l.jsonl"), "--record"])
            self.assertEqual(len((d / "l.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
