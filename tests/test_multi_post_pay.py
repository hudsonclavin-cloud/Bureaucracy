"""A pay figure on a node that stands for several posts: which fields may
carry one, what they must say, and how the gate checks it.

Until 2026-09-23 every pay field was stripped from every multi-post node. That
was right for a listing's rate and wrong for a tier's -- "District Judge (×28
active)" carries 28 posts each paid the district-judge rate by statute -- so
the rule is per field now, and this file pins it in both directions: an
office-rate figure stays with a `holders` block the sweep recomputes from the
node's own stated count, a listing-based figure is stripped, and a roster
figure stays only when the roster listed every holder at one rate.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification.pay_tables import (
    INCUMBENCY_PAY_FIELDS,
    OFFICE_RATE_PAY_FIELDS,
    UNIFORM_ROSTER_PAY_FIELDS,
    holders_for,
    withdraw_pay_from_multi_post_nodes,
)
from data_pipeline.verification.pay_documents import PAY_FIELDS
from scripts import validate_published_graph as gate

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _label(node):
    return "node {!r}".format(node.get("id"))


def _tree():
    return {
        "id": "root", "name": "Root", "type": "Foundation",
        "children": [
            {"id": "bench", "name": "Judge (×18)", "type": "Position",
             "representsPosts": {"text": "×18", "kind": "exact", "count": 18},
             "positionStatutoryPay": {"amount": 1.0},
             "positionDerivedPay": {"amount": 1.0},
             "positionTierPay": {"minimum": 1.0, "maximum": 2.0},
             "positionPayRate": {"amount": 1.0},
             "positionGradePay": {"minimum": 1.0, "maximum": 2.0},
             "positionCurrentPay": {"amount": 1.0},
             "positionSchedulePay": {"amount": 1.0}},
            {"id": "roster-uniform", "name": "Special Assistant (×4)", "type": "Position",
             "representsPosts": {"text": "×4", "kind": "exact", "count": 4},
             "positionReportedPay": {"amount": 1.0, "holders": {"count": 4, "uniformRate": True, "note": "each"}}},
            {"id": "roster-wrong-count", "name": "Press Assistant (×2)", "type": "Position",
             "representsPosts": {"text": "×2", "kind": "exact", "count": 2},
             "positionReportedPay": {"amount": 1.0, "holders": {"count": 3, "uniformRate": True, "note": "each"}}},
            {"id": "roster-no-claim", "name": "Advisor (×5)", "type": "Position",
             "representsPosts": {"text": "×5", "kind": "exact", "count": 5},
             "positionReportedPay": {"amount": 1.0}},
            {"id": "single", "name": "Chief Judge", "type": "Position",
             "positionStatutoryPay": {"amount": 1.0, "holders": {"text": "×2", "kind": "exact", "count": 2}}},
        ],
    }


class FieldClassTests(unittest.TestCase):
    def test_every_pay_field_is_classified_exactly_once(self):
        classified = set(INCUMBENCY_PAY_FIELDS) | set(OFFICE_RATE_PAY_FIELDS) | set(UNIFORM_ROSTER_PAY_FIELDS)
        self.assertEqual(set(PAY_FIELDS), classified)
        self.assertEqual(
            len(PAY_FIELDS),
            len(INCUMBENCY_PAY_FIELDS) + len(OFFICE_RATE_PAY_FIELDS) + len(UNIFORM_ROSTER_PAY_FIELDS))

    def test_the_gate_mirrors_the_classes(self):
        self.assertEqual(set(INCUMBENCY_PAY_FIELDS), set(gate.INCUMBENCY_PAY_FIELDS))
        self.assertEqual(set(OFFICE_RATE_PAY_FIELDS), set(gate.OFFICE_RATE_PAY_FIELDS))
        self.assertEqual(set(UNIFORM_ROSTER_PAY_FIELDS), set(gate.UNIFORM_ROSTER_PAY_FIELDS))

    def test_a_listing_based_figure_is_never_an_office_rate(self):
        for field in ("positionPayRate", "positionGradePay", "positionCurrentPay", "positionSchedulePay"):
            self.assertIn(field, INCUMBENCY_PAY_FIELDS)
        for field in ("positionStatutoryPay", "positionDerivedPay", "positionTierPay"):
            self.assertIn(field, OFFICE_RATE_PAY_FIELDS)


class SweepTests(unittest.TestCase):
    def setUp(self):
        self.tree = _tree()
        self.withdrawn = withdraw_pay_from_multi_post_nodes(self.tree)
        self.by_id = {n["id"]: n for n in self.tree["children"]}

    def test_listing_based_fields_are_stripped_from_a_multi_post_node(self):
        bench = self.by_id["bench"]
        for field in INCUMBENCY_PAY_FIELDS:
            self.assertNotIn(field, bench)

    def test_office_rate_fields_stay_and_gain_holders(self):
        bench = self.by_id["bench"]
        for field in OFFICE_RATE_PAY_FIELDS:
            self.assertIn(field, bench)
            holders = bench[field]["holders"]
            self.assertEqual("×18", holders["text"])
            self.assertEqual(18, holders["count"])
            self.assertTrue(holders["appliesToEachHolder"])
            self.assertIn("each holder alike", holders["note"])

    def test_holders_is_recomputed_from_the_nodes_own_count(self):
        bench = self.by_id["bench"]
        bench["representsPosts"] = {"text": "×19", "kind": "exact", "count": 19}
        withdraw_pay_from_multi_post_nodes(self.tree)
        self.assertEqual(19, bench["positionStatutoryPay"]["holders"]["count"])

    def test_a_multiplicity_the_sweep_cannot_read_strips_every_field(self):
        """A bare count where `annotate_stated_counts` writes a dict is still
        a multiplicity, and nothing can say "for each of N" off it. The gate
        refuses the same form (`holders_violations`), so the two agree."""
        bench = self.by_id["bench"]
        self.assertTrue(any(field in bench for field in OFFICE_RATE_PAY_FIELDS))
        bench["representsPosts"] = 18
        withdrawn = withdraw_pay_from_multi_post_nodes(self.tree)
        self.assertGreaterEqual(withdrawn, 1)
        for field in INCUMBENCY_PAY_FIELDS + OFFICE_RATE_PAY_FIELDS + UNIFORM_ROSTER_PAY_FIELDS:
            self.assertNotIn(field, bench)

    def test_a_uniform_roster_figure_stays_when_its_count_is_the_names(self):
        node = self.by_id["roster-uniform"]
        self.assertIn("positionReportedPay", node)
        self.assertEqual("×4", node["positionReportedPay"]["holders"]["text"])
        self.assertTrue(node["positionReportedPay"]["holders"]["appliesToEachHolder"])

    def test_a_roster_figure_with_the_wrong_count_is_stripped(self):
        self.assertNotIn("positionReportedPay", self.by_id["roster-wrong-count"])

    def test_a_roster_figure_with_no_uniform_claim_is_stripped(self):
        self.assertNotIn("positionReportedPay", self.by_id["roster-no-claim"])

    def test_a_uniform_roster_block_on_a_node_stating_no_count_is_withdrawn(self):
        """"The report lists N people under this title" cannot be restated as
        one person's pay by dropping `holders`; the gate refuses the block, so
        the sweep withdraws it rather than trimming it."""
        node = {"id": "roster-single", "name": "Press Assistant", "type": "Position",
                "positionReportedPay": {"amount": 1.0, "quote": "PRESS ASSISTANT — listed 2 times, each at $1",
                                        "holders": {"count": 2, "uniformRate": True, "note": "each"}}}
        self.tree["children"].append(node)
        withdrawn = withdraw_pay_from_multi_post_nodes(self.tree)
        self.assertGreaterEqual(withdrawn, 1)
        self.assertNotIn("positionReportedPay", node)

    def test_a_uniform_block_without_its_sentence_is_stripped(self):
        node = self.by_id["roster-uniform"]
        node["positionReportedPay"]["holders"].pop("note", None)
        withdraw_pay_from_multi_post_nodes(self.tree)
        self.assertNotIn("positionReportedPay", node)

    def test_a_stale_holders_block_on_a_single_post_node_is_removed(self):
        self.assertNotIn("holders", self.by_id["single"]["positionStatutoryPay"])

    def test_the_withdrawn_count_is_the_stripped_fields(self):
        # four listing-based fields on the bench, two roster blocks
        self.assertEqual(4 + 2, self.withdrawn)

    def test_holders_for_carries_every_kind(self):
        self.assertEqual(18, holders_for({"text": "×18", "kind": "exact", "count": 18})["count"])
        ranged = holders_for({"text": "×2-4", "kind": "range", "low": 2, "high": 4})
        self.assertEqual((2, 4), (ranged["low"], ranged["high"]))
        unstated = holders_for({"text": "×multiple", "kind": "unstated", "as_written": "multiple"})
        self.assertEqual("multiple", unstated["as_written"])
        self.assertNotIn("count", unstated)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tree = _tree()
        withdraw_pay_from_multi_post_nodes(self.tree)
        self.by_id = {n["id"]: n for n in self.tree["children"]}

    def test_an_office_rate_block_with_holders_passes(self):
        bench = self.by_id["bench"]
        for field in OFFICE_RATE_PAY_FIELDS:
            self.assertEqual([], gate.holders_violations(bench, bench[field], field, _label))

    def test_a_listing_based_block_on_a_multi_post_node_is_refused(self):
        bench = copy.deepcopy(self.by_id["bench"])
        for field in INCUMBENCY_PAY_FIELDS:
            out = gate.holders_violations(bench, {"amount": 1.0}, field, _label)
            self.assertTrue(any("one listing's" in v for v in out), field)

    def test_a_missing_holders_block_is_refused(self):
        bench = self.by_id["bench"]
        out = gate.holders_violations(bench, {"amount": 1.0}, "positionStatutoryPay", _label)
        self.assertTrue(any("does not say the figure applies to each holder" in v for v in out))

    def test_a_holders_block_stating_another_count_is_refused(self):
        bench = self.by_id["bench"]
        pay = copy.deepcopy(bench["positionStatutoryPay"])
        pay["holders"]["text"] = "×17"
        out = gate.holders_violations(bench, pay, "positionStatutoryPay", _label)
        self.assertTrue(any("while its name states" in v for v in out))

    def test_a_holders_block_stating_another_count_number_or_kind_is_refused(self):
        """The panel prints `count` before `text`, so the number and the kind
        are checked as the text is: 17 on a name stating ×18, a missing
        count, a kind the name does not have, and a key the name does not
        state are each refused."""
        node = self.by_id["bench"]
        for field in OFFICE_RATE_PAY_FIELDS:
            good = copy.deepcopy(node[field])
            self.assertEqual([], gate.holders_violations(node, good, field, _label))
            for label_text, mutate in {
                "count 17": lambda h: h.__setitem__("count", 17),
                "count missing": lambda h: h.pop("count"),
                "kind unstated": lambda h: h.__setitem__("kind", "unstated"),
                "a range the name does not state": lambda h: h.__setitem__("low", 3),
            }.items():
                pay = copy.deepcopy(good)
                mutate(pay["holders"])
                with self.subTest(field=field, case=label_text):
                    self.assertNotEqual([], gate.holders_violations(node, pay, field, _label))

    def test_a_holders_block_not_claiming_each_holder_is_refused(self):
        bench = self.by_id["bench"]
        pay = copy.deepcopy(bench["positionStatutoryPay"])
        pay["holders"]["appliesToEachHolder"] = False
        out = gate.holders_violations(bench, pay, "positionStatutoryPay", _label)
        self.assertTrue(any("does not claim the figure for each holder" in v for v in out))

    def test_a_holders_block_with_no_sentence_is_refused(self):
        bench = self.by_id["bench"]
        pay = copy.deepcopy(bench["positionStatutoryPay"])
        pay["holders"]["note"] = ""
        out = gate.holders_violations(bench, pay, "positionStatutoryPay", _label)
        self.assertTrue(any("no sentence saying so" in v for v in out))

    def test_a_roster_block_needs_a_uniform_claim_with_the_names_count(self):
        node = self.by_id["roster-uniform"]
        self.assertEqual([], gate.holders_violations(node, node["positionReportedPay"], "positionReportedPay", _label))
        pay = copy.deepcopy(node["positionReportedPay"])
        pay["holders"]["uniformRate"] = False
        out = gate.holders_violations(node, pay, "positionReportedPay", _label)
        self.assertTrue(any("one person's reported pay" in v for v in out))
        pay = copy.deepcopy(node["positionReportedPay"])
        pay["holders"]["count"] = 5
        out = gate.holders_violations(node, pay, "positionReportedPay", _label)
        self.assertTrue(any("while its name states" in v for v in out))

    def test_a_holders_block_on_a_single_post_node_is_refused(self):
        single = {"id": "s", "name": "Chief Judge", "type": "Position"}
        pay = {"amount": 1.0, "holders": {"text": "×2", "count": 2, "appliesToEachHolder": True, "note": "x"}}
        out = gate.holders_violations(single, pay, "positionStatutoryPay", _label)
        self.assertTrue(any("stands for one post" in v for v in out))

    def test_a_non_record_multiplicity_refuses_everything(self):
        odd = {"id": "o", "name": "X (×3)", "type": "Position", "representsPosts": 3}
        out = gate.holders_violations(odd, {"amount": 1.0}, "positionStatutoryPay", _label)
        self.assertTrue(any("cannot read" in v for v in out))


class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        cls.nodes = []
        if path.exists():
            stack = [json.loads(path.read_text(encoding="utf-8"))]
            while stack:
                node = stack.pop()
                cls.nodes.append(node)
                stack.extend(node.get("children") or [])

    def test_no_listing_based_figure_sits_on_a_multi_post_node(self):
        if not self.nodes:
            self.skipTest("no published graph")
        for node in self.nodes:
            if node.get("representsPosts"):
                for field in INCUMBENCY_PAY_FIELDS:
                    self.assertNotIn(field, node, node.get("id"))

    def test_every_multi_post_pay_block_says_who_it_covers(self):
        if not self.nodes:
            self.skipTest("no published graph")
        seen = 0
        for node in self.nodes:
            if not node.get("representsPosts"):
                continue
            for field in OFFICE_RATE_PAY_FIELDS + UNIFORM_ROSTER_PAY_FIELDS:
                block = node.get(field)
                if isinstance(block, dict):
                    seen += 1
                    with self.subTest("{} {}".format(node.get("id"), field)):
                        self.assertEqual([], gate.holders_violations(node, block, field, _label))
        self.assertGreater(seen, 0, "the published graph prices no multi-post node")

    def test_the_judge_x18_carries_the_tax_courts_rate_for_each_judge(self):
        if not self.nodes:
            self.skipTest("no published graph")
        bench = next((n for n in self.nodes if n.get("id") == "jud-specialized-tax-judge-18"), None)
        if bench is None:
            self.skipTest("no Tax Court bench node")
        pay = bench.get("positionDerivedPay")
        self.assertIsInstance(pay, dict)
        self.assertEqual(18, pay["holders"]["count"])
        self.assertEqual("$249,900", pay["rateText"])

    def test_no_bench_bundling_senior_judges_is_priced(self):
        if not self.nodes:
            self.skipTest("no published graph")
        for node in self.nodes:
            if node.get("representsPosts") and gate.SENIOR_JUDGE_MARKER.search(str(node.get("name") or "")):
                self.assertNotIn("positionStatutoryPay", node, node.get("id"))
                self.assertNotIn("positionDerivedPay", node, node.get("id"))


if __name__ == "__main__":
    unittest.main()
