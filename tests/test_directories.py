"""Evidence from the Federal Register's agency directory: what the
directory says, said as itself, and nothing inferred beyond it."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification.directories import (
    FR_METHOD,
    FR_PLACEMENT_METHOD,
    STATUS_DISAGREES,
    STATUS_LISTED,
    apply_directory_evidence,
    federal_register_name_keys,
    load_directory_file,
    match_federal_register,
)
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, apply_evidence_to_tree
from scripts import derive_directory_evidence
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                    {"id": "doe-science", "name": "Office of Science", "type": "Office", "children": [
                        {"id": "doe-science-director", "name": "Director", "type": "Position", "children": []},
                    ]},
                    {"id": "doe-nnsa", "name": "National Nuclear Security Administration", "type": "Component Agency", "children": []},
                    {"id": "doe-gc", "name": "General Counsel", "type": "Office", "children": []},
                ]},
                {"id": "exec-dept-army", "name": "Department of the Army", "type": "Military Department", "children": [
                    {"id": "army-gc", "name": "General Counsel", "type": "Office", "children": []},
                    {"id": "army-corps", "name": "Corps of Engineers", "type": "Component Agency", "children": []},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
# Shaped like https://www.federalregister.gov/api/v1/agencies.json entries.
DIRECTORY = {
    "fetched_at": "2026-09-08T19:30:00+00:00",
    "url": "https://www.federalregister.gov/api/v1/agencies.json",
    "data": [
        {"id": 1, "parent_id": None, "name": "Energy Department", "slug": "energy-department", "agency_url": "https://www.energy.gov"},
        {"id": 2, "parent_id": 1, "name": "Office of Science", "slug": "science-office", "agency_url": None},
        {"id": 3, "parent_id": 1, "name": "National Nuclear Security Administration", "slug": "national-nuclear-security-administration"},
        {"id": 4, "parent_id": 1, "name": "Bonneville Power Administration", "slug": "bonneville-power-administration"},
        {"id": 5, "parent_id": None, "name": "Army Department", "slug": "army-department"},
        {"id": 6, "parent_id": 7, "name": "Corps of Engineers", "slug": "engineers-corps"},
        {"id": 7, "parent_id": None, "name": "Defense Department", "slug": "defense-department"},
        {"id": 8, "parent_id": 1, "name": "General Counsel", "slug": "general-counsel"},
    ],
}


class NameKeyTests(unittest.TestCase):
    def test_a_department_answers_to_the_curated_spelling(self) -> None:
        self.assertIn("department of energy", federal_register_name_keys("Energy Department"))
        self.assertIn("department of the army", federal_register_name_keys("Army Department"))
        self.assertEqual(federal_register_name_keys("Office of Science"), {"office of science"})
        self.assertEqual(federal_register_name_keys(""), set())


class MatchTests(unittest.TestCase):
    def _match(self, directory=DIRECTORY):
        tree = json.loads(json.dumps(BASE))
        node_map, parent_map = index_tree(tree)
        return match_federal_register(directory["data"], node_map, parent_map, root_id=ROOT_ID, fetched_at=directory["fetched_at"])

    def test_one_entry_to_one_node_and_the_directory_s_own_words(self) -> None:
        records, report = self._match()
        self.assertEqual(report["matched"], 5)   # DOE, Science, NNSA, Army, Corps
        doe = records["exec-dept-doe"]
        self.assertEqual((doe["status"], doe["listedName"], doe["url"]), (STATUS_LISTED, "Energy Department", "https://www.federalregister.gov/agencies/energy-department"))
        self.assertEqual(doe["agencyUrl"], "https://www.energy.gov")
        self.assertEqual(doe["checkedAt"], "2026-09-08T19:30:00+00:00")
        self.assertNotIn("placement", doe, "a top-level entry claims nothing about the curated grouping above it")
        self.assertIn("Bonneville Power Administration", report["unmatched_entries"])

    def test_placement_agrees_or_disagrees_and_is_never_resolved(self) -> None:
        records, report = self._match()
        science = records["doe-science"]
        self.assertEqual(science["placement"], {"status": STATUS_LISTED, "parentId": "exec-dept-doe", "parentListedName": "Energy Department"})
        self.assertEqual(report["placements_listed"], 2)   # Science and NNSA under DOE
        # The Corps' directory parent, "Defense Department", has no node in this
        # graph: the directory's word about the edge is recorded, but no claim
        # is made either way — that is "parent unmatched", not a disagreement.
        corps = records["army-corps"]
        self.assertNotIn("placement", corps)
        self.assertEqual(corps["parentListedName"], "Defense Department")
        self.assertEqual(report["placements_parent_unmatched"], 1)

    def test_a_name_several_nodes_share_matches_nothing(self) -> None:
        records, report = self._match()
        self.assertNotIn("doe-gc", records)
        self.assertNotIn("army-gc", records)
        self.assertIn("General Counsel", report["unmatched_entries"])
        self.assertIn("general counsel", report["ambiguous_names_in_graph"])

    def test_two_entries_for_one_node_match_nothing(self) -> None:
        directory = json.loads(json.dumps(DIRECTORY))
        directory["data"].append({"id": 9, "parent_id": 1, "name": "Office of Science", "slug": "science-office-2"})
        records, report = self._match(directory)
        self.assertNotIn("doe-science", records)
        self.assertTrue(any(a["name"] == "Office of Science" for a in report["ambiguous_entries"]))


class ApplyTests(unittest.TestCase):
    def _tree(self):
        return json.loads(json.dumps(BASE))

    def _records(self):
        tree = self._tree()
        node_map, parent_map = index_tree(tree)
        return match_federal_register(DIRECTORY["data"], node_map, parent_map, root_id=ROOT_ID, fetched_at=DIRECTORY["fetched_at"])[0]

    def test_a_listing_is_a_source_a_date_a_method_and_a_placement(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, self._records())
        nodes = index_tree(tree)[0]
        science = nodes["doe-science"]
        self.assertEqual(stats["listed"], 5)
        self.assertEqual(stats["placements_listed"], 2)
        self.assertEqual(science["sourceUrls"], ["https://www.federalregister.gov/agencies/science-office"])
        self.assertIn("federal_register_directory", science["sourceTypes"])
        self.assertEqual(science["verificationMethod"], FR_METHOD)
        self.assertEqual(science["lastVerified"], "2026-09-08T19:30:00+00:00")
        self.assertEqual(science["directoryListing"]["parentListedName"], "Energy Department")
        self.assertIs(science["placementVerified"], True)
        self.assertEqual(science["placementMethod"], FR_PLACEMENT_METHOD)
        self.assertEqual(science["placementMatchedText"], "Office of Science")
        self.assertEqual(science["placementParentId"], "exec-dept-doe")
        self.assertNotIn("placementVerified", nodes["exec-dept-doe"], "a top-level entry is no evidence for the curated grouping above")

    def test_a_disagreement_is_published_as_one_and_resolves_nothing(self) -> None:
        directory = json.loads(json.dumps(DIRECTORY))
        directory["data"].append({"id": 10, "parent_id": None, "name": "Defense Department", "slug": "defense-department-2"})
        # Give the graph a Defense node so the Corps' directory parent exists and differs from its tree parent.
        tree = self._tree()
        cabinet = index_tree(tree)[0]["exec-cabinet"]
        cabinet["children"].append({"id": "exec-dept-defense", "name": "Department of Defense", "type": "Cabinet Department", "children": []})
        directory["data"] = [e for e in directory["data"] if e["id"] != 10]
        node_map, parent_map = index_tree(tree)
        records, report = match_federal_register(directory["data"], node_map, parent_map, root_id=ROOT_ID, fetched_at=directory["fetched_at"])
        self.assertEqual(records["army-corps"]["placement"]["status"], STATUS_DISAGREES)
        self.assertEqual(report["placements_disagree"][0]["directory_parent"], "exec-dept-defense")
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, records)
        corps = index_tree(tree)[0]["army-corps"]
        self.assertEqual(stats["placements_disagree"], 1)
        self.assertNotIn("placementVerified", corps)
        self.assertEqual(corps["placementDirectoryDisagreement"]["listedUnder"], "Defense Department")
        self.assertEqual(corps["placementDirectoryDisagreement"]["directoryParentId"], "exec-dept-defense")

    def test_a_page_claim_is_kept_and_the_directory_sits_beside_it(self) -> None:
        tree = self._tree()
        page = {"doe-science": {"status": "confirmed", "checkedAt": "2026-09-09T00:00:00+00:00", "method": "name_labelled_on_own_official_page",
                                "siteFrom": "doe-science", "sources": [{"url": "https://science.osti.gov/", "matchedText": "Office of Science"}],
                                "placement": {"status": "listed", "parentId": "exec-dept-doe", "url": "https://www.energy.gov/", "matchedText": "Office of Science", "checkedAt": "2026-09-09T00:00:00+00:00"}}}
        apply_evidence_to_tree(tree, page)
        apply_directory_evidence(tree, self._records())
        science = index_tree(tree)[0]["doe-science"]
        self.assertEqual(science["verificationMethod"], "name_labelled_on_own_official_page")
        self.assertEqual(science["placementMethod"], "name_labelled_on_parent_official_page")
        self.assertEqual(science["lastVerified"], "2026-09-09T00:00:00+00:00", "the later page read stands")
        self.assertEqual(science["directoryListing"]["listedName"], "Office of Science")
        self.assertEqual(sorted(science["sourceUrls"]), sorted(["https://science.osti.gov/", "https://www.federalregister.gov/agencies/science-office"]))

    def test_a_withdrawn_listing_leaves_nothing_behind(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {})
        apply_directory_evidence(tree, self._records())
        apply_evidence_to_tree(tree, {})          # the next build: the page module withdraws everything owned
        apply_directory_evidence(tree, {})        # and the directory has nothing this time
        science = index_tree(tree)[0]["doe-science"]
        for field in EVIDENCE_OWNED_FIELDS:
            self.assertNotIn(field, science, field)
        self.assertFalse(science.get("sourceUrls"))
        self.assertFalse(science.get("lastVerified"))

    def test_a_renamed_node_keeps_no_listing_earned_by_its_old_name(self) -> None:
        tree = self._tree()
        records = self._records()
        index_tree(tree)[0]["doe-science"]["name"] = "Office of Basic Research"
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, records)
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("directoryListing", index_tree(tree)[0]["doe-science"])


class ScriptAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"directory-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"; self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.fr = self.tmp / "fr.json"; self.fr.write_text(json.dumps(DIRECTORY), encoding="utf-8")
        self.out = self.tmp / "directory_evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_script_derives_records_and_the_build_publishes_them(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_directory_evidence.main(["d", "--base-graph", str(self.base), "--federal-register", str(self.fr), "--out", str(self.out)])
        self.assertEqual(code, 0, buf.getvalue())
        store = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(store["source"]["fetched_at"], DIRECTORY["fetched_at"])
        self.assertEqual(len(store["nodes"]), 5)
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=self.out,
        )
        self.assertEqual(result.validation["directory_evidence"]["listed"], 5)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        nodes = index_tree(graph)[0]
        self.assertEqual(nodes["doe-nnsa"]["verificationMethod"], FR_METHOD)
        self.assertIs(nodes["doe-nnsa"]["placementVerified"], True)
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("directory-listed     : 5 in the Federal Register's agency directory; 2 placements from it", out.getvalue())
        # And an invented directory method still fails the gate.
        corrupted = json.loads(json.dumps(graph))
        index_tree(corrupted)[0]["doe-nnsa"]["placementMethod"] = "listed_in_a_directory_i_made_up"
        path = self.tmp / "bad.json"; path.write_text(json.dumps(corrupted), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(path)])
        self.assertEqual(code, 1)

    def test_dry_run_writes_nothing(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_directory_evidence.main(["d", "--base-graph", str(self.base), "--federal-register", str(self.fr), "--out", str(self.out), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertFalse(self.out.exists())
        self.assertIn("matched 5", buf.getvalue())
