"""Recorded decisions to keep a name a document was read and does not carry:
the refusals, the decided set, the report's class, and the gate's stdlib mirror
equal to the module in both directions."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.verification import name_decisions as nd
from scripts import validate_published_graph as gate
from scripts.report_evidence_coverage import classify

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"


def _row(**over):
    row = {"name": "Some Unit", "kind": "graphs_own_grouping", "basis": "the graph's own grouping", "source": "name_decisions"}
    row.update(over)
    return row


def _node(**over):
    node = {"id": "n1", "name": "Some Unit", "verificationFailure": "not_found"}
    node.update(over)
    return node


class RefusalTests(unittest.TestCase):
    def test_a_good_row_stands(self):
        self.assertIsNone(nd.refusal(_row(), _node()))

    def test_each_refusal_fires(self):
        self.assertIn("not in the graph", nd.refusal(_row(), None))
        self.assertIn("no longer carries the name", nd.refusal(_row(), _node(name="Renamed Unit")))
        self.assertIn("no basis", nd.refusal(_row(basis=""), _node()))
        self.assertIn("vocabulary", nd.refusal(_row(kind="vibes"), _node()))
        self.assertIn("no negative", nd.refusal(_row(), _node(verificationFailure=None)))

    def test_the_kind_vocabulary_binds_this_table_only(self):
        """A curatedNames row carries a list disposition, not a name-decision kind."""
        self.assertIsNone(nd.refusal(_row(source="list_dispositions", kind="not_carried_by_the_list"), _node()))

    def test_decided_ids_and_refusals(self):
        rows = {"n1": _row(), "n2": _row(name="Gone"), "n3": _row()}
        nodes = [_node(), _node(id="n2", name="Other"), _node(id="n3", verificationFailure=None)]
        decided, refused = nd.decided_ids(nodes, rows)
        self.assertEqual(decided, {"n1"})
        # only a node that still carries a negative reports a stale row
        self.assertEqual(set(refused), {"n2"})


class ClassTests(unittest.TestCase):
    def test_a_decision_changes_the_count_not_the_negative(self):
        node = _node()
        self.assertEqual(classify(node, frozenset()), "negative_read")
        self.assertEqual(classify(node, frozenset({"n1"})), "decided_negative")
        self.assertEqual(node["verificationFailure"], "not_found")


class PublishedGraphTests(unittest.TestCase):
    def _nodes(self):
        if not GRAPH.exists():
            self.skipTest("no published graph")
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        out, stack = [], [graph]
        while stack:
            n = stack.pop()
            out.append(n)
            stack.extend(n.get("children") or [])
        return out

    def test_the_gate_mirror_equals_the_module(self):
        nodes = self._nodes()
        self.assertEqual(gate.name_decisions_standing(nodes), nd.decided_ids(nodes))
        self.assertEqual(tuple(gate.NAME_DECISION_KINDS), nd.KINDS)

    def test_no_row_is_stale_on_the_published_graph(self):
        decided, refused = nd.decided_ids(self._nodes())
        self.assertEqual(refused, {})
        self.assertGreater(len(decided), 0)

    def test_every_row_has_a_quoted_page_or_a_basis(self):
        table = json.loads((PROJECT_ROOT / "data" / "curation" / "name_decisions.json").read_text(encoding="utf-8"))
        for row in table["decisions"]:
            self.assertTrue(row["basis"].strip(), row["nodeId"])
            self.assertIn(row["kind"], nd.KINDS, row["nodeId"])
            if row["kind"] == "page_prints_another_wording":
                self.assertTrue(row.get("url", "").startswith("https://"), row["nodeId"])
                self.assertTrue(row.get("observed", "").strip(), row["nodeId"])

    def test_a_decision_never_removes_the_negative(self):
        nodes = self._nodes()
        by_id = {n.get("id"): n for n in nodes}
        decided, _ = nd.decided_ids(nodes)
        for node_id in decided:
            self.assertTrue(by_id[node_id].get("verificationFailure"), node_id)
            self.assertFalse(by_id[node_id].get("verificationMethod"), node_id)


if __name__ == "__main__":
    unittest.main()
