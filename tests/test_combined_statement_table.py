"""The reviewed Combined Statement table, published and gated in both directions.

Every row lists every account the Legislative Branch chapter prints for its
unit; the figure is the sum of those accounts' printed figures; the two
commissions the Treasury files under the Legislative Branch and this graph
curates elsewhere say so; the gate re-reads the chapter, the PDF and the
September statement itself and refuses each corruption; and the figures divide
a pool only where every unit beside them carries one (CURATION.md Sec 22.8).
"""

from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    MINIMAL_GRAPH_FIELDS,
    get_node_weight,
    index_tree,
    load_base_graph,
    resolve_sibling_weights,
)
from data_pipeline.verification import combined_statement as cs  # noqa: E402
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from scripts import validate_published_graph as gate  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def walk(node, parent=None):
    yield node, parent
    for child in node.get("children") or []:
        yield from walk(child, node)


_SHARED: dict = {}


def shared():
    if not _SHARED:
        base = load_base_graph(DEFAULT_BASE_GRAPH)
        node_map, parent_map = index_tree(base)
        records, report = cs.build_records(node_map, parent_map)
        _SHARED.update(base=base, records=records, report=report)
    return _SHARED


class TableTests(unittest.TestCase):
    def test_the_gate_mirrors_the_table(self):
        mirrored = {
            node_id: (row["nodeName"], tuple(row["accounts"]), row["phrase"], row["chapterUnit"],
                      row["filedInAnotherSection"])
            for node_id, row in cs.REVIEWED_ROWS.items()
        }
        self.assertEqual(mirrored, gate.COMBINED_STATEMENT_ROWS)
        self.assertEqual(gate.COMBINED_STATEMENT_FISCAL_YEAR, cs.FISCAL_YEAR)
        self.assertEqual(gate.COMBINED_STATEMENT_CHAPTER, cs.CHAPTER_STEM)
        self.assertEqual(gate.COMBINED_STATEMENT_BRANCH_ID, cs.CHAPTER_BRANCH_ID)

    def test_the_field_is_owned_and_in_the_viewer_copy(self):
        self.assertIn(cs.FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(cs.FIELD, MINIMAL_GRAPH_FIELDS)

    def test_fifteen_rows_publish_with_their_printed_sums(self):
        s = shared()
        self.assertEqual(s["report"]["refused"], {})
        amounts = {node_id: record["amountRaw"] for node_id, record in s["records"].items()}
        self.assertEqual(amounts, {
            "leg-support-aoc-capitol-building": "55,027,979.70",
            "leg-support-aoc-capitol-grounds": "17,858,652.41",
            "leg-support-aoc-senate-office-buildings": "128,021,693.98",
            "leg-support-aoc-house-office-buildings": "156,916,099.98",
            "leg-support-aoc-capitol-power-plant": "122,012,533.26",
            "leg-support-aoc-capitol-visitor-center": "25,198,692.39",
            "leg-support-aoc-library-of-congress-buildings": "94,205,042.27",
            "leg-support-aoc-capital-construction-and-operations": "158,585,469.94",
            "leg-support-aoc-capitol-police-buildings-and-grounds": "204,227,240.13",
            "leg-support-loc-crs": "141,782,158.43",
            "leg-support-loc-copyright": "63,962,820.59",
            "leg-support-loc-nls": "64,367,416.42",
            "leg-senate-admin-legal": "1,165,507.91",
            "exec-ind-misc-macpac": "10,186,355.32",
            "exec-ind-misc-medpac": "686,932.49",
        })

    def test_two_accounts_where_the_chapter_prints_two(self):
        s = shared()
        for node_id, printed in (
            ("leg-support-aoc-capitol-visitor-center", ["30,190,121.91", "-4,991,429.52"]),
            ("leg-support-loc-copyright", ["63,321,276.20", "641,544.39"]),
        ):
            record = s["records"][node_id]
            self.assertEqual([c["printed"] for c in record["components"]], printed)
            self.assertEqual(record["documentsStatingTheFigure"], 0)
        self.assertEqual(s["records"]["leg-support-loc-crs"]["documentsStatingTheFigure"], 1)

    def test_only_the_two_commissions_are_filed_in_another_section(self):
        s = shared()
        marked = sorted(k for k, r in s["records"].items() if r["treasurySection"]["filedInAnotherSection"])
        self.assertEqual(marked, ["exec-ind-misc-macpac", "exec-ind-misc-medpac"])
        self.assertEqual(s["records"]["exec-ind-misc-macpac"]["treasurySection"]["graphBranch"], "Executive Branch")
        self.assertIn("note", s["records"]["exec-ind-misc-medpac"]["treasurySection"])
        self.assertNotIn("note", s["records"]["leg-support-loc-crs"]["treasurySection"])

    def test_every_record_is_net_outlays_for_a_completed_year_and_never_more_than_a_proxy(self):
        for record in shared()["records"].values():
            self.assertEqual(record["costBasis"], "net_outlays")
            self.assertEqual(record["fiscalYear"], 2025)
            self.assertEqual(record["scopeMatch"], "proxy")
            self.assertEqual(record["financialEvidenceStatus"], "partial")
            self.assertEqual(record["unitsEvidenceKind"], gate.COMBINED_STATEMENT_UNITS_KIND)
            self.assertIn("not this node's cost", record["notTheCost"])


class BuilderRefusalTests(unittest.TestCase):
    def build(self, rows=None, mutate_base=None):
        base = copy.deepcopy(shared()["base"])
        node_map, parent_map = index_tree(base)
        if mutate_base:
            mutate_base(node_map)
        with mock.patch.dict(cs.REVIEWED_ROWS, rows or {}, clear=False):
            return cs.build_records(node_map, parent_map)

    def row(self, node_id, **changes):
        return {node_id: {**cs.REVIEWED_ROWS[node_id], **changes}}

    def test_a_row_missing_one_of_the_units_accounts_is_refused(self):
        _, report = self.build(self.row("leg-support-loc-copyright",
                                        accounts=("Salaries and Expenses, Copyright Office, Library of Congress",)))
        self.assertIn("leg-support-loc-copyright", report["refused"]["chapter_prints_another_account_for_the_unit"])

    def test_an_account_the_chapter_does_not_print_is_refused(self):
        _, report = self.build(self.row("leg-support-loc-crs", accounts=("Salaries and Expenses, CRS",)))
        self.assertIn("leg-support-loc-crs", report["refused"]["account_not_printed_exactly_once"])

    def test_an_account_under_another_units_total_is_refused(self):
        _, report = self.build(self.row("leg-support-loc-crs", chapterUnit="Senate"))
        self.assertIn("leg-support-loc-crs", report["refused"]["account_closed_by_another_unit_total"])

    def test_a_section_mark_the_tree_contradicts_is_refused_both_ways(self):
        _, report = self.build({**self.row("exec-ind-misc-macpac", filedInAnotherSection=False),
                                **self.row("leg-support-loc-nls", filedInAnotherSection=True)})
        self.assertEqual(sorted(report["refused"]["section_mark_disagrees_with_the_tree"]),
                         ["exec-ind-misc-macpac", "leg-support-loc-nls"])

    def test_a_renamed_node_is_refused(self):
        def rename(node_map):
            node_map["leg-support-aoc-capitol-grounds"]["name"] = "Capitol Lawns"
        _, report = self.build(mutate_base=rename)
        self.assertIn("leg-support-aoc-capitol-grounds", report["refused"]["node_renamed_since_the_row_was_written"])

    def test_a_post_is_refused(self):
        def retype(node_map):
            node_map["leg-senate-admin-legal"]["type"] = "Position"
        _, report = self.build(mutate_base=retype)
        self.assertIn("leg-senate-admin-legal", report["refused"]["not_an_organisation"])


class ApplyTests(unittest.TestCase):
    def test_apply_stamps_fifteen_and_withdraws_what_it_no_longer_has(self):
        graph = copy.deepcopy(shared()["base"])
        stats = cs.apply_combined_statement_evidence(graph, shared()["records"])
        self.assertEqual(stats["applied"], 15)
        stats = cs.apply_combined_statement_evidence(graph, {})
        self.assertEqual(stats["withdrawn_first"], 15)
        self.assertFalse(any(cs.FIELD in n for n, _ in walk(graph)))

    def test_apply_refuses_an_unlisted_node_a_rename_and_a_moved_record(self):
        graph = copy.deepcopy(shared()["base"])
        records = copy.deepcopy(shared()["records"])
        records["leg-support-loc-law"] = records.pop("leg-support-loc-crs")
        node_map, _ = index_tree(graph)
        node_map["leg-support-loc-nls"]["name"] = "Talking Books Service"
        stats = cs.apply_combined_statement_evidence(graph, records)
        self.assertEqual((stats["applied"], stats["refused_not_a_reviewed_row"], stats["refused_renamed"]), (13, 1, 1))


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cs.apply_combined_statement_evidence(graph, shared()["records"])
        cls.graph = graph
        cls.docs = gate.combined_statement_documents()

    def check(self, graph):
        pairs = list(walk(graph))
        tree_parents = {str(n.get("id") or ""): str((p or {}).get("id") or "") for n, p in pairs}
        out = []
        for node, _ in pairs:
            if isinstance(node.get(cs.FIELD), dict):
                out.extend(gate.combined_statement_violations(node, node[cs.FIELD], self.docs, gate.label, tree_parents))
        return out

    def corrupt(self, node_id, mutate):
        graph = copy.deepcopy(self.graph)
        nodes = {n["id"]: n for n, _ in walk(graph) if n.get("id")}
        mutate(nodes[node_id], nodes)
        return self.check(graph)

    def test_the_true_blocks_pass(self):
        self.assertNotIn("error", self.docs)
        self.assertEqual(self.check(copy.deepcopy(self.graph)), [])
        self.assertEqual(sum(1 for n, _ in walk(self.graph) if cs.FIELD in n), 15)

    def test_each_corruption_is_refused(self):
        single, double, commission = "leg-support-loc-crs", "leg-support-aoc-capitol-visitor-center", "exec-ind-misc-macpac"

        def setblock(key, value):
            return lambda node, nodes: node[cs.FIELD].__setitem__(key, value)

        def move_to(target):
            return lambda node, nodes: nodes[target].__setitem__(cs.FIELD, node.pop(cs.FIELD))

        cases = [
            ("a figure that is not the accounts' sum", single, setblock("amount", 141782158.0)),
            ("a thousandfold figure", single, setblock("amount", 141782158430.0)),
            ("the revolving fund dropped", double, lambda n, _: n[cs.FIELD]["components"].pop()),
            ("a component's printed figure altered", double,
             lambda n, _: n[cs.FIELD]["components"][1].__setitem__("printed", "4,991,429.52")),
            ("a component's account renamed", single,
             lambda n, _: n[cs.FIELD]["components"][0].__setitem__("account", "Salaries and Expenses, CRS")),
            ("a sum claimed to be printed", double, setblock("documentsStatingTheFigure", 1)),
            ("a digest the chapter does not have", single,
             lambda n, _: n[cs.FIELD]["document"].__setitem__("xlsxSha256", "0" * 64)),
            ("a PDF digest the chapter does not have", single,
             lambda n, _: n[cs.FIELD]["document"].__setitem__("pdfSha256", "0" * 64)),
            ("a reconciliation a cent off", single,
             lambda n, _: n[cs.FIELD]["scaleReconciliation"]["statementLine"].__setitem__("amountRaw", "7232968757.52")),
            ("the prior-year column", single,
             lambda n, _: n[cs.FIELD]["scaleReconciliation"]["statementLine"].__setitem__("field", "prior_fytd_net_outly_amt")),
            ("another fiscal year", single, setblock("fiscalYear", 2026)),
            ("another basis", single, setblock("costBasis", "obligations")),
            ("more than a proxy", single, setblock("scopeMatch", "exact")),
            ("the not-the-cost sentence removed", single, setblock("notTheCost", "")),
            ("no reviewed basis", single, setblock("matchBasis", "")),
            ("the commission's section mark removed", commission,
             lambda n, _: n[cs.FIELD]["treasurySection"].__setitem__("filedInAnotherSection", False)),
            ("a section mark on a unit the graph files under the Legislative Branch", single,
             lambda n, _: n[cs.FIELD]["treasurySection"].update(filedInAnotherSection=True, note="x")),
            ("the commission's note removed", commission,
             lambda n, _: n[cs.FIELD]["treasurySection"].pop("note")),
            ("a block moved onto a sibling the table does not carry", single, move_to("leg-support-loc-law")),
            ("a block moved onto another reviewed unit", single, move_to("leg-support-loc-nls")),
            ("a renamed node", single, lambda n, _: n.__setitem__("name", "Research Service")),
            ("a block on a post", single, lambda n, _: n.__setitem__("type", "Position")),
            ("a block beside a measured cost", single, lambda n, _: n.__setitem__("cost_status", "official")),
            ("the estimate equal to the figure", single,
             lambda n, _: n.__setitem__("resolved_total_amount", n[cs.FIELD]["amount"])),
            ("the chapter among the node's own sources", single,
             lambda n, _: n.__setitem__("sourceUrls", [n[cs.FIELD]["document"]["xlsxUrl"]])),
        ]
        for name, node_id, mutate in cases:
            with self.subTest(case=name):
                self.assertNotEqual(self.corrupt(node_id, mutate), [], f"{name} was accepted")

    def test_a_row_dropped_from_the_gate_mirror_omits_an_account(self):
        trimmed = dict(gate.COMBINED_STATEMENT_ROWS)
        name, titles, phrase, unit, another = trimmed["leg-support-loc-copyright"]
        trimmed["leg-support-loc-copyright"] = (name, titles[:1], phrase, unit, another)
        with mock.patch.object(gate, "COMBINED_STATEMENT_ROWS", trimmed):
            out = self.check(copy.deepcopy(self.graph))
        self.assertTrue(any("omits an account" in v for v in out))


class WeightTests(unittest.TestCase):
    """The figures divide a pool only where every unit beside them carries one."""

    @staticmethod
    def unit(node_id, amount=None, *, another=False, sha="chapter", type_="Division"):
        node = {"id": node_id, "name": node_id, "type": type_}
        if amount is not None:
            node[cs.FIELD] = {"amount": amount, "fiscalYear": 2025, "document": {"xlsxSha256": sha},
                              "treasurySection": {"filedInAnotherSection": another}}
        return node

    def resolve(self, children):
        sizes = {c["id"]: 1 for c in children}
        weighted = [(c, *get_node_weight(c, sizes)) for c in children]
        return resolve_sibling_weights(weighted, sizes)

    def test_every_unit_with_a_figure_divides_by_it_and_a_post_is_implied(self):
        children = [self.unit("a", 300.0), self.unit("b", 100.0), self.unit("p", type_="Position")]
        resolved, cls, implied = self.resolve(children)
        self.assertEqual(cls, "combined_statement")
        bases = {c["id"]: basis for c, _, basis in resolved}
        self.assertEqual(bases, {"a": "combined_statement_weight", "b": "combined_statement_weight",
                                 "p": "implied_combined_statement_weight"})
        self.assertTrue(implied)

    def test_one_unit_without_a_figure_and_none_divides_by_them(self):
        resolved, cls, _ = self.resolve([self.unit("a", 300.0), self.unit("b", 100.0), self.unit("c")])
        self.assertEqual(cls, "subtree")
        self.assertFalse(any("combined" in basis for _, _, basis in resolved))

    def test_a_figure_filed_in_another_section_never_divides(self):
        resolved, cls, _ = self.resolve([self.unit("a", 300.0), self.unit("b", 100.0, another=True)])
        self.assertFalse(any("combined" in basis for _, _, basis in resolved))

    def test_two_chapters_never_divide_one_pool(self):
        resolved, cls, _ = self.resolve([self.unit("a", 300.0), self.unit("b", 100.0, sha="other")])
        self.assertFalse(any("combined" in basis for _, _, basis in resolved))

    def test_a_figure_at_or_below_zero_weights_nothing(self):
        resolved, cls, _ = self.resolve([self.unit("a", 300.0), self.unit("b", -5.0)])
        self.assertFalse(any("combined" in basis for _, _, basis in resolved))

    # The gate's half.
    @staticmethod
    def placed(node_id, amount, share, basis, **kw):
        node = WeightTests.unit(node_id, amount, **kw)
        node.update(cost_status="allocated", resolved_total_amount=share, cost_basis=basis)
        return node

    def gate_check(self, nodes):
        return gate.combined_statement_weight_violations(nodes, {n["id"]: "parent" for n in nodes}, lambda n: n["id"])

    def test_the_gate_accepts_a_licensed_proportional_split(self):
        nodes = [self.placed("a", 300.0, 750.0, "combined_statement_weight"),
                 self.placed("b", 100.0, 250.0, "combined_statement_weight"),
                 self.placed("p", None, 10.0, "implied_combined_statement_weight", type_="Position")]
        self.assertEqual(self.gate_check(nodes), [])

    def test_the_gate_accepts_a_post_that_keeps_its_implied_weight_and_publishes_nothing(self):
        # The counterfactual with all seven of the Architect's divisions found
        # this: the four posts beside them keep an implied weight and publish
        # `unavailable` under the post rule, which the gate first refused.
        post = self.placed("p", None, None, "implied_combined_statement_weight", type_="Position")
        post["cost_status"] = "unavailable"
        nodes = [self.placed("a", 300.0, 750.0, "combined_statement_weight"),
                 self.placed("b", 100.0, 250.0, "combined_statement_weight"), post]
        self.assertEqual(self.gate_check(nodes), [])

    def test_the_gate_refuses_a_licensed_set_left_unweighted(self):
        nodes = [self.placed("a", 300.0, 500.0, "subtree_weight"), self.placed("b", 100.0, 500.0, "subtree_weight")]
        self.assertTrue(any("every unit" in v for v in self.gate_check(nodes)))

    def test_the_gate_refuses_a_weight_not_every_unit_licenses(self):
        nodes = [self.placed("a", 300.0, 750.0, "combined_statement_weight"),
                 self.placed("c", None, 250.0, "subtree_weight")]
        self.assertTrue(any("not every unit" in v for v in self.gate_check(nodes)))

    def test_the_gate_refuses_a_unit_given_an_implied_share(self):
        nodes = [self.placed("a", 300.0, 750.0, "combined_statement_weight"),
                 self.placed("b", 100.0, 250.0, "combined_statement_weight"),
                 self.placed("c", None, 80.0, "implied_combined_statement_weight")]
        self.assertTrue(any("implied" in v for v in self.gate_check(nodes)))

    def test_the_gate_refuses_shares_out_of_proportion(self):
        nodes = [self.placed("a", 300.0, 500.0, "combined_statement_weight"),
                 self.placed("b", 100.0, 500.0, "combined_statement_weight")]
        self.assertTrue(any("proportion" in v for v in self.gate_check(nodes)))

    def test_the_gate_refuses_a_weight_from_a_figure_filed_elsewhere(self):
        nodes = [self.placed("a", 300.0, 750.0, "combined_statement_weight", another=True),
                 self.placed("b", 100.0, 250.0, "combined_statement_weight")]
        self.assertNotEqual(self.gate_check(nodes), [])

    @unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
    def test_the_published_graph_weights_the_architects_units_only_and_passes(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        pairs = list(walk(graph))
        nodes = [n for n, _ in pairs]
        parents = {str(n.get("id")): str((p or {}).get("id") or "") for n, p in pairs}
        self.assertEqual(gate.combined_statement_weight_violations(nodes, parents, lambda n: n["id"]), [])
        # Only the Architect of the Capitol has a figure on every unit beneath
        # it: seven divisions and the two accounts carried as lines. Its four
        # posts take an implied weight and publish nothing. The Library's Law
        # Library and Folklife Center, and every other set, carry none.
        weighted = sorted(n["id"] for n in nodes if n.get("cost_basis") == "combined_statement_weight")
        self.assertEqual(len(weighted), 9)
        self.assertEqual({parents[i] for i in weighted}, {"leg-support-aoc"})
        implied = [n for n in nodes if n.get("cost_basis") == "implied_combined_statement_weight"]
        self.assertEqual(len(implied), 4)
        self.assertTrue(all(n.get("cost_status") == "unavailable" and "Position" in n.get("type", "") for n in implied))
        self.assertEqual(sum(1 for n in nodes if cs.FIELD in n), 15)
        by_id = {n["id"]: n for n in nodes}
        aoc = by_id["leg-support-aoc"]
        units = sum(by_id[i]["resolved_total_amount"] for i in weighted)
        # Each unit's share is its FY2025 figure times one rate.
        rates = {round(by_id[i]["resolved_total_amount"] / by_id[i][cs.FIELD]["amount"], 9) for i in weighted}
        self.assertEqual(len(rates), 1)
        # What the posts' implied weight withholds is published by nobody.
        self.assertLess(units, aoc["resolved_total_amount"])


@unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
class FullGateTests(unittest.TestCase):
    def test_the_gate_refuses_a_forged_block(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        node = next(n for n, _ in walk(graph) if n.get("id") == "leg-support-loc-nls")
        node[cs.FIELD]["amount"] = 1.0
        tmp = PROJECT_ROOT / "tests" / "_combined_statement_gate_tmp.json"
        try:
            tmp.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate.main(["gate", str(tmp)])
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(code, 1)
        self.assertIn("a Combined Statement figure is the chapter's own printed accounts", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
