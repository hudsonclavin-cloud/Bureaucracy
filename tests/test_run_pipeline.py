from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.run_pipeline import format_pipeline_summary, run_pipeline


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


class RunPipelineTests(unittest.TestCase):
    def test_run_pipeline_writes_graph_candidates_and_stats(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=False,
                stats_output_path=stats_output_path,
                direct_payload_fetchers=[
                    lambda: {
                        "nodes": [
                            {
                                "id": "contractor-acme",
                                "name": "Acme Corp",
                                "type": "Corporation",
                                "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                            }
                        ],
                        "edges": [
                            {
                                "source": "department-of-energy",
                                "target": "contractor-acme",
                                "type": "contracts_with",
                            }
                        ],
                    }
                ],
                discovery_fetchers={
                    "wikidata_records": lambda: [
                        {
                            "label": "Office of Grid Deployment",
                            "parentName": "Department of Energy",
                            "officialWebsite": "https://www.energy.gov/gdo/office-grid-deployment",
                            "wikidataId": "Q999",
                            "description": "Office discovered via Wikidata.",
                            "countryLabel": "United States",
                        }
                    ],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            graph = json.loads(graph_output_path.read_text(encoding="utf-8"))
            candidates = json.loads(candidate_output_path.read_text(encoding="utf-8"))
            saved_stats = json.loads(stats_output_path.read_text(encoding="utf-8"))

            self.assertTrue(graph_output_path.exists())
            self.assertTrue(candidate_output_path.exists())
            self.assertTrue(stats_output_path.exists())
            self.assertGreaterEqual(stats["new_nodes_added"], 1)
            self.assertEqual(saved_stats["nodes_after"], stats["nodes_after"])
            self.assertTrue(any(node["name"] == "Office of Grid Deployment" for node in candidates))
            department = next(child for child in graph["children"] if child["id"] == "department-of-energy")
            self.assertTrue(any(child["id"] == "department-of-energy-office-of-grid-deployment" for child in department["children"]))
            self.assertIn("verification_breakdown", stats)
            self.assertFalse(stats["all_fetch_stages_failed"])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_total_fetch_failure_preserves_outputs_and_reports(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            sentinel = json.dumps({"sentinel": True})
            graph_output_path.write_text(sentinel, encoding="utf-8")
            nodes_output_path.write_text(sentinel, encoding="utf-8")
            edges_output_path.write_text(sentinel, encoding="utf-8")
            candidate_output_path.write_text(sentinel, encoding="utf-8")

            def fail() -> dict:
                raise RuntimeError("network down")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                validity_report_output_path=tmp_path / "node_validity_report.json",
                stats_output_path=stats_output_path,
                direct_payload_fetchers=[fail],
                discovery_fetchers={
                    "wikidata_records": fail,
                    "official_directory_records": fail,
                    "federal_register_records": fail,
                },
            )

            self.assertTrue(stats["all_fetch_stages_failed"])
            self.assertEqual(len(stats["stage_errors"]), 4)
            self.assertEqual(stats["nodes_after"], stats["nodes_before"])
            self.assertEqual(stats["new_nodes_added"], 0)
            # Existing outputs must not be overwritten by a base-graph-only export.
            self.assertEqual(graph_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(nodes_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(edges_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(candidate_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertTrue(stats_output_path.exists())
            # Wrappers (scheduler/nightly_update.run_once) read these nested keys.
            self.assertEqual(stats["build_validation"]["exported_edge_count"], 0)
            self.assertEqual(stats["outputs"]["graph"], str(graph_output_path))
            self.assertEqual(stats["outputs"]["expanded_nodes"], str(nodes_output_path))
            self.assertEqual(stats["outputs"]["expanded_edges"], str(edges_output_path))
            self.assertEqual(stats["outputs"]["candidate_nodes"], str(candidate_output_path))
            summary = format_pipeline_summary(stats)
            self.assertIn("stage_errors", summary)
            self.assertIn("RuntimeError", summary)
            self.assertIn("ALL FETCH STAGES FAILED", summary)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_silent_empty_fetches_preserve_outputs(self) -> None:
        # The real crawlers swallow network errors and return empty results
        # instead of raising, so a total outage arrives here as "no errors,
        # no data". The overwrite guard must fire on that signal too.
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            sentinel = json.dumps({"sentinel": True})
            graph_output_path.write_text(sentinel, encoding="utf-8")
            nodes_output_path.write_text(sentinel, encoding="utf-8")
            edges_output_path.write_text(sentinel, encoding="utf-8")
            candidate_output_path.write_text(sentinel, encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                validity_report_output_path=tmp_path / "node_validity_report.json",
                stats_output_path=stats_output_path,
                direct_payload_fetchers=[lambda: {"nodes": [], "edges": []}],
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            self.assertTrue(stats["all_fetch_stages_failed"])
            self.assertEqual(stats["new_nodes_added"], 0)
            self.assertEqual(graph_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(nodes_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(edges_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertEqual(candidate_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertIn("ALL FETCH STAGES FAILED", format_pipeline_summary(stats))
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_partial_fetch_failure_still_writes_outputs(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            def fail() -> dict:
                raise RuntimeError("network down")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=False,
                stats_output_path=stats_output_path,
                direct_payload_fetchers=[
                    fail,
                    lambda: {
                        "nodes": [
                            {
                                "id": "contractor-acme",
                                "name": "Acme Corp",
                                "type": "Corporation",
                            }
                        ],
                        "edges": [],
                    },
                ],
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            self.assertFalse(stats["all_fetch_stages_failed"])
            self.assertEqual(len(stats["stage_errors"]), 1)
            self.assertIn("RuntimeError", stats["stage_errors"][0])
            self.assertTrue(graph_output_path.exists())
            self.assertIn("stage_errors", format_pipeline_summary(stats))
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


    def test_run_pipeline_export_gate_prunes_nodes_without_cost(self) -> None:
        """With the gate on and no Treasury total, nothing is publishable.

        This is the behaviour that makes the publication guard necessary: a node
        can be fully sourced and proven and still be rejected, because
        CostValidator requires a resolved cost and the cost cascade has nothing
        to allocate from. Pinning it here so the coupling between the Treasury
        fetch and the export gate is a documented contract rather than a
        surprise discovered during a deploy.
        """
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=tmp_path / "candidate_nodes.json",
                graph_output_path=graph_output_path,
                nodes_output_path=tmp_path / "expanded_nodes.json",
                edges_output_path=tmp_path / "expanded_edges.json",
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=True,
                stats_output_path=tmp_path / "pipeline_stats.json",
                direct_payload_fetchers=[
                    lambda: {
                        "nodes": [
                            {
                                "id": "contractor-acme",
                                "name": "Acme Corp",
                                "type": "Corporation",
                                "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                            }
                        ],
                        "edges": [
                            {
                                "source": "department-of-energy",
                                "target": "contractor-acme",
                                "type": "contracts_with",
                            }
                        ],
                        "budgetSummary": {"government_total_outlay_amount": 3102409296183},
                    }
                ],
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            self.assertEqual(stats["new_nodes_added"], 0)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_refuses_to_publish_without_treasury_total(self) -> None:
        """A partial outage must not overwrite a good graph with an empty one."""
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
            sentinel = "PUBLISHED-GRAPH-SENTINEL"
            graph_output_path.write_text(sentinel, encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=tmp_path / "candidate_nodes.json",
                graph_output_path=graph_output_path,
                nodes_output_path=tmp_path / "expanded_nodes.json",
                edges_output_path=tmp_path / "expanded_edges.json",
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=True,
                stats_output_path=tmp_path / "pipeline_stats.json",
                direct_payload_fetchers=[
                    lambda: {
                        "nodes": [
                            {
                                "id": "contractor-acme",
                                "name": "Acme Corp",
                                "type": "Corporation",
                                "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                            }
                        ],
                        "edges": [],
                    }
                ],
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            self.assertEqual(graph_output_path.read_text(encoding="utf-8"), sentinel)
            self.assertTrue(
                any("Treasury budget summary" in error for error in stats["stage_errors"])
            )
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
