"""The flat CSV (Part 2, "Export / download"): one row per node in tree
order, figures the nodes' own, blanks where the graph publishes nothing, the
gate's column mirror equal to the script's, the committed file a fresh render,
and the page naming the files it offers."""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from scripts import export_flat_csv as ex  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"
CSV_PATH = PROJECT_ROOT / "output" / "nodes.csv"
INDEX = PROJECT_ROOT / "index.html"


class RenderTests(unittest.TestCase):
    def test_columns_are_mirrored_by_the_gate(self):
        self.assertEqual(tuple(ex.COLUMNS), gate.FLAT_CSV_COLUMNS)

    def test_a_small_graph_renders_one_row_per_node_with_blanks_for_nothing(self):
        graph = {
            "id": "the-constitution-of-the-united-states", "name": "Constitution", "type": "Foundation", "cost_status": "root_total", "resolved_total_amount": 1000.0,
            "children": [
                {"id": "exec", "name": "Executive", "type": "Branch", "cost_status": "official", "resolved_total_amount": 600.0, "treasury_row_name": "Executive",
                 "sourceUrls": ["https://fiscaldata.treasury.gov/x"], "verificationMethod": "name_labelled_on_own_official_page", "verificationSiteFrom": "https://www.whitehouse.gov/", "lastVerified": "2026-09-13",
                 "children": [
                     {"id": "sec", "name": "Secretary", "type": "Position", "cost_status": "unavailable", "cost_validation": "post_is_not_a_budget_unit",
                      "positionSchedulePay": {"amount": 253100.0, "url": "https://www.opm.gov/ex", "source": "us_code_executive_schedule", "verification": {"documents": 2}}, "children": []},
                     {"id": "unit", "name": "Unit", "type": "Office", "cost_status": "allocated", "resolved_total_amount": 10.0,
                      "ombBudget": {"outlays": -5.0, "fiscalYear": 2025, "url": "https://www.govinfo.gov/omb"}, "children": []},
                 ]},
            ],
        }
        rows = list(csv.DictReader(io.StringIO(ex.render(graph))))
        self.assertEqual([r["id"] for r in rows], ["the-constitution-of-the-united-states", "exec", "sec", "unit"])
        self.assertEqual(rows[1]["cost_amount_usd"], "600.00"); self.assertEqual(rows[1]["treasury_row_name"], "Executive"); self.assertEqual(rows[1]["cost_source_url"], "https://fiscaldata.treasury.gov/x")
        self.assertEqual(rows[1]["verification_url"], "https://www.whitehouse.gov/"); self.assertEqual(rows[1]["verification_date"], "2026-09-13")
        self.assertEqual(rows[2]["cost_amount_usd"], ""); self.assertEqual(rows[2]["pay_field"], "positionSchedulePay"); self.assertEqual(rows[2]["pay_amount_usd"], "253100.00"); self.assertEqual(rows[2]["pay_documents"], "2")
        self.assertEqual(rows[2]["branch"], "exec"); self.assertEqual(rows[2]["depth"], "2"); self.assertEqual(rows[2]["parent_name"], "Executive")
        self.assertEqual(rows[3]["cost_amount_usd"], "10.00"); self.assertEqual(rows[3]["cost_status"], "allocated"); self.assertEqual(rows[3]["omb_outlays_usd"], "-5.00")
        self.assertEqual(rows[3]["treasury_row_name"], "", "an estimate carries no Treasury row")
        self.assertEqual(rows[0]["branch"], "")
        # the gate accepts this file beside this graph and refuses a tampered one
        tmp = PROJECT_ROOT / "tests" / ".tmp"; tmp.mkdir(exist_ok=True)
        (tmp / "graph.json").write_text("{}", encoding="utf-8")
        (tmp / "nodes.csv").write_text(ex.render(graph), encoding="utf-8")
        self.assertEqual(gate.flat_csv_violations(graph, tmp / "graph.json", gate.label), [])
        (tmp / "nodes.csv").write_text(ex.render(graph).replace("600.00", "601.00"), encoding="utf-8")
        self.assertTrue(gate.flat_csv_violations(graph, tmp / "graph.json", gate.label))
        (tmp / "nodes.csv").write_text("\n".join(ex.render(graph).splitlines()[:-1]) + "\n", encoding="utf-8")
        self.assertTrue(gate.flat_csv_violations(graph, tmp / "graph.json", gate.label))


class PublishedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PUBLISHED.is_file() and CSV_PATH.is_file()):
            raise unittest.SkipTest("no published graph with a CSV beside it")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

    def test_the_committed_csv_is_a_fresh_render_and_the_gate_accepts_it(self):
        self.assertEqual(CSV_PATH.read_text(encoding="utf-8"), ex.render(self.graph))
        self.assertEqual(gate.flat_csv_violations(self.graph, PUBLISHED, gate.label), [])

    def test_no_row_publishes_a_zero_and_every_measured_row_names_its_line(self):
        rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
        self.assertFalse(any(r["cost_amount_usd"] == "0.00" for r in rows))
        measured = [r for r in rows if r["cost_status"] == "official"]
        self.assertGreater(len(measured), 100)
        self.assertTrue(all(r["cost_source_url"].startswith("https://fiscaldata.treasury.gov") or r["cost_source_url"].startswith("https://api.fiscaldata") for r in measured))
        priced = [r for r in rows if r["pay_field"]]
        self.assertGreater(len(priced), 1000)
        self.assertTrue(all(r["pay_amount_usd"] or r["pay_minimum_usd"] for r in priced))


class PageTests(unittest.TestCase):
    def test_the_page_names_the_files_it_offers_and_each_exists(self):
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="btn-download"', text)
        self.assertIn('id="download-body"', text)
        paths = re.findall(r'\["\./([^"]+)", "([^"]+)", "', text)
        self.assertGreaterEqual(len(paths), 5)
        names = {name for _, name in paths}
        self.assertIn("nodes.csv", names); self.assertIn("graph.json", names); self.assertIn("source_registry.json", names)
        for rel, _name in paths:
            self.assertTrue((PROJECT_ROOT / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
