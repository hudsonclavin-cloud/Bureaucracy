"""How a measured unit's total adds up: the parts are the committed statement's
own, landed as the tree lands them; the gate re-derives them and refuses every
corruption; the published graph carries a block on every measured unit whose
header has parts."""

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
from data_pipeline.exporter import treasury_sums as ts  # noqa: E402
from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, index_tree  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def _find(root, node_id):
    return index_tree(root)[0][node_id]


class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.is_file():
            raise unittest.SkipTest("no published graph")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cls.nodes = [n for n, _ in gate.walk(cls.graph)]

    def test_the_field_is_in_the_viewer_copy(self):
        self.assertIn(ts.FIELD, MINIMAL_GRAPH_FIELDS)

    def test_every_measured_unit_whose_header_has_parts_carries_a_block_and_the_gate_passes(self):
        self.assertEqual(gate.treasury_sum_violations(self.nodes, self.graph, gate.label), [])
        blocks = [n for n in self.nodes if isinstance(n.get(ts.FIELD), dict)]
        self.assertGreater(len(blocks), 40)
        for node in blocks:
            block = node[ts.FIELD]
            with self.subTest(node=node["id"]):
                self.assertAlmostEqual(block["total"], float(node["resolved_total_amount"]), places=2)
                self.assertAlmostEqual(block["partsSum"], sum(p["amount"] for p in block["parts"]), places=2)
                self.assertAlmostEqual(block["notAttributed"], block["total"] - block["partsSum"], places=2)
                self.assertAlmostEqual(block["landedOnChildren"] + block["appliedElsewhere"] + block["toNoNode"], block["partsSum"], places=2)

    def test_the_va_names_the_statements_departmental_administration_as_reaching_no_node(self):
        va = _find(self.graph, "exec-dept-va")
        block = va.get(ts.FIELD)
        self.assertIsInstance(block, dict)
        names = {p["name"]: p for p in block["parts"]}
        self.assertEqual(names["Departmental Administration"]["where"], ts.WHERE_NONE)
        self.assertEqual(names["Veterans Health Administration"]["nodeId"], "exec-dept-va-vha")
        self.assertEqual(names["Veterans Health Administration"]["where"], ts.WHERE_CHILD)
        self.assertEqual({c["id"] for c in block["estimatedChildren"]}, {"exec-dept-va-nca", "exec-dept-va-bva"})
        self.assertEqual(block["notAttributed"], 0.0)
        self.assertTrue(any(p["kind"] == ts.KIND_RECEIPTS and p["nodeId"] == "exec-dept-va--treasury-receipts" for p in block["parts"]))

    def test_the_tax_court_is_measured_elsewhere_inside_the_legislative_total(self):
        leg = _find(self.graph, "legislative-branch")[ts.FIELD]
        part = next(p for p in leg["parts"] if p["name"] == "United States Tax Court")
        self.assertEqual(part["where"], ts.WHERE_ELSEWHERE)
        self.assertEqual(part["nodeId"], "jud-specialized-tax")
        self.assertGreater(leg["appliedElsewhere"], 0)

    def test_the_pass_is_idempotent_and_clears_before_it_recomputes(self):
        graph = copy.deepcopy(self.graph)
        va = _find(graph, "exec-dept-va")
        va[ts.FIELD] = {"stale": True}
        _find(graph, "exec-dept-va-vha")[ts.FIELD] = {"stale": True}
        stats = ts.annotate_treasury_sums(graph)
        self.assertGreater(stats["stamped"], 40)
        self.assertNotIn("stale", _find(graph, "exec-dept-va")[ts.FIELD])
        again = copy.deepcopy(graph)
        ts.annotate_treasury_sums(again)
        self.assertEqual(_find(again, "exec-dept-va")[ts.FIELD], _find(graph, "exec-dept-va")[ts.FIELD])
        self.assertEqual(gate.treasury_sum_violations([n for n, _ in gate.walk(graph)], graph, gate.label), [])

    def test_no_committed_statement_means_no_block_and_a_reason(self):
        graph = copy.deepcopy(self.graph)
        graph["__budgetSummary"]["record_date"] = "1999-01-31"
        stats = ts.annotate_treasury_sums(graph)
        self.assertEqual(stats["stamped"], 0)
        self.assertEqual(stats["reason"], "no_committed_statement_for_the_anchor_date")
        self.assertFalse(any(ts.FIELD in n for n, _ in gate.walk(graph)))


class GateCorruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.is_file():
            raise unittest.SkipTest("no published graph")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

    def _violations(self, corrupt):
        graph = copy.deepcopy(self.graph)
        nodes = index_tree(graph)[0]
        corrupt(graph, nodes)
        return gate.treasury_sum_violations([n for n, _ in gate.walk(graph)], graph, gate.label)

    def test_each_corruption_is_refused(self):
        va = "exec-dept-va"
        cases = {
            "a part's amount changed": lambda g, n: n[va][ts.FIELD]["parts"][0].__setitem__("amount", 1.0),
            "a part dropped": lambda g, n: n[va][ts.FIELD]["parts"].pop(),
            "a part renamed": lambda g, n: n[va][ts.FIELD]["parts"][0].__setitem__("name", "Something"),
            "a landing moved": lambda g, n: n[va][ts.FIELD]["parts"][1].__setitem__("nodeId", "exec-dept-va-nca"),
            "a landing's where changed": lambda g, n: n[va][ts.FIELD]["parts"][1].__setitem__("where", "none"),
            "a no-node part given a node": lambda g, n: next(p for p in n[va][ts.FIELD]["parts"] if p["where"] == "none").__setitem__("nodeId", "exec-dept-va-nca"),
            "the total changed": lambda g, n: n[va][ts.FIELD].__setitem__("total", 1.0),
            "partsSum changed": lambda g, n: n[va][ts.FIELD].__setitem__("partsSum", 1.0),
            "toNoNode changed": lambda g, n: n[va][ts.FIELD].__setitem__("toNoNode", 1.0),
            "notAttributed invented": lambda g, n: n[va][ts.FIELD].__setitem__("notAttributed", 5.0),
            "an estimated child dropped": lambda g, n: n[va][ts.FIELD]["estimatedChildren"].pop(),
            "a statement date not committed": lambda g, n: n[va][ts.FIELD].__setitem__("statementDate", "1999-01-31"),
            "another node's classification id": lambda g, n: n[va][ts.FIELD].__setitem__("classificationId", "1"),
            "an extra key on the block": lambda g, n: n[va][ts.FIELD].__setitem__("sentence", "x"),
            "an extra key on a part": lambda g, n: n[va][ts.FIELD]["parts"][0].__setitem__("note", "x"),
            "a block on a post": lambda g, n: n["exec-dept-va-inspector-general"].__setitem__(ts.FIELD, dict(n[va][ts.FIELD])),
            "a block on an estimate": lambda g, n: n["exec-dept-va-nca"].__setitem__(ts.FIELD, dict(n[va][ts.FIELD])),
            "a block on the receipts line": lambda g, n: n["exec-dept-va--treasury-receipts"].__setitem__(ts.FIELD, dict(n[va][ts.FIELD])),
            "a measured unit's block removed": lambda g, n: n[va].pop(ts.FIELD),
            "not an object": lambda g, n: n[va].__setitem__(ts.FIELD, "yes"),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self._violations(corrupt), [], name)


if __name__ == "__main__":
    unittest.main()
