"""The Senate's committee list as evidence: a complete list, so absence
counts, and the graph's stale names are published as checked negatives."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification.congress import (
    SENATE_METHOD,
    SENATE_PLACEMENT_METHOD,
    STATUS_LISTED,
    STATUS_NOT_IN_LIST,
    committee_key,
    load_senate_committees,
    match_senate,
    subcommittee_key,
)
from data_pipeline.verification.directories import FAILURE_NOT_IN_LIST, apply_directory_evidence
from data_pipeline.verification.evidence import apply_evidence_to_tree
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-senate", "name": "United States Senate", "type": "Chamber", "children": [
                {"id": "leg-senate-committees", "name": "Senate Committees", "type": "Division", "children": [
                    {"id": "leg-senate-cmte-judiciary", "name": "Senate Committee on Judiciary", "type": "Committee", "children": [
                        {"id": "leg-senate-cmte-judiciary-sub-constitution", "name": "Constitution", "type": "Subcommittee", "children": []},
                        {"id": "leg-senate-cmte-judiciary-sub-antitrust", "name": "Competition Policy, Antitrust & Consumer Rights", "type": "Subcommittee", "children": []},
                        {"id": "leg-senate-cmte-judiciary-chair", "name": "Chair, Judiciary", "type": "Position", "children": []},
                    ]},
                    {"id": "leg-senate-cmte-ethics", "name": "Senate Committee on Select Committee on Ethics", "type": "Committee", "children": []},
                    {"id": "leg-senate-cmte-stale", "name": "Senate Committee on Post Roads", "type": "Committee", "children": []},
                ]},
            ]},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
XML = """<?xml version="1.0" encoding="UTF-8"?><committee_membership><committees><majority_party>R</majority_party>
<committee_name>{name}</committee_name><committee_code>{code}00</committee_code><members></members>{subs}</committees></committee_membership>"""
SUB = "<subcommittee><subcommittee_name>{name}</subcommittee_name><committee_code>{code}</committee_code><members></members></subcommittee>"


def write_fixture(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "SSJU": ("Committee on the Judiciary", [("Subcommittee on the Constitution", "SSJU02"),
                                                 ("Subcommittee on Antitrust, Competition Policy, and Consumer Rights", "SSJU01"),
                                                 ("Subcommittee on Immigration, Citizenship, and Border Safety", "SSJU04")]),
        "SLET": ("Select Committee on Ethics", []),
    }
    for code, (name, subs) in files.items():
        xml = XML.format(name=name, code=code, subs="".join(SUB.format(name=n, code=c) for n, c in subs))
        (directory / f"committee_memberships_{code}.xml").write_text(xml, encoding="utf-8")
        (directory / f"committee_memberships_{code}.xml.meta.json").write_text(json.dumps({
            "fetched_at": "2026-09-08T19:20:53Z", "url": f"https://www.senate.gov/general/committee_membership/committee_memberships_{code}.xml",
            "final_url": f"https://www.senate.gov/general/committee_membership/committee_memberships_{code}.xml", "status": 200,
        }), encoding="utf-8")


class KeyTests(unittest.TestCase):
    def test_curation_artifacts_and_the_senate_s_names_share_a_key(self) -> None:
        self.assertEqual(committee_key("Senate Committee on Select Committee on Ethics"), committee_key("Select Committee on Ethics"))
        self.assertEqual(committee_key("Senate Committee on Judiciary"), committee_key("Committee on the Judiciary"))
        self.assertEqual(committee_key("Senate Committee on Budget"), committee_key("Committee on the Budget"))
        self.assertEqual(subcommittee_key("Constitution"), subcommittee_key("Subcommittee on the Constitution"))
        # A renamed subcommittee is a different key: no fuzzing.
        self.assertNotEqual(subcommittee_key("Competition Policy, Antitrust & Consumer Rights"), subcommittee_key("Subcommittee on Antitrust, Competition Policy, and Consumer Rights"))


class MatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"senate-{uuid.uuid4().hex}"
        write_fixture(self.tmp / "senate")
        self.committees = load_senate_committees(self.tmp / "senate")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_loader_reads_the_files_and_their_meta(self) -> None:
        self.assertEqual({c["code"] for c in self.committees}, {"SSJU00", "SLET00"})
        judiciary = next(c for c in self.committees if c["code"] == "SSJU00")
        self.assertEqual(len(judiciary["subcommittees"]), 3)
        self.assertEqual(judiciary["fetched_at"], "2026-09-08T19:20:53Z")
        self.assertTrue(judiciary["url"].startswith("https://www.senate.gov/"))

    def test_listed_placed_absent_and_missing_are_each_recorded_as_themselves(self) -> None:
        tree = json.loads(json.dumps(BASE))
        node_map, parent_map = index_tree(tree)
        records, report = match_senate(self.committees, node_map, parent_map)
        self.assertEqual(report["committees_matched"], 2)
        self.assertEqual(records["leg-senate-cmte-ethics"]["listedName"], "Select Committee on Ethics")
        constitution = records["leg-senate-cmte-judiciary-sub-constitution"]
        self.assertEqual((constitution["status"], constitution["listedName"]), (STATUS_LISTED, "Subcommittee on the Constitution"))
        self.assertEqual(constitution["placement"]["parentId"], "leg-senate-cmte-judiciary")
        stale = records["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertEqual(stale["status"], STATUS_NOT_IN_LIST)
        self.assertEqual(stale["listedUnder"], "Committee on the Judiciary")
        self.assertIn("Subcommittee on Antitrust, Competition Policy, and Consumer Rights", stale["listedSubcommittees"])
        self.assertEqual(report["subcommittees_not_in_graph"], [{"committee": "Committee on the Judiciary", "subcommittee": "Subcommittee on Antitrust, Competition Policy, and Consumer Rights"},
                                                                {"committee": "Committee on the Judiciary", "subcommittee": "Subcommittee on Immigration, Citizenship, and Border Safety"}])
        self.assertEqual(records["leg-senate-cmte-stale"]["status"], STATUS_NOT_IN_LIST)
        self.assertEqual(report["graph_committees_not_in_list"], [{"id": "leg-senate-cmte-stale", "name": "Senate Committee on Post Roads"}])
        self.assertNotIn("leg-senate-cmte-judiciary-chair", records, "positions are not committees")

    def test_applied_a_listing_verifies_and_places_and_an_absence_is_a_checked_negative(self) -> None:
        tree = json.loads(json.dumps(BASE))
        node_map, parent_map = index_tree(tree)
        records, _ = match_senate(self.committees, node_map, parent_map)
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, records)
        nodes = index_tree(tree)[0]
        self.assertEqual((stats["listed"], stats["placements_listed"], stats["not_in_list"]), (3, 1, 2))
        constitution = nodes["leg-senate-cmte-judiciary-sub-constitution"]
        self.assertEqual(constitution["verificationMethod"], SENATE_METHOD)
        self.assertEqual(constitution["placementMethod"], SENATE_PLACEMENT_METHOD)
        self.assertIn("senate_committee_list", constitution["sourceTypes"])
        stale = nodes["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertEqual(stale["verificationFailure"], FAILURE_NOT_IN_LIST)
        self.assertEqual(stale["verificationFailureSource"]["listedUnder"], "Committee on the Judiciary")
        self.assertEqual(stale["lastVerified"], "2026-09-08T19:20:53Z")
        self.assertFalse(stale.get("sourceUrls"))
        # Withdrawn with the rest on the next build.
        apply_evidence_to_tree(tree, {})
        stale = index_tree(tree)[0]["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertNotIn("verificationFailure", stale)
        self.assertNotIn("verificationFailureSource", stale)
        self.assertFalse(stale.get("lastVerified"))

    def test_the_gate_accepts_the_list_s_claims_and_refuses_an_unbacked_negative(self) -> None:
        base = self.tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
        tree = json.loads(json.dumps(BASE)); node_map, parent_map = index_tree(tree)
        records, _ = match_senate(self.committees, node_map, parent_map)
        ev = self.tmp / "directory_evidence.json"; ev.write_text(json.dumps({"nodes": records}), encoding="utf-8")
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=None, sites_path=None, directory_evidence_path=ev,
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("Senate list          : 3 committees and subcommittees listed; 1 placements from it; 2 curated names the list does not carry", out.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        for name, mutate in {
            "negative without the list's URL": lambda n: n["leg-senate-cmte-judiciary-sub-antitrust"].__setitem__("verificationFailureSource", {"source": "senate_committee_list"}),
            "an invented failure kind": lambda n: n["leg-senate-cmte-judiciary-sub-antitrust"].__setitem__("verificationFailure", "vibes"),
        }.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph)); mutate(index_tree(corrupted)[0])
                path = self.tmp / f"{uuid.uuid4().hex}.json"; path.write_text(json.dumps(corrupted), encoding="utf-8")
                out = io.StringIO()
                with redirect_stdout(out):
                    code = gate_main(["gate", str(path)])
                self.assertEqual(code, 1, f"{name}:\n{out.getvalue()}")
