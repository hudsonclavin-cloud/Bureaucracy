"""Structural integrity of what the exporter publishes.

Each test here is a way a rerun of the pipeline could quietly damage the
published graph: attributing one entity's evidence to another with the same
name, swapping a node's parent on every run, republishing the whole curated
tree as "expanded" nodes, or leaving a parentId that points at a node the gate
removed.
"""

from __future__ import annotations

import json
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from data_pipeline.discovery.source_discovery import (
    classify_source_url,
    discover_candidates,
    estimate_candidate_confidence,
)
from data_pipeline.exporter.build_graph import build_graph, resolve_root_orphans
from data_pipeline.processors.normalize_nodes import verify_node_sources


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TREASURY = {"government_total_outlay_amount": 1_000_000}


def _workspace(base_graph: dict) -> tuple[Path, dict]:
    tmp_path = TEST_TMP_ROOT / f"integrity-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    base_graph_path = tmp_path / "base.json"
    base_graph_path.write_text(json.dumps(base_graph), encoding="utf-8")
    paths = dict(
        base_graph_path=base_graph_path,
        graph_output_path=tmp_path / "graph.json",
        nodes_output_path=tmp_path / "expanded_nodes.json",
        edges_output_path=tmp_path / "expanded_edges.json",
        validity_report_output_path=tmp_path / "node_validity_report.json",
    )
    return tmp_path, paths


def _ids(node: dict) -> set[str]:
    found = set()
    stack = [node]
    while stack:
        current = stack.pop()
        found.add(current["id"])
        stack.extend(current.get("children", []))
    return found


def _find(node: dict, node_id: str, parent: dict | None = None):
    if node["id"] == node_id:
        return node, parent
    for child in node.get("children", []):
        hit = _find(child, node_id, node)
        if hit:
            return hit
    return None


class RootOrphanTests(unittest.TestCase):
    def test_merging_an_orphan_carries_its_evidence_and_recomputes_counts(self) -> None:
        root = {
            "id": "root",
            "name": "Root",
            "children": [
                {"id": "dept-dhs", "name": "Department of Homeland Security", "type": "Department", "children": []},
                {
                    "id": "us-department-of-homeland-security",
                    "name": "U.S. Department of Homeland Security",
                    "type": "Organization",
                    "sourceUrls": ["https://fiscaldata.treasury.gov/x"],
                    "sourceTypes": ["treasury_outlays"],
                    "rollup_total_amount": 1000,
                    "children": [],
                },
            ],
        }
        result = resolve_root_orphans(root, trusted_node_ids={"dept-dhs"})

        self.assertEqual(result["summary"]["duplicates_removed"], 1)
        self.assertEqual(_ids(root), {"root", "dept-dhs"})
        dhs = root["children"][0]
        self.assertEqual(dhs["sourceUrls"], ["https://fiscaldata.treasury.gov/x"])
        self.assertEqual(dhs["sourceCount"], 1)
        self.assertEqual(dhs["rollup_total_amount"], 1000)

    def test_an_ambiguous_name_is_never_a_merge_target(self) -> None:
        root = {
            "id": "root",
            "name": "Root",
            "children": [
                {
                    "id": "department-a",
                    "name": "Department A",
                    "children": [{"id": "a-cos", "name": "Chief of Staff", "children": []}],
                },
                {
                    "id": "department-b",
                    "name": "Department B",
                    "children": [{"id": "b-cos", "name": "Chief of Staff", "children": []}],
                },
                {
                    "id": "department-b-chief-of-staff",
                    "name": "Chief of Staff",
                    "sourceUrls": ["https://www.b.gov/leadership"],
                    "children": [],
                },
            ],
        }
        trusted = {"department-a", "a-cos", "department-b", "b-cos"}
        result = resolve_root_orphans(root, trusted_node_ids=trusted)

        self.assertEqual(result["summary"]["duplicates_removed"], 0)
        a_cos, _ = _find(root, "a-cos")
        self.assertNotIn("sourceUrls", a_cos)
        orphan, parent = _find(root, "department-b-chief-of-staff")
        self.assertEqual(parent["id"], "department-b")
        self.assertEqual(orphan["parentId"], "department-b")


    def test_two_same_named_crawler_orphans_stay_two_nodes(self) -> None:
        root = {
            "id": "root",
            "name": "Root",
            "children": [
                {"id": "department-a", "name": "Department A", "children": []},
                {"id": "department-b", "name": "Department B", "children": []},
                {"id": "department-a-chief-of-staff", "name": "Chief of Staff", "sourceUrls": ["https://www.a.gov/x"], "children": []},
                {"id": "department-b-chief-of-staff", "name": "Chief of Staff", "sourceUrls": ["https://www.b.gov/x"], "children": []},
            ],
        }
        result = resolve_root_orphans(root, trusted_node_ids={"department-a", "department-b"})
        self.assertEqual(result["summary"]["duplicates_removed"], 0)
        a_cos, a_parent = _find(root, "department-a-chief-of-staff")
        b_cos, b_parent = _find(root, "department-b-chief-of-staff")
        self.assertEqual(a_parent["id"], "department-a")
        self.assertEqual(b_parent["id"], "department-b")
        # Reattached under a parent: no longer a root attachment.
        self.assertNotIn("attachToRoot", a_cos)
        self.assertEqual(a_cos["parentId"], "department-a")


class RerunStabilityTests(unittest.TestCase):
    BASE = {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [
            {"id": "agency-alpha", "name": "Agency Alpha", "type": "Agency", "children": []},
            {"id": "parent-two", "name": "Parent Two", "type": "Agency", "children": []},
        ],
    }

    def test_a_node_keeps_its_parent_and_secondary_edge_across_reruns(self) -> None:
        tmp_path, paths = _workspace(self.BASE)
        try:
            payload = {
                "nodes": [
                    {"id": "office-multi", "name": "Office Multi", "type": "Office", "sourceUrls": ["https://www.alpha.gov/office"]}
                ],
                "edges": [
                    {"source": "office-multi", "target": "agency-alpha", "type": "reports_to"},
                    {"source": "office-multi", "target": "parent-two", "type": "reports_to"},
                ],
                "budgetSummary": dict(TREASURY),
            }
            outcomes = []
            for _ in range(3):
                result = build_graph([json.loads(json.dumps(payload))], enforce_export_gate=False, **paths)
                _, parent = _find(result.graph, "office-multi")
                outcomes.append((parent["id"], sorted((e["source"], e["target"]) for e in result.edges)))
            self.assertEqual(outcomes[0], outcomes[1])
            self.assertEqual(outcomes[1], outcomes[2])
            self.assertEqual(outcomes[0][0], "agency-alpha")
            self.assertEqual(outcomes[0][1], [("office-multi", "parent-two")])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_a_rerun_does_not_republish_the_curated_tree_as_expanded_nodes(self) -> None:
        tmp_path, paths = _workspace(self.BASE)
        try:
            payload = {
                "nodes": [{"id": "office-x", "name": "Office X", "type": "Office", "sourceUrls": ["https://www.alpha.gov/x"], "parentId": "agency-alpha"}],
                "edges": [],
                "budgetSummary": dict(TREASURY),
            }
            build_graph([json.loads(json.dumps(payload))], enforce_export_gate=False, **paths)
            second = build_graph([{"nodes": [], "edges": []}], enforce_export_gate=False, **paths)
            exported_ids = {node["id"] for node in second.nodes}
            self.assertEqual(exported_ids, {"office-x"})
            self.assertEqual(_ids(second.graph), {"root", "agency-alpha", "parent-two", "office-x"})
            self.assertNotIn("relationships", second.nodes[0])
            self.assertNotIn("__budgetSummary", second.nodes[0])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_parent_id_follows_the_tree_after_pruning(self) -> None:
        base = {
            "id": "root",
            "name": "Root",
            "type": "Foundation",
            "children": [{"id": "dept", "name": "Department", "type": "Department", "children": []}],
        }
        tmp_path, paths = _workspace(base)
        try:
            payload = {
                "nodes": [
                    # Proven but uncosted: the gate rejects it.
                    {"id": "crawl-p", "name": "Program Office", "type": "Office", "sourceUrls": ["https://www.dept.gov/p"]},
                    # Carries an official rollup: published, promoted under dept.
                    {
                        "id": "crawl-c",
                        "name": "Cost Center",
                        "type": "Office",
                        "sourceUrls": ["https://fiscaldata.treasury.gov/c"],
                        "sourceTypes": ["treasury_outlays"],
                        "rollup_total_amount": 1000,
                    },
                ],
                "edges": [
                    {"source": "crawl-p", "target": "dept", "type": "reports_to"},
                    {"source": "crawl-c", "target": "crawl-p", "type": "reports_to"},
                ],
                "budgetSummary": dict(TREASURY),
            }
            result = build_graph([payload], enforce_export_gate=True, **paths)
            self.assertNotIn("crawl-p", _ids(result.graph))
            hit = _find(result.graph, "crawl-c")
            self.assertIsNotNone(hit, "the costed node must survive the gate")
            node, parent = hit
            self.assertEqual(parent["id"], "dept")
            self.assertEqual(node.get("parentId"), "dept")
            exported = {n["id"]: n for n in result.nodes}
            self.assertEqual(exported["crawl-c"].get("parentId"), "dept")
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_expanded_nodes_carry_the_curated_name_not_the_payload_copy(self) -> None:
        tmp_path, paths = _workspace(self.BASE)
        try:
            payload = {
                "nodes": [
                    # A crawler copy of a curated node with a mangled name, plus provenance.
                    {"id": "agency-alpha", "name": "AGENCY ALPHA", "type": "Organization", "sourceUrls": ["https://www.alpha.gov/about"]}
                ],
                "edges": [],
                "budgetSummary": dict(TREASURY),
            }
            result = build_graph([payload], enforce_export_gate=False, **paths)
            tree_node, _ = _find(result.graph, "agency-alpha")
            self.assertEqual(tree_node["name"], "Agency Alpha")
            self.assertEqual(tree_node["type"], "Agency")
            exported = {n["id"]: n for n in result.nodes}
            self.assertEqual(exported["agency-alpha"]["name"], "Agency Alpha")
            self.assertEqual(exported["agency-alpha"]["type"], "Agency")
            self.assertEqual(exported["agency-alpha"]["sourceUrls"], ["https://www.alpha.gov/about"])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_a_treasury_line_of_zero_is_not_a_measured_cost(self) -> None:
        tmp_path, paths = _workspace(self.BASE)
        try:
            payload = {
                "nodes": [],
                "edges": [],
                "outlayRows": [
                    {"name": "Agency Alpha", "originalName": "Agency Alpha", "rollup_total_amount": 0, "sourceUrls": ["https://fiscaldata.treasury.gov/x"], "sourceTypes": ["treasury_outlays"]}
                ],
                "budgetSummary": dict(TREASURY),
            }
            result = build_graph([payload], enforce_export_gate=True, **paths)
            alpha, _ = _find(result.graph, "agency-alpha")
            self.assertEqual(alpha["cost_status"], "allocated")
            self.assertGreater(alpha["resolved_total_amount"], 0)
            self.assertEqual(result.validation["treasury_outlay_rows"]["rows"], 0)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_a_node_whose_parent_was_dropped_is_counted(self) -> None:
        tmp_path, paths = _workspace(self.BASE)
        try:
            payload = {
                "nodes": [
                    {"id": "crawl-q", "name": "Unplaceable", "type": "Office"},
                    {"id": "crawl-d", "name": "Dependent", "type": "Office", "parentId": "crawl-q"},
                ],
                "edges": [],
                "budgetSummary": dict(TREASURY),
            }
            result = build_graph([payload], enforce_export_gate=False, **paths)
            self.assertEqual(_ids(result.graph), {"root", "agency-alpha", "parent-two"})
            self.assertEqual(result.validation["root_attached_missing_parent_nodes"], 1)
            self.assertEqual(result.validation["nodes_removed_missing_parent"], 1)
            self.assertEqual(result.validation["pipeline_summary"]["nodes_removed_missing_parent"], 1)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class ProofNeedsEvidenceTests(unittest.TestCase):
    def test_a_type_label_with_no_url_proves_nothing(self) -> None:
        for node in (
            {"sourceTypes": ["official_site"]},
            {"sourceUrls": ["   "], "sourceTypes": ["official_http"]},
            {"sourceTypes": ["wikidata", "federal_register"]},
        ):
            with self.subTest(node=node):
                scored = verify_node_sources(dict(node))
                self.assertFalse(scored["existsProven"])
                self.assertEqual(scored["proofStatus"], "unproven")
                self.assertEqual(scored["proofReason"], "no_evidence_recorded")

    def test_official_site_must_be_backed_by_a_gov_url(self) -> None:
        asserted = verify_node_sources({"sourceUrls": ["https://example.com/page"], "sourceTypes": ["official_site"]})
        self.assertFalse(asserted["existsProven"])
        real = verify_node_sources({"sourceUrls": ["https://www.energy.gov/about"]})
        self.assertTrue(real["existsProven"])
        self.assertEqual(real["proofReason"], "official_source_recorded")


    def test_no_url_means_no_proof_sources_either(self) -> None:
        scored = verify_node_sources({"sourceTypes": ["official_site"]})
        self.assertEqual(scored["proofSourceCount"], 0)
        self.assertEqual(scored["proofReason"], "no_evidence_recorded")

    def test_a_federal_register_notice_is_documentation_not_an_official_site(self) -> None:
        from data_pipeline.processors.normalize_nodes import classify_source_url as classify

        self.assertEqual(classify("https://www.federalregister.gov/documents/2026/x"), "federal_register")
        scored = verify_node_sources({"sourceUrls": ["https://www.federalregister.gov/documents/2026/x"]})
        self.assertNotIn("official_site", scored["sourceTypes"])
        self.assertTrue(scored["existsProven"])
        self.assertEqual(scored["proofReason"], "historical_documentation_recorded")


class DiscoveryScoringTests(unittest.TestCase):
    def test_federal_register_hosts_are_not_official_sites(self) -> None:
        self.assertEqual(classify_source_url("https://www.federalregister.gov/documents/2026/x"), "federal_register")
        self.assertEqual(classify_source_url("https://www.facadatabase.gov/committee/1"), "advisory_directory")
        self.assertEqual(classify_source_url("https://www.energy.gov/about"), "official_site")

    def test_a_single_federal_register_notice_stays_below_the_promotion_gate(self) -> None:
        score = estimate_candidate_confidence("https://www.federalregister.gov/documents/2026/x", "federal_register_listing_scan")
        self.assertLess(score, 0.7)

    def test_template_leadership_is_off_unless_enabled(self) -> None:
        existing = [{"id": "office-x", "name": "Office of Things", "type": "Office"}]
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PIPELINE_ENABLE_TEMPLATE_LEADERSHIP", None)
            quiet = discover_candidates(existing_nodes=existing)
        self.assertFalse(any(str(c.get("sourceUrl", "")).startswith("generated://") for c in quiet))
        with mock.patch.dict(os.environ, {"PIPELINE_ENABLE_TEMPLATE_LEADERSHIP": "1"}):
            loud = discover_candidates(existing_nodes=existing)
        self.assertTrue(any(str(c.get("sourceUrl", "")).startswith("generated://") for c in loud))


if __name__ == "__main__":
    unittest.main()
