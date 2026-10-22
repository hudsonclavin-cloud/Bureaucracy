"""The pay blank: a post no pay document prices names the held title-listing
pay documents checked for its title and says whether any prints it.

Both directions are pinned: the module stamps exactly the documents and the
title hits the committed fixtures give; the gate re-derives every universe with
its own readers (stdlib only), the two agree title for title, and every
corruption of a block or of the root's list is refused.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, MINIMAL_GRAPH_ROOT_FIELDS  # noqa: E402
from data_pipeline.verification import pay_no_document as pnd  # noqa: E402
from data_pipeline.verification.pay_documents import PAY_FIELDS  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def post(node_id, name, **fields):
    return {"id": node_id, "name": name, "type": "Position", "children": [], "cost_status": "unavailable",
            "cost_validation": "post_is_not_a_budget_unit", **fields}


def org(node_id, name, *children, **fields):
    return {"id": node_id, "name": name, "type": "Agency", "children": list(children), "cost_status": "allocated",
            "resolved_total_amount": 100.0, **fields}


def tree(*children):
    return {"id": "the-constitution-of-the-united-states", "name": "Root", "type": "Foundation",
            "__budgetSummary": {"record_date": "2026-08-31"},
            "children": [{"id": "branch", "name": "A Branch", "type": "Branch", "cost_status": "official",
                          "resolved_total_amount": 1000.0, "children": list(children)}]}


def by_id(root):
    return {n["id"]: n for n, _ in gate.walk(root)}


class UniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = pnd.document_universes()
        cls.mirror = gate.pay_no_document_universes()

    def test_six_documents_in_the_declared_order(self):
        self.assertEqual([u["id"] for u in self.module], [
            "executive_schedule_5_usc_5312_5316", "opm_current_plum_export", "opm_plum_archive",
            "whitehouse_staff_report", "us_government_manual_leadership_tables", "schedule_8_enlisted_footnote"])
        self.assertEqual([u["id"] for u in self.mirror], [u["id"] for u in self.module])

    def test_the_gate_s_universes_equal_the_module_s_title_for_title(self):
        for ours, theirs in zip(self.module, self.mirror):
            with self.subTest(document=ours["id"]):
                self.assertEqual(ours["version"], theirs["version"])
                self.assertEqual(ours["sha256"], theirs["sha256"])
                self.assertEqual(ours["names"], theirs["names"])
                self.assertEqual(gate.PAY_NO_DOCUMENT_LABELS[ours["id"]], ours["document"])
        self.assertEqual(gate.PAY_NO_DOCUMENT_KIND_NONE, pnd.KIND_NONE)
        self.assertEqual(gate.PAY_NO_DOCUMENT_KIND_NAMED, pnd.KIND_NAMED)
        self.assertEqual(gate.PAY_NO_DOCUMENT_REASONS, pnd.REASONS)
        self.assertEqual(gate.PAY_NO_DOCUMENT_REF, pnd.DOCUMENTS_REF)
        self.assertEqual(gate.PAY_NO_DOCUMENT_ROOT_FIELD, pnd.ROOT_FIELD)
        self.assertEqual(set(gate.PAY_NO_DOCUMENT_PAY_FIELDS), set(PAY_FIELDS))

    def test_the_universes_carry_what_the_documents_print(self):
        names = {u["id"]: u["names"] for u in self.module}
        self.assertIn("secretary of state", names["executive_schedule_5_usc_5312_5316"])
        self.assertIn("general counsel", names["opm_current_plum_export"])
        self.assertIn("general counsel", names["opm_plum_archive"])
        self.assertIn("press assistant", names["whitehouse_staff_report"])
        self.assertIn("inspector general", names["us_government_manual_leadership_tables"])
        self.assertIn("sergeant major of the army", names["schedule_8_enlisted_footnote"])
        # the incumbent columns are never read: the universes are built from the
        # loaders whose READ_COLUMNS / ROW_FIELDS name no incumbent column, and
        # tests/test_plum_current.py plants a sentinel in those columns
        from data_pipeline.verification import plum_current, positions
        for column in plum_current.READ_COLUMNS:
            self.assertNotIn("name", column.casefold().replace("position title", ""), column)
        self.assertFalse({"IncumbentName", "FirstName", "LastName", "Incumbent"} & set(positions.ROW_FIELDS))

    def test_the_field_and_the_root_list_are_in_the_viewer_copy(self):
        self.assertIn(pnd.FIELD, MINIMAL_GRAPH_FIELDS)
        self.assertIn(pnd.ROOT_FIELD, MINIMAL_GRAPH_ROOT_FIELDS)


class ApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.universes = pnd.document_universes()

    def _apply(self, root):
        return pnd.apply_pay_no_document(root, universes=self.universes)

    def test_a_post_no_document_prices_is_explained_and_a_printed_title_says_where(self):
        root = tree(org("a", "An Agency",
                        post("x", "Chief Widget Wrangler"),
                        post("gc", "General Counsel"),
                        post("multi", "Economist (×multiple)", representsPosts={"kind": "unstated", "text": "×multiple"}),
                        post("listed", "Staff Director", positionCurrentListing={"source": "x"})))
        stats = self._apply(root)
        nodes = by_id(root)
        blank = nodes["x"][pnd.FIELD]
        self.assertEqual(blank["kind"], pnd.KIND_NONE)
        self.assertEqual(blank["reason"], "unreached")
        self.assertEqual(blank["namedIn"], [])
        self.assertEqual(blank["documentsRef"], pnd.DOCUMENTS_REF)
        self.assertEqual(blank["documentsChecked"], 6)
        named = nodes["gc"][pnd.FIELD]
        self.assertEqual(named["kind"], pnd.KIND_NAMED)
        self.assertIn("opm_current_plum_export", [h["document"] for h in named["namedIn"]])
        self.assertEqual(nodes["multi"][pnd.FIELD]["reason"], "multiplicity")
        self.assertEqual(nodes["listed"][pnd.FIELD]["reason"], "listed_no_rate")
        self.assertEqual(len(root[pnd.ROOT_FIELD]), 6)
        self.assertEqual([d["id"] for d in root[pnd.ROOT_FIELD]], [u["id"] for u in self.universes])
        self.assertEqual(stats["stamped"], 4)
        self.assertEqual(stats["reasons"], {"unreached": 2, "multiplicity": 1, "listed_no_rate": 1})

    def test_beneath_a_replaced_unit_the_reason_is_the_report_s(self):
        root = tree(org("old", "Old Network", post("p", "Network Pharmacist"), lifecycle="superseded"))
        self._apply(root)
        self.assertEqual(by_id(root)["p"][pnd.FIELD]["reason"], "beneath_replaced_unit")

    def test_never_where_a_figure_an_employer_or_another_rule_stands(self):
        root = tree(org("a", "An Agency",
                        post("priced", "A Priced Post", positionStatutoryPay={"amount": 1.0}),
                        post("ranged", "A Ranged Post", positionGradePay={"minimum": 1.0}),
                        post("lab", "Division Director", positionEmployer={"federallyPaid": False, "kind": "contractor_operated_laboratory"}),
                        post("line", "A Line", type="Treasury accounting line"),
                        {"id": "unit", "name": "A Unit", "type": "Office", "children": [], "cost_status": "allocated"},
                        post("ok", "Plain Post")))
        self._apply(root)
        nodes = by_id(root)
        for node_id in ("priced", "ranged", "lab", "line", "unit", "a", "branch"):
            self.assertNotIn(pnd.FIELD, nodes[node_id], node_id)
        self.assertIn(pnd.FIELD, nodes["ok"])

    def test_the_field_and_the_root_list_are_cleared_before_they_are_recomputed(self):
        root = tree(org("a", "An Agency", post("priced", "A Priced Post", positionStatutoryPay={"amount": 1.0}, **{pnd.FIELD: {"kind": pnd.KIND_NONE}})))
        root[pnd.ROOT_FIELD] = [{"id": "stale"}]
        self._apply(root)
        self.assertNotIn(pnd.FIELD, by_id(root)["priced"], "a post that gained a figure loses the blank")
        self.assertNotIn(pnd.ROOT_FIELD, root, "no blank, no list")


class GateTests(unittest.TestCase):
    def _graph(self):
        root = tree(org("a", "An Agency",
                        post("x", "Chief Widget Wrangler"),
                        post("gc", "General Counsel"),
                        post("priced", "A Priced Post", positionStatutoryPay={"amount": 1.0})),
                    org("old", "Old Network", post("p", "Network Pharmacist"), lifecycle="superseded"))
        pnd.apply_pay_no_document(root)
        return root, by_id(root)

    def test_what_the_module_stamps_passes(self):
        root, _ = self._graph()
        self.assertEqual(gate.pay_no_document_violations(root, gate.label), [])

    def test_a_post_without_a_block_is_refused_once_the_pass_has_run(self):
        root, nodes = self._graph()
        del nodes["x"][pnd.FIELD]
        self.assertTrue(any("carries no payNoDocument block" in v for v in gate.pay_no_document_violations(root, gate.label)))
        for node_id in ("gc", "p"):
            del nodes[node_id][pnd.FIELD]
        self.assertTrue(any("__heldPayDocuments while no post" in v for v in gate.pay_no_document_violations(root, gate.label)))
        del root[pnd.ROOT_FIELD]
        self.assertEqual(gate.pay_no_document_violations(root, gate.label), [], "a graph the pass never ran over owes nothing")

    def test_each_corruption_is_refused(self):
        cases = {
            "not an object": lambda r, n: n["x"].__setitem__(pnd.FIELD, "yes"),
            "on a priced post": lambda r, n: n["priced"].__setitem__(pnd.FIELD, dict(n["x"][pnd.FIELD], name="A Priced Post")),
            "on an organisation": lambda r, n: n["a"].__setitem__(pnd.FIELD, dict(n["x"][pnd.FIELD], name="An Agency")),
            "beside an employer block": lambda r, n: n["x"].__setitem__("positionEmployer", {"federallyPaid": False}),
            "another node's name": lambda r, n: n["x"][pnd.FIELD].__setitem__("name", "Something Else"),
            "a kind the documents do not support": lambda r, n: n["x"][pnd.FIELD].__setitem__("kind", pnd.KIND_NAMED),
            "a named kind with the hit dropped": lambda r, n: n["gc"][pnd.FIELD].__setitem__("namedIn", []),
            "an invented hit": lambda r, n: n["x"][pnd.FIELD].__setitem__("namedIn", [{"document": "opm_plum_archive", "printed": "Chief Widget Wrangler"}]),
            "the wrong reason": lambda r, n: n["x"][pnd.FIELD].__setitem__("reason", "multiplicity"),
            "a replaced unit's post read as unreached": lambda r, n: n["p"][pnd.FIELD].__setitem__("reason", "unreached"),
            "a reference to another list": lambda r, n: n["x"][pnd.FIELD].__setitem__("documentsRef", "sharedDocuments"),
            "a count the list does not hold": lambda r, n: n["x"][pnd.FIELD].__setitem__("documentsChecked", 9),
            "an extra key on the block": lambda r, n: n["x"][pnd.FIELD].__setitem__("sentence", "a paraphrase"),
            "the root list dropped": lambda r, n: r.pop(pnd.ROOT_FIELD),
            "a document dropped from the root list": lambda r, n: r[pnd.ROOT_FIELD].pop(),
            "a document's digest changed": lambda r, n: r[pnd.ROOT_FIELD][0].__setitem__("sha256", "0" * 64),
            "a document's version changed": lambda r, n: r[pnd.ROOT_FIELD][1].__setitem__("version", "fetched 2099-01-01"),
            "a document's count changed": lambda r, n: r[pnd.ROOT_FIELD][2].__setitem__("titlesChecked", 1),
            "a document relabelled": lambda r, n: r[pnd.ROOT_FIELD][0].__setitem__("document", "a paraphrase"),
            "an extra key on a document": lambda r, n: r[pnd.ROOT_FIELD][0].__setitem__("note", "x"),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                root, nodes = self._graph()
                corrupt(root, nodes)
                self.assertNotEqual(gate.pay_no_document_violations(root, gate.label), [], name)

    @unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
    def test_the_published_graph_passes_and_leaves_no_post_unexplained(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        self.assertEqual(gate.pay_no_document_violations(graph, gate.label), [])
        unexplained = []
        stack = [(graph, False)]
        while stack:
            node, replaced = stack.pop()
            replaced = replaced or str(node.get("lifecycle") or "") == "superseded"
            if node is not graph and gate.pay_no_document_reason(node, replaced) and not isinstance(node.get(pnd.FIELD), dict):
                unexplained.append(node["id"])
            stack.extend((c, replaced) for c in node.get("children") or [] if isinstance(c, dict))
        self.assertEqual(unexplained, [])
        blanks = [n for n, _ in gate.walk(graph) if isinstance(n.get(pnd.FIELD), dict)]
        self.assertGreater(len(blanks), 3000)
        self.assertTrue(all(b[pnd.FIELD]["reason"] in pnd.REASONS for b in blanks))


if __name__ == "__main__":
    unittest.main()
