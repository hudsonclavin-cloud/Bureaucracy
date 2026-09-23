"""How many documents each pay figure rests on, counted off the block itself.

Both directions throughout. The count is a fact about the block -- the
distinct URLs its own declared keys carry -- rather than a constant, so the
tests that matter most are the ones that remove a URL and assert the published
count falls with it, and the one that asserts the gate's mirror equals the
module's table.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS
from data_pipeline.verification.derived_pay import STRENGTH_SCALE, document_strength_percent
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.pay_documents import (
    PAY_DOCUMENT_FIELDS,
    PAY_FIELDS,
    annotate_pay_documents,
    count_documents,
)
from scripts.validate_published_graph import (
    DERIVED_PAY_STRENGTH_BY_COUNT,
    PAY_DOCUMENT_STATES_FIGURE,
    PAY_DOCUMENT_URL_KEYS,
    pay_document_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TABLE = "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx"
LISTING = "https://escs.opm.gov/escs-net/api/pbpub/download-data"
STATUTE = "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section5315&num=0&edition=prelim"


def _label(node):
    return "node {!r}".format(node.get("id"))


def _tree():
    return {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [
            {
                "id": "two-doc",
                "name": "A Post",
                "type": "Position",
                "positionPayRate": {"amount": 1.0, "url": TABLE, "levelSource": {"url": LISTING}},
            },
            {
                "id": "one-doc",
                "name": "Another Post",
                "type": "Position",
                "positionStatutoryPay": {"amount": 2.0, "url": TABLE},
            },
            {
                "id": "derived",
                "name": "A Third Post",
                "type": "Position",
                "positionDerivedPay": {
                    "amount": 3.0,
                    "url": STATUTE,
                    "documents": [{"url": STATUTE}, {"url": TABLE}],
                },
            },
            {
                "id": "scoped",
                "name": "A Fourth Post",
                "type": "Position",
                "positionSchedulePay": {"amount": 4.0, "url": TABLE, "statuteUrl": STATUTE},
            },
        ],
    }


class TableTests(unittest.TestCase):
    def test_every_pay_field_declares_a_document_count(self):
        """A new pay field cannot be added without deciding this. The list is
        pinned against the sweep that withdraws them all from a multi-post
        node, which is the other place every pay field must be named."""
        from data_pipeline.verification import pay_tables

        source = (PROJECT_ROOT / "data_pipeline" / "verification" / "pay_tables.py").read_text(encoding="utf-8")
        swept = {field for field in PAY_FIELDS if '"{}"'.format(field) in source}
        self.assertEqual(set(PAY_FIELDS), swept)
        self.assertTrue(hasattr(pay_tables, "withdraw_pay_from_multi_post_nodes"))

    def test_the_gate_mirrors_the_url_keys(self):
        self.assertEqual(set(PAY_DOCUMENT_URL_KEYS), set(PAY_DOCUMENT_FIELDS))
        for field, spec in PAY_DOCUMENT_FIELDS.items():
            self.assertEqual(tuple(spec["urlKeys"]), tuple(PAY_DOCUMENT_URL_KEYS[field]))

    def test_the_gate_mirrors_which_documents_state_the_figure(self):
        self.assertEqual(set(PAY_DOCUMENT_STATES_FIGURE), set(PAY_DOCUMENT_FIELDS))
        for field, spec in PAY_DOCUMENT_FIELDS.items():
            self.assertEqual(spec["statesTheFigure"], PAY_DOCUMENT_STATES_FIGURE[field])

    def test_only_the_derived_field_states_nothing(self):
        """The distinction the whole feature turns on."""
        zero = {f for f, s in PAY_DOCUMENT_FIELDS.items() if s["statesTheFigure"] == 0}
        self.assertEqual({"positionDerivedPay"}, zero)

    def test_the_gate_mirrors_the_scale(self):
        for count, percent in DERIVED_PAY_STRENGTH_BY_COUNT.items():
            self.assertEqual(document_strength_percent(count), percent)

    def test_every_field_carries_a_caution_sentence(self):
        for field, spec in PAY_DOCUMENT_FIELDS.items():
            with self.subTest(field):
                self.assertTrue(str(spec["caution"]).strip())


class CountTests(unittest.TestCase):
    def test_a_two_document_join_counts_two(self):
        count, roles = count_documents(
            "positionPayRate", {"url": TABLE, "levelSource": {"url": LISTING}})
        self.assertEqual(2, count)
        self.assertEqual({TABLE, LISTING}, {r["url"] for r in roles})
        self.assertTrue(all(r.get("role") for r in roles))

    def test_a_single_document_counts_one(self):
        self.assertEqual(1, count_documents("positionStatutoryPay", {"url": TABLE})[0])

    def test_a_derived_block_counts_its_document_list(self):
        count, _ = count_documents(
            "positionDerivedPay", {"documents": [{"url": STATUTE}, {"url": TABLE}]})
        self.assertEqual(2, count)

    def test_the_same_url_twice_is_one_document(self):
        """A build that put the table in both keys would be resting on one
        document, not two, and must publish 70% rather than 80%."""
        self.assertEqual(1, count_documents("positionSchedulePay", {"url": TABLE, "statuteUrl": TABLE})[0])

    def test_a_missing_second_url_drops_the_count(self):
        self.assertEqual(1, count_documents("positionPayRate", {"url": TABLE})[0])

    def test_an_empty_url_is_not_a_document(self):
        self.assertEqual(0, count_documents("positionStatutoryPay", {"url": "  "})[0])


class AnnotateTests(unittest.TestCase):
    def setUp(self):
        self.tree = _tree()
        self.stats = annotate_pay_documents(self.tree)
        self.by_id = {n["id"]: n for n in self.tree["children"]}

    def test_every_block_is_annotated(self):
        self.assertEqual(4, self.stats["annotated"])
        self.assertEqual(0, self.stats["no_document"])

    def test_two_documents_publish_eighty_percent(self):
        block = self.by_id["two-doc"]["positionPayRate"]["verification"]
        self.assertEqual(2, block["documents"])
        self.assertEqual(80, block["percent"])
        self.assertEqual(1, block["documentsStatingTheFigure"])
        self.assertEqual(STRENGTH_SCALE, block["scale"])

    def test_one_document_publishes_seventy_percent(self):
        block = self.by_id["one-doc"]["positionStatutoryPay"]["verification"]
        self.assertEqual(1, block["documents"])
        self.assertEqual(70, block["percent"])

    def test_a_derived_figure_says_none_of_its_documents_states_it(self):
        block = self.by_id["derived"]["positionDerivedPay"]["verification"]
        self.assertEqual(2, block["documents"])
        self.assertEqual(80, block["percent"])
        self.assertEqual(0, block["documentsStatingTheFigure"])
        self.assertIn("No document here states the figure", block["caution"])

    def test_dropping_a_url_drops_the_count_on_the_next_build(self):
        del self.by_id["two-doc"]["positionPayRate"]["levelSource"]
        annotate_pay_documents(self.tree)
        block = self.by_id["two-doc"]["positionPayRate"]["verification"]
        self.assertEqual(1, block["documents"])
        self.assertEqual(70, block["percent"])

    def test_a_block_with_no_document_publishes_no_percentage(self):
        self.by_id["one-doc"]["positionStatutoryPay"] = {"amount": 2.0}
        stats = annotate_pay_documents(self.tree)
        self.assertEqual(1, stats["no_document"])
        self.assertIsNone(self.by_id["one-doc"]["positionStatutoryPay"].get("verification"))

    def test_it_writes_no_source_or_cost_field(self):
        for node in self.tree["children"]:
            for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod",
                          "resolved_total_amount", "cost_status"):
                self.assertIsNone(node.get(field))

    def test_the_fields_reach_the_viewer_and_are_withdrawn_each_build(self):
        for field in PAY_FIELDS:
            with self.subTest(field):
                self.assertIn(field, EVIDENCE_OWNED_FIELDS)
                self.assertIn(field, MINIMAL_GRAPH_FIELDS)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tree = _tree()
        annotate_pay_documents(self.tree)
        self.by_id = {n["id"]: n for n in self.tree["children"]}

    def _check(self, node_id, field, mutate=None):
        node = copy.deepcopy(self.by_id[node_id])
        if mutate:
            mutate(node[field])
        return pay_document_violations(node, field, node[field], _label)

    def test_an_honest_block_passes(self):
        for node_id, field in (("two-doc", "positionPayRate"), ("one-doc", "positionStatutoryPay"),
                               ("derived", "positionDerivedPay"), ("scoped", "positionSchedulePay")):
            with self.subTest(node_id):
                self.assertEqual([], self._check(node_id, field))

    def test_a_count_the_block_does_not_support_is_caught(self):
        out = self._check("one-doc", "positionStatutoryPay",
                          lambda b: b["verification"].update(documents=2, percent=80))
        self.assertTrue(any("citable URL" in v for v in out))

    def test_an_inflated_percentage_is_caught(self):
        out = self._check("two-doc", "positionPayRate", lambda b: b["verification"].update(percent=95))
        self.assertTrue(any("own scale gives" in v for v in out))

    def test_claiming_a_derived_document_states_the_figure_is_caught(self):
        out = self._check("derived", "positionDerivedPay",
                          lambda b: b["verification"].update(documentsStatingTheFigure=1))
        self.assertTrue(any("state the figure" in v for v in out))

    def test_a_missing_verification_block_is_caught(self):
        out = self._check("one-doc", "positionStatutoryPay", lambda b: b.pop("verification"))
        self.assertTrue(any("no statement of how many documents" in v for v in out))

    def test_a_percentage_with_no_scale_is_caught(self):
        out = self._check("one-doc", "positionStatutoryPay",
                          lambda b: b["verification"].update(scale=""))
        self.assertTrue(any("what scale" in v for v in out))

    def test_a_percentage_with_no_caution_is_caught(self):
        out = self._check("one-doc", "positionStatutoryPay",
                          lambda b: b["verification"].update(caution=""))
        self.assertTrue(any("what it does not measure" in v for v in out))

    def test_a_role_naming_a_url_the_block_does_not_carry_is_caught(self):
        out = self._check("two-doc", "positionPayRate",
                          lambda b: b["verification"]["documentRoles"].__setitem__(
                              0, {"url": "https://example.gov/elsewhere", "role": "x"}))
        self.assertTrue(any("does not carry" in v for v in out))

    def test_a_zero_count_is_caught(self):
        out = self._check("one-doc", "positionStatutoryPay",
                          lambda b: b["verification"].update(documents=0))
        self.assertTrue(any("document count" in v for v in out))


class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        cls.nodes = []
        if not path.exists():
            return
        root = json.loads(path.read_text(encoding="utf-8"))
        stack = [root]
        while stack:
            node = stack.pop()
            cls.nodes.append(node)
            stack.extend(node.get("children") or [])

    def test_every_published_pay_block_carries_a_document_count(self):
        if not self.nodes:
            self.skipTest("no published graph")
        seen = 0
        for node in self.nodes:
            for field in PAY_FIELDS:
                block = node.get(field)
                if isinstance(block, dict):
                    seen += 1
                    with self.subTest("{} {}".format(node.get("id"), field)):
                        self.assertEqual([], pay_document_violations(node, field, block, _label))
        self.assertGreater(seen, 0)

    def test_the_two_document_joins_really_publish_two(self):
        if not self.nodes:
            self.skipTest("no published graph")
        for field in ("positionPayRate", "positionSchedulePay", "positionDerivedPay"):
            counts = {
                node[field]["verification"]["documents"]
                for node in self.nodes
                if isinstance(node.get(field), dict)
            }
            with self.subTest(field):
                self.assertTrue(counts <= {2}, "{} published {}".format(field, counts))


if __name__ == "__main__":
    unittest.main()
