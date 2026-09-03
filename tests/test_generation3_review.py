"""Behaviours pinned after the review of the generation-2 changes.

Each one is a way the previous fixes could still publish something wrong:
a department line rescaled to fit an unlined grouping's guess, a negative
Treasury line anchored as a cost, a crawler twin making a curated node's
line ambiguous, a promoted-then-pruned candidate vanishing from the review
queue, a stale line leaving its period behind, a unit name truncated at its
own "for".
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.crawler import federal_register
from data_pipeline.discovery.source_discovery import pending_review_queue
from data_pipeline.exporter.build_graph import build_graph, resolve_root_orphans
from data_pipeline.run_pipeline import run_pipeline
from scripts.repair_review_queue import has_us_federal_evidence, is_foreign, repair


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
DATASET_URL = "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"


def _line(name, amount, **extra):
    return {
        "name": name,
        "originalName": name,
        "rollup_total_amount": amount,
        "amount_kind": "fytd_net_outlays",
        "budget_as_of": "2026-06-30",
        "budget_source": "Treasury MTS Table 5",
        "sourceUrls": [DATASET_URL],
        "sourceTypes": ["treasury_outlays"],
        **extra,
    }


def _workspace(base):
    tmp_path = TEST_TMP_ROOT / f"gen3-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    base_graph_path = tmp_path / "base.json"
    base_graph_path.write_text(json.dumps(base), encoding="utf-8")
    return tmp_path, dict(
        base_graph_path=base_graph_path,
        graph_output_path=tmp_path / "graph.json",
        nodes_output_path=tmp_path / "expanded_nodes.json",
        edges_output_path=tmp_path / "expanded_edges.json",
        validity_report_output_path=tmp_path / "node_validity_report.json",
        enforce_export_gate=True,
    )


def _index(node, out=None):
    out = {} if out is None else out
    out[node["id"]] = node
    for child in node.get("children", []):
        _index(child, out)
    return out


BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {
            "id": "executive-branch",
            "name": "Executive Branch",
            "type": "Branch",
            "children": [
                {
                    "id": "exec-cabinet",
                    "name": "The Cabinet — Executive Departments",
                    "type": "Grouping",
                    "children": [
                        {"id": "exec-dept-a", "name": "Department of Alpha", "type": "Cabinet Department", "children": []},
                        {"id": "exec-dept-b", "name": "Department of Beta", "type": "Cabinet Department", "children": []},
                    ],
                },
                {
                    "id": "exec-independent",
                    "name": "Independent Establishments",
                    "type": "Grouping",
                    "children": [
                        {"id": f"exec-ind-{i}", "name": f"Independent Agency {i}", "type": "Agency", "children": [
                            {"id": f"exec-ind-{i}-office", "name": f"Office {i}", "type": "Office", "children": []}
                        ]}
                        for i in range(20)
                    ],
                },
                {"id": "exec-ind-usps", "name": "United States Postal Service", "type": "Government Corporation", "children": []},
            ],
        },
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}


class OfficialFloorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path, self.paths = _workspace(BASE)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def _build(self, lines, total=1_000_000.0):
        payload = {"nodes": [], "edges": [], "outlayRows": lines, "budgetSummary": {"government_total_outlay_amount": total}}
        return build_graph([payload], **self.paths)

    def test_department_lines_under_an_unlined_grouping_are_not_rescaled(self) -> None:
        # By subtree size the two-node Cabinet would get a sliver next to the
        # 40-node Independent grouping; its department lines total 700,000.
        result = self._build([_line("Department of Alpha", 400_000), _line("Department of Beta", 300_000)])
        nodes = _index(result.graph)
        self.assertEqual(nodes["exec-dept-a"]["cost_status"], "official")
        self.assertEqual(nodes["exec-dept-a"]["resolved_total_amount"], 400_000)
        self.assertEqual(nodes["exec-dept-b"]["resolved_total_amount"], 300_000)
        self.assertGreaterEqual(nodes["exec-cabinet"]["resolved_total_amount"], 700_000)
        # The rest of the executive share still goes to the others by weight.
        self.assertGreater(nodes["exec-independent"]["resolved_total_amount"], 0)
        executive = nodes["executive-branch"]["resolved_total_amount"]
        children_sum = sum(c["resolved_total_amount"] for c in nodes["executive-branch"]["children"])
        self.assertAlmostEqual(children_sum, executive, places=2)
        self.assertEqual(result.validation["sibling_sets_scaled_to_official_floors"], 0)

    def test_floors_beyond_the_parent_share_scale_and_say_so(self) -> None:
        result = self._build([_line("Department of Alpha", 900_000), _line("Department of Beta", 900_000)])
        nodes = _index(result.graph)
        self.assertEqual(nodes["exec-dept-a"]["cost_status"], "scaled_official")
        self.assertLess(nodes["exec-dept-a"]["resolved_total_amount"], 900_000)
        self.assertEqual(nodes["exec-dept-a"]["rollup_total_amount"], 900_000)
        self.assertGreaterEqual(result.validation["sibling_sets_scaled_to_official_floors"], 1)

    def test_a_negative_line_is_set_aside_not_anchored(self) -> None:
        result = self._build([_line("United States Postal Service", -25_000), _line("Department of Alpha", 100_000)])
        nodes = _index(result.graph)
        self.assertEqual(nodes["exec-ind-usps"]["cost_status"], "allocated")
        self.assertGreater(nodes["exec-ind-usps"]["resolved_total_amount"], 0)
        stats = result.validation["treasury_outlay_rows"]
        self.assertEqual(stats["rows_negative_skipped"], 1)
        self.assertEqual(stats["negative_sample"], ["United States Postal Service"])
        self.assertEqual(stats["rows_applied"], 1)

    def test_a_crawler_twin_does_not_make_the_curated_line_ambiguous(self) -> None:
        payload = {
            "nodes": [{"id": "department-of-alpha", "name": "Department of Alpha", "type": "Organization", "sourceUrls": ["https://www.alpha.gov"], "parentId": "executive-branch"}],
            "edges": [],
            "outlayRows": [_line("Department of Alpha", 400_000)],
            "budgetSummary": {"government_total_outlay_amount": 1_000_000},
        }
        result = build_graph([payload], **self.paths)
        nodes = _index(result.graph)
        self.assertEqual(nodes["exec-dept-a"]["cost_status"], "official")
        self.assertEqual(result.validation["treasury_outlay_rows"]["rows_ambiguous"], 0)

    def test_a_run_without_lines_clears_last_runs_lines_completely(self) -> None:
        self._build([_line("Department of Alpha", 400_000)])
        second = self._build([])
        nodes = _index(second.graph)
        alpha = nodes["exec-dept-a"]
        self.assertEqual(alpha["cost_status"], "allocated")
        for field in ("rollup_total_amount", "budget_source", "budget_as_of", "amount_kind", "treasury_row_name"):
            self.assertNotIn(field, alpha, field)
        self.assertNotIn("treasury_outlays", alpha.get("sourceTypes", []))
        self.assertFalse(any("fiscaldata" in url for url in alpha.get("sourceUrls", [])))
        self.assertEqual(second.validation["treasury_outlay_rows"]["stale_rollups_cleared"], 1)


class OrphanChainTests(unittest.TestCase):
    def test_a_placed_orphan_can_still_be_a_prefix_parent(self) -> None:
        root = {
            "id": "root",
            "name": "Root",
            "children": [
                {"id": "department-a", "name": "Department A", "children": []},
                {"id": "office-of-widgets", "name": "Office of Widgets", "sourceUrls": ["https://www.a.gov/w"], "children": []},
                {"id": "office-of-widgets-director", "name": "Director", "sourceUrls": ["https://www.a.gov/w/d"], "children": []},
            ],
        }
        result = resolve_root_orphans(root, trusted_node_ids={"department-a"})
        self.assertEqual(result["summary"]["duplicates_removed"], 0)
        widgets = next(c for c in root["children"] if c["id"] == "office-of-widgets")
        self.assertEqual([c["id"] for c in widgets["children"]], ["office-of-widgets-director"])
        self.assertNotIn("attachToRoot", widgets["children"][0])


class PromotedButPrunedTests(unittest.TestCase):
    def test_pending_queue_keeps_a_record_whose_node_was_not_published(self) -> None:
        candidates = [{"id": "cand-1", "name": "Office One"}, {"id": "cand-2", "name": "Office Two"}, {"id": "cand-3", "name": "Office Three"}]
        stats = {"consumed_candidate_ids": ["cand-1", "cand-2"], "consumed_candidate_targets": {"cand-1": "office-one", "cand-2": "exec-dept-doe"}}
        queue = pending_review_queue(candidates, stats, published_ids={"exec-dept-doe"})
        self.assertEqual([c["id"] for c in queue], ["cand-1", "cand-3"])
        # Without knowledge of what was published, consumed means consumed.
        self.assertEqual([c["id"] for c in pending_review_queue(candidates, stats)], ["cand-3"])

    def test_run_pipeline_keeps_a_pruned_promotion_in_the_queue(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"gen3-run-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base = {"id": "root", "name": "Root", "type": "Foundation", "children": [{"id": "department-of-energy", "name": "Department of Energy", "type": "Department", "children": []}]}
            base_path = tmp_path / "base.json"
            base_path.write_text(json.dumps(base), encoding="utf-8")
            candidate_path = tmp_path / "candidate_nodes.json"
            run_pipeline(
                base_graph_path=base_path,
                candidate_output_path=candidate_path,
                graph_output_path=tmp_path / "graph.json",
                nodes_output_path=tmp_path / "expanded_nodes.json",
                edges_output_path=tmp_path / "expanded_edges.json",
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=True,
                stats_output_path=tmp_path / "pipeline_stats.json",
                direct_payload_fetchers=[("treasury_outlays", lambda: {"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1000}})],
                discovery_fetchers={
                    "wikidata_records": lambda: [],
                    "official_directory_records": lambda: [
                        {"agencyName": "Department of Energy", "officeName": "Office of Grid Deployment", "directoryUrl": "https://www.energy.gov/leadership", "sourceUrl": "https://www.energy.gov/leadership", "description": "x"}
                    ],
                    "federal_register_records": lambda: [],
                },
            )
            graph = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
            ids = set(_index(graph))
            queue = json.loads(candidate_path.read_text(encoding="utf-8"))
            names = {c["name"] for c in queue}
            # Either it was published, or it is still awaiting review — never neither.
            self.assertTrue("Office of Grid Deployment" in names or any("grid-deployment" in i for i in ids))
            if not any("grid-deployment" in i for i in ids):
                self.assertIn("Office of Grid Deployment", names)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class FederalRegisterNameTests(unittest.TestCase):
    def test_a_units_own_for_is_kept(self) -> None:
        self.assertEqual(federal_register.extract_units("Administration for Children and Families; Notice"), ["Administration for Children and Families"])
        self.assertEqual(federal_register.extract_units("Office for Civil Rights; Notice of Meeting"), ["Office for Civil Rights"])
        self.assertEqual(federal_register.extract_units("Office of the Assistant Secretary for Health"), ["Office of the Assistant Secretary for Health"])

    def test_commas_inside_a_name_survive(self) -> None:
        self.assertEqual(federal_register.extract_units("Bureau of Alcohol, Tobacco, Firearms and Explosives; Notice"), ["Bureau of Alcohol, Tobacco, Firearms and Explosives"])
        self.assertEqual(federal_register.extract_units("Office of Planning, Research, and Evaluation"), ["Office of Planning, Research, and Evaluation"])

    def test_sentences_still_stop(self) -> None:
        self.assertEqual(federal_register.extract_units("Submission to the Office of Management and Budget for Review and Approval"), ["Office of Management and Budget"])


class ReviewQueueUsRuleTests(unittest.TestCase):
    def test_positive_evidence_and_country_words(self) -> None:
        gov = {"name": "Office of Widgets", "sourceUrls": ["https://www.widgets.gov"], "discoveryMethod": "wikidata_government_entity_scan"}
        self.assertTrue(has_us_federal_evidence(gov))
        australia = {"name": "Treasurer of Australia", "sourceUrls": ["https://treasury.gov.au"], "possibleParent": "Department of the Treasury", "discoveryMethod": "wikidata_government_entity_scan"}
        self.assertFalse(has_us_federal_evidence(australia))
        self.assertTrue(is_foreign(australia))
        friendship = {"name": "Japan-United States Friendship Commission", "sourceUrls": ["https://www.jusfc.gov"]}
        self.assertFalse(is_foreign(friendship))
        self.assertTrue(has_us_federal_evidence(friendship))

    def test_repair_applies_the_positive_rule_and_the_current_extractor(self) -> None:
        records = [
            {"id": "a", "name": "Treasurer of Australia", "sourceUrl": "https://treasury.gov.au", "sourceUrls": ["https://treasury.gov.au"], "possibleParent": "Department of the Treasury", "discoveryMethod": "wikidata_government_entity_scan", "confidenceEstimate": 0.6},
            {"id": "b", "name": "Court of Justice of the European Union", "sourceUrl": "https://curia.europa.eu", "sourceUrls": ["https://curia.europa.eu"], "possibleParent": None, "discoveryMethod": "wikidata_government_entity_scan", "confidenceEstimate": 0.6},
            {"id": "e", "name": "Municipal Waterworks Board", "sourceUrl": "https://waterworks.example.org", "sourceUrls": ["https://waterworks.example.org"], "possibleParent": None, "discoveryMethod": "wikidata_government_entity_scan", "confidenceEstimate": 0.6},
            {"id": "c", "name": "Office of Management and Budget for Review and Approval", "sourceUrl": "https://www.federalregister.gov/documents/x", "sourceUrls": ["https://www.federalregister.gov/documents/x"], "sourceTypes": ["official_site"], "possibleParent": "Education Department", "discoveryMethod": "federal_register_listing_scan", "confidenceEstimate": 0.7},
            {"id": "d", "name": "Office of Grid Deployment", "sourceUrl": "https://www.energy.gov/x", "sourceUrls": ["https://www.energy.gov/x"], "possibleParent": "Department of Energy", "discoveryMethod": "wikidata_government_entity_scan", "confidenceEstimate": 0.9},
        ]
        kept, report = repair(records, published_names={"department of energy"}, ids_by_name={"department of energy": "exec-dept-doe"})
        self.assertEqual([r["id"] for r in kept], ["d"])
        # Australia and the EU carry foreign words; the waterworks carries nothing at all.
        self.assertEqual(report["dropped"]["no_us_federal_evidence"], 1)
        self.assertEqual(report["dropped"]["non_us_public_body"], 2)
        self.assertEqual(report["dropped"]["federal_register_fragment"], 1)
        self.assertEqual(kept[0]["sourceTypes"], ["candidate_discovery", "official_site"])
        self.assertTrue(kept[0]["existsProven"])


if __name__ == "__main__":
    unittest.main()
