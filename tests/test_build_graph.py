from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    build_graph,
    canonical_name_key,
    index_tree,
    safe_attach_child,
)


BASE_GRAPH = {
    "id": "root",
    "name": "Root",
    "type": "Foundation",
    "color": "#c8a84a",
    "children": [
        {
            "id": "agency-alpha",
            "name": "Agency Alpha",
            "type": "Agency",
            "color": "#4a8ac8",
            "children": [],
        }
    ],
}

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def build_graph_with_paths(payloads: list[dict[str, object]]) -> object:
    tmp_path = TEST_TMP_ROOT / f"build-graph-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        base_path = tmp_path / "base.json"
        graph_path = tmp_path / "graph.json"
        nodes_path = tmp_path / "nodes.json"
        edges_path = tmp_path / "edges.json"
        validity_report_path = tmp_path / "node_validity_report.json"
        base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
        return build_graph(
            payloads,
            base_graph_path=base_path,
            graph_output_path=graph_path,
            nodes_output_path=nodes_path,
            edges_output_path=edges_path,
            validity_report_output_path=validity_report_path,
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


class BuildGraphTests(unittest.TestCase):
    def find_graph_node(self, root: dict[str, object], node_id: str) -> dict[str, object]:
        stack = [root]
        while stack:
            current = stack.pop()
            if current.get("id") == node_id:
                return current
            stack.extend(reversed(current.get("children", [])))
        raise KeyError(node_id)

    def test_build_graph_attaches_related_orphans_and_drops_unrelated_orphans(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "contractor-acme",
                        "name": "Acme",
                        "type": "Corporation",
                        "rollup_total_amount": 40.0,
                        "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                        "sourceTypes": ["usaspending_direct"],
                    },
                    {"id": "floating-node", "name": "Floating", "type": "Corporation"},
                ],
                "edges": [
                    {"source": "agency-alpha", "target": "contractor-acme", "type": "contracts_with"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 40.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        exported_ids = {node["id"] for node in result.nodes}
        self.assertIn("contractor-acme", exported_ids)
        self.assertNotIn("floating-node", exported_ids)

        contractor = next(node for node in result.nodes if node["id"] == "contractor-acme")
        self.assertTrue(contractor["attachToRoot"])
        self.assertEqual(result.validation["attached_to_root"], 1)
        self.assertEqual(result.validation["nodes_removed_missing_parent"], 0)
        self.assertEqual(result.validation["root_attached_missing_parent_nodes"], 1)
        self.assertEqual(result.validation["nodes_reattached_to_root"], 1)

    def test_build_graph_keeps_hierarchical_parent_references(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "office-beta",
                        "name": "Office Beta",
                        "type": "Office",
                        "rollup_total_amount": 50.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                ],
                "edges": [
                    {"source": "office-beta", "target": "agency-alpha", "type": "reports_to"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 50.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-beta")
        self.assertEqual(office["parentId"], "agency-alpha")
        self.assertNotIn("attachToRoot", office)
        self.assertEqual(result.edges, [])

    def test_build_graph_keeps_explicit_root_attachments_without_edges(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "special-advisor",
                        "name": "Special Advisor",
                        "type": "Position",
                        "attachToRoot": True,
                        "rollup_total_amount": 60.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                ],
                "edges": [],
                "budgetSummary": {
                    "government_total_outlay_amount": 60.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        advisor = next(node for node in result.nodes if node["id"] == "special-advisor")
        self.assertTrue(advisor["attachToRoot"])
        self.assertEqual(advisor["parentId"], "root")
        self.assertEqual(result.validation["attached_to_root"], 1)
        self.assertEqual(result.validation["nodes_removed_structural_errors"], 0)

    def test_build_graph_drops_edges_with_unknown_endpoints(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "contractor-acme",
                        "name": "Acme",
                        "type": "Corporation",
                        "rollup_total_amount": 25.0,
                        "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                        "sourceTypes": ["usaspending_direct"],
                    },
                ],
                "edges": [
                    {"source": "agency-alpha", "target": "contractor-acme", "type": "contracts_with"},
                    {"source": "missing-source", "target": "contractor-acme", "type": "contracts_with"},
                    {"source": "agency-alpha", "target": "missing-target", "type": "contracts_with"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 25.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(len(result.edges), 1)
        self.assertEqual(result.validation["dropped_edges_missing_source"], 1)
        self.assertEqual(result.validation["dropped_edges_missing_target"], 1)

    def test_build_graph_exports_verification_metadata(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "office-gamma",
                        "name": "Office Gamma",
                        "type": "Office",
                        "rollup_total_amount": 75.0,
                        "sourceUrls": [
                            "https://www.energy.gov/ne/office-gamma",
                            "https://www.wikidata.org/wiki/Q456",
                        ],
                    },
                ],
                "edges": [
                    {"source": "office-gamma", "target": "agency-alpha", "type": "reports_to"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 75.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-gamma")
        self.assertEqual(office["verificationStatus"], "verified")
        self.assertEqual(office["sourceCount"], 2)
        self.assertGreater(office["confidenceScore"], 0.8)
        self.assertIn("verification_status_counts", result.validation)
        self.assertIn("verified_node_count", result.validation)
        self.assertIn("export_verification_status_counts", result.validation)
        self.assertIn("graph_summary", result.validation)
        self.assertIn("pipeline_summary", result.validation)
        self.assertEqual(result.validation["pipeline_summary"]["final_node_count"], len(result.nodes))
        self.assertIn("relationships", result.graph)

    def test_build_graph_drops_placeholder_generated_nodes(self) -> None:
        payloads = [
            {
                "nodes": [
                    {},
                ],
                "edges": [],
            }
        ]

        result = build_graph_with_paths(payloads)

        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("unnamed-node", exported_ids)
        self.assertEqual(result.validation["nodes_removed_structural_errors"], 1)
        self.assertEqual(result.validation["dropped_placeholder_nodes"], 1)

    def test_build_graph_keeps_trusted_base_nodes_without_sources(self) -> None:
        result = build_graph_with_paths(payloads=[])

        agency = self.find_graph_node(result.graph, "agency-alpha")
        self.assertEqual(agency["proofStatus"], "baseline")
        self.assertEqual(agency["proofReason"], "trusted_base_graph")
        self.assertFalse(agency["existsProven"])
        self.assertIn("baseline", result.validation["proof_status_counts"])

    def test_build_graph_culls_unproven_overlay_org_nodes(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "agency-beta", "name": "Agency Beta", "type": "Agency"},
                ],
                "edges": [
                    {"source": "agency-beta", "target": "agency-alpha", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("agency-beta", exported_ids)
        with self.assertRaises(KeyError):
            self.find_graph_node(result.graph, "agency-beta")
        self.assertEqual(result.validation["proof_status_counts_before_cull"]["unproven"], 1)

    def test_build_graph_keeps_proven_nodes_with_real_costs_and_drops_unverified_child_costs(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "agency-beta",
                        "name": "Agency Beta",
                        "type": "Agency",
                        "official_website": "https://www.energy.gov/agency-beta",
                        "rollup_total_amount": 100.0,
                    },
                    {
                        "id": "agency-beta-office-chief-of-staff",
                        "name": "Chief of Staff",
                        "type": "Position",
                    },
                ],
                "edges": [
                    {"source": "agency-beta", "target": "agency-alpha", "type": "reports_to"},
                    {"source": "agency-beta-office-chief-of-staff", "target": "agency-beta", "type": "reports_to"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        agency = next(node for node in result.nodes if node["id"] == "agency-beta")
        self.assertEqual(agency["proofStatus"], "proven")
        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("agency-beta-office-chief-of-staff", exported_ids)
        self.assertGreaterEqual(result.validation["cost_validation_rejected_nodes"], 1)

    def test_build_graph_preserves_budget_summary_metadata(self) -> None:
        payloads = [
            {
                "nodes": [],
                "edges": [],
                "budgetSummary": {
                    "government_total_outlay_amount": 3102409296183.04,
                    "label": "FYTD net outlays through 2026-02-28",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertIn("__budgetSummary", result.graph)
        self.assertEqual(result.graph["__budgetSummary"]["government_total_outlay_amount"], 3102409296183.04)
        self.assertIn("budget_summary", result.validation)
        self.assertEqual(result.validation["budget_summary"]["record_date"], "2026-02-28")

    def test_canonical_name_key_matches_official_name_variants(self) -> None:
        self.assertEqual(
            canonical_name_key("U.S. Fish & Wildlife Service (FWS)"),
            canonical_name_key("United States Fish and Wildlife Service"),
        )
        self.assertEqual(
            canonical_name_key("Department of Health & Human Services (HHS)"),
            canonical_name_key("The United States Department of Health and Human Services"),
        )
        self.assertNotEqual(
            canonical_name_key("Department of Energy"),
            canonical_name_key("Department of Education"),
        )

    def test_build_graph_merges_duplicate_root_orphans_into_canonical_nodes(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "agency-alpha-duplicate-record",
                        "name": "Agency Alpha (AA)",
                        "type": "Agency",
                        "attachToRoot": True,
                        "rollup_total_amount": 30.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                    {
                        "id": "agency-alpha-office-of-testing",
                        "name": "Office of Testing",
                        "type": "Office",
                        "attachToRoot": True,
                        "rollup_total_amount": 70.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                ],
                "edges": [],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("agency-alpha-duplicate-record", exported_ids)
        root_child_ids = {child["id"] for child in result.graph["children"]}
        self.assertEqual(root_child_ids, {"agency-alpha"})

        agency = self.find_graph_node(result.graph, "agency-alpha")
        self.assertIn(
            "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government",
            agency.get("sourceUrls", []),
        )
        office = self.find_graph_node(result.graph, "agency-alpha-office-of-testing")
        self.assertEqual(office["parentId"], "agency-alpha")
        self.assertIn(office["id"], {child["id"] for child in agency["children"]})

        resolution = result.validation["root_orphan_resolution"]
        self.assertEqual(resolution["duplicates_removed"], 1)
        self.assertEqual(resolution["orphans_reattached"], 1)

    def test_build_graph_drops_duplicate_rollup_on_same_named_child(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "agency-alpha-agency-alpha",
                        "name": "Agency Alpha (AA)",
                        "type": "Position",
                        "rollup_total_amount": 40.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                    {
                        "id": "office-beta",
                        "name": "Office Beta",
                        "type": "Office",
                        "attachToRoot": True,
                        "rollup_total_amount": 60.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                ],
                "edges": [
                    {"source": "agency-alpha-agency-alpha", "target": "agency-alpha", "type": "reports_to"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]
        # Give the parent the same rollup the child duplicates.
        payloads[0]["nodes"].insert(
            0,
            {
                "id": "agency-alpha",
                "name": "Agency Alpha",
                "type": "Agency",
                "rollup_total_amount": 40.0,
                "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                "sourceTypes": ["treasury_outlays"],
            },
        )

        result = build_graph_with_paths(payloads)

        self.assertEqual(result.validation["duplicate_child_rollups_dropped"], 1)
        agency = self.find_graph_node(result.graph, "agency-alpha")
        office = self.find_graph_node(result.graph, "office-beta")
        # Without the duplicate, official rollups (40 + 60) fit the total of 100
        # exactly, so nothing is rescaled.
        self.assertEqual(agency["cost_status"], "official")
        self.assertEqual(agency["resolved_total_amount"], 40.0)
        self.assertEqual(office["cost_status"], "official")
        self.assertEqual(office["resolved_total_amount"], 60.0)
        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("agency-alpha-agency-alpha", exported_ids)

    def test_safe_attach_child_refuses_second_parent(self) -> None:
        root = {
            "id": "root",
            "children": [
                {"id": "a", "children": [{"id": "c", "children": []}]},
                {"id": "b", "children": []},
            ],
        }
        node_map, parent_map = index_tree(root)

        self.assertFalse(safe_attach_child(node_map["b"], node_map["c"], parent_map=parent_map))
        self.assertEqual(node_map["b"]["children"], [])
        self.assertEqual(parent_map["c"], "a")

    def test_build_graph_is_idempotent_over_its_own_output(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"build-graph-idem-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_path = tmp_path / "base.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
            payloads = [
                {
                    "nodes": [
                        {
                            "id": "office-beta",
                            "name": "Office Beta",
                            "type": "Office",
                            "rollup_total_amount": 100.0,
                            "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                            "sourceTypes": ["treasury_outlays"],
                        }
                    ],
                    "edges": [
                        {"source": "office-beta", "target": "agency-alpha", "type": "reports_to"},
                    ],
                    "budgetSummary": {
                        "government_total_outlay_amount": 100.0,
                        "label": "Test total",
                        "record_date": "2026-02-28",
                        "fiscal_year": "2026",
                    },
                }
            ]

            def run(build_index: int, build_payloads, reuse_from: Path | None):
                return build_graph(
                    build_payloads,
                    base_graph_path=base_path,
                    graph_output_path=tmp_path / f"graph{build_index}.json",
                    nodes_output_path=tmp_path / f"nodes{build_index}.json",
                    edges_output_path=tmp_path / f"edges{build_index}.json",
                    validity_report_output_path=tmp_path / f"validity{build_index}.json",
                    reuse_existing_graph_payload=reuse_from is not None,
                    existing_graph_payload_path=reuse_from,
                )

            first = run(1, payloads, None)
            second = run(2, [], tmp_path / "graph1.json")

            def visits(node):
                return 1 + sum(visits(child) for child in node.get("children", []) if isinstance(child, dict))

            def ids(node, acc):
                acc.add(node["id"])
                for child in node.get("children", []):
                    if isinstance(child, dict):
                        ids(child, acc)
                return acc

            for result in (first, second):
                self.assertEqual(visits(result.graph), len(ids(result.graph, set())), "node attached twice in tree")
            self.assertEqual(ids(first.graph, set()), ids(second.graph, set()))
            office_first = self.find_graph_node(first.graph, "office-beta")
            office_second = self.find_graph_node(second.graph, "office-beta")
            self.assertEqual(office_first["resolved_total_amount"], office_second["resolved_total_amount"])
            self.assertEqual(office_first["cost_status"], office_second["cost_status"])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_build_graph_writes_minimal_viewer_graph(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"build-graph-min-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_path = tmp_path / "base.json"
            graph_path = tmp_path / "graph.json"
            min_graph_path = tmp_path / "graph.min.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            validity_report_path = tmp_path / "node_validity_report.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                [
                    {
                        "nodes": [
                            {
                                "id": "office-beta",
                                "name": "Office Beta",
                                "type": "Office",
                                "rollup_total_amount": 100.0,
                                "sourceUrls": [
                                    "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"
                                ],
                                "sourceTypes": ["treasury_outlays"],
                            }
                        ],
                        "edges": [
                            {"source": "office-beta", "target": "agency-alpha", "type": "reports_to"},
                        ],
                        "budgetSummary": {
                            "government_total_outlay_amount": 100.0,
                            "label": "Test total",
                            "record_date": "2026-02-28",
                            "fiscal_year": "2026",
                        },
                    }
                ],
                base_graph_path=base_path,
                graph_output_path=graph_path,
                min_graph_output_path=min_graph_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
                validity_report_output_path=validity_report_path,
            )

            self.assertEqual(result.min_graph_path, min_graph_path)
            self.assertTrue(min_graph_path.exists())
            min_graph = json.loads(min_graph_path.read_text(encoding="utf-8"))
            self.assertEqual(min_graph["id"], "root")
            self.assertEqual(min_graph["name"], "Root")
            self.assertIn("children", min_graph)
            self.assertNotIn("relationships", min_graph)
            self.assertEqual(set(min_graph.keys()), {"id", "name", "type", "color", "children", "resolved_total_amount"})
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_build_graph_assigns_resolved_costs_to_each_node(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-beta", "name": "Office Beta", "type": "Office"},
                ],
                "edges": [
                    {"source": "office-beta", "target": "agency-alpha", "type": "reports_to"},
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        root = result.graph
        agency = self.find_graph_node(root, "agency-alpha")

        self.assertEqual(root["resolved_total_amount"], 100.0)
        self.assertEqual(agency["resolved_total_amount"], 100.0)
        self.assertEqual(root["costVerificationStatus"], "verified")
        self.assertEqual(agency["costVerificationStatus"], "unverified")
        self.assertEqual(result.validation["resolved_cost_node_count"], 2)
        self.assertEqual(result.validation["unresolved_cost_node_count"], 0)
        self.assertIn("cost_status_counts", result.validation)
        self.assertIn("cost_verification_status_counts", result.validation)
        self.assertEqual(result.validation["verified_cost_node_count"], 1)
        exported_ids = {node["id"] for node in result.nodes}
        self.assertNotIn("office-beta", exported_ids)
        self.assertGreaterEqual(result.validation["cost_validation_rejected_nodes"], 1)

    def test_build_graph_scales_conflicting_official_rollups(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "special-advisor",
                        "name": "Special Advisor",
                        "type": "Position",
                        "attachToRoot": True,
                        "rollup_total_amount": 60.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                    {
                        "id": "agency-alpha",
                        "name": "Agency Alpha",
                        "type": "Agency",
                        "rollup_total_amount": 80.0,
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["treasury_outlays"],
                    },
                ],
                "edges": [],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        agency = self.find_graph_node(result.graph, "agency-alpha")
        advisor = self.find_graph_node(result.graph, "special-advisor")
        combined = round(float(agency["resolved_total_amount"]) + float(advisor["resolved_total_amount"]), 2)

        self.assertEqual(combined, 100.0)
        self.assertEqual(agency["cost_status"], "scaled_official")
        self.assertEqual(advisor["cost_status"], "scaled_official")
        self.assertEqual(agency["costVerificationStatus"], "partial")
        self.assertEqual(advisor["costVerificationStatus"], "partial")
        self.assertGreater(result.validation["estimated_cost_node_count"], 0)
        self.assertGreater(result.validation["partial_cost_node_count"], 0)

    def test_build_graph_marks_matched_official_rollups_as_cost_verified(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "agency-alpha",
                        "name": "Agency Alpha",
                        "type": "Agency",
                        "rollup_total_amount": 100.0,
                    },
                ],
                "edges": [],
                "budgetSummary": {
                    "government_total_outlay_amount": 100.0,
                    "label": "Test total",
                    "record_date": "2026-02-28",
                    "fiscal_year": "2026",
                },
            }
        ]

        result = build_graph_with_paths(payloads)

        agency = self.find_graph_node(result.graph, "agency-alpha")
        self.assertEqual(agency["cost_status"], "official")
        self.assertEqual(agency["costVerificationStatus"], "verified")
        self.assertGreaterEqual(agency["costConfidenceScore"], 0.95)


if __name__ == "__main__":
    unittest.main()
