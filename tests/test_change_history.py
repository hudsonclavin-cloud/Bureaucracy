"""The change history, the change budget and the review queue (Part 2 "Change
history", criteria 5 and 7): the diff reads every kind of change off two
graphs, each budget rule trips on its own case and no other, the queue keeps
every record ever opened and closes rather than deletes, the committed history
describes the published graph, the gate refuses each corruption, and the
committed document is what the script renders."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from data_pipeline import changes as ch  # noqa: E402
from scripts.build_change_history import render  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"
HISTORY = ch.HISTORY_PATH
QUEUE = ch.QUEUE_PATH
DOC = PROJECT_ROOT / "docs" / "CHANGE_HISTORY.md"


def small_graph():
    return {
        "id": "the-constitution-of-the-united-states", "name": "Constitution", "type": "Foundation",
        "cost_status": "root_total", "resolved_total_amount": 1000.0,
        "__budgetSummary": {"record_date": "2026-08-31", "government_total_outlay_amount": 1000.0},
        "__sourceRegistry": {"sources": [{"id": "s1", "copy": {"date": "2026-08-31"}, "statusAtBuild": "current", "expected": {"next": "2026-09-30"}}]},
        "children": [
            {"id": "exec", "name": "Executive", "type": "Branch", "cost_status": "official", "resolved_total_amount": 600.0,
             "verificationMethod": "name_labelled_on_own_official_page", "sourceUrls": ["https://www.whitehouse.gov/"],
             "children": [
                 {"id": "dept", "name": "Department", "type": "Department", "cost_status": "official", "resolved_total_amount": 400.0,
                  "cost_weight_dispute": {"period": "2025-03", "curatedEmployees": "~350", "officialEmployees": 287, "url": "https://www.opm.gov/x.zip"},
                  "children": [
                      {"id": "sec", "name": "Secretary", "type": "Position", "cost_status": "unavailable",
                       "positionSchedulePay": {"amount": 253100.0, "url": "https://uscode.house.gov/5312"}, "children": []},
                      {"id": "gc", "name": "General Counsel", "type": "Position", "cost_status": "unavailable",
                       "positionPayRate": {"amount": 197200.0, "url": "https://www.opm.gov/ex"}, "children": []},
                      {"id": "bureau", "name": "Bureau", "type": "Bureau", "cost_status": "allocated", "resolved_total_amount": 100.0,
                       "verificationFailure": "not_found", "children": []},
                  ]},
             ]},
            {"id": "leg", "name": "Legislative", "type": "Branch", "cost_status": "official", "resolved_total_amount": 300.0,
             "placementDirectoryDisagreement": {"source": "us_government_manual", "listedUnder": "Elsewhere", "directoryParentId": "x", "url": "https://www.govinfo.gov/g"},
             "children": []},
            {"id": "jud", "name": "Judicial", "type": "Branch", "cost_status": "official", "resolved_total_amount": 100.0, "children": []},
        ],
    }


class DiffTests(unittest.TestCase):
    def test_an_unchanged_graph_is_within_the_budget_and_touches_nothing(self):
        g = small_graph()
        entry = ch.diff_graphs(g, copy.deepcopy(g), built_at="2026-10-22T00:00:00Z")
        self.assertFalse(entry["budget"]["held"])
        self.assertEqual(entry["touched"], [])
        self.assertEqual({r["rule"] for r in entry["budget"]["rules"]}, set(ch.BUDGET_RULES))
        self.assertIn("within the change budget", entry["summary"])

    def _rules(self, before, after):
        entry = ch.diff_graphs(before, after, built_at="2026-10-22T00:00:00Z")
        return {r["rule"]: r["tripped"] for r in entry["budget"]["rules"]}, entry

    def test_a_build_that_read_no_statement_is_held_and_a_carried_forward_baseline_is_not_blamed_again(self):
        base = small_graph()
        after = copy.deepcopy(base); after["__budgetSummary"]["reused_from_previous_build"] = True
        rules, entry = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_REBUILT_WITHOUT_STATEMENT]); self.assertTrue(entry["budget"]["held"])
        self.assertFalse(rules[ch.RULE_NODE_COUNT]); self.assertFalse(rules[ch.RULE_MEASURED_SAME_STATEMENT])
        rules, entry = self._rules(after, copy.deepcopy(after))
        self.assertFalse(rules[ch.RULE_REBUILT_WITHOUT_STATEMENT], "blamed once, when it began")
        rules, _ = self._rules(base, copy.deepcopy(base))
        self.assertFalse(rules[ch.RULE_REBUILT_WITHOUT_STATEMENT])
        self.assertEqual(ch.BUDGET_RULES[:5], ch.BUDGET_RULES_ORIGINAL)
        self.assertEqual(tuple(gate.CHANGE_BUDGET_RULES), ch.BUDGET_RULES)

    def test_the_gate_accepts_the_original_five_rules_only_on_an_entry_recorded_before_the_sixth_existed(self):
        import tempfile
        history = json.loads(HISTORY.read_text(encoding="utf-8"))
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

        def budget_violations(entries):
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                (tmp / "graph.json").write_text("{}", encoding="utf-8")
                (tmp / "change_history.json").write_text(json.dumps(entries), encoding="utf-8")
                return [v for v in gate.change_history_violations(graph, tmp / "graph.json", gate.label, QUEUE) if "budget rule" in v]

        five = copy.deepcopy(history[0])
        five["budget"]["rules"] = [r for r in five["budget"]["rules"] if r["rule"] in ch.BUDGET_RULES_ORIGINAL]
        five["builtAt"] = "2026-10-22T08:00:00Z"
        self.assertEqual(budget_violations([five, five]), [], "recorded before the sixth rule existed")
        five["builtAt"] = gate.CHANGE_BUDGET_SIXTH_RULE_FROM + "T08:00:00Z"
        self.assertTrue(budget_violations([five]), "recorded after it, so it must carry all six")
        six = copy.deepcopy(five)
        six["budget"]["rules"] = [{"rule": r, "tripped": False, "detail": "x"} for r in ch.BUDGET_RULES]
        self.assertEqual(budget_violations([six]), [])

    def test_an_event_record_stays_open_until_a_person_resolves_it_and_a_condition_record_closes(self):
        today = "2026-10-25"
        event = {"key": "e1", "kind": "measured_cost_moved_with_new_statement", "status": "open", "opened": "2026-10-22", "closed": None}
        condition = {"key": "c1", "kind": "placement_directory_disagreement", "status": "open", "opened": "2026-10-22", "closed": None}
        resolved = {"key": "e2", "kind": "node_removed", "status": "resolved", "resolution": "intended", "opened": "2026-10-20", "closed": None}
        out = {r["key"]: r for r in ch.merge_queue([event, condition, resolved], [], today)}
        self.assertEqual(out["e1"]["status"], "open", "the next build finds nothing, but nobody has looked")
        self.assertEqual(out["c1"]["status"], "closed")
        self.assertEqual(out["c1"]["closed"], today)
        self.assertEqual(out["e2"]["status"], "resolved")
        self.assertEqual(out["e2"]["resolution"], "intended")
        for kind in ch.EVENT_QUEUE_KINDS:
            self.assertIn(kind, ch.QUEUE_KINDS)
        for kind in ("placement_directory_disagreement", "cost_weight_dispute", "verification_failure", "source_overdue"):
            self.assertNotIn(kind, ch.EVENT_QUEUE_KINDS)

    def test_each_budget_rule_trips_on_its_own_case(self):
        base = small_graph()
        # the node count drops
        after = copy.deepcopy(base); after["children"][0]["children"][0]["children"].pop(2)
        rules, entry = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_NODE_COUNT]); self.assertFalse(rules[ch.RULE_MEASURED_SAME_STATEMENT])
        self.assertEqual([x["id"] for x in entry["nodes"]["removed"]], ["bureau"])
        # a measured cost moves with the SAME statement
        after = copy.deepcopy(base); after["children"][0]["children"][0]["resolved_total_amount"] = 401.0
        rules, entry = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_MEASURED_SAME_STATEMENT]); self.assertFalse(rules[ch.RULE_NODE_COUNT])
        self.assertEqual(entry["measuredCosts"]["moved"][0]["id"], "dept")
        # the same move with a NEW statement is explained, not held, and large moves go to review
        after["__budgetSummary"]["record_date"] = "2026-09-30"
        after["children"][0]["children"][0]["resolved_total_amount"] = 2_500_000_000.0
        after["children"][0]["resolved_total_amount"] = 2_500_000_600.0
        before = copy.deepcopy(base); before["children"][0]["children"][0]["resolved_total_amount"] = 1_000_000_000.0
        rules, entry = self._rules(before, after)
        self.assertFalse(rules[ch.RULE_MEASURED_SAME_STATEMENT]); self.assertFalse(entry["budget"]["held"])
        # both the department and its parent moved by more than half on more than $1bn
        self.assertEqual({x["id"] for x in entry["measuredCosts"]["forReview"]}, {"dept", "exec"})
        # the anchor goes backwards
        after = copy.deepcopy(base); after["__budgetSummary"]["record_date"] = "2026-07-31"
        rules, _ = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_ANCHOR_BACKWARDS])
        # the anchor is lost
        after = copy.deepcopy(base); after["__budgetSummary"] = {}
        rules, _ = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_ANCHOR_LOST])
        # more than 5% of pay claims withdrawn (here one of two)
        after = copy.deepcopy(base); after["children"][0]["children"][0]["children"][1].pop("positionPayRate")
        rules, entry = self._rules(base, after)
        self.assertTrue(rules[ch.RULE_PAY_WITHDRAWN])
        self.assertEqual(entry["pay"]["withdrawn"][0]["field"], "positionPayRate")
        self.assertEqual(entry["pay"]["withdrawn"][0]["document"], "https://www.opm.gov/ex")
        self.assertIn("no longer applies", entry["pay"]["withdrawn"][0]["why"])

    def test_added_withdrawn_renamed_and_sourced_changes_are_read(self):
        base = small_graph()
        after = copy.deepcopy(base)
        dept = after["children"][0]["children"][0]
        dept["name"] = "Department of Things"
        dept["children"][0]["positionSchedulePay"]["amount"] = 260000.0
        dept["children"].append({"id": "new", "name": "New Office", "type": "Office", "cost_status": "allocated", "resolved_total_amount": 1.0, "children": []})
        after["children"][0].pop("verificationMethod")
        dept["usaspendingOutlays"] = {"amount": 5.0, "url": "https://api.usaspending.gov/x"}
        after["children"][1]["lifecycle"] = "superseded"; after["children"][1]["supersededOn"] = "2026-07-14"
        entry = ch.diff_graphs(base, after, built_at="2026-10-22T00:00:00Z")
        self.assertEqual([x["id"] for x in entry["nodes"]["added"]], ["new"])
        self.assertEqual(entry["nodes"]["renamed"], [{"id": "dept", "before": "Department", "after": "Department of Things"}])
        self.assertEqual([x["id"] for x in entry["nodes"]["newlySuperseded"]], ["leg"])
        self.assertEqual(entry["pay"]["moved"][0]["after"], [260000.0])
        self.assertEqual(entry["evidence"]["withdrawn"][0]["method"], "name_labelled_on_own_official_page")
        self.assertEqual([x["id"] for x in entry["sourcedFigures"]["usaspendingOutlays"]["added"]], ["dept"])
        self.assertEqual(sorted(entry["touched"]), ["dept", "exec", "leg", "new", "sec"])

    def test_the_queue_holds_the_graphs_disagreements_and_merges_without_deleting(self):
        base = small_graph()
        entry = ch.diff_graphs(base, copy.deepcopy(base), built_at="2026-10-22T00:00:00Z")
        queue = ch.review_queue(entry, base, [], today="2026-10-22")
        kinds = sorted(r["kind"] for r in queue)
        self.assertEqual(kinds, ["cost_weight_dispute", "placement_directory_disagreement", "verification_failure"])
        for record in queue:
            self.assertEqual(record["status"], "open")
            self.assertEqual(len(record["documents"]), 2, record)
        # a person resolves one; the next run keeps that and the opening date
        queue[0]["status"] = "resolved"; queue[0]["resolution"] = "the Manual's placement is right; re-parent in curation"
        later = ch.review_queue(entry, base, queue, today="2026-11-22")
        kept = next(r for r in later if r["key"] == queue[0]["key"])
        self.assertEqual(kept["status"], "resolved"); self.assertEqual(kept["opened"], "2026-10-22"); self.assertIn("re-parent", kept["resolution"])
        # a condition that vanishes is closed, never deleted
        fixed = copy.deepcopy(base); fixed["children"][0]["children"][0].pop("cost_weight_dispute")
        later = ch.review_queue(ch.diff_graphs(base, fixed, built_at="2026-12-01T00:00:00Z"), fixed, queue, today="2026-12-01")
        closed = [r for r in later if r["kind"] == "cost_weight_dispute"]
        self.assertEqual(len(closed), 1); self.assertEqual(closed[0]["status"], "closed"); self.assertEqual(closed[0]["closed"], "2026-12-01")
        # a held build opens a budget_hold record with the rule's detail
        broken = copy.deepcopy(base); broken["children"][2]["children"] = []; broken["children"].pop(2)
        held_entry = ch.diff_graphs(base, broken, built_at="2026-12-02T00:00:00Z")
        held_queue = ch.review_queue(held_entry, broken, later, today="2026-12-02")
        self.assertTrue(any(r["kind"] == "budget_hold" and "node_count_drops" in r["detail"] for r in held_queue))
        self.assertTrue(any(r["kind"] == "node_removed" and r["nodeId"] == "jud" for r in held_queue))


class PublishedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PUBLISHED.is_file() and HISTORY.is_file() and QUEUE.is_file()):
            raise unittest.SkipTest("no published graph with a recorded history")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cls.history = json.loads(HISTORY.read_text(encoding="utf-8"))
        cls.queue = json.loads(QUEUE.read_text(encoding="utf-8"))

    def test_the_latest_entry_describes_the_published_graph_and_the_gate_accepts_it(self):
        self.assertEqual(gate.change_history_violations(self.graph, PUBLISHED, gate.label), [])
        latest = self.history[0]
        self.assertFalse(latest.get("trimmed"))
        self.assertEqual(latest["nodes"]["after"], sum(1 for _ in ch.walk(self.graph)))
        self.assertIn("reviewQueueOpen", latest)

    def test_the_queue_holds_exactly_the_graphs_open_disagreements(self):
        expected = gate.review_queue_expected_keys(self.graph)
        open_keys = {r["key"] for r in self.queue if r["kind"] in gate.REVIEW_QUEUE_GRAPH_KINDS and r["status"] in ("open", "resolved")}
        self.assertEqual(open_keys, expected)
        self.assertTrue(any(r["kind"] == "source_overdue" for r in self.queue))

    def test_the_committed_document_is_what_the_script_renders(self):
        if not DOC.exists():
            self.skipTest("no committed document")
        self.assertEqual(DOC.read_text(encoding="utf-8"), render(self.history, self.queue))

    def test_each_corruption_is_refused(self):
        def run(mutate_history=None, mutate_queue=None, mutate_graph=None):
            import tempfile
            graph = copy.deepcopy(self.graph)
            history = copy.deepcopy(self.history)
            queue = copy.deepcopy(self.queue)
            if mutate_graph: mutate_graph(graph)
            if mutate_history: mutate_history(history)
            if mutate_queue: mutate_queue(queue)
            with tempfile.TemporaryDirectory(dir=str(PROJECT_ROOT / "tests" / ".tmp")) as tmp:
                d = Path(tmp)
                (d / "graph.json").write_text("{}", encoding="utf-8")
                (d / "change_history.json").write_text(json.dumps(history), encoding="utf-8")
                q = d / "review_queue.json"; q.write_text(json.dumps(queue), encoding="utf-8")
                return gate.change_history_violations(graph, d / "graph.json", gate.label, queue_path=q)
        (PROJECT_ROOT / "tests" / ".tmp").mkdir(exist_ok=True)
        self.assertEqual(run(), [])
        cases = {
            "node count misreported": dict(mutate_history=lambda h: h[0]["nodes"].__setitem__("after", 1)),
            "anchor misreported": dict(mutate_history=lambda h: h[0]["anchor"]["after"].__setitem__("recordDate", "1999-01-31")),
            "pay claims misreported": dict(mutate_history=lambda h: h[0]["pay"].__setitem__("claimsAfter", 0)),
            "held disagrees with the rules": dict(mutate_history=lambda h: h[0]["budget"].__setitem__("held", True)),
            "a rule dropped": dict(mutate_history=lambda h: h[0]["budget"]["rules"].pop()),
            "latest entry trimmed": dict(mutate_history=lambda h: h[0].__setitem__("trimmed", True)),
            "future build": dict(mutate_history=lambda h: h[0].__setitem__("builtAt", "2099-01-01T00:00:00Z")),
            "a disagreement record deleted": dict(mutate_queue=lambda q: q.remove(next(r for r in q if r["kind"] == "placement_directory_disagreement"))),
            "a disagreement record closed while the graph still publishes it": dict(mutate_queue=lambda q: next(r for r in q if r["kind"] == "cost_weight_dispute").__setitem__("status", "closed")),
            "a record for a disagreement the graph does not publish": dict(mutate_queue=lambda q: q.append(dict(q[0], key="cost_weight_dispute:000000000000", kind="cost_weight_dispute"))),
            "a record of unknown kind": dict(mutate_queue=lambda q: q[0].__setitem__("kind", "vibes")),
            "a record with no documents": dict(mutate_queue=lambda q: q[0].__setitem__("documents", [])),
            "a duplicate key": dict(mutate_queue=lambda q: q.append(dict(q[0]))),
            "the graph grew a disagreement the queue lacks": dict(mutate_graph=lambda g: g["children"][0].__setitem__("placementDirectoryDisagreement", {"source": "x", "listedUnder": "y"})),
        }
        for name, kwargs in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(run(**kwargs), [], name)


if __name__ == "__main__":
    unittest.main()
