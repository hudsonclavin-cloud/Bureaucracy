"""OPM's PLUM archive as evidence for position nodes: what the archive of
the previous administration lists, said as itself and dated, one title to
one node or nothing, never across organisations, and never a negative."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree, load_base_graph
from data_pipeline.verification.positions import (
    DEFAULT_ARCHIVE_CSV,
    DEFAULT_ARCHIVE_PAGE,
    DEFAULT_EDITION,
    PLUM_METHOD,
    PLUM_PLACEMENT_METHOD,
    PLUM_SOURCE,
    apply_position_evidence,
    load_plum_archive,
    load_position_evidence,
    match_positions,
    organisation_name_keys,
    position_name_alternatives,
    read_archive_edition,
    strip_parent_qualifier,
)
from scripts import derive_position_evidence

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ID = "the-constitution-of-the-united-states"
CSV_NAME = "plum-archive-biden-administration.csv"
CSV_URL = f"https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/{CSV_NAME}"
FETCHED_AT = "2026-09-08T19:49:47Z"
HEADER = ("AgencyName,OrganizationName,PositionTitle,PositionStatus,AppointmentTypeDescription,ExpirationDate,"
          "LevelGradePay,Location,IncumbentFirstName,IncumbentLastName,PaymentPlanDescription,Tenure,IncumbentBeginDate,IncumbentVacateDate")


def P(node_id: str, name: str) -> dict:
    return {"id": node_id, "name": name, "type": "Position", "children": []}


BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                    P("doe-secretary", "Secretary, DOE"),
                    P("doe-cos", "Chief of Staff"),
                    P("doe-gc", "General Counsel"),
                    {"id": "doe-science", "name": "Office of Science (SC)", "type": "Office", "children": [
                        P("doe-science-director", "Director, Office of Science"),
                        P("doe-science-deputy", "Deputy Director / Vice Chair"),
                        P("doe-science-pd-1", "Program Director (×multiple)"),
                        P("doe-science-pd-2", "Program Director (×multiple)"),
                        P("doe-science-cio", "Chief Information Officer"),
                    ]},
                    {"id": "doe-ogc", "name": "Office of General Counsel", "type": "Office", "children": [
                        P("doe-ogc-dgc", "Deputy General Counsel"),
                    ]},
                    {"id": "doe-oig", "name": "Office of Inspector General", "type": "Office", "children": [P("doe-oig-ig", "Inspector General")]},
                ]},
                {"id": "exec-dept-treasury", "name": "Department of the Treasury", "type": "Cabinet Department", "children": [
                    P("treas-cos", "Chief of Staff"),
                    {"id": "treas-ogc", "name": "Office of General Counsel", "type": "Office", "children": [
                        P("treas-ogc-dgc", "Deputy General Counsel"),
                    ]},
                    {"id": "treas-oig", "name": "Office of Inspector General", "type": "Office", "children": [P("treas-oig-ig", "Inspector General")]},
                ]},
                {"id": "exec-dept-army", "name": "Department of the Army", "type": "Military Department", "children": [P("army-secretary", "Secretary of the Army")]},
            ]},
            {"id": "exec-independent", "name": "Independent Agencies", "type": "Division", "children": [
                {"id": "exec-ind-nasa", "name": "National Aeronautics & Space Administration (NASA)", "type": "Agency", "children": [
                    P("nasa-admin", "Administrator, NASA"),
                    P("nasa-cos", "Chief of Staff"),
                ]},
                {"id": "exec-ind-nea", "name": "National Endowment for the Arts (NEA)", "type": "Agency", "children": [
                    P("nea-head", "Director / Administrator / Chair, National Endowment for the Arts"),
                ]},
                {"id": "exec-ind-neh", "name": "National Endowment for the Humanities (NEH)", "type": "Agency", "children": [
                    P("neh-head", "Director / Chair, NEH"),
                ]},
                {"id": "exec-ind-abmc", "name": "American Battle Monuments Commission (ABMC)", "type": "Agency", "children": [
                    P("abmc-secretary", "Secretary, ABMC"),
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}


def row(agency: str, org: str, title: str, status: str = "Filled", appt: str = "PAS", level: str = "IV",
        pay: str = "EX", vacated: str = "") -> str:
    begin = "1/20/2021 0:00" if status == "Filled" else ""
    return f'{agency},{org},{title},{status},{appt},,{level},"Washington, DC",A,B,{pay},4,{begin},{vacated}'


DOE, TR, NASA, NEA, NEH, ABMC, OIG = (
    "DEPARTMENT OF ENERGY", "DEPARTMENT OF TREASURY", "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION",
    "NATIONAL ENDOWMENT FOR THE ARTS", "NATIONAL ENDOWMENT FOR THE HUMANITIES", "AMERICAN BATTLE MONUMENTS COMMISSION",
    "OFFICE OF INSPECTOR GENERAL",
)
ROWS = [
    row(DOE, DOE, "SECRETARY", "Filled", "PAS", "I"),
    row(DOE, DOE, "GENERAL COUNSEL", "Vacant", "PAS", "IV"),
    row(DOE, DOE, "SPECIAL ADVISOR", "Filled", "SC", "15", "GS"),
    row(DOE, "OFFICE OF THE SECRETARY", "CHIEF OF STAFF", "Filled", "NA", "", "ES"),
    row(DOE, "OFFICE OF SCIENCE", "DIRECTOR", "Filled", "PAS", "IV"),
    row(DOE, "OFFICE OF SCIENCE", "DIRECTOR", "Filled", "PAS", "IV", vacated="6/30/2022 0:00"),
    row(DOE, "OFFICE OF SCIENCE", "DEPUTY DIRECTOR", "Vacant", "CA", "", "ES"),
    row(DOE, "OFFICE OF SCIENCE", "PROGRAM DIRECTOR", "Filled", "CA", "", "ES"),
    row(DOE, "OFFICE OF SCIENCE", "PROGRAM DIRECTOR", "Filled", "CA", "", "ES"),
    row(DOE, "OFFICE OF GENERAL COUNSEL", "DEPUTY GENERAL COUNSEL", "Filled", "NA", "", "ES"),
    row(DOE, "OFFICE OF GENERAL COUNSEL", "(Principal) DEPUTY GENERAL COUNSEL", "Filled", "CA", "", "ES"),
    row(TR, "OFFICE OF GENERAL COUNSEL", "DEPUTY GENERAL COUNSEL", "Filled", "NA", "", "ES"),
    row(TR, TR, "CHIEF OF STAFF", "Filled", "NA", "", "ES"),
    row(TR, TR, "CHIEF OF STAFF", "Vacant", "NA", "", "ES"),
    row(NASA, NASA, "ADMINISTRATOR", "Filled", "PAS", "II"),
    row(NEA, NEA, "CHAIR", "Filled", "PAS", "III"),
    row(NEH, NEH, "CHAIR", "Filled", "PAS", "III"),
    row(NEH, NEH, "DIRECTOR", "Filled", "NA", "", "ES"),
    row(ABMC, ABMC, "THE SECRETARY", "Filled", "PA", "", "AD", vacated="3/15/2021 0:00"),
    row(OIG, OIG, "INSPECTOR GENERAL", "Filled", "PAS", "IV"),
]
ARCHIVE_PAGE = f"""<html><body><h1>PLUM Archive</h1><h2>PLUM Reporting Website Archive</h2>
<ul>
<li><a href="/about-us/open-government/plum-reporting/plum-archive/{CSV_NAME}" title="Plum Archive Biden Administration">Biden Administration</a> (January 21, 2021 - January 20, 2025)</li>
</ul></body></html>"""


def write_fixture(directory: Path, rows: list[str] | None = None) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / CSV_NAME
    csv_path.write_text("﻿" + HEADER + "\r\n" + "\r\n".join(rows or ROWS) + "\r\n", encoding="utf-8")
    csv_path.with_name(CSV_NAME + ".meta.json").write_text(json.dumps({"fetched_at": FETCHED_AT, "url": CSV_URL, "final_url": CSV_URL}), encoding="utf-8")
    page = directory / "opm_plum_archive_page.html"
    page.write_text(ARCHIVE_PAGE, encoding="utf-8")
    return csv_path, page


class NameTests(unittest.TestCase):
    def test_only_the_department_article_and_the_case_are_tolerated(self) -> None:
        self.assertEqual(organisation_name_keys("DEPARTMENT OF THE TREASURY"), {"department of the treasury", "department of treasury"})
        self.assertEqual(organisation_name_keys("Department of Energy (DOE)"), {"department of energy", "department of the energy"})
        self.assertEqual(organisation_name_keys("OFFICE OF SCIENCE"), {"office of science"})
        self.assertEqual(organisation_name_keys(""), set())

    def test_a_trailing_qualifier_is_stripped_only_when_it_is_the_parent(self) -> None:
        self.assertEqual(strip_parent_qualifier("Administrator, NASA", "National Aeronautics & Space Administration (NASA)"), ("Administrator", "NASA"))
        self.assertEqual(strip_parent_qualifier("Director, Office of Science", "Office of Science (SC)"), ("Director", "Office of Science"))
        self.assertEqual(strip_parent_qualifier("Chair, Agriculture, Nutrition, and Forestry", "Senate Committee on Agriculture, Nutrition, and Forestry"),
                         ("Chair, Agriculture, Nutrition, and Forestry", None))
        self.assertEqual(strip_parent_qualifier("Chief, Office of Policy & Strategy", "U.S. Citizenship & Immigration Services (USCIS)"),
                         ("Chief, Office of Policy & Strategy", None))

    def test_alternatives_split_on_the_slash_and_drop_a_leading_the(self) -> None:
        self.assertEqual(position_name_alternatives("Director / Administrator / Chair, AmeriCorps", "AmeriCorps"), ["director", "administrator", "chair"])
        self.assertEqual(position_name_alternatives("AF/A1 (Manpower & Personnel)", "Air Force"), ["af a1"])
        self.assertEqual(position_name_alternatives("The Secretary", "ABMC"), ["secretary"])
        self.assertEqual(position_name_alternatives("Program Director (×multiple)", "Office"), ["program director"])


class ArchiveReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plum-{uuid.uuid4().hex}"
        self.csv, self.page = write_fixture(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_archive_is_read_with_its_meta_and_grouped_by_agency_and_organisation(self) -> None:
        archive = load_plum_archive(self.csv)
        self.assertEqual(archive["url"], CSV_URL)
        self.assertEqual(archive["fetched_at"], FETCHED_AT)
        self.assertEqual(len(archive["rows"]), len(ROWS))
        self.assertIn((DOE, "OFFICE OF SCIENCE"), archive["groups"])
        first = archive["rows"][0]
        self.assertEqual((first["agency"], first["title"], first["status"], first["appointmentType"], first["payPlan"], first["level"], first["vacated"]),
                         (DOE, "SECRETARY", "Filled", "PAS", "EX", "I", False))
        self.assertTrue(archive["rows"][5]["vacated"])

    def test_without_a_meta_file_no_record_can_carry_a_date(self) -> None:
        self.csv.with_name(CSV_NAME + ".meta.json").unlink()
        archive = load_plum_archive(self.csv)
        self.assertIsNone(archive["fetched_at"])
        self.assertIsNone(archive["url"])

    def test_the_edition_is_what_the_archive_page_prints_for_the_file(self) -> None:
        edition = read_archive_edition(self.page, CSV_NAME)
        self.assertEqual(edition["edition"], "Biden Administration (January 21, 2021 - January 20, 2025)")
        self.assertEqual(edition["period"], "January 21, 2021 - January 20, 2025")
        self.assertEqual((edition["periodStart"], edition["periodEnd"]), ("2021-01-21", "2025-01-20"))
        self.assertIsNone(read_archive_edition(self.tmp / "missing.html", CSV_NAME))
        self.assertIsNone(read_archive_edition(self.page, "some-other-file.csv"))


class MatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plum-{uuid.uuid4().hex}"
        self.csv, self.page = write_fixture(self.tmp)
        self.node_map, self.parent_map = index_tree(BASE)
        self.archive = load_plum_archive(self.csv)
        self.edition = read_archive_edition(self.page, CSV_NAME)
        self.records, self.report = match_positions(self.archive, self.node_map, self.parent_map, root_id=ROOT_ID, edition=self.edition)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_agencies_match_by_canonical_name_with_the_department_tolerance(self) -> None:
        self.assertEqual(self.report["agencies"], 7)
        self.assertEqual(self.report["agencies_matched"], 6)
        # Two curated "Office of Inspector General" nodes answer to the one name: nothing.
        self.assertEqual([a["name"] for a in self.report["agencies_ambiguous"]], [OIG])
        self.assertEqual(self.report["agencies_unmatched"], [])
        self.assertNotIn("doe-oig-ig", self.records)
        self.assertNotIn("treas-oig-ig", self.records)

    def test_organisations_are_scoped_beneath_their_agency(self) -> None:
        # The same-named Office of General Counsel of two departments stay apart.
        self.assertEqual(self.records["treas-ogc-dgc"]["listedAgency"], TR)
        self.assertEqual(self.records["treas-ogc-dgc"]["placement"]["parentId"], "treas-ogc")
        # Nine of the archive's eleven (agency, organisation) groups resolve to a
        # node: the six whose organisation is the agency itself (DOE, TR, NASA,
        # NEA, NEH, ABMC), and three offices matched beneath their own agency —
        # DOE's Office of Science, DOE's Office of General Counsel and Treasury's
        # Office of General Counsel, the last two same-named and kept apart by the
        # scoping this test is about. The other two groups are the one unmatched
        # organisation and the one under an ambiguous agency, asserted below;
        # 9 + 1 + 1 accounts for all eleven.
        self.assertEqual(self.report["organizations_matched"], 9)
        self.assertEqual(self.report["organizations_of_agency"], 6)
        self.assertEqual([o["organization"] for o in self.report["organizations_unmatched"]], ["OFFICE OF THE SECRETARY"])
        self.assertEqual(self.report["organizations_under_unmatched_agency"], 1)

    def test_a_title_is_never_matched_across_organisations(self) -> None:
        # The archive files DOE's Chief of Staff under OFFICE OF THE SECRETARY,
        # which the graph lacks; the department's own node is not offered it.
        self.assertNotIn("doe-cos", self.records)
        self.assertIn("doe-gc", self.records)
        self.assertIn("doe-secretary", self.records)

    def test_the_parent_qualifier_and_the_acronym_are_stripped(self) -> None:
        self.assertEqual(self.records["nasa-admin"]["listedTitle"], "ADMINISTRATOR")
        self.assertEqual(self.records["doe-secretary"]["listedTitle"], "SECRETARY")
        self.assertEqual(self.records["doe-science-director"]["listedTitle"], "DIRECTOR")
        self.assertEqual(self.records["abmc-secretary"]["listedTitle"], "THE SECRETARY")

    def test_slash_alternatives_accept_any_one_listed_title_and_refuse_two(self) -> None:
        self.assertEqual(self.records["nea-head"]["listedTitle"], "CHAIR")
        self.assertEqual(self.records["nea-head"]["matchedAlternative"], "chair")
        self.assertEqual(self.records["doe-science-deputy"]["listedTitle"], "DEPUTY DIRECTOR")
        self.assertNotIn("neh-head", self.records)
        self.assertEqual([a["id"] for a in self.report["positions_ambiguous_alternatives"]], ["neh-head"])

    def test_a_shared_title_and_an_archive_spelling_collision_match_nothing(self) -> None:
        self.assertNotIn("doe-science-pd-1", self.records)
        self.assertNotIn("doe-science-pd-2", self.records)
        self.assertEqual(sorted(s["id"] for s in self.report["positions_shared_title"]), ["doe-science-pd-1", "doe-science-pd-2"])
        self.assertNotIn("doe-ogc-dgc", self.records)
        self.assertEqual(self.report["positions_title_ambiguous_in_archive"][0]["id"], "doe-ogc-dgc")

    def test_no_negative_record_is_written_for_a_position_the_archive_lacks(self) -> None:
        self.assertNotIn("doe-science-cio", self.records)
        self.assertNotIn("nasa-cos", self.records)
        self.assertNotIn("army-secretary", self.records)
        self.assertTrue(all(r.get("listedTitle") for r in self.records.values()))
        self.assertEqual(self.report["positions_unmatched"], 3)
        self.assertEqual(self.report["positions_in_graph"], 19)
        self.assertEqual(self.report["positions_under_matched_organization"], 16)
        # Nine, each of them asserted by name elsewhere in this file: doe-secretary,
        # doe-gc, doe-science-director, doe-science-deputy, treas-cos, treas-ogc-dgc,
        # nasa-admin, nea-head and abmc-secretary — the ninth being abmc-secretary,
        # "Secretary, ABMC" matched to the archive's "THE SECRETARY" once the
        # parent's acronym is stripped and the key drops the article, a real match
        # whose only listing is a past incumbency (see the test below). The sixteen
        # positions under a matched organisation are exactly 9 matched + 3 the
        # archive lacks + 2 sharing a title + 1 whose alternatives answer to two
        # listed titles + 1 whose title two archive spellings collapse onto.
        self.assertEqual(self.report["positions_matched"], 9)

    def test_a_record_says_what_the_archive_says_and_names_the_archive(self) -> None:
        record = self.records["doe-science-director"]
        self.assertEqual(record["source"], PLUM_SOURCE)
        self.assertEqual(record["edition"], "Biden Administration (January 21, 2021 - January 20, 2025)")
        self.assertEqual(record["period"], "January 21, 2021 - January 20, 2025")
        self.assertEqual((record["listedAgency"], record["listedOrganization"]), (DOE, "OFFICE OF SCIENCE"))
        self.assertEqual((record["status"], record["appointmentType"], record["payPlan"], record["level"]), ("Filled", "PAS", "EX", "IV"))
        self.assertEqual((record["incumbencies"], record["standing"]), (2, 1))
        self.assertEqual(record["url"], CSV_URL)
        self.assertEqual(record["checkedAt"], FETCHED_AT)
        self.assertEqual(record["placement"], {"status": "listed", "parentId": "doe-science", "parentListedName": "OFFICE OF SCIENCE"})

    def test_disagreeing_standing_rows_publish_null_with_the_counts(self) -> None:
        record = self.records["treas-cos"]
        self.assertIsNone(record["status"])
        self.assertEqual(record["statusCounts"], {"Filled": 1, "Vacant": 1})
        self.assertEqual(record["appointmentType"], "NA")
        self.assertEqual(record["standing"], 2)

    def test_a_title_with_only_past_incumbencies_has_no_status(self) -> None:
        record = self.records["abmc-secretary"]
        self.assertIsNone(record["status"])
        self.assertEqual((record["incumbencies"], record["standing"], record["valuesFrom"]), (1, 0, "past_incumbencies"))
        self.assertEqual(record["appointmentType"], "PA")

    def test_without_the_archive_page_the_edition_claims_no_dates(self) -> None:
        records, report = match_positions(self.archive, self.node_map, self.parent_map, root_id=ROOT_ID, edition=None)
        self.assertEqual(report["edition"], DEFAULT_EDITION)
        self.assertEqual(records["nasa-admin"]["edition"], DEFAULT_EDITION)
        self.assertNotIn("period", records["nasa-admin"])


class ApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plum-{uuid.uuid4().hex}"
        self.csv, self.page = write_fixture(self.tmp)
        node_map, parent_map = index_tree(BASE)
        self.records, _ = match_positions(load_plum_archive(self.csv), node_map, parent_map, root_id=ROOT_ID,
                                          edition=read_archive_edition(self.page, CSV_NAME))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_listing_is_stamped_beside_other_claims_never_over_them(self) -> None:
        root = json.loads(json.dumps(BASE))
        node_map, _ = index_tree(root)
        node_map["nasa-admin"]["verificationMethod"] = "name_labelled_on_own_official_page"
        node_map["nasa-admin"]["sourceUrls"] = ["https://www.nasa.gov/about"]
        node_map["nasa-admin"]["lastVerified"] = "2026-09-01T00:00:00Z"
        stats = apply_position_evidence(root, self.records)
        self.assertEqual(stats["listed"], len(self.records))
        self.assertEqual(stats["placements_listed"], len(self.records))
        nasa = node_map["nasa-admin"]
        self.assertEqual(nasa["verificationMethod"], "name_labelled_on_own_official_page")
        self.assertEqual(nasa["sourceUrls"], ["https://www.nasa.gov/about", CSV_URL])
        self.assertEqual(nasa["evidenceUrls"], [CSV_URL])
        self.assertIn("opm_plum_archive", nasa["sourceTypes"])
        self.assertEqual(nasa["lastVerified"], FETCHED_AT)
        listing = nasa["positionListing"]
        self.assertEqual(listing["edition"], "Biden Administration (January 21, 2021 - January 20, 2025)")
        self.assertEqual((listing["listedTitle"], listing["status"], listing["appointmentType"], listing["payPlan"], listing["level"]), ("ADMINISTRATOR", "Filled", "PAS", "EX", "II"))
        self.assertEqual(listing["checkedAt"], FETCHED_AT)
        doe = node_map["doe-gc"]
        self.assertEqual(doe["verificationMethod"], PLUM_METHOD)
        self.assertEqual(doe["placementMethod"], PLUM_PLACEMENT_METHOD)
        # placementMatchedText is the text that names the node in the source —
        # the archive's own title — the way evidence.py stamps the label found
        # on the parent's page; the organisation the archive files it under is
        # in the listing itself.
        self.assertEqual((doe["placementVerified"], doe["placementParentId"], doe["placementMatchedText"]), (True, "exec-dept-doe", "GENERAL COUNSEL"))
        self.assertEqual(doe["positionListing"]["listedOrganization"], DOE)
        self.assertEqual(node_map["treas-cos"]["positionListing"]["statusCounts"], {"Filled": 1, "Vacant": 1})
        self.assertEqual(node_map["treas-cos"]["sourceCount"], 1)

    def test_a_renamed_or_reparented_node_inherits_nothing(self) -> None:
        root = json.loads(json.dumps(BASE))
        node_map, _ = index_tree(root)
        node_map["nasa-admin"]["name"] = "Deputy Administrator, NASA"
        moved = node_map["exec-ind-nea"]["children"].pop(0)
        node_map["exec-ind-neh"]["children"].append(moved)
        stats = apply_position_evidence(root, self.records)
        # One: the rename. The move is the placement's business — nea-head's own
        # name did not change, and judging its qualifier against the new parent
        # would charge a re-parenting to the name check, and only for names that
        # happen to carry a qualifier.
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("positionListing", node_map["nasa-admin"])
        self.assertEqual(stats["placements_stale_parent"], 1)
        self.assertIn("positionListing", node_map["nea-head"])
        self.assertNotIn("placementVerified", node_map["nea-head"])

    def test_a_record_without_a_date_or_url_applies_nothing(self) -> None:
        root = json.loads(json.dumps(BASE))
        node_map, _ = index_tree(root)
        undated = {k: dict(v, checkedAt=None) for k, v in self.records.items()}
        stats = apply_position_evidence(root, undated)
        self.assertEqual(stats["undated"], len(self.records))
        self.assertNotIn("positionListing", node_map["nasa-admin"])


class ScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plum-{uuid.uuid4().hex}"
        self.csv, self.page = write_fixture(self.tmp)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.out = self.tmp / "position_evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra: str) -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = derive_position_evidence.main(["derive_position_evidence.py", "--base-graph", str(self.base), "--archive", str(self.csv),
                                                  "--archive-page", str(self.page), "--out", str(self.out), *extra])
        self.assertEqual(code, 0)
        return buffer.getvalue()

    def test_dry_run_reports_and_writes_nothing(self) -> None:
        output = self._run("--dry-run")
        self.assertFalse(self.out.exists())
        self.assertIn("Biden Administration (January 21, 2021 - January 20, 2025)", output)
        self.assertIn("No negative records", output)
        self.assertIn("agencies matched 6", output)

    def test_the_store_names_the_archive_its_edition_and_its_fetch(self) -> None:
        self._run()
        store = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(set(store), {"_note", "source", "report", "nodes"})
        self.assertIn("PREVIOUS administration", store["_note"])
        self.assertIn("June 15, 2026", store["_note"])
        self.assertEqual(store["source"]["url"], CSV_URL)
        self.assertEqual(store["source"]["fetched_at"], FETCHED_AT)
        self.assertEqual(store["source"]["edition"], "Biden Administration (January 21, 2021 - January 20, 2025)")
        self.assertEqual(store["report"]["positions_matched"], 9)
        self.assertEqual(len(store["nodes"]), 9)
        self.assertEqual(load_position_evidence(self.out)["doe-gc"]["listedTitle"], "GENERAL COUNSEL")
        self.assertEqual(load_position_evidence(self.tmp / "missing.json"), {})


class RealFixtureTests(unittest.TestCase):
    """Pinned against the committed archive and the curated graph; a change
    in either moves these numbers, and the report must be re-read."""

    @classmethod
    def setUpClass(cls) -> None:
        root = load_base_graph(PROJECT_ROOT / "data" / "federal_gov_complete_1.json")
        node_map, parent_map = index_tree(root)
        cls.archive = load_plum_archive(DEFAULT_ARCHIVE_CSV)
        cls.edition = read_archive_edition(DEFAULT_ARCHIVE_PAGE, DEFAULT_ARCHIVE_CSV.name)
        cls.records, cls.report = match_positions(cls.archive, node_map, parent_map, root_id=str(root["id"]), edition=cls.edition)

    def test_the_archive_is_the_previous_administrations_and_says_so(self) -> None:
        self.assertEqual(self.edition["edition"], "Biden Administration (January 21, 2021 - January 20, 2025)")
        self.assertEqual(self.archive["fetched_at"], "2026-09-08T19:49:47Z")
        self.assertEqual(self.archive["url"], CSV_URL)
        self.assertTrue(all(r["edition"] == self.edition["edition"] and r["checkedAt"] == "2026-09-08T19:49:47Z" for r in self.records.values()))

    def test_the_archive_counts(self) -> None:
        r = self.report
        self.assertEqual((r["rows"], r["agencies"], r["organizations"], r["organization_names"], r["titles"]), (21312, 169, 1477, 1259, 7415))
        self.assertEqual(r["appointment_types"], {"CA": 7468, "SC": 5612, "NA": 3152, "PAS": 2167, "XS": 1807, "PA": 809, "TA": 229, "CG": 41, "DA": 15, "EA": 9, "SS": 3})
        self.assertEqual(r["position_status"], {"Filled": 18475, "Vacant": 2837})

    def test_the_matching_counts(self) -> None:
        r = self.report
        self.assertEqual((r["agencies_matched"], len(r["agencies_unmatched"]), len(r["agencies_ambiguous"])), (59, 110, 0))
        self.assertEqual((r["organizations_matched"], r["organizations_of_agency"], len(r["organizations_unmatched"]), len(r["organizations_ambiguous"]), r["organizations_under_unmatched_agency"]),
                         (154, 27, 894, 0, 429))
        self.assertEqual((r["positions_in_graph"], r["positions_under_matched_agency_node"], r["positions_under_matched_organization"]), (4382, 584, 1084))
        self.assertEqual((r["positions_matched"], r["positions_unmatched"], len(r["positions_shared_title"]), len(r["positions_ambiguous_alternatives"]), len(r["positions_title_ambiguous_in_archive"])),
                         (91, 991, 0, 0, 2))
        self.assertEqual(len(self.records), 91)
        self.assertEqual(self.records["exec-dept-dhs-cisa-chief-of-staff"]["listedTitle"], "CHIEF OF STAFF")
        self.assertEqual(self.records["exec-dept-dhs-cisa-chief-of-staff"]["placement"]["parentId"], "exec-dept-dhs-cisa")


if __name__ == "__main__":
    unittest.main()
