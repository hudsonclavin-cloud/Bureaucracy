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
    HOUSE_METHOD,
    HOUSE_PLACEMENT_METHOD,
    HOUSE_SOURCE,
    SENATE_METHOD,
    SENATE_PLACEMENT_METHOD,
    STATUS_LISTED,
    STATUS_NOT_IN_LIST,
    committee_key,
    load_house_committees,
    load_senate_committees,
    match_house,
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

    def test_the_complete_list_s_absence_outranks_a_page_s_not_found_and_keeps_the_read(self) -> None:
        # Both facts were true of nine Senate subcommittees on 2026-09-13: the
        # committee's subcommittees page did not label the curated name, and
        # the Senate's complete list did not carry it. The page module runs
        # first, and the list's stronger claim was then refused for standing
        # "beside a page's own failed check" — so the site published the
        # weaker of two true negatives. The list's badge wins; the page read
        # is kept as a fact in the field a listing already uses for it.
        tree = json.loads(json.dumps(BASE))
        node_map, parent_map = index_tree(tree)
        records, _ = match_senate(self.committees, node_map, parent_map)
        apply_evidence_to_tree(tree, {})
        nodes = index_tree(tree)[0]
        stale = nodes["leg-senate-cmte-judiciary-sub-antitrust"]
        # What the page module stamps for a not_found (evidence.py).
        stale.update({
            "lastVerified": "2026-09-13T21:59:29+00:00", "evidenceVerifiedAt": "2026-09-13T21:59:29+00:00",
            "verificationFailure": "not_found", "verificationSiteFrom": "leg-senate-cmte-judiciary-sub-antitrust",
            "verificationFailureSource": {
                "source": "own_official_page", "url": "https://www.judiciary.senate.gov/about/subcommittees",
                "urlsRead": ["https://www.judiciary.senate.gov/about/subcommittees"], "checkedAt": "2026-09-13T21:59:29+00:00",
            },
        })
        # A negative from a different list is another list's claim, not a page's: left alone.
        other = nodes["leg-senate-cmte-stale"]
        other.update({
            "verificationFailure": FAILURE_NOT_IN_LIST, "lastVerified": "2026-09-01T00:00:00Z", "evidenceVerifiedAt": "2026-09-01T00:00:00Z",
            "verificationFailureSource": {"source": "some_other_official_list", "url": "https://www.senate.gov/other.xml", "checkedAt": "2026-09-01T00:00:00Z"},
        })
        stats = apply_directory_evidence(tree, records)
        nodes = index_tree(tree)[0]
        stale = nodes["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertEqual(stats["page_negatives_superseded"], 1)
        self.assertEqual(stale["verificationFailure"], FAILURE_NOT_IN_LIST)
        self.assertEqual(stale["verificationFailureSource"]["source"], "senate_committee_list")
        self.assertEqual(stale["verificationFailureSource"]["listedUnder"], "Committee on the Judiciary")
        self.assertEqual(stale["lastVerified"], "2026-09-08T19:20:53Z")
        self.assertNotIn("verificationSiteFrom", stale)
        self.assertEqual(stale["pageReadNotNamed"], {
            "url": "https://www.judiciary.senate.gov/about/subcommittees", "checkedAt": "2026-09-13T21:59:29+00:00",
        })
        other = nodes["leg-senate-cmte-stale"]
        self.assertEqual(other["verificationFailureSource"]["source"], "some_other_official_list")
        self.assertEqual(other["lastVerified"], "2026-09-01T00:00:00Z")
        self.assertNotIn("pageReadNotNamed", other)
        # A node a page confirmed is not touched by the list's absence at all.
        tree2 = json.loads(json.dumps(BASE))
        apply_evidence_to_tree(tree2, {})
        confirmed = index_tree(tree2)[0]["leg-senate-cmte-judiciary-sub-antitrust"]
        confirmed.update({"sourceUrls": ["https://www.judiciary.senate.gov/about/subcommittees"], "sourceTypes": ["official_site"],
                          "lastVerified": "2026-09-13T21:59:29+00:00"})
        stats2 = apply_directory_evidence(tree2, records)
        confirmed = index_tree(tree2)[0]["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertNotIn("verificationFailure", confirmed)
        self.assertNotIn("pageReadNotNamed", confirmed)
        self.assertEqual(stats2["page_negatives_superseded"], 0)
        # And the superseded shape is withdrawn whole on the next build.
        apply_evidence_to_tree(tree, {})
        stale = index_tree(tree)[0]["leg-senate-cmte-judiciary-sub-antitrust"]
        self.assertNotIn("verificationFailure", stale)
        self.assertNotIn("pageReadNotNamed", stale)

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


# ---------------------------------------------------------------------------
# The House Clerk's spreadsheet: the same claim, the same gate, the other chamber.

HOUSE_BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-house", "name": "United States House of Representatives", "type": "Chamber", "children": [
                {"id": "leg-house-committees", "name": "House Committees", "type": "Division", "children": [
                    {"id": "leg-house-cmte-armed-services", "name": "House Committee on Armed Services", "type": "Committee", "children": [
                        {"id": "leg-house-cmte-armed-services-sub-readiness", "name": "Subcommittee on Readiness", "type": "Subcommittee", "children": []},
                        {"id": "leg-house-cmte-armed-services-sub-cyber", "name": "Subcommittee on Cyber, Information Technology & Innovation", "type": "Subcommittee", "children": []},
                        {"id": "leg-house-cmte-armed-services-chair", "name": "Chair, Armed Services", "type": "Position", "children": []},
                    ]},
                    {"id": "leg-house-cmte-judiciary", "name": "House Committee on Judiciary", "type": "Committee", "children": []},
                    {"id": "leg-house-cmte-permanent-select-committee-on-intelligence", "name": "House Committee on Permanent Select Committee on Intelligence", "type": "Committee", "children": []},
                    {"id": "leg-house-cmte-oversight-accountability", "name": "House Committee on Oversight & Accountability", "type": "Committee", "children": []},
                ]},
            ]},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
HOUSE_ROWS = [
    ["Committee Name", "Committee Code", "Committee Type", "Parent Committee", "Address", "City", "State", "Zip Code", "Telephone", "Website"],
    ["Committee on Armed Services", "AS00", "Standing", "", "2216 Rayburn", "Washington", "DC", "20515", "(202) 225-4151", "https://armedservices.house.gov"],
    ["Readiness", "AS03", "Subcommittee", "AS00", "2216 Rayburn", "Washington", "DC", "20515", "(202) 225-4151", ""],
    ["Cyber, Information Technologies, and Innovation", "AS35", "Subcommittee", "AS00", "2216 Rayburn", "Washington", "DC", "20515", "(202) 225-4151", ""],
    ["Committee on the Judiciary", "JU00", "Standing", "", "2138 Rayburn", "Washington", "DC", "20515", "(202) 225-3951", "https://judiciary.house.gov"],
    ["Permanent Select Committee on Intelligence", "IG00", "Select", "", "HVC304 Capitol", "Washington", "DC", "20515", "(202) 225-4121", ""],
    ["Committee on Oversight and Government Reform", "GO00", "Standing", "", "2157 Rayburn", "Washington", "DC", "20515", "(202) 225-5074", "https://oversight.house.gov"],
    ["Joint Committee on Taxation", "JT00", "Joint", "", "1625 Longworth", "Washington", "DC", "20515", "(202) 225-3621", ""],
]
HOUSE_URL = "https://clerk.house.gov/Committees/ExcelCommitteeData"
HOUSE_FETCHED = "2026-09-13T22:51:28Z"


def write_house_xlsx(path: Path, rows=None, *, meta: bool = True) -> None:
    """A minimal .xlsx — the same zip-of-XML the Clerk serves, inline strings —
    written by hand so the loader is tested on the format and not on a
    library."""
    import zipfile
    from xml.sax.saxutils import escape

    rows = HOUSE_ROWS if rows is None else rows
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    body = "".join(
        "<row r=\"{}\">{}</row>".format(
            r + 1,
            "".join("<c r=\"{}{}\" t=\"inlineStr\"><is><t>{}</t></is></c>".format(chr(65 + c), r + 1, escape(v)) for c, v in enumerate(cells)),
        )
        for r, cells in enumerate(rows)
    )
    sheet = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><worksheet xmlns=\"{}\"><sheetData>{}</sheetData></worksheet>".format(ns, body)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<?xml version=\"1.0\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")
        archive.writestr("xl/workbook.xml", "<?xml version=\"1.0\"?><workbook xmlns=\"{}\"><sheets><sheet name=\"Sheet1\" sheetId=\"1\"/></sheets></workbook>".format(ns))
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    if meta:
        path.with_name(path.name + ".meta.json").write_text(json.dumps({
            "fetched_at": HOUSE_FETCHED, "url": HOUSE_URL, "final_url": HOUSE_URL, "status": 200,
        }), encoding="utf-8")


class HouseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"house-{uuid.uuid4().hex}"
        self.xlsx = self.tmp / "committees.xlsx"
        write_house_xlsx(self.xlsx)
        self.committees = load_house_committees(self.xlsx)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_loader_reads_the_clerk_s_spreadsheet_and_refuses_one_without_a_date(self) -> None:
        self.assertEqual([c["code"] for c in self.committees], ["AS00", "JU00", "IG00", "GO00", "JT00"])
        armed = self.committees[0]
        self.assertEqual([s["name"] for s in armed["subcommittees"]], ["Readiness", "Cyber, Information Technologies, and Innovation"])
        self.assertEqual((armed["website"], armed["url"], armed["fetched_at"], armed["kind"]),
                         ("https://armedservices.house.gov", HOUSE_URL, HOUSE_FETCHED, "Standing"))
        self.assertIsNone(self.committees[2]["website"])
        # The committed fixture itself reads, and is the Clerk's list, not a sample.
        real = load_house_committees(Path(__file__).resolve().parent / "fixtures" / "directories" / "house" / "committees.xlsx")
        self.assertGreaterEqual(len(real), 20)
        self.assertIn("Committee on Agriculture", [c["name"] for c in real])
        self.assertTrue(all(c["url"].startswith("https://clerk.house.gov/") and c["fetched_at"] for c in real))
        # No meta sidecar: no date and no URL, so nothing is returned rather than an undated claim.
        undated = self.tmp / "undated.xlsx"
        write_house_xlsx(undated, meta=False)
        self.assertEqual(load_house_committees(undated), [])
        self.assertEqual(load_house_committees(self.tmp / "missing.xlsx"), [])

    def test_the_keys_fold_the_house_s_artifacts_onto_the_clerk_s_names(self) -> None:
        for graph, clerk in (
            ("House Committee on Armed Services", "Committee on Armed Services"),
            ("House Committee on Judiciary", "Committee on the Judiciary"),
            ("House Committee on Permanent Select Committee on Intelligence", "Permanent Select Committee on Intelligence"),
            ("House Committee on Veterans' Affairs", "Committee on Veterans' Affairs"),
            ("House Committee on Science, Space & Technology", "Committee on Science, Space, and Technology"),
        ):
            with self.subTest(graph=graph):
                self.assertEqual(committee_key(graph), committee_key(clerk))
        self.assertNotEqual(committee_key("House Committee on Oversight & Accountability"), committee_key("Committee on Oversight and Government Reform"))
        self.assertEqual(subcommittee_key("Subcommittee on Readiness"), subcommittee_key("Readiness"))

    def test_listed_placed_and_absent_are_each_recorded_and_applied_as_themselves(self) -> None:
        tree = json.loads(json.dumps(HOUSE_BASE))
        node_map, parent_map = index_tree(tree)
        records, report = match_house(self.committees, node_map, parent_map)
        self.assertEqual((report["committees_matched"], report["subcommittees_matched"]), (3, 1))
        self.assertEqual(report["committees_not_in_graph"], ["Committee on Oversight and Government Reform", "Joint Committee on Taxation"])
        self.assertEqual([c["name"] for c in report["graph_committees_not_in_list"]], ["House Committee on Oversight & Accountability"])
        self.assertEqual([s["name"] for s in report["subcommittees_not_in_list"]], ["Subcommittee on Cyber, Information Technology & Innovation"])
        self.assertEqual(report["subcommittees_not_in_graph"], [{"committee": "Committee on Armed Services", "subcommittee": "Cyber, Information Technologies, and Innovation"}])
        armed = records["leg-house-cmte-armed-services"]
        self.assertEqual((armed["source"], armed["status"], armed["listedName"], armed["agencyUrl"]),
                         (HOUSE_SOURCE, STATUS_LISTED, "Committee on Armed Services", "https://armedservices.house.gov"))
        readiness = records["leg-house-cmte-armed-services-sub-readiness"]
        self.assertEqual(readiness["placement"], {"status": STATUS_LISTED, "parentId": "leg-house-cmte-armed-services", "parentListedName": "Committee on Armed Services"})
        cyber = records["leg-house-cmte-armed-services-sub-cyber"]
        self.assertEqual((cyber["status"], cyber["listedUnder"], cyber["listedSubcommittees"]),
                         (STATUS_NOT_IN_LIST, "Committee on Armed Services", ["Readiness", "Cyber, Information Technologies, and Innovation"]))
        self.assertEqual(records["leg-house-cmte-oversight-accountability"]["listedUnder"], "the House Clerk's committee list")
        # Applied: the House method and placement method, the Clerk's URL, the honest negative.
        apply_evidence_to_tree(tree, {})
        stats = apply_directory_evidence(tree, records)
        nodes = index_tree(tree)[0]
        self.assertEqual((stats["listed"], stats["placements_listed"], stats["not_in_list"]), (4, 1, 2))
        readiness = nodes["leg-house-cmte-armed-services-sub-readiness"]
        self.assertEqual(readiness["verificationMethod"], HOUSE_METHOD)
        self.assertEqual(readiness["placementMethod"], HOUSE_PLACEMENT_METHOD)
        self.assertEqual(readiness["sourceUrls"], [HOUSE_URL])
        self.assertIn("house_clerk_committee_list", readiness["sourceTypes"])
        self.assertEqual(readiness["directoryListing"]["source"], HOUSE_SOURCE)
        cyber = nodes["leg-house-cmte-armed-services-sub-cyber"]
        self.assertEqual(cyber["verificationFailure"], FAILURE_NOT_IN_LIST)
        self.assertEqual(cyber["verificationFailureSource"]["source"], HOUSE_SOURCE)
        self.assertEqual(cyber["verificationFailureSource"]["url"], HOUSE_URL)
        # And withdrawn whole on the next build.
        apply_evidence_to_tree(tree, {})
        nodes = index_tree(tree)[0]
        for node_id in ("leg-house-cmte-armed-services-sub-readiness", "leg-house-cmte-armed-services-sub-cyber"):
            for field in ("verificationMethod", "placementMethod", "verificationFailure", "directoryListing"):
                self.assertNotIn(field, nodes[node_id])
        self.assertNotIn("house_clerk_committee_list", nodes["leg-house-cmte-armed-services-sub-readiness"].get("sourceTypes") or [])

    def test_the_gate_accepts_the_clerk_s_claims_and_refuses_them_without_the_clerk_s_url(self) -> None:
        base = self.tmp / "base.json"; base.write_text(json.dumps(HOUSE_BASE), encoding="utf-8")
        tree = json.loads(json.dumps(HOUSE_BASE)); node_map, parent_map = index_tree(tree)
        records, _ = match_house(self.committees, node_map, parent_map)
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
        self.assertIn("House Clerk list     : 4 committees and subcommittees listed; 1 placements from it; 2 curated names the list does not carry", out.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        for name, mutate in {
            "a negative citing a page instead of the list": lambda n: n["leg-house-cmte-armed-services-sub-cyber"]["verificationFailureSource"].__setitem__("url", "https://armedservices.house.gov/"),
            "a placement method the pipeline cannot produce": lambda n: n["leg-house-cmte-armed-services-sub-readiness"].__setitem__("placementMethod", "listed_under_committee_in_house_gov_page"),
            "the Clerk's method with the Clerk's URL removed": lambda n: n["leg-house-cmte-armed-services-sub-readiness"].__setitem__("sourceUrls", []),
        }.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph)); mutate(index_tree(corrupted)[0])
                path = self.tmp / f"{uuid.uuid4().hex}.json"; path.write_text(json.dumps(corrupted), encoding="utf-8")
                out = io.StringIO()
                with redirect_stdout(out):
                    code = gate_main(["gate", str(path)])
                self.assertEqual(code, 1, f"{name}:\n{out.getvalue()}")
