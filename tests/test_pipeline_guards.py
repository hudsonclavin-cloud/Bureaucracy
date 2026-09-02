"""Publication guard and reporting contracts of run_pipeline and the scheduler.

Each of these is a way a bad run could have looked like a good one: an anchor
that parses to zero, a Treasury failure buried under an anonymous stage name,
a refusal reported as success by the documented entry point, or a stats file
too large to commit describing a graph that no longer exists.
"""

from __future__ import annotations

import json
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from data_pipeline.run_pipeline import getenv_float, run_pipeline, usable_budget_total
from data_pipeline.scheduler import nightly_update


BASE_GRAPH = {
    "id": "root",
    "name": "Root",
    "type": "Foundation",
    "color": "#c8a84a",
    "children": [
        {
            "id": "department-of-energy",
            "name": "Department of Energy",
            "type": "Department",
            "children": [],
        }
    ],
}
TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
SENTINEL = "PUBLISHED-GRAPH-SENTINEL"
NO_DISCOVERY = {
    "wikidata_records": lambda: [],
    "official_directory_records": lambda: [],
    "federal_register_records": lambda: [],
}


def _acme_payload(**extra):
    return {
        "nodes": [
            {
                "id": "contractor-acme",
                "name": "Acme Corp",
                "type": "Corporation",
                "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
            }
        ],
        "edges": [],
        **extra,
    }


class _Workspace:
    def __init__(self) -> None:
        self.path = TEST_TMP_ROOT / f"guards-{uuid.uuid4().hex}"
        self.path.mkdir(parents=True, exist_ok=True)
        self.base_graph_path = self.path / "base.json"
        self.base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
        self.graph_output_path = self.path / "graph.json"
        self.graph_output_path.write_text(SENTINEL, encoding="utf-8")

    def run(self, fetchers, *, enforce_export_gate=True):
        return run_pipeline(
            base_graph_path=self.base_graph_path,
            candidate_output_path=self.path / "candidate_nodes.json",
            graph_output_path=self.graph_output_path,
            nodes_output_path=self.path / "expanded_nodes.json",
            edges_output_path=self.path / "expanded_edges.json",
            validity_report_output_path=self.path / "node_validity_report.json",
            enforce_export_gate=enforce_export_gate,
            stats_output_path=self.path / "pipeline_stats.json",
            direct_payload_fetchers=fetchers,
            discovery_fetchers=NO_DISCOVERY,
        )

    def graph_untouched(self) -> bool:
        return self.graph_output_path.read_text(encoding="utf-8") == SENTINEL

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class AnchorGuardTests(unittest.TestCase):
    def test_usable_budget_total_rejects_unusable_anchors(self) -> None:
        self.assertEqual(usable_budget_total({"budgetSummary": {"government_total_outlay_amount": 42}}), 42.0)
        for bad in (0, -5, "not a number", "nan", None, float("inf")):
            with self.subTest(value=bad):
                self.assertIsNone(usable_budget_total({"budgetSummary": {"government_total_outlay_amount": bad}}))
        self.assertIsNone(usable_budget_total({"nodes": []}))
        self.assertIsNone(usable_budget_total(None))

    def test_zero_negative_or_unreadable_total_blocks_publication(self) -> None:
        for bad in (0, -5, "not a number", "nan"):
            with self.subTest(value=bad):
                ws = _Workspace()
                try:
                    stats = ws.run([("treasury_outlays", lambda bad=bad: _acme_payload(budgetSummary={"government_total_outlay_amount": bad}))])
                    self.assertTrue(stats["publication_blocked"])
                    self.assertFalse(stats["treasury_total_fetched"])
                    self.assertTrue(ws.graph_untouched())
                    self.assertTrue(any("Treasury budget summary" in error for error in stats["stage_errors"]))
                finally:
                    ws.cleanup()

    def test_a_fresh_treasury_total_alone_is_a_successful_run(self) -> None:
        """The crawl currently contributes no published nodes, so the anchor is
        the only thing a nightly run can refresh. It must not be reported as
        'all stages failed'."""
        ws = _Workspace()
        try:
            stats = ws.run(
                [
                    ("treasury_outlays", lambda: {"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 3102409296183}}),
                    ("usaspending", lambda: {"nodes": [], "edges": []}),
                ]
            )
            self.assertFalse(stats["all_fetch_stages_failed"])
            self.assertFalse(stats["publication_blocked"])
            self.assertTrue(stats["treasury_total_fetched"])
            self.assertFalse(ws.graph_untouched())
            graph = json.loads(ws.graph_output_path.read_text(encoding="utf-8"))
            self.assertEqual(graph["resolved_total_amount"], 3102409296183)
            self.assertEqual(stats["stage_results"]["treasury_outlays"], "data")
            self.assertEqual(stats["stage_results"]["usaspending"], "empty")
        finally:
            ws.cleanup()


class StageReportingTests(unittest.TestCase):
    def test_a_failed_stage_is_named_in_stage_errors(self) -> None:
        def boom():
            raise RuntimeError("FiscalData 503")

        ws = _Workspace()
        try:
            stats = ws.run(
                [
                    ("treasury_outlays", boom),
                    ("usaspending", lambda: _acme_payload()),
                ]
            )
            self.assertTrue(any(error.startswith("treasury_outlays: RuntimeError") for error in stats["stage_errors"]))
            self.assertEqual(stats["stage_results"]["treasury_outlays"], "error")
            self.assertTrue(stats["publication_blocked"])
        finally:
            ws.cleanup()

    def test_bare_callables_are_still_accepted_and_named(self) -> None:
        ws = _Workspace()
        try:
            stats = ws.run(
                [lambda: _acme_payload(budgetSummary={"government_total_outlay_amount": 100})],
                enforce_export_gate=False,
            )
            self.assertIn("direct_payload_1", stats["stage_results"])
            self.assertFalse(stats["publication_blocked"])
        finally:
            ws.cleanup()

    def test_stats_file_carries_the_audit_summary_only(self) -> None:
        ws = _Workspace()
        try:
            stats = ws.run([("treasury_outlays", lambda: _acme_payload(budgetSummary={"government_total_outlay_amount": 100}))])
            written = json.loads((ws.path / "pipeline_stats.json").read_text(encoding="utf-8"))
            audit = written["build_validation"]["audit_report"]
            self.assertEqual(set(audit), {"summary"})
            self.assertEqual(set(stats["build_validation"]["audit_report"]), {"summary"})
            # The per-node detail still exists, in its own file.
            full = json.loads(Path(stats["outputs"]["audit_report"]).read_text(encoding="utf-8"))
            self.assertIn("summary", full)
            self.assertIn("nodes_delta", written)
        finally:
            ws.cleanup()

    def test_malformed_promotion_threshold_falls_back_instead_of_crashing(self) -> None:
        self.assertEqual(getenv_float("PIPELINE_PROMOTION_THRESHOLD_TEST_ABSENT", 0.7), 0.7)
        with mock.patch.dict(os.environ, {"PIPELINE_PROMOTION_THRESHOLD": "abc"}):
            self.assertEqual(getenv_float("PIPELINE_PROMOTION_THRESHOLD", 0.7), 0.7)
            ws = _Workspace()
            try:
                stats = ws.run([("treasury_outlays", lambda: _acme_payload(budgetSummary={"government_total_outlay_amount": 100}))])
                self.assertFalse(stats["publication_blocked"])
            finally:
                ws.cleanup()

    def test_review_queue_is_not_written_when_the_build_raises(self) -> None:
        ws = _Workspace()
        candidate_path = ws.path / "candidate_nodes.json"
        candidate_path.write_text(SENTINEL, encoding="utf-8")
        try:
            with mock.patch("data_pipeline.run_pipeline.build_graph", side_effect=RuntimeError("disk full")):
                with self.assertRaises(RuntimeError):
                    ws.run([("treasury_outlays", lambda: _acme_payload(budgetSummary={"government_total_outlay_amount": 100}))])
            self.assertEqual(candidate_path.read_text(encoding="utf-8"), SENTINEL)
            self.assertTrue(ws.graph_untouched())
            written = json.loads((ws.path / "pipeline_stats.json").read_text(encoding="utf-8"))
            self.assertTrue(written["publication_blocked"])
            self.assertTrue(any(error.startswith("build_graph: RuntimeError") for error in written["stage_errors"]))
        finally:
            ws.cleanup()


class SchedulerTests(unittest.TestCase):
    def _blocked_result(self):
        return {
            "nodes_after": 5170,
            "build_validation": {"exported_edge_count": 0},
            "outputs": {"expanded_nodes": "n", "expanded_edges": "e", "graph": "g", "candidate_nodes": "c"},
            "publication_blocked": True,
            "all_fetch_stages_failed": False,
            "stage_errors": ["treasury_outlays: RuntimeError: down"],
        }

    def test_run_once_surfaces_a_refusal_to_publish(self) -> None:
        with mock.patch.object(nightly_update, "run_pipeline", return_value=self._blocked_result()):
            outcome = nightly_update.run_once()
        self.assertTrue(outcome["publication_blocked"])
        self.assertEqual(outcome["stage_errors"], ["treasury_outlays: RuntimeError: down"])
        self.assertFalse(nightly_update.run_succeeded(outcome))

    def test_run_once_entry_point_exits_nonzero_on_refusal(self) -> None:
        from data_pipeline import run_once as entry_point

        with mock.patch.object(nightly_update, "run_pipeline", return_value=self._blocked_result()):
            self.assertEqual(entry_point.main(), 1)
        ok = dict(self._blocked_result(), publication_blocked=False, stage_errors=[])
        with mock.patch.object(nightly_update, "run_pipeline", return_value=ok):
            self.assertEqual(entry_point.main(), 0)


if __name__ == "__main__":
    unittest.main()
