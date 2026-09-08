"""The statement's own tree, read off the real 2026-07-31 Table 5.

tests/fixtures/mts_table5_latest.json is the FiscalData API response
verbatim. Everything asserted here is a fact about that file, not about the
code's expectations of it.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.crawler.treasury_outlays import parse_outlay_rows
from data_pipeline.exporter.build_graph import collect_treasury_outlay_rows
from data_pipeline.exporter.treasury_sections import RECEIPTS_LABELS, SectionTree, UNDISTRIBUTED_LABEL, plain_label

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mts_table5_latest.json"


def load_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows, summary = parse_outlay_rows(raw["rows"])
    return raw, rows, summary


class CrawlerKeepsTheTreeTests(unittest.TestCase):
    def test_headers_are_kept_and_flagged_and_every_row_carries_its_ids(self) -> None:
        raw, rows, summary = load_fixture()
        self.assertEqual(raw["record_date"], "2026-07-31")
        self.assertEqual(summary["government_total_outlay_amount"], 6284235715734.18)
        headers = [r for r in rows if r["is_header"]]
        self.assertEqual(len(headers), 154)
        self.assertTrue(all(r["rollup_total_amount"] is None for r in headers))
        self.assertTrue(all(r["classification_id"] and r["parent_id"] is not None or r["parent_id"] is None for r in rows))
        self.assertTrue(all(r.get("classification_id") for r in rows))
        # The grand total and the surplus block are never lines.
        names = {r["originalName"] for r in rows}
        self.assertNotIn("Total Outlays", names)
        self.assertNotIn("Total Surplus (+) or Deficit (-)", names)
        self.assertNotIn("Total On-Budget", names)

    def test_consumers_that_want_a_figure_skip_the_headers(self) -> None:
        _, rows, summary = load_fixture()
        figures = collect_treasury_outlay_rows([{"outlayRows": rows, "budgetSummary": summary}])
        self.assertTrue(all(r["rollup_total_amount"] not in (None, 0) for r in figures))
        self.assertEqual(len(figures), 644, "every priced line, the same 644 the cascade always saw; the 154 headers are new and skipped")


class SectionTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, rows, summary = load_fixture()
        cls.tree = SectionTree.from_rows(rows)
        cls.anchor = summary["government_total_outlay_amount"]

    def test_the_identity_holds_to_the_cent(self) -> None:
        identity = self.tree.identity(self.anchor)
        self.assertEqual(identity["sections"], 30)
        self.assertTrue(identity["holds"], identity)
        self.assertEqual(identity["difference"], 0.0)

    def test_every_section_nets_to_its_printed_total_but_one(self) -> None:
        mismatches = self.tree.section_mismatches()
        self.assertEqual([m["section"] for m in mismatches], ["International Assistance Programs"])
        self.assertAlmostEqual(mismatches[0]["lines_sum"] - mismatches[0]["printed_total"], 1096539.75, places=1)

    def test_a_department_total_is_net_of_its_own_receipts(self) -> None:
        legislative = next(s for s in self.tree.top_sections() if plain_label(s) == "Legislative Branch")
        self.assertEqual(self.tree.section_total(legislative), 5836998774.43)
        receipts = self.tree.receipts_rows(legislative)
        self.assertEqual([plain_label(r) for r in receipts], ["Proprietary Receipts from the Public", "Intrabudgetary Transactions", "Offsetting Governmental Receipts"])
        self.assertAlmostEqual(sum(self.tree.amount(r) for r in receipts), -61229949.26, places=2)
        lines = [k for k in self.tree.kids(legislative) if plain_label(k) not in RECEIPTS_LABELS and not k["originalName"].startswith("Total")]
        self.assertAlmostEqual(sum(self.tree.amount(r) for r in lines) + sum(self.tree.amount(r) for r in receipts), 5836998774.43, places=2)

    def test_the_undistributed_section_is_government_wide_and_negative(self) -> None:
        undistributed = self.tree.undistributed_section()
        self.assertIsNotNone(undistributed)
        self.assertEqual(self.tree.section_total(undistributed), -343316737551.34)
        self.assertEqual({plain_label(r) for r in self.tree.receipts_rows(undistributed)},
                         {"Employer Share, Employee Retirement", "Interest Received by Trust Funds",
                          "Rents and Royalties on the Outer Continental Shelf Lands", "Sale of Major Assets", "Other Interest"})
        # The section's own lines are exactly its printed total: nothing is left out.
        self.assertAlmostEqual(sum(self.tree.amount(r) for r in self.tree.receipts_rows(undistributed)), -343316737551.34, places=2)

    def test_receipts_components_are_never_organisations(self) -> None:
        components = self.tree.receipts_component_ids()
        navy_receipts = [r for r in self.tree.rows.values() if r["originalName"] == "Department of the Navy" and self.tree.amount(r) < 0]
        self.assertTrue(navy_receipts)
        self.assertTrue(all(r["classification_id"] in components for r in navy_receipts))
        navy_lines = [r for r in self.tree.rows.values() if r["originalName"] == "Department of the Navy" and self.tree.amount(r) > 0]
        self.assertTrue(navy_lines)
        self.assertFalse(any(r["classification_id"] in components for r in navy_lines))
        self.assertIn(UNDISTRIBUTED_LABEL, {plain_label(self.tree.rows[i]) for i in components if i in self.tree.rows})

    def test_a_line_that_is_also_a_section_keeps_its_own_amount(self) -> None:
        peace = next(r for r in self.tree.rows.values() if r["originalName"] == "Peace Corps")
        self.assertTrue(self.tree.kids(peace))
        self.assertEqual(self.tree.amount(peace), 335797574.1)

    def test_a_row_knows_its_top_level_section(self) -> None:
        tax_court = next(r for r in self.tree.rows.values() if r["originalName"] == "United States Tax Court")
        self.assertEqual(plain_label(self.tree.top_section_of(tax_court)), "Legislative Branch")
        irs = next(r for r in self.tree.rows.values() if r["originalName"] == "Total--Internal Revenue Service")
        self.assertEqual(plain_label(self.tree.top_section_of(irs)), "Department of the Treasury")

    def test_a_payload_without_ids_yields_no_tree(self) -> None:
        self.assertFalse(SectionTree.from_rows([{"originalName": "x", "rollup_total_amount": 1.0}]).complete)
