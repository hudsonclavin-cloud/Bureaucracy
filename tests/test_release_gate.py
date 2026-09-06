"""The release gate and the offline rebuild have to be tested like any gate.

Commit a2b2207 describes the gate as verified against three corrupted copies;
that verification was done by hand. A gate whose checks can be loosened
without a failing test is one more validator that "ran happily and was wrong".
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
from scripts import regenerate_published_graph
from scripts.validate_published_graph import main as gate_main


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID,
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {
            "id": "legislative-branch",
            "name": "Legislative Branch",
            "type": "Branch",
            "employees": "30,000",
            "children": [{"id": "leg-senate", "name": "United States Senate", "type": "Chamber", "children": []}],
        },
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "employees": "4,000,000", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "employees": "30,000", "children": []},
    ],
}


def _gate(path: Path) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = gate_main(["gate", str(path)])
    return code, out.getvalue()


def _find(node, node_id):
    if node["id"] == node_id:
        return node
    for child in node.get("children", []):
        hit = _find(child, node_id)
        if hit:
            return hit
    return None


class ReleaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"gate-{uuid.uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        base_graph_path = self.tmp_path / "base.json"
        base_graph_path.write_text(json.dumps(BASE), encoding="utf-8")
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base_graph_path,
            graph_output_path=self.tmp_path / "graph.json",
            nodes_output_path=self.tmp_path / "expanded_nodes.json",
            edges_output_path=self.tmp_path / "expanded_edges.json",
            validity_report_output_path=self.tmp_path / "node_validity_report.json",
            reuse_existing_graph_payload=False,
            enforce_export_gate=True,
            # This fixture is a gate test, not a crawl test. With the real
            # evidence file the fixture's own leg-senate picked up the source
            # www.senate.gov earned on 2026-09-06, and "costSourceCount with
            # nothing behind it" stopped being a corruption — the gate was
            # right and the test was stale. What the gate does with real
            # evidence is asserted in tests/test_verification.py.
            evidence_path=None,
        )
        self.graph_path = result.graph_path
        self.graph = json.loads(self.graph_path.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def _write_corrupted(self, mutate) -> Path:
        graph = json.loads(json.dumps(self.graph))
        mutate(graph)
        path = self.tmp_path / f"corrupted-{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return path

    def test_a_clean_graph_passes(self) -> None:
        code, out = _gate(self.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("PASSED", out)

    def test_each_corruption_is_named(self) -> None:
        cases = {
            "estimate wearing the measured badge": (
                lambda g: _find(g, "leg-senate").__setitem__("costVerificationStatus", "verified"),
                "United States Senate",
            ),
            "child costs more than its parent": (
                lambda g: _find(g, "leg-senate").__setitem__("resolved_total_amount", 999_999_999),
                "United States Senate",
            ),
            "attachToRoot together with parentId": (
                lambda g: _find(g, "judicial-branch").update({"attachToRoot": True, "parentId": ROOT_ID}),
                "Judicial Branch",
            ),
            "duplicate id": (
                lambda g: g["children"].append(json.loads(json.dumps(_find(g, "judicial-branch")))),
                "judicial-branch appears 2 times",
            ),
            "zero amount": (
                lambda g: _find(g, "leg-senate").__setitem__("resolved_total_amount", 0),
                "United States Senate",
            ),
            "missing amount without unavailable": (
                lambda g: _find(g, "leg-senate").__setitem__("resolved_total_amount", None),
                "United States Senate",
            ),
            "cost source with no evidence": (
                lambda g: _find(g, "leg-senate").__setitem__("costSourceCount", 1),
                "United States Senate",
            ),
            "wrong root": (lambda g: g.__setitem__("id", "root"), "expected"),
        }
        for name, (mutate, expected_text) in cases.items():
            with self.subTest(case=name):
                code, out = _gate(self._write_corrupted(mutate))
                self.assertEqual(code, 1, f"{name} should fail the gate:\n{out}")
                self.assertIn(expected_text, out)

    def test_missing_file_is_a_distinct_exit_code(self) -> None:
        code, _ = _gate(self.tmp_path / "nope.json")
        self.assertEqual(code, 2)


class OfflineRegenerationTests(unittest.TestCase):
    def test_rebuild_reports_what_it_did_and_gates_the_result(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"regen-{uuid.uuid4().hex}"
        out_dir = tmp_path / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            base_graph_path.write_text(json.dumps(BASE), encoding="utf-8")
            anchor_graph = tmp_path / "anchor.json"
            anchor_graph.write_text(
                json.dumps({"id": ROOT_ID, "name": "x", "__budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30", "label": "FYTD through 2026-06-30"}, "children": []}),
                encoding="utf-8",
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = regenerate_published_graph.main(
                    ["regen", "--anchor", str(anchor_graph), "--base-graph", str(base_graph_path), "--output-dir", str(out_dir)]
                )
            self.assertEqual(code, 0, out.getvalue())
            stats = json.loads((out_dir / "pipeline_stats.json").read_text(encoding="utf-8"))
            self.assertEqual(stats["mode"], "offline_regeneration")
            self.assertFalse(stats["treasury_total_fetched"])
            self.assertEqual(stats["nodes_after"], 5)
            self.assertEqual(stats["build_validation"]["published_node_count"], 5)
            self.assertEqual(stats["build_validation"]["exported_node_count"], 0)  # payload nodes: none
            self.assertEqual(stats["nodes_delta_vs_published"], 5 - 1)
            self.assertTrue(stats["build_validation"]["budget_summary"]["reused_from_previous_build"])
            self.assertNotIn("nodes", stats["build_validation"]["audit_report"])
            self.assertIsNone(stats["outputs"]["candidate_nodes"])
            graph = json.loads((out_dir / "graph.json").read_text(encoding="utf-8"))
            self.assertTrue(graph["__budgetSummary"]["reused_from_previous_build"])
            self.assertEqual(graph["resolved_total_amount"], 1_000_000)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_an_anchor_without_a_usable_total_refuses(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"regen-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            anchor_graph = tmp_path / "anchor.json"
            anchor_graph.write_text(json.dumps({"id": ROOT_ID, "__budgetSummary": {"government_total_outlay_amount": 0}, "children": []}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                regenerate_published_graph.load_anchor(anchor_graph)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
