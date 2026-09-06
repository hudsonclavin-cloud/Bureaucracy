"""Treasury per-agency outlay lines reach the nodes they name.

The crawler has always returned Table 5 of the Monthly Treasury Statement under
payload['outlayRows']; until this wiring nothing read them, so every agency was
an estimate apportioned from the single total while its measured outlays sat
unused in the payload. The fixture mimics the shapes that bite: a department's
header and "Total--" lines normalising to one name, a generic sub-line shared
by several departments, a line naming a branch whose base-graph name differs,
a "--" qualified department name, and lines no organisation owns.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph
from data_pipeline.processors.normalize_nodes import verify_node_sources
from scripts.validate_published_graph import main as gate_main


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
DATASET_URL = "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"
TOTAL = 1_000_000_000_000.0

BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {
            "id": "legislative-branch",
            "name": "Legislative Branch — The Congress",
            "type": "Branch",
            "children": [
                {
                    "id": "leg-senate",
                    "name": "United States Senate",
                    "type": "Chamber",
                    "children": [
                        {"id": "leg-sub-legislative-branch", "name": "Legislative Branch", "type": "Subcommittee", "children": []}
                    ],
                }
            ],
        },
        {
            "id": "executive-branch",
            "name": "Executive Branch",
            "type": "Branch",
            "children": [
                {
                    "id": "exec-dept-treasury",
                    "name": "Department of the Treasury",
                    "type": "Cabinet Department",
                    "children": [
                        {"id": "exec-dept-treasury-irs", "name": "Internal Revenue Service (IRS)", "type": "Bureau", "children": []},
                        {"id": "exec-dept-treasury-osec", "name": "Office of the Secretary", "type": "Office", "children": []},
                        {"id": "exec-dept-treasury-secretary", "name": "Secretary of the Treasury", "type": "Position", "children": []},
                    ],
                },
                {
                    "id": "exec-dept-hhs",
                    "name": "Department of Health and Human Services",
                    "type": "Cabinet Department",
                    "children": [
                        {"id": "exec-dept-hhs-osec", "name": "Office of the Secretary", "type": "Office", "children": []}
                    ],
                },
                {"id": "exec-dept-defense", "name": "Department of Defense (DoD)", "type": "Cabinet Department", "children": []},
                {"id": "exec-ind-misc", "name": "Other Independent Agencies (25+)", "type": "Division", "children": []},
            ],
        },
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}


def _row(name, amount, *, original=None, level=1, order=0):
    return {
        "name": name,
        "originalName": original or name,
        "rollup_total_amount": amount,
        "amount_kind": "fytd_net_outlays",
        "budget_year": "2026",
        "budget_as_of": "2026-06-30",
        "source_system": "Treasury Fiscal Data",
        "budget_source": "Treasury MTS Table 5",
        "allocation_basis": "treasury_rollup",
        "sourceUrls": [DATASET_URL],
        "sourceTypes": ["treasury_outlays"],
        "sequence_level": level,
        "print_order": order,
    }


ROWS = [
    _row("Legislative Branch", 5e9, order=1),
    _row("Judicial Branch", 8e9, order=2),
    _row("Department of the Treasury", 100.0, order=10),  # header line, tiny placeholder
    _row("Internal Revenue Service", 12e9, level=2, order=11),
    _row("Office of the Secretary", 1e9, level=2, order=12),  # shared by two departments
    _row("Department of the Treasury", 300e9, original="Total--Department of the Treasury", order=13),
    _row("Department of Defense--Military Programs", 400e9, order=20),
    _row("Undistributed Offsetting Receipts", -50e9, order=90),
    _row("Interest on Treasury Debt Securities (Gross)", 90e9, order=91),
]


def _index(node, out=None, parent=None):
    out = {} if out is None else out
    out[node["id"]] = (node, parent)
    for child in node.get("children", []):
        _index(child, out, node)
    return out


class TreasuryOutlayWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"treasury-{uuid.uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.base_graph_path = self.tmp_path / "base.json"
        self.base_graph_path.write_text(json.dumps(BASE), encoding="utf-8")
        self.paths = dict(
            base_graph_path=self.base_graph_path,
            graph_output_path=self.tmp_path / "graph.json",
            nodes_output_path=self.tmp_path / "expanded_nodes.json",
            edges_output_path=self.tmp_path / "expanded_edges.json",
            validity_report_output_path=self.tmp_path / "node_validity_report.json",
            enforce_export_gate=True,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def _build(self, rows):
        payload = {
            "nodes": [],
            "edges": [],
            "outlayRows": json.loads(json.dumps(rows)),
            "budgetSummary": {"government_total_outlay_amount": TOTAL, "record_date": "2026-06-30", "amount_kind": "fytd_net_outlays"},
        }
        return build_graph([payload], **self.paths)

    def test_lines_land_on_the_nodes_they_name(self) -> None:
        result = self._build(ROWS)
        nodes = _index(result.graph)
        stats = result.validation["treasury_outlay_rows"]

        # Branch lines go to the branch, not to the subcommittee named after it.
        self.assertEqual(nodes["legislative-branch"][0]["resolved_total_amount"], 5e9)
        self.assertEqual(nodes["legislative-branch"][0]["cost_status"], "official")
        self.assertIsNone(nodes["leg-sub-legislative-branch"][0].get("rollup_total_amount"))
        self.assertEqual(nodes["judicial-branch"][0]["resolved_total_amount"], 8e9)
        # The Total-- line wins over the header line with the same name.
        self.assertEqual(nodes["exec-dept-treasury"][0]["resolved_total_amount"], 300e9)
        self.assertEqual(nodes["exec-dept-treasury"][0]["treasury_row_name"], "Total--Department of the Treasury")
        # A sub-line under its department.
        self.assertEqual(nodes["exec-dept-treasury-irs"][0]["resolved_total_amount"], 12e9)
        self.assertEqual(nodes["exec-dept-treasury-irs"][0]["cost_status"], "official")
        # "Department of Defense--Military Programs" matches on its prefix.
        self.assertEqual(nodes["exec-dept-defense"][0]["resolved_total_amount"], 400e9)
        # A name two departments share is applied to neither.
        self.assertEqual(nodes["exec-dept-treasury-osec"][0]["cost_status"], "allocated")
        self.assertEqual(nodes["exec-dept-hhs-osec"][0]["cost_status"], "allocated")
        # A position never receives an agency's outlays.
        self.assertEqual(nodes["exec-dept-treasury-secretary"][0]["cost_status"], "allocated")

        self.assertEqual(stats["rows_applied"], 5)
        self.assertEqual(stats["rows_superseded"], 1)
        self.assertEqual(stats["rows_ambiguous"], 1)
        self.assertEqual(stats["rows_unmatched"], 1)
        self.assertEqual(stats["rows_negative_skipped"], 1)
        self.assertEqual(stats["ambiguous_sample"], ["Office of the Secretary"])
        self.assertEqual(stats["unmatched_sample"], ["Interest on Treasury Debt Securities (Gross)"])
        self.assertEqual(stats["negative_sample"], ["Undistributed Offsetting Receipts"])

    def test_applied_lines_are_measured_and_carry_their_source(self) -> None:
        result = self._build(ROWS)
        nodes = _index(result.graph)
        treasury = nodes["exec-dept-treasury"][0]
        self.assertEqual(treasury["costVerificationStatus"], "verified")
        self.assertEqual(treasury["costVerificationReason"], "matched_official_rollup")
        self.assertEqual(treasury["costSourceCount"], 1)
        self.assertEqual(treasury["sourceUrls"], [DATASET_URL])
        self.assertEqual(treasury["sourceCount"], 1)
        self.assertIn("treasury_outlays", treasury["sourceTypes"])
        self.assertEqual(treasury["budget_as_of"], "2026-06-30")
        self.assertEqual(treasury["amount_kind"], "fytd_net_outlays")
        self.assertIsNone(treasury["lastVerified"])
        # The remainder still reconciles: executive-branch = total - leg - jud.
        executive = nodes["executive-branch"][0]
        self.assertAlmostEqual(executive["resolved_total_amount"], TOTAL - 5e9 - 8e9, places=2)
        children_sum = sum(child["resolved_total_amount"] for child in executive["children"])
        self.assertAlmostEqual(children_sum, executive["resolved_total_amount"], places=2)
        # HHS got no line, so it is still an estimate — and says so.
        self.assertEqual(nodes["exec-dept-hhs"][0]["cost_status"], "allocated")
        self.assertEqual(nodes["exec-dept-hhs"][0]["costVerificationStatus"], "unverified")

    def test_the_release_gate_accepts_treasury_lines_as_measured(self) -> None:
        result = self._build(ROWS)
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("root + 5 Treasury line(s)", out.getvalue())

    def test_a_measured_claim_without_a_treasury_line_fails_the_gate(self) -> None:
        result = self._build(ROWS)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        hhs = next(c for c in graph["children"][1]["children"] if c["id"] == "exec-dept-hhs")
        hhs["costVerificationStatus"] = "verified"
        corrupted = self.tmp_path / "corrupted.json"
        corrupted.write_text(json.dumps(graph), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(corrupted)])
        self.assertEqual(code, 1)
        self.assertIn("Department of Health and Human Services", out.getvalue())

    def test_fresh_lines_replace_stale_rollups(self) -> None:
        self._build(ROWS)
        fewer = [row for row in ROWS if row["name"] != "Internal Revenue Service"]
        second = self._build(fewer)
        nodes = _index(second.graph)
        self.assertEqual(nodes["exec-dept-treasury-irs"][0]["cost_status"], "allocated")
        self.assertIsNone(nodes["exec-dept-treasury-irs"][0].get("rollup_total_amount"))
        self.assertEqual(nodes["exec-dept-treasury"][0]["resolved_total_amount"], 300e9)
        self.assertGreaterEqual(second.validation["treasury_outlay_rows"]["stale_rollups_cleared"], 1)

    def test_the_run_writes_a_budget_vs_actual_report(self) -> None:
        result = self._build(ROWS)
        summary = result.validation["budget_reconciliation"]
        self.assertGreaterEqual(summary["actual_only_rows"] + summary["complete_rows"], 5)
        report_path = self.tmp_path / "budget_reconciliation.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        rows = {row["id"]: row for row in report["rows"]}
        self.assertEqual(rows["exec-dept-treasury"]["actual_amount"], 300e9)
        self.assertEqual(rows["exec-dept-treasury"]["actual_as_of"], "2026-06-30")
        self.assertNotIn("exec-dept-treasury-secretary", rows)

    def test_no_lines_means_no_change(self) -> None:
        result = self._build([])
        nodes = _index(result.graph)
        self.assertEqual(nodes["exec-dept-treasury"][0]["cost_status"], "allocated")
        self.assertEqual(result.validation["treasury_outlay_rows"]["rows"], 0)


class LastVerifiedTests(unittest.TestCase):
    def test_a_source_url_does_not_invent_a_verification_date(self) -> None:
        node = verify_node_sources({"sourceUrls": ["https://www.energy.gov/about"]})
        self.assertEqual(node["sourceCount"], 1)
        self.assertIsNone(node["lastVerified"])
        kept = verify_node_sources({"sourceUrls": ["https://www.energy.gov/about"], "lastVerified": "2026-01-02"})
        self.assertEqual(kept["lastVerified"], "2026-01-02")


if __name__ == "__main__":
    unittest.main()
