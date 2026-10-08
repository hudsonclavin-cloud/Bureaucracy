"""A committee's disbursements: the chamber's own printed totals, beside the
estimate and never as the cost.

The House's Statement of Disbursements and the Senate's Report of the Secretary
of the Senate are the only documents that state what a committee spent. Both
name staff beside what they were paid, and both print a committee's money as
several totals rather than one. So these tests pin four things in both
directions: the documents are read as committed and nothing about a person
leaves them; every figure is the sum of totals the document prints; the new
`disbursements` basis sits on a committee and on nothing else, with the House's
scale bounded by the statement's own marked total; and the gate re-derives
every block and refuses each way one can be faked.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    MINIMAL_GRAPH_FIELDS,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification import committee_disbursements as cd  # noqa: E402
from data_pipeline.verification import financial_evidence as fe  # noqa: E402
from data_pipeline.verification.congress import committee_key  # noqa: E402
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from scripts import validate_published_graph as gate  # noqa: E402

EVIDENCE = cd.DEFAULT_EVIDENCE_PATH
PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def walk(node, parent=None):
    yield node, parent
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from walk(child, node)


class Shared:
    """The documents and the derivation, read once for the whole module."""

    _cache: dict = {}

    @classmethod
    def get(cls):
        if not cls._cache:
            base = load_base_graph(DEFAULT_BASE_GRAPH)
            node_map, parent_map = index_tree(base)
            house = cd.load_house_statement()
            senate = cd.load_senate_report()
            house_records, house_report = cd.build_house_records(node_map, parent_map, house)
            senate_records, senate_report = cd.build_senate_records(node_map, parent_map, senate)
            cls._cache.update(
                base=base, node_map=node_map, parent_map=parent_map, house=house, senate=senate,
                records={**house_records, **senate_records},
                reports={"house": house_report, "senate": senate_report},
            )
        return cls._cache


class DocumentTests(unittest.TestCase):
    """The committed documents, read as the publishers print them."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.s = Shared.get()

    def test_the_house_statement_names_its_quarter_and_its_marked_total(self) -> None:
        house = self.s["house"]
        self.assertEqual(house["period"]["start"], "2026-04-01")
        self.assertEqual(house["period"]["end"], "2026-06-30")
        self.assertEqual(house["statementTotal"]["text"], "$ 449,333,548.30")
        # The marked line plus the deposits is the total the statement prints;
        # the loader refuses the page otherwise, which is what ties the mark to
        # the salaries-and-expenses line rather than to the deposits.
        cents = lambda s: round(float(s.replace("$", "").replace(",", "")) * 100)  # noqa: E731
        self.assertEqual(
            cents(house["statementTotal"]["text"]) + cents(house["statementTotal"]["deposited"]),
            cents(house["statementTotal"]["totalFundsDisbursed"]),
        )

    def test_the_senate_report_names_its_half_year(self) -> None:
        senate = self.s["senate"]
        self.assertEqual(senate["period"]["start"], "2025-10-01")
        self.assertEqual(senate["period"]["end"], "2026-03-31")
        self.assertGreaterEqual(len(senate["sections"]), 70)

    def test_a_tampered_document_is_refused(self) -> None:
        original = cd.HOUSE_CSV
        tmp = PROJECT_ROOT / "tests" / "_disbursement_tmp"
        tmp.mkdir(exist_ok=True)
        try:
            copy = tmp / original.name
            copy.write_bytes(original.read_bytes().replace(b"1571274.53", b"1571274.54"))
            (tmp / (original.name + ".meta.json")).write_bytes(
                original.with_name(original.name + ".meta.json").read_bytes())
            cd.HOUSE_CSV = copy
            with self.assertRaises(cd.Unreadable):
                cd.load_house_statement()
        finally:
            cd.HOUSE_CSV = original
            for path in tmp.glob("*"):
                path.unlink()
            tmp.rmdir()

    def test_no_person_reaches_a_record(self) -> None:
        """The House file read carries no person; the Senate's summary pages
        carry payee rows beneath the block. Nothing from those rows -- the
        column heading over them, a document number, a payee -- may appear in
        what this module writes."""
        text = json.dumps(self.s["records"])
        for marker in ("PAYEE", "DOCUMENT NO", "DATE POSTED", "OBLIGATION/SERVICE", "PERSONNEL COMP",
                       "STAFF PER DIEM", "STAFF TRANSPORTATION", "SERGEANT AT ARMS"):
            self.assertNotIn(marker, text)
        for record in self.s["records"].values():
            for component in record["components"]:
                if record["chamber"] == "senate":
                    self.assertRegex(component["printed"], r"^-?\$[\d,]*\.\d\d$")
                else:
                    self.assertRegex(component["printed"], r"^-?\d+(?:\.\d{1,2})?$")


class MatchingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.s = Shared.get()

    def test_every_house_committee_and_all_but_one_senate_committee(self) -> None:
        records = self.s["records"]
        house = [r for r in records.values() if r["chamber"] == "house"]
        senate = [r for r in records.values() if r["chamber"] == "senate"]
        self.assertEqual(len(house), 21)
        self.assertEqual(len(senate), 19)
        # The Senate Appropriations Committee is not funded from the Inquiries
        # and Investigations account Part II prints; it carries nothing.
        self.assertNotIn("leg-senate-cmte-appropriations", records)

    def test_no_subcommittee_and_no_post_carries_one(self) -> None:
        for node_id in self.s["records"]:
            self.assertEqual(self.s["node_map"][node_id].get("type"), "Committee")

    def test_a_split_committee_is_summed_whole(self) -> None:
        record = self.s["records"]["leg-house-cmte-energy-commerce"]
        self.assertEqual(record["matchRule"], "reviewed_row")
        self.assertIn("2026 COMM ON ENERGY & COMMERCE-MIN", record["listedNames"])
        self.assertEqual({c["label"] for c in record["components"]},
                         {"2026 COMMITTEE ON ENERGY & COMMERCE", "2026 COMM ON ENERGY & COMMERCE-MIN"})

    def test_the_sum_is_the_printed_totals_and_says_so(self) -> None:
        record = self.s["records"]["leg-senate-cmte-agriculture-nutrition-and-forestry"]
        # -$41,659.80, -$13,341.10, -$483,438.47 and -$2,862,601.38 on four pages.
        self.assertEqual(record["amount"], 3401040.75)
        self.assertEqual(record["componentCount"], 4)
        self.assertEqual(record["documentsStatingTheFigure"], 0)
        single = self.s["records"]["leg-house-cmte-permanent-select-committee-on-intelligence"]
        self.assertEqual(single["componentCount"], 1)
        self.assertEqual(single["documentsStatingTheFigure"], 1)
        self.assertEqual(single["amount"], 2087349.75)

    def test_a_credit_printed_without_a_minus_sign_reduces_the_total(self) -> None:
        record = self.s["records"]["leg-senate-cmte-environment-public-works"]
        credit = [c for c in record["components"] if not c["printed"].startswith("-")]
        self.assertEqual([c["amount"] for c in credit], [-1253.55])
        self.assertAlmostEqual(record["amount"], sum(c["amount"] for c in record["components"]), places=2)

    def test_the_gate_mirrors_the_reviewed_rows_by_id(self) -> None:
        mirrored = {
            node_id: (row["chamber"], row["name"], tuple(row["labels"]))
            for node_id, row in cd.REVIEWED_ROWS.items()
        }
        self.assertEqual(mirrored, gate.COMMITTEE_DISBURSEMENT_ROWS)

    def test_the_gate_s_committee_key_is_the_module_s(self) -> None:
        names = [n.get("name") for n in self.s["node_map"].values()
                 if str(n.get("type") or "").casefold() in ("committee", "subcommittee")]
        names += [label for record in self.s["records"].values() for label in record["listedNames"]]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(gate.disbursement_committee_key(name), committee_key(name))

    def test_the_gate_reads_the_documents_as_the_module_does(self) -> None:
        docs = gate.committee_disbursement_documents()
        self.assertNotIn("error", docs)
        self.assertEqual(docs["house"]["statementTotal"], self.s["house"]["statementTotal"]["text"])
        self.assertEqual((docs["house"]["start"], docs["house"]["end"]),
                         (self.s["house"]["period"]["start"], self.s["house"]["period"]["end"]))
        module_sections = sorted((s["label"], s["funding"], s["netPrinted"]) for s in self.s["senate"]["sections"])
        gate_sections = sorted((label, funding, net)
                               for label, items in docs["senate"]["sections"].items() for funding, _p, net in items)
        self.assertEqual(module_sections, gate_sections)

    def test_the_evidence_file_is_the_derivation(self) -> None:
        store = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(store["nodes"], json.loads(json.dumps(self.s["records"])))


def committee_node():
    return {"id": "leg-house-cmte-rules", "name": "House Committee on Rules", "type": "Committee"}


def house_record(**changes):
    record = {
        "nodeId": "leg-house-cmte-rules", "financialEvidenceStatus": "partial", "costBasis": "disbursements",
        "sourceType": "house_statement_of_disbursements", "units": "usd", "normalizedMultiplier": 1,
        "unitsEvidence": ("QTD AMOUNT: 2026 COMMITTEE ON RULES,GENERAL EXPENDITURES,OFFICE TOTALS:,1789655.25,900002.05"
                          " | statement total: $ 449,333,548.30 | anchor: 900002.05"),
        "statementTotal": {"text": "$ 449,333,548.30", "label": "Disbursements for salaries and expenses"},
        "columnAnchor": {"amountRaw": "900002.05", "column": "QTD AMOUNT"},
        "quote": "2026 COMMITTEE ON RULES,GENERAL EXPENDITURES,OFFICE TOTALS:,1789655.25,900002.05",
        "amountRaw": "900002.05", "amount": 900002.05,
        "fiscalYear": 2026, "periodCoverage": "quarter", "periodAsOf": "2026-06-30",
        "retrievedAt": "2026-10-06T16:20:22Z", "scopeMatch": "proxy", "amountScope": "2026 COMMITTEE ON RULES",
        "rollupRole": "subtotal", "sourceUrl": "https://www.house.gov/x.csv", "documentSha256": "a" * 64,
        "locator": {"row": 1},
    }
    record.update(changes)
    return record


def senate_record(**changes):
    evidence = ("NET EXPENDITURES FOR THE PERIOD OF 10/01/2025 THRU 03/31/2026 ($) | "
                "ORGANIZATION TOTALS 4,464,935.00 -$483,438.47 -$4,123,872.49")
    record = house_record(
        sourceType="senate_secretary_report", unitsEvidence=evidence, quote=evidence,
        amountRaw="483,438.47", amount=483438.47, periodCoverage="fiscal_year_to_date", periodAsOf="2026-03-31",
        sourceUrl="https://www.govinfo.gov/x.pdf",
    )
    for key in ("statementTotal", "columnAnchor"):
        record.pop(key)
    record.update(changes)
    return record


class BasisTests(unittest.TestCase):
    """`disbursements` sits on a committee and nothing else, both ways."""

    def test_a_disbursement_on_a_committee_is_accepted(self) -> None:
        self.assertEqual(fe.validate_record(house_record(), committee_node())["unitsEvidenceKind"],
                         "currency_mark_on_the_statements_own_total_bounds_the_column")
        self.assertEqual(fe.validate_record(senate_record(), committee_node())["unitsEvidenceKind"],
                         "currency_mark_on_the_printed_figure")
        sub = dict(committee_node(), type="Subcommittee")
        fe.validate_record(house_record(), sub)  # the validator's scope; the module and gate narrow it

    def test_a_disbursement_on_anything_else_is_refused(self) -> None:
        for node in (
            {"id": "leg-house-cmte-rules", "name": "Library of Congress", "type": "Legislative Agency"},
            {"id": "leg-house-cmte-rules", "name": "Chair, Rules", "type": "Position"},
            dict(committee_node(), synthetic="treasury_receipts"),
        ):
            with self.subTest(type=node["type"]), self.assertRaises(fe.Rejected):
                fe.validate_record(house_record(), node)

    def test_no_other_basis_may_sit_on_a_committee(self) -> None:
        with self.assertRaises(fe.Rejected):
            fe.validate_record(house_record(costBasis="net_outlays", sourceType="treasury_mts"), committee_node())

    def test_the_house_scale_needs_the_statement_s_marked_total(self) -> None:
        refusals = {
            "no statement total": house_record(statementTotal=None),
            "an unmarked total": house_record(statementTotal={"text": "449,333,548.30", "label": "x"}),
            "an anchor too small to rule out thousands":
                house_record(columnAnchor={"amountRaw": "400000.00", "column": "QTD AMOUNT"},
                             amountRaw="400000.00", amount=400000.0,
                             unitsEvidence="QTD AMOUNT 400000.00 | $ 449,333,548.30", quote="x 400000.00"),
            "a figure larger than its anchor":
                house_record(columnAnchor={"amountRaw": "900000", "column": "QTD AMOUNT"}),
            "an anchor larger than the whole House's quarter":
                house_record(columnAnchor={"amountRaw": "500000000", "column": "QTD AMOUNT"},
                             unitsEvidence="QTD AMOUNT 900002.05 500000000 | $ 449,333,548.30"),
            "the total not quoted in the evidence":
                house_record(unitsEvidence="QTD AMOUNT 900002.05"),
            "the rule claimed by another source type":
                house_record(sourceType="senate_secretary_report"),
        }
        for name, record in refusals.items():
            with self.subTest(case=name), self.assertRaises(fe.Rejected):
                fe.validate_record(record, committee_node())

    def test_the_senate_scale_needs_the_mark_on_its_own_figure(self) -> None:
        bare = ("NET EXPENDITURES FOR THE PERIOD OF 10/01/2025 THRU 03/31/2026 ($) | "
                "ORGANIZATION TOTALS 4,464,935.00 -483,438.47 -$4,123,872.49")
        with self.assertRaises(fe.Rejected):
            fe.validate_record(senate_record(unitsEvidence=bare, quote=bare), committee_node())

    def test_a_realized_figure_cannot_be_filed_for_a_year_not_begun(self) -> None:
        with self.assertRaises(fe.Rejected):
            fe.validate_record(house_record(fiscalYear=2030), committee_node())


class ApplyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.s = Shared.get()

    def test_the_field_is_owned_withdrawn_and_published(self) -> None:
        self.assertIn(cd.FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(cd.FIELD, MINIMAL_GRAPH_FIELDS)

    def test_apply_withdraws_refuses_and_stamps(self) -> None:
        record = self.s["records"]["leg-house-cmte-rules"]
        root = {"id": "r", "name": "r", "children": [
            {"id": "leg-house-cmte-rules", "name": "House Committee on Rules", "type": "Committee", "children": []},
            {"id": "x", "name": "x", "type": "Subcommittee", cd.FIELD: {"stale": True}, "children": []},
        ]}
        report = cd.apply_committee_disbursements_evidence(root, {"leg-house-cmte-rules": record, "x": record})
        self.assertEqual(report["applied"], 1)
        self.assertEqual(report["withdrawn_first"], 1)
        self.assertEqual(report["refused_not_a_committee"], 1)
        self.assertNotIn(cd.FIELD, root["children"][1])
        self.assertEqual(root["children"][0][cd.FIELD]["amount"], record["amount"])
        root["children"][0]["name"] = "House Committee on Something Else"
        report = cd.apply_committee_disbursements_evidence(root, {"leg-house-cmte-rules": record})
        self.assertEqual(report["refused_renamed"], 1)
        self.assertNotIn(cd.FIELD, root["children"][0])


class GateTests(unittest.TestCase):
    """The gate accepts the true blocks and refuses each corruption."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.s = Shared.get()
        graph = json.loads(json.dumps(cls.s["base"]))
        cd.apply_committee_disbursements_evidence(graph, cls.s["records"])
        cls.graph = graph
        cls.docs = gate.committee_disbursement_documents()

    def check(self, graph):
        pairs = list(walk(graph))
        tree_parents = {str(n.get("id") or ""): str((p or {}).get("id") or "") for n, p in pairs}
        by_id = {str(n.get("id") or ""): n for n, _ in pairs}
        out = []
        for node, _ in pairs:
            block = node.get(cd.FIELD)
            if isinstance(block, dict):
                out.extend(gate.committee_disbursement_violations(node, block, self.docs, gate.label, tree_parents, by_id))
        return out

    def corrupt(self, node_id, mutate):
        graph = json.loads(json.dumps(self.graph))
        nodes = {n["id"]: n for n, _ in walk(graph) if n.get("id")}
        mutate(nodes[node_id], nodes)
        return self.check(graph)

    def test_the_true_blocks_pass(self) -> None:
        self.assertEqual(self.check(json.loads(json.dumps(self.graph))), [])
        carried = [n for n, _ in walk(self.graph) if n.get(cd.FIELD)]
        self.assertEqual(len(carried), 40)

    def test_each_corruption_is_refused(self) -> None:
        house, senate = "leg-house-cmte-agriculture", "leg-senate-cmte-finance"
        reviewed = "leg-house-cmte-energy-commerce"

        def setblock(key, value):
            return lambda node, nodes: node[cd.FIELD].__setitem__(key, value)

        def move_to(target_id):
            def mutate(node, nodes):
                nodes[target_id][cd.FIELD] = node.pop(cd.FIELD)
            return mutate

        cases = [
            ("a figure the document does not print", house, setblock("amount", 1234.56)),
            ("a component dropped", senate,
             lambda node, nodes: node[cd.FIELD]["components"].pop()),
            ("a component's printed text altered", house,
             lambda node, nodes: node[cd.FIELD]["components"][0].__setitem__("printed", "1.00")),
            ("a digest the committed document does not have", house,
             lambda node, nodes: node[cd.FIELD]["document"].__setitem__("sha256", "0" * 64)),
            ("a period the document does not print", senate,
             lambda node, nodes: node[cd.FIELD]["period"].__setitem__("end", "2026-09-30")),
            ("a label the document does not carry", house, setblock("listedNames", ["2026 COMMITTEE ON NOTHING"])),
            ("the House block moved onto a Senate committee", house, move_to("leg-senate-cmte-agriculture-nutrition-and-forestry")),
            ("a block moved onto another committee of the same chamber", house, move_to("leg-house-cmte-budget")),
            ("a block on a subcommittee", house, lambda node, nodes: node.__setitem__("type", "Subcommittee")),
            ("a block on a post", house, lambda node, nodes: node.__setitem__("type", "Position")),
            ("a block beside a measured cost", house, lambda node, nodes: node.__setitem__("cost_status", "official")),
            ("the estimate equal to the figure", senate,
             lambda node, nodes: node.update(cost_status="allocated", resolved_total_amount=node[cd.FIELD]["amount"])),
            ("the document among the node's own sources", senate,
             lambda node, nodes: node.__setitem__("sourceUrls", [node[cd.FIELD]["document"]["url"]])),
            ("a renamed node", house, lambda node, nodes: node.__setitem__("name", "House Committee on Farming")),
            ("another basis", house, setblock("costBasis", "net_outlays")),
            ("more than a proxy", house, setblock("scopeMatch", "exact")),
            ("a sum claimed to be printed", senate, setblock("documentsStatingTheFigure", 1)),
            ("the not-the-cost sentence removed", senate, setblock("notTheCost", "")),
            ("the House caveat removed", house, setblock("caveat", "")),
            ("a scale bound that is not the statement's", house,
             lambda node, nodes: node[cd.FIELD]["unitsEvidence"].__setitem__("statementTotal", "$ 1.00")),
            ("a reviewed row's labels altered", reviewed, setblock("listedNames", ["2026 COMMITTEE ON ENERGY & COMMERCE"])),
            ("a reviewed committee claimed by the name rule", reviewed, setblock("matchRule", "committee_key_equal")),
            ("a name-rule match claimed as reviewed", house, setblock("matchRule", "reviewed_row")),
            ("an unknown rule", house, setblock("matchRule", "fuzzy")),
        ]
        for name, node_id, mutate in cases:
            with self.subTest(case=name):
                self.assertNotEqual(self.corrupt(node_id, mutate), [], f"{name} was accepted")


@unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
class FullGateTests(unittest.TestCase):
    """Wired into the gate's main: a block with a figure the document does not
    print fails the whole run."""

    def test_the_gate_refuses_a_forged_block(self) -> None:
        import io
        from contextlib import redirect_stdout

        s = Shared.get()
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cd.apply_committee_disbursements_evidence(graph, s["records"])
        node = next(n for n, _ in walk(graph) if n.get("id") == "leg-house-cmte-rules")
        node[cd.FIELD]["amount"] = 1.0
        tmp = PROJECT_ROOT / "tests" / "_disbursement_gate_tmp.json"
        try:
            tmp.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate.main(["gate", str(tmp)])
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(code, 1)
        self.assertIn("a committee's disbursements are the chamber's own printed totals", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()


class PayoutWeightGateTests(unittest.TestCase):
    """The gate's check on committee shares divided by their payouts."""

    @staticmethod
    def _committee(node_id, amount, share, sha="doc", basis="disbursement_weight", start="2026-04-01"):
        node = {"id": node_id, "name": node_id, "cost_status": "allocated", "cost_basis": basis,
                "resolved_total_amount": share}
        if amount is not None:
            node["committeeDisbursements"] = {"amount": amount, "document": {"sha256": sha},
                                              "period": {"start": start, "end": "2026-06-30"}}
        return node

    def _check(self, nodes):
        parents = {str(n["id"]): "grouping" for n in nodes}
        return gate.disbursement_weight_violations(nodes, parents, lambda n: n["id"])

    def test_proportional_shares_from_one_statement_pass(self):
        nodes = [self._committee("a", 3000.0, 750.0), self._committee("b", 1000.0, 250.0),
                 self._committee("c", None, 500.0, basis="implied_disbursement_weight")]
        self.assertEqual(self._check(nodes), [])

    def test_shares_out_of_proportion_fail(self):
        nodes = [self._committee("a", 3000.0, 500.0), self._committee("b", 1000.0, 500.0)]
        self.assertTrue(any("proportion" in v for v in self._check(nodes)))

    def test_two_statements_in_one_set_fail(self):
        nodes = [self._committee("a", 3000.0, 750.0), self._committee("b", 1000.0, 250.0, sha="other")]
        self.assertTrue(any("different statements" in v for v in self._check(nodes)))

    def test_a_payout_weight_without_its_block_fails(self):
        nodes = [self._committee("a", 3000.0, 750.0), self._committee("b", None, 250.0)]
        self.assertTrue(any("does not carry" in v for v in self._check(nodes)))

    def test_an_implied_payout_with_nothing_to_imply_it_from_fails(self):
        nodes = [self._committee("c", None, 500.0, basis="implied_disbursement_weight")]
        self.assertTrue(any("no sibling" in v for v in self._check(nodes)))

    def test_an_implied_payout_beside_its_own_block_fails(self):
        nodes = [self._committee("a", 3000.0, 750.0),
                 self._committee("b", 1000.0, 250.0, basis="implied_disbursement_weight")]
        self.assertTrue(any("given an implied one" in v for v in self._check(nodes)))

    def test_a_payout_weight_on_a_measured_figure_fails(self):
        node = self._committee("a", 3000.0, 750.0)
        node["cost_status"] = "official"
        self.assertTrue(any("payout weight on" in v for v in self._check([node])))

    def test_the_published_graph_passes(self):
        graph_path = Path(__file__).resolve().parents[1] / "output" / "graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        nodes, parents, stack = [], {}, [graph]
        while stack:
            node = stack.pop()
            nodes.append(node)
            for child in node.get("children") or []:
                parents[str(child["id"])] = str(node["id"])
                stack.append(child)
        self.assertEqual(gate.disbursement_weight_violations(nodes, parents, lambda n: n["id"]), [])
        self.assertEqual(sum(1 for n in nodes if n.get("cost_basis") == "disbursement_weight"), 40)
