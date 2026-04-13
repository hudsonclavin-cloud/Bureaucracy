from __future__ import annotations

import json
import os
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.run_pipeline import run_pipeline


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
    def setUp(self) -> None:
        self.previous_http_limit = os.environ.get("PIPELINE_ENRICHMENT_HTTP_LIMIT")
        os.environ["PIPELINE_ENRICHMENT_HTTP_LIMIT"] = "0"

    def tearDown(self) -> None:
        if self.previous_http_limit is None:
            os.environ.pop("PIPELINE_ENRICHMENT_HTTP_LIMIT", None)
        else:
            os.environ["PIPELINE_ENRICHMENT_HTTP_LIMIT"] = self.previous_http_limit

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
            enrichment_stats_output_path = tmp_path / "enrichment_stats.json"
            audit_output_path = tmp_path / "audit_report.json"
            budget_reconciliation_output_path = tmp_path / "budget_vs_actual.json"
            frontier_output_path = tmp_path / "frontier_targets.json"
            state_output_path = tmp_path / "pipeline_state.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                audit_output_path=audit_output_path,
                budget_reconciliation_output_path=budget_reconciliation_output_path,
                frontier_output_path=frontier_output_path,
                state_output_path=state_output_path,
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
            audit_report = json.loads(audit_output_path.read_text(encoding="utf-8"))
            budget_vs_actual = json.loads(budget_reconciliation_output_path.read_text(encoding="utf-8"))
            frontier_targets = json.loads(frontier_output_path.read_text(encoding="utf-8"))
            pipeline_state = json.loads(state_output_path.read_text(encoding="utf-8"))

            self.assertTrue(graph_output_path.exists())
            self.assertTrue(candidate_output_path.exists())
            self.assertTrue(stats_output_path.exists())
            self.assertTrue(enrichment_stats_output_path.exists())
            self.assertTrue(audit_output_path.exists())
            self.assertTrue(budget_reconciliation_output_path.exists())
            self.assertTrue(frontier_output_path.exists())
            self.assertTrue(state_output_path.exists())
            self.assertGreaterEqual(stats["new_nodes_added"], 1)
            self.assertEqual(saved_stats["nodes_after"], stats["nodes_after"])
            self.assertTrue(any(node["name"] == "Office of Grid Deployment" for node in candidates))
            department = next(child for child in graph["children"] if child["id"] == "department-of-energy")
            self.assertTrue(any(child["id"] == "department-of-energy-office-of-grid-deployment" for child in department["children"]))
            self.assertIn("verification_breakdown", stats)
            self.assertIn("cost_verification_breakdown", stats)
            self.assertIn("discovery_sources_used", stats)
            self.assertIn("wikidata_records", stats["discovery_sources_used"])
            self.assertIn("direct_payload_counts", stats)
            self.assertIn("audit_report", stats)
            self.assertIn("budget_vs_actual", stats)
            self.assertEqual(audit_report["summary"]["total_nodes"], stats["audit_report"]["total_nodes_checked"])
            self.assertEqual(budget_vs_actual["summary"]["rows_emitted"], stats["budget_vs_actual"]["rows_emitted"])
            self.assertIn("frontier_targets_written", stats)
            self.assertGreaterEqual(stats["frontier_targets_written"], 1)
            self.assertTrue(any(item["agencyName"] == "Department of Energy" for item in frontier_targets))
            self.assertIn("runCount", pipeline_state)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_keeps_previous_expanded_nodes_across_runs(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-cumulative-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            enrichment_stats_output_path = tmp_path / "enrichment_stats.json"
            audit_output_path = tmp_path / "audit_report.json"
            budget_reconciliation_output_path = tmp_path / "budget_vs_actual.json"
            frontier_output_path = tmp_path / "frontier_targets.json"
            state_output_path = tmp_path / "pipeline_state.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                audit_output_path=audit_output_path,
                budget_reconciliation_output_path=budget_reconciliation_output_path,
                frontier_output_path=frontier_output_path,
                state_output_path=state_output_path,
                direct_payload_fetchers=[],
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

            run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                audit_output_path=audit_output_path,
                budget_reconciliation_output_path=budget_reconciliation_output_path,
                frontier_output_path=frontier_output_path,
                state_output_path=state_output_path,
                direct_payload_fetchers=[],
                reuse_existing_graph_payload=True,
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            graph = json.loads(graph_output_path.read_text(encoding="utf-8"))
            department = next(child for child in graph["children"] if child["id"] == "department-of-energy")
            self.assertTrue(any(child["id"] == "department-of-energy-office-of-grid-deployment" for child in department["children"]))
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_run_pipeline_skips_live_publish_when_blocking_stage_errors_occur(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-publish-skip-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            enrichment_stats_output_path = tmp_path / "enrichment_stats.json"
            audit_output_path = tmp_path / "audit_report.json"
            budget_reconciliation_output_path = tmp_path / "budget_vs_actual.json"
            frontier_output_path = tmp_path / "frontier_targets.json"
            state_output_path = tmp_path / "pipeline_state.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                audit_output_path=audit_output_path,
                budget_reconciliation_output_path=budget_reconciliation_output_path,
                frontier_output_path=frontier_output_path,
                state_output_path=state_output_path,
                direct_payload_fetchers=[],
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

            graph_before = json.loads(graph_output_path.read_text(encoding="utf-8"))
            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                audit_output_path=audit_output_path,
                budget_reconciliation_output_path=budget_reconciliation_output_path,
                frontier_output_path=frontier_output_path,
                state_output_path=state_output_path,
                direct_payload_fetchers=[],
                discovery_fetchers={
                    "wikidata_records": lambda: (_ for _ in ()).throw(TimeoutError("wikidata timed out")),
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            graph_after = json.loads(graph_output_path.read_text(encoding="utf-8"))
            audit_report = json.loads(audit_output_path.read_text(encoding="utf-8"))
            budget_vs_actual = json.loads(budget_reconciliation_output_path.read_text(encoding="utf-8"))
            self.assertEqual(graph_before, graph_after)
            self.assertTrue(stats["publish_skipped"])
            self.assertIn("wikidata_records", "".join(stats["blocking_stage_errors"]))
            self.assertTrue(audit_report["summary"]["publish_skipped"])
            self.assertTrue(budget_vs_actual["summary"]["publish_skipped"])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
