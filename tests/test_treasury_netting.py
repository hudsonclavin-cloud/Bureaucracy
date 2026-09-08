"""Publishing the statement's true lines, on the real 2026-07-31 Table 5.

The cascade used to set every negative line aside and cap every measured
department at 96% of what the Treasury reported. Now each section's
receipts are carried as one explicit negative line beneath the unit whose
net total they reduce, the government-wide receipts sit beside the three
branches, and the whole construction is gated on the statement's own
identity — every section total plus the undistributed receipts summing to
Total Outlays. Every number asserted here is read off the fixture.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.crawler.treasury_outlays import parse_outlay_rows
from data_pipeline.exporter.build_graph import (
    UNDISTRIBUTED_NODE_ID,
    build_graph,
    index_tree,
    summarize_scaled_official,
)
from scripts.validate_published_graph import main as gate_main

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mts_table5_latest.json"
TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"

# Names are the statement's own labels so the lines match without aliases.
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-senate", "name": "Senate", "type": "Chamber", "children": []},
            {"id": "leg-house", "name": "House of Representatives", "type": "Chamber", "children": []},
            {"id": "leg-joint", "name": "Joint Committees", "type": "Division", "children": []},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-dept-treasury", "name": "Department of the Treasury", "type": "Cabinet Department", "children": [
                {"id": "exec-dept-treasury-irs", "name": "Internal Revenue Service", "type": "Component Agency", "children": []},
                {"id": "exec-dept-treasury-mint", "name": "United States Mint", "type": "Component Agency", "children": [
                    {"id": "exec-dept-treasury-mint-director", "name": "Director of the Mint", "type": "Position", "children": []},
                ]},
                {"id": "exec-dept-treasury-curator", "name": "Office of the Curator", "type": "Office", "children": []},
            ]},
            {"id": "exec-eop", "name": "Executive Office of the President", "type": "Office", "children": [
                {"id": "exec-eop-omb", "name": "Office of Management and Budget", "type": "Office", "children": []},
                {"id": "exec-eop-cea", "name": "Council of Economic Advisers", "type": "Office", "children": []},
            ]},
            {"id": "exec-regulatory", "name": "Independent Regulatory Commissions", "type": "Division", "children": [
                {"id": "exec-regulatory-fdic", "name": "Federal Deposit Insurance Corporation", "type": "Government Corporation", "children": []},
                {"id": "exec-regulatory-fed", "name": "Federal Reserve System", "type": "Independent Agency", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": [
            {"id": "jud-scotus", "name": "Supreme Court of the United States", "type": "Court", "children": []},
            {"id": "jud-specialized-tax", "name": "United States Tax Court", "type": "Court", "children": []},
        ]},
    ],
}


def statement_payload(*, anchor_offset: float = 0.0):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows, summary = parse_outlay_rows(raw["rows"])
    summary = dict(summary)
    summary["government_total_outlay_amount"] = summary["government_total_outlay_amount"] + anchor_offset
    return {"nodes": [], "edges": [], "budgetSummary": summary, "outlayRows": rows}


def row_amount(name):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    matches = [r for r in raw["rows"] if r["classification_desc"] == name]
    assert len(matches) == 1, (name, len(matches))
    return float(matches[0]["current_fytd_net_outly_amt"])


class NettingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"netting-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, payloads, *, reuse=False):
        return build_graph(
            payloads, base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "expanded_nodes.json", edges_output_path=self.tmp / "expanded_edges.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=reuse,
            existing_graph_payload_path=self.tmp / "graph.json", enforce_export_gate=True, evidence_path=None, sites_path=None,
        )

    def _gate(self, path):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(path)])
        return code, out.getvalue()

    def _graph(self, result):
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        return graph, index_tree(graph)[0]

    def test_every_department_publishes_the_treasury_s_own_net_figure(self) -> None:
        result = self._build([statement_payload()])
        graph, nodes = self._graph(result)
        netting = result.validation["treasury_outlay_rows"]["treasury_netting"]
        self.assertTrue(netting["applied"], netting)
        self.assertTrue(netting["identity"]["holds"])
        treasury = nodes["exec-dept-treasury"]
        self.assertEqual(treasury["cost_status"], "official")
        self.assertEqual(treasury["resolved_total_amount"], row_amount("Total--Department of the Treasury"))
        self.assertEqual(treasury["treasury_section"], "Department of the Treasury")
        self.assertTrue(treasury["treasury_netted"])
        receipts = nodes["exec-dept-treasury--treasury-receipts"]
        self.assertEqual(receipts["synthetic"], "treasury_receipts")
        self.assertEqual(receipts["type"], "Treasury accounting line")
        self.assertLess(receipts["resolved_total_amount"], 0)
        # Treasury's section prints two of the three receipts labels; the components are exactly what it prints.
        self.assertEqual({c["name"] for c in receipts["treasury_component_rows"]},
                         {"Proprietary Receipts from the Public", "Intrabudgetary Transactions"})
        self.assertIn("fiscaldata.treasury.gov", receipts["sourceUrls"][0])
        self.assertEqual(receipts["descriptionSource"], "generated_from_treasury_lines")
        self.assertIn("Not an organisation", receipts["desc"], "the curated field is desc, and the page reads that one")
        # The lines, the receipts and the estimate for the unlined office sum to the net figure, to the cent.
        self.assertAlmostEqual(sum(c["resolved_total_amount"] for c in treasury["children"]), treasury["resolved_total_amount"], places=2)
        self.assertEqual(nodes["exec-dept-treasury-curator"]["cost_status"], "allocated")
        self.assertEqual(summarize_scaled_official(graph)["top_most_nodes"], 0, "nothing is capped any more")

    def test_a_negative_line_is_published_as_the_treasury_reports_it(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        mint = nodes["exec-dept-treasury-mint"]
        self.assertEqual((mint["cost_status"], mint["resolved_total_amount"]), ("official", row_amount("United States Mint")))
        self.assertLess(mint["resolved_total_amount"], 0)
        # Nothing can be apportioned from a negative figure, and the position says why.
        director = nodes["exec-dept-treasury-mint-director"]
        self.assertEqual((director["cost_status"], director["cost_validation"]), ("unavailable", "treasury_pool_negative"))
        self.assertLess(mint["treasury_pool_negative"], 0)

    def test_the_government_wide_receipts_sit_beside_the_three_branches(self) -> None:
        graph, nodes = self._graph(self._build([statement_payload()]))
        self.assertEqual([c["id"] for c in graph["children"]],
                         ["legislative-branch", "executive-branch", "judicial-branch", UNDISTRIBUTED_NODE_ID])
        line = nodes[UNDISTRIBUTED_NODE_ID]
        self.assertEqual(line["resolved_total_amount"], row_amount("Total--Undistributed Offsetting Receipts"))
        self.assertEqual(line["cost_status"], "official")
        self.assertTrue(line["attachToRoot"])
        self.assertNotIn("parentId", line)
        self.assertAlmostEqual(sum(c["resolved_total_amount"] for c in graph["children"]), graph["resolved_total_amount"], places=2)
        self.assertEqual(nodes["legislative-branch"]["resolved_total_amount"], row_amount("Total--Legislative Branch"))
        self.assertEqual(nodes["legislative-branch"]["cost_status"], "official")

    def test_a_line_filed_under_another_section_is_measured_but_outside_its_parent_s_total(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        tax = nodes["jud-specialized-tax"]
        self.assertEqual((tax["cost_status"], tax["resolved_total_amount"]), ("official", row_amount("United States Tax Court")))
        self.assertTrue(tax["treasury_external_section"])
        self.assertEqual(tax["treasury_section"], "Legislative Branch")
        judicial = nodes["judicial-branch"]
        inside = [c for c in judicial["children"] if not c.get("treasury_external_section")]
        self.assertEqual({c["id"] for c in inside}, {"jud-scotus", "judicial-branch--treasury-receipts"})
        # This small graph has no node for the courts of appeals and district
        # courts, so their $9.5B goes nowhere: children sum below the branch,
        # never past it, and the branch says how much is unapportioned.
        inside_sum = sum(c["resolved_total_amount"] for c in inside)
        self.assertLess(inside_sum, judicial["resolved_total_amount"])
        self.assertAlmostEqual(judicial["treasury_unapportioned"], judicial["resolved_total_amount"] - inside_sum, places=2)
        self.assertAlmostEqual(judicial["treasury_unapportioned"],
                               row_amount("Courts of Appeals, District Courts, and Other Judicial Services") + 732405810.89, places=2)

    def test_a_unit_whose_lines_exceed_its_net_total_declares_the_negative_pool(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        eop = nodes["exec-eop"]
        self.assertEqual((eop["cost_status"], eop["resolved_total_amount"]), ("official", row_amount("Total--Executive Office of the President")))
        self.assertLess(eop["resolved_total_amount"], 0)
        self.assertLess(eop["treasury_pool_negative"], 0)
        self.assertEqual(nodes["exec-eop-omb"]["cost_status"], "official")
        self.assertEqual((nodes["exec-eop-cea"]["cost_status"], nodes["exec-eop-cea"]["cost_validation"]), ("unavailable", "treasury_pool_negative"))
        # The lines and the receipts exceed the total by exactly the declared pool.
        total = sum(c["resolved_total_amount"] for c in eop["children"] if c["resolved_total_amount"] is not None)
        self.assertAlmostEqual(total - eop["resolved_total_amount"], -eop["treasury_pool_negative"], places=2)

    def test_a_grouping_whose_measured_members_net_below_zero_says_so(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        regulatory = nodes["exec-regulatory"]
        fdic = nodes["exec-regulatory-fdic"]
        self.assertEqual(fdic["cost_status"], "official")
        self.assertLess(fdic["resolved_total_amount"], 0)
        self.assertEqual(regulatory["cost_status"], "allocated")
        self.assertLess(regulatory["measured_net_beneath"], 0)
        # The Fed is off the statement: an estimate, from the grouping's excess share, never from the FDIC's receipts.
        fed = nodes["exec-regulatory-fed"]
        self.assertEqual(fed["cost_status"], "allocated")
        self.assertAlmostEqual(fed["resolved_total_amount"], regulatory["resolved_total_amount"] - fdic["resolved_total_amount"], places=2)

    def test_the_whole_construction_rests_on_the_statement_s_identity(self) -> None:
        result = self._build([statement_payload(anchor_offset=1000.0)])
        netting = result.validation["treasury_outlay_rows"]["treasury_netting"]
        self.assertFalse(netting["applied"])
        self.assertEqual(netting["reason"], "identity_failed")
        self.assertFalse(netting["identity"]["holds"])
        graph, nodes = self._graph(result)
        self.assertEqual([c["id"] for c in graph["children"]], ["legislative-branch", "executive-branch", "judicial-branch"])
        self.assertFalse([i for i in nodes if i.endswith("--treasury-receipts")])
        self.assertNotIn("treasury_section", nodes["exec-dept-treasury"])

    def test_receipts_lines_are_carried_forward_and_never_duplicated(self) -> None:
        first = self._build([statement_payload()])
        _, nodes = self._graph(first)
        lines = sorted(i for i in nodes if nodes[i].get("synthetic") == "treasury_receipts")
        self.assertTrue(lines)
        # No statement: the published lines ride along, receipts included.
        carried = self._build([{"nodes": [], "edges": [], "budgetSummary": statement_payload()["budgetSummary"]}], reuse=True)
        _, nodes = self._graph(carried)
        self.assertEqual(sorted(i for i in nodes if nodes[i].get("synthetic") == "treasury_receipts"), lines)
        self.assertEqual(carried.validation["treasury_outlay_rows"]["treasury_netting"]["reason"], "carried_forward")
        self.assertEqual(nodes["exec-dept-treasury"]["resolved_total_amount"], row_amount("Total--Department of the Treasury"))
        # A fresh statement replaces them: the same ids, once each.
        again = self._build([statement_payload()], reuse=True)
        graph, nodes = self._graph(again)
        self.assertEqual(sorted(i for i in nodes if nodes[i].get("synthetic") == "treasury_receipts"), lines)
        self.assertGreater(again.validation["treasury_outlay_rows"]["synthetic_receipts_cleared"], 0)
        self.assertEqual(sum(1 for c in graph["children"] if c["id"] == UNDISTRIBUTED_NODE_ID), 1)

    def test_the_gate_accepts_the_true_lines_and_refuses_each_way_they_can_be_faked(self) -> None:
        result = self._build([statement_payload()])
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))

        def corrupt(mutate):
            corrupted = json.loads(json.dumps(graph))
            mutate(corrupted, index_tree(corrupted)[0])
            path = self.tmp / f"{uuid.uuid4().hex}.json"
            path.write_text(json.dumps(corrupted), encoding="utf-8")
            return self._gate(path)

        cases = {
            "a negative amount without a Treasury line": lambda g, n: n["leg-joint"].__setitem__("resolved_total_amount", -5.0),
            "a zero amount": lambda g, n: n["leg-senate"].__setitem__("resolved_total_amount", 0.0),
            "a second receipts line at the root": lambda g, n: g["children"].append(dict(n[UNDISTRIBUTED_NODE_ID], id="treasury-undistributed-offsetting-receipts-2")),
            "an ordinary node at the root": lambda g, n: g["children"].append({"id": "x", "name": "X", "type": "Agency", "cost_status": "unavailable", "children": []}),
            "a child past the parent and its negative lines": lambda g, n: n["exec-dept-treasury-irs"].__setitem__(
                "resolved_total_amount",
                n["exec-dept-treasury"]["resolved_total_amount"]
                - sum(c["resolved_total_amount"] for c in n["exec-dept-treasury"]["children"] if (c.get("resolved_total_amount") or 0) < 0)
                + 1e6),
            "children past a negative pool that is not declared": lambda g, n: n["exec-eop"].pop("treasury_pool_negative"),
            "a receipts line hidden as unavailable": lambda g, n: n["exec-dept-treasury--treasury-receipts"].update({"cost_status": "unavailable", "resolved_total_amount": None}),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                code, out = corrupt(mutate)
                self.assertEqual(code, 1, f"{name}:\n{out}")
