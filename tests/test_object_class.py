"""USAspending's FY2025 object-class breakdown (`spendingByKind`), both ways:
the module and the gate agree on the committed fixtures, every published
block passes, and each corruption the gate exists for fails."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, index_tree, load_base_graph  # noqa: E402
from data_pipeline.verification import object_class  # noqa: E402
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from data_pipeline.verification.usaspending import load_crosswalk  # noqa: E402
from scripts.validate_published_graph import (  # noqa: E402
    OBJECT_CLASS_AGENCIES,
    OBJECT_CLASS_FISCAL_YEAR,
    spending_by_kind_violations,
)

BASE = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
GRAPH = PROJECT_ROOT / "output" / "graph.json"
label = lambda node: str(node.get("id"))


def derive():
    node_map, _ = index_tree(load_base_graph(BASE))
    return object_class.build_records(node_map, load_crosswalk())


class ModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.report = derive()

    def test_mirror_equals_the_derive_step(self):
        self.assertEqual({k: r["toptierCode"] for k, r in self.records.items()}, OBJECT_CLASS_AGENCIES)
        self.assertEqual(OBJECT_CLASS_FISCAL_YEAR, object_class.FISCAL_YEAR)

    def test_committed_evidence_is_the_derive_steps_output(self):
        store = json.loads(object_class.DEFAULT_EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(store["nodes"], self.records)

    def test_endpoints_that_disagree_are_refused(self):
        reason = self.report["refused"]["exec-ind-misc-appalachian-regional-commission-arc"]
        self.assertTrue(reason.startswith("endpoints_disagree"))

    def test_staff_pay_is_11_and_12_and_never_13(self):
        for record in self.records.values():
            codes = [row[0] for row in record["staffPay"]["classes"]]
            self.assertTrue(codes and all(c.startswith(("11.", "12.")) for c in codes))
            self.assertAlmostEqual(record["staffPay"]["amount"], sum(r[2] for r in record["staffPay"]["classes"]), places=2)
            self.assertGreater(record["staffPay"]["amount"], 0)

    def test_field_is_owned_and_kept_for_the_viewer(self):
        self.assertIn(object_class.FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(object_class.FIELD, MINIMAL_GRAPH_FIELDS)

    def test_apply_refuses_a_post_and_withdraws(self):
        root = load_base_graph(BASE)
        node_map, _ = index_tree(root)
        post = next(n for n in node_map.values() if "position" in str(n.get("type") or "").lower())
        record = dict(next(iter(self.records.values())), nodeId=post["id"])
        post[object_class.FIELD] = {"stale": True}
        stats = object_class.apply_evidence(root, {post["id"]: record}, index_tree=index_tree)
        self.assertEqual(stats["applied"], 0)
        self.assertNotIn(object_class.FIELD, post)


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        cls.nodes = {k: n for k, n in node_map.items() if isinstance(n.get("spendingByKind"), dict)}

    def fails(self, node, block=None):
        return spending_by_kind_violations(node, block if block is not None else node["spendingByKind"], label)

    def test_every_published_block_passes(self):
        self.assertEqual(set(self.nodes), set(OBJECT_CLASS_AGENCIES))
        for node in self.nodes.values():
            self.assertEqual(self.fails(node), [], node["id"])

    def corrupt(self, mutate, node_mutate=None):
        node = copy.deepcopy(self.nodes["exec-regulatory-fcc"])
        mutate(node["spendingByKind"])
        if node_mutate:
            node_mutate(node)
        self.assertTrue(self.fails(node))

    def test_on_a_post(self):
        self.corrupt(lambda b: None, lambda n: n.update(type="Position"))

    def test_on_a_node_the_crosswalk_does_not_reach(self):
        self.corrupt(lambda b: None, lambda n: n.update(id="exec-dept-usda"))

    def test_staff_pay_not_the_sum(self):
        self.corrupt(lambda b: b["staffPay"].update(amount=b["staffPay"]["amount"] + 1))

    def test_staff_pay_dropping_a_row(self):
        self.corrupt(lambda b: b["staffPay"]["classes"].pop())

    def test_staff_pay_claiming_former_personnel(self):
        self.corrupt(lambda b: b["staffPay"]["classes"].append(["13.0", "Benefits for former personnel", 1.0]))

    def test_missing_fiscal_year(self):
        self.corrupt(lambda b: b.pop("fiscalYear"))

    def test_total_altered(self):
        self.corrupt(lambda b: b.update(totalObligations=b["totalObligations"] * 1000))

    def test_class_figure_altered(self):
        self.corrupt(lambda b: b["classes"][0].__setitem__(1, b["classes"][0][1] + 5))

    def test_digest_mismatch(self):
        self.corrupt(lambda b: b["documents"]["minor"].update(sha256="0" * 64))

    def test_equal_to_measured_cost(self):
        self.corrupt(lambda b: None, lambda n: n.update(cost_status="official",
                                                         resolved_total_amount=n["spendingByKind"]["totalObligations"]))

    def test_url_among_sources(self):
        self.corrupt(lambda b: None, lambda n: n.update(sourceUrls=[b_url(n)]))

    def test_renamed_node(self):
        self.corrupt(lambda b: None, lambda n: n.update(name="Some Other Commission"))


def b_url(node):
    return node["spendingByKind"]["documents"]["minor"]["url"]


if __name__ == "__main__":
    unittest.main()
