"""The Treasury row probe is the tool the alias table is edited from.

If it under-reports (a capped sample presented as the whole list) or mislabels
a match, the alias work it drives is done against a false picture.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import apply_treasury_outlay_rows, build_graph_tree
from scripts import probe_treasury_rows


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {
            "id": "executive-branch",
            "name": "Executive Branch",
            "type": "Branch",
            "children": [
                {"id": "exec-dept-doe", "name": "Department of Energy", "type": "Department", "children": []},
                {"id": "twin-a", "name": "Office of Inspector General", "type": "Office", "children": []},
                {"id": "twin-b", "name": "Office of Inspector General", "type": "Office", "children": []},
            ],
        },
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}


def _row(name, amount, level=2):
    return {
        "name": name.split("--", 1)[-1] if name.startswith("Total--") else name,
        "originalName": name,
        "rollup_total_amount": amount,
        "sequence_level": level,
        "budget_source": "Treasury MTS Table 5",
    }


ROWS = [
    _row("Department of Energy", 45_000_000_000),
    _row("Corps of Engineers", 9_000_000_000),
    _row("Office of Inspector General", 800_000_000),
    _row("United States Postal Service", -2_000_000_000),
]


class SampleCapTests(unittest.TestCase):
    def test_the_default_caps_hold_and_the_probe_lifts_them(self) -> None:
        rows = [_row(f"Programme Number {index}", 1_000_000 + index) for index in range(45)]
        root = build_graph_tree(base_graph_path=self._base(), nodes=[], edges=[])
        capped = apply_treasury_outlay_rows(root, rows, root_id=BASE["id"])
        self.assertEqual(capped["rows_unmatched"], 45)
        self.assertEqual(len(capped["unmatched_sample"]), 40)  # committed stats stay small

        root = build_graph_tree(base_graph_path=self._base(), nodes=[], edges=[])
        full = apply_treasury_outlay_rows(root, rows, root_id=BASE["id"], sample_limit=1000)
        self.assertEqual(len(full["unmatched_sample"]), 45)

    def _base(self) -> Path:
        path = TEST_TMP_ROOT / f"probe-{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, True)
        base = path / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        return base


class ProbeOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = TEST_TMP_ROOT / f"probe-{uuid.uuid4().hex}"
        self.path.mkdir(parents=True, exist_ok=True)
        self.base = self.path / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.rows = self.path / "rows.json"
        self.rows.write_text(
            json.dumps({"outlayRows": ROWS, "budgetSummary": {"government_total_outlay_amount": 5e12, "label": "FYTD through 2026-06-30"}}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def _run(self) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            code = probe_treasury_rows.main(
                ["probe", "--rows", str(self.rows), "--base-graph", str(self.base)]
            )
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_every_outcome_is_named_with_its_amount(self) -> None:
        out = self._run()
        self.assertIn("applied 1  unmatched 1  ambiguous 1", out)
        self.assertIn("$45.0B  Department of Energy  ->  exec-dept-doe", out)
        self.assertIn("$9.0B  Corps of Engineers", out)          # no node carries it
        self.assertIn("Office of Inspector General", out)        # two nodes do
        self.assertIn("United States Postal Service", out)       # net receipts
        self.assertIn("negative 1", out)
        self.assertIn("FYTD through 2026-06-30", out)

    def test_it_reads_nothing_from_output(self) -> None:
        """A diagnostic that touched the published files could not be run
        against a live crawl without risking them."""
        before = {p: p.read_bytes() for p in Path("output").glob("*.json")}
        self._run()
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, f"{path} changed")


if __name__ == "__main__":
    unittest.main()


class ReconciliationTests(unittest.TestCase):
    """The report explains the anchor-vs-lines gap in the statement's own
    terms and decides nothing. It must attribute the gap to the right level
    and must not lose the negatives the cascade sets aside."""

    def test_the_gap_is_attributed_to_top_level_lines_the_graph_cannot_place(self) -> None:
        from scripts.probe_treasury_rows import reconcile_rows

        rows = [
            {"originalName": "Total--Department A", "rollup_total_amount": 600.0, "sequence_level": 1, "print_order": 10},
            {"originalName": "Bureau A1", "rollup_total_amount": 700.0, "sequence_level": 2, "print_order": 11},
            {"originalName": "Proprietary Receipts from the Public", "rollup_total_amount": -100.0, "sequence_level": 2, "print_order": 12},
            {"originalName": "Total--Department B", "rollup_total_amount": 400.0, "sequence_level": 1, "print_order": 20},
            {"originalName": "Interest on Treasury Debt Securities (Gross)", "rollup_total_amount": 300.0, "sequence_level": 1, "print_order": 30},
            {"originalName": "Undistributed Offsetting Receipts", "rollup_total_amount": -250.0, "sequence_level": 1, "print_order": 40},
        ]
        report = reconcile_rows(rows, anchor=1050.0)  # 600 + 400 + 300 - 250
        self.assertEqual(report["shallowest_total_level"], 1)
        self.assertEqual(report["top_level_totals"], 2)
        self.assertEqual(report["top_level_totals_sum"], 1000.0)
        self.assertEqual(report["anchor_minus_top_totals"], 50.0)          # = interest 300 + undistributed -250
        self.assertEqual([i["name"] for i in report["top_level_other_positive"]], ["Interest on Treasury Debt Securities (Gross)"])
        self.assertEqual(report["largest_negatives"][0]["name"], "Undistributed Offsetting Receipts")
        self.assertEqual(report["negative_total"], -350.0)
        self.assertEqual(report["by_level"]["2"]["negative"], -100.0)

    def test_the_flag_prints_without_a_network(self) -> None:
        import io
        from contextlib import redirect_stdout
        from scripts import probe_treasury_rows

        tmp = TEST_TMP_ROOT / f"reconcile-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
            rows = tmp / "rows.json"
            rows.write_text(json.dumps({"outlayRows": ROWS + [
                {"name": "Undistributed Offsetting Receipts", "originalName": "Undistributed Offsetting Receipts",
                 "rollup_total_amount": -1_000_000_000, "sequence_level": 1, "budget_source": "Treasury MTS Table 5"}],
                "budgetSummary": {"government_total_outlay_amount": 5e12, "label": "x"}}), encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = probe_treasury_rows.main(["probe", "--rows", str(rows), "--base-graph", str(base), "--reconcile"])
            self.assertEqual(code, 0)
            self.assertIn("reconciliation", out.getvalue())
            self.assertIn("Undistributed Offsetting Receipts", out.getvalue())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
