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
    STATUS_ANCESTOR,
    STATUS_DISAGREES,
    STATUS_LISTED,
    apply_directory_evidence,
    federal_register_name_keys,
    load_directory_file,
    match_federal_register,
    split_qualifier,
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
                    {"id": "doe-gc", "name": "Office of General Counsel", "type": "Office", "children": []},
                ]},
                {"id": "exec-dept-army", "name": "Department of the Army", "type": "Military Department", "children": [
                    {"id": "army-gc", "name": "Office of General Counsel", "type": "Office", "children": []},
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
        {"id": 8, "parent_id": 1, "name": "General Counsel Office", "slug": "general-counsel-office"},
        {"id": 9, "parent_id": 5, "name": "General Counsel Office, Army Department", "slug": "general-counsel-office-army-department"},
    ],
}


class NameKeyTests(unittest.TestCase):
    def test_a_department_answers_to_the_curated_spelling(self) -> None:
        self.assertIn("department of energy", federal_register_name_keys("Energy Department"))
        self.assertIn("department of the army", federal_register_name_keys("Army Department"))
        self.assertIn("office of science", federal_register_name_keys("Office of Science"))
        self.assertEqual(federal_register_name_keys(""), set())

    def test_the_head_noun_last_convention_is_inverted_for_the_curated_prepositions(self) -> None:
        self.assertIn("commission on civil rights", federal_register_name_keys("Civil Rights Commission"))
        self.assertIn("bureau of alcohol tobacco firearms and explosives", federal_register_name_keys("Alcohol, Tobacco, Firearms, and Explosives Bureau"))
        self.assertIn("office of inspector general", federal_register_name_keys("Inspector General Office"))
        self.assertIn("agency for international development", federal_register_name_keys("International Development Agency"))
        # A name whose last word is not a head noun is not rewritten.
        self.assertEqual({k for k in federal_register_name_keys("Architect of the Capitol") if "of" in k}, {"architect of the capitol", "united states architect of the capitol"})

    def test_a_dropped_united_states_is_tolerated_both_ways(self) -> None:
        self.assertIn("united states coast guard", federal_register_name_keys("Coast Guard"))
        self.assertIn("mint", federal_register_name_keys("United States Mint"))

    def test_a_comma_is_a_qualifier_only_when_the_tail_is_itself_an_entry(self) -> None:
        names = {"Energy Department", "Inspector General Office, Energy Department", "Alcohol, Tobacco, Firearms, and Explosives Bureau"}
        self.assertEqual(split_qualifier("Inspector General Office, Energy Department", names), ("Inspector General Office", "Energy Department"))
        self.assertEqual(split_qualifier("Alcohol, Tobacco, Firearms, and Explosives Bureau", names), ("Alcohol, Tobacco, Firearms, and Explosives Bureau", None))


class MatchTests(unittest.TestCase):
    def _match(self, directory=DIRECTORY):
        tree = json.loads(json.dumps(BASE))
        node_map, parent_map = index_tree(tree)
        return match_federal_register(directory["data"], node_map, parent_map, root_id=ROOT_ID, fetched_at=directory["fetched_at"])

    def test_one_entry_to_one_node_and_the_directory_s_own_words(self) -> None:
        records, report = self._match()
        self.assertEqual(report["matched"], 6)   # DOE, Science, NNSA, Army, Corps, the Army's General Counsel
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
        self.assertEqual(report["placements_listed"], 3)   # Science and NNSA under DOE, the Army's General Counsel under the Army
        # The Corps' directory parent, "Defense Department", has no node in this
        # graph: the directory's word about the edge is recorded, but no claim
        # is made either way — that is "parent unmatched", not a disagreement.
        corps = records["army-corps"]
        self.assertNotIn("placement", corps)
        self.assertEqual(corps["parentListedName"], "Defense Department")
        self.assertEqual(report["placements_parent_unmatched"], 1)

    def test_a_name_several_nodes_share_matches_nothing_unless_the_directory_qualifies_it(self) -> None:
        records, report = self._match()
        self.assertNotIn("doe-gc", records, "the unqualified entry could be either General Counsel")
        self.assertIn("General Counsel Office", report["unmatched_entries"])
        self.assertIn("office of general counsel", report["ambiguous_names_in_graph"])
        # "General Counsel Office, Army Department" is scoped by its qualifier to the Army's.
        army_gc = records["army-gc"]
        self.assertEqual(army_gc["listedName"], "General Counsel Office, Army Department")
        self.assertEqual(army_gc["placement"], {"status": STATUS_LISTED, "parentId": "exec-dept-army", "parentListedName": "Army Department"})

    def test_a_directory_parent_that_is_an_ancestor_here_is_neither_agreement_nor_contradiction(self) -> None:
        tree = json.loads(json.dumps(BASE))
        doe = index_tree(tree)[0]["exec-dept-doe"]
        # Put a curated grouping between DOE and NNSA, as the base graph does for the Defense agencies.
        nnsa = next(c for c in doe["children"] if c["id"] == "doe-nnsa")
        doe["children"] = [c for c in doe["children"] if c["id"] != "doe-nnsa"] + [{"id": "doe-agencies", "name": "Semi-autonomous agencies", "type": "Division", "children": [nnsa]}]
        node_map, parent_map = index_tree(tree)
        records, report = match_federal_register(DIRECTORY["data"], node_map, parent_map, root_id=ROOT_ID, fetched_at=DIRECTORY["fetched_at"])
        self.assertEqual(records["doe-nnsa"]["placement"]["status"], STATUS_ANCESTOR)
        self.assertEqual(records["doe-nnsa"]["placement"]["ancestorId"], "exec-dept-doe")
        self.assertEqual(records["doe-nnsa"]["placement"]["distance"], 2)
        self.assertEqual(report["placements_ancestor"], 1)
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, records)
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        self.assertEqual(stats["placements_ancestor"], 1)
        self.assertNotIn("placementVerified", nnsa)
        self.assertEqual(nnsa["placementDirectoryAncestor"]["listedUnder"], "Energy Department")

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
        self.assertEqual(stats["listed"], 6)
        self.assertEqual(stats["placements_listed"], 3)
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

    def test_a_listing_withdraws_the_page_s_failed_check_on_the_same_node(self) -> None:
        # The page module recorded that the unit's own page does not name it;
        # the directory lists it. "Checked, not found" beside a source is what
        # the gate forbids, and the documented rule is that the negative is
        # published only where no other route gave the node a source.
        tree = self._tree()
        page = {"doe-science": {"status": "not_found", "checkedAt": "2026-09-09T00:00:00+00:00", "siteFrom": "doe-science",
                                "ownPage": True, "pagesRead": 1,
                                "failures": [{"url": "https://science.osti.gov/", "reason": "name_not_labelled_on_page"}]}}
        apply_evidence_to_tree(tree, page)
        science = index_tree(tree)[0]["doe-science"]
        self.assertEqual(science["verificationFailure"], "not_found")
        stats = apply_directory_evidence(tree, self._records())
        self.assertEqual(stats["failed_checks_withdrawn"], 1)
        self.assertNotIn("verificationFailure", science)
        self.assertNotIn("verificationSiteFrom", science)
        self.assertEqual(science["sourceUrls"], ["https://www.federalregister.gov/agencies/science-office"])
        self.assertEqual(science["verificationMethod"], FR_METHOD)
        self.assertEqual(science["lastVerified"], "2026-09-08T19:30:00+00:00", "the date is the listing's, not the withdrawn fetch's")
        self.assertEqual(science["evidenceVerifiedAt"], "2026-09-08T19:30:00+00:00")

    def test_a_failed_check_stands_where_the_directory_lists_nothing(self) -> None:
        tree = self._tree()
        page = {"doe-gc": {"status": "not_found", "checkedAt": "2026-09-09T00:00:00+00:00", "siteFrom": "doe-gc",
                           "ownPage": True, "pagesRead": 1,
                           "failures": [{"url": "https://www.energy.gov/gc", "reason": "name_not_labelled_on_page"}]}}
        apply_evidence_to_tree(tree, page)
        records = {k: v for k, v in self._records().items() if k != "doe-gc"}
        stats = apply_directory_evidence(tree, records)
        gc = index_tree(tree)[0]["doe-gc"]
        self.assertEqual(stats["failed_checks_withdrawn"], 0)
        self.assertEqual(gc["verificationFailure"], "not_found")
        self.assertEqual(gc["lastVerified"], "2026-09-09T00:00:00+00:00")
        self.assertFalse(gc.get("sourceUrls"))

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
            code = derive_directory_evidence.main(["d", "--base-graph", str(self.base), "--federal-register", str(self.fr), "--out", str(self.out),
                                                   "--senate-dir", str(self.tmp / "no-senate")])
        self.assertEqual(code, 0, buf.getvalue())
        store = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(store["sources"][0]["fetched_at"], DIRECTORY["fetched_at"])
        self.assertEqual(len(store["nodes"]), 6)
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=self.out,
        )
        self.assertEqual(result.validation["directory_evidence"]["listed"], 6)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        nodes = index_tree(graph)[0]
        self.assertEqual(nodes["doe-nnsa"]["verificationMethod"], FR_METHOD)
        self.assertIs(nodes["doe-nnsa"]["placementVerified"], True)
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("directory-listed     : 6 in the Federal Register's agency directory; 3 placements from it", out.getvalue())
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
            code = derive_directory_evidence.main(["d", "--base-graph", str(self.base), "--federal-register", str(self.fr), "--out", str(self.out), "--dry-run",
                                                   "--senate-dir", str(self.tmp / "no-senate")])
        self.assertEqual(code, 0)
        self.assertFalse(self.out.exists())
        self.assertIn("matched 6", buf.getvalue())


class GateMirrorsTheMatcherTests(unittest.TestCase):
    """The gate keeps a stdlib copy of the directory's naming rule; the two
    must agree, or a placement the matcher accepts would fail the gate."""

    def test_the_gate_s_copy_of_the_naming_rule_agrees_with_the_matcher(self) -> None:
        from scripts.validate_published_graph import directory_name_keys

        for name in ("Prisons Bureau", "Energy Department", "Civil Rights Commission", "Coast Guard", "United States Mint",
                     "Alcohol, Tobacco, Firearms, and Explosives Bureau", "Inspector General Office, Energy Department",
                     "Administration Office, Executive Office of the President", "Architect of the Capitol"):
            with self.subTest(name=name):
                expected = federal_register_name_keys(split_qualifier(name, {"Energy Department", "Executive Office of the President"})[0])
                self.assertEqual(directory_name_keys(name), expected)
