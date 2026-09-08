"""Headcounts from OPM's FedScope employment table: what the table says,
said as itself, matched to the curated organisations by name and nothing
looser — and compared with the uncited figures the cost cascade weights by."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification.headcounts import (
    COVERAGE_STATEMENT,
    DEFAULT_FEDSCOPE_ZIP,
    LEVEL_AGENCY,
    LEVEL_SUBAGENCY,
    agency_totals,
    compare_with_curated,
    headcount_name_keys,
    listed_name_still_names,
    load_fedscope_agency_subagency,
    load_fedscope_meta,
    load_headcount_evidence,
    match_fedscope,
    period_label,
)
from scripts import derive_headcount_evidence

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-house-ig", "name": "Office of the Inspector General", "type": "Office", "children": []},
            {"id": "leg-support-gpo", "name": "Government Publishing Office (GPO)", "type": "Agency", "employees": "~1,700", "children": []},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-treasury", "name": "Department of the Treasury", "type": "Cabinet Department", "employees": "~100,000", "children": [
                    {"id": "treasury-irs", "name": "Internal Revenue Service (IRS)", "type": "Bureau", "employees": "~74,000", "children": []},
                    {"id": "treasury-oig", "name": "Office of the Inspector General", "type": "Office", "children": []},
                    {"id": "treasury-secretary", "name": "Secretary of the Treasury", "type": "Position", "children": []},
                ]},
                {"id": "exec-dept-doi", "name": "Department of the Interior (DOI)", "type": "Cabinet Department", "employees": "~67,000", "children": [
                    {"id": "doi-oig", "name": "Office of the Inspector General", "type": "Office", "children": []},
                    {"id": "doi-nps", "name": "National Park Service", "type": "Bureau", "children": []},
                ]},
                {"id": "exec-dept-defense", "name": "Department of Defense (DoD)", "type": "Cabinet Department", "employees": "~750,000 civilian + 1.3M active military", "children": [
                    {"id": "exec-dept-defense-army", "name": "Department of the Army", "type": "Military Department", "employees": "~450,000 active duty", "children": []},
                    {"id": "dod-dla", "name": "Defense Logistics Agency", "type": "Defense Agency", "children": []},
                ]},
                {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "employees": "~14,000 federal + 95,000 contractor", "children": []},
            ]},
            {"id": "exec-independent", "name": "Independent Agencies", "type": "Division", "children": [
                {"id": "exec-ind-ssa", "name": "Social Security Administration (SSA)", "type": "Independent Agency", "employees": "~60,000", "children": []},
                {"id": "exec-ind-nara", "name": "National Archives and Records Administration (NARA)", "type": "Independent Agency", "employees": "~3,000", "children": []},
                {"id": "exec-ind-nasa", "name": "National Aeronautics & Space Administration (NASA)", "type": "Agency", "employees": "~18,000", "children": [
                    {"id": "nasa-goddard", "name": "Goddard Space Flight Center (GSFC)", "type": "NASA Center", "children": []},
                ]},
                {"id": "exec-regulatory-ferc", "name": "Federal Energy Regulatory Commission (FERC)", "type": "Independent Regulatory Commission", "children": []},
                {"id": "exec-ind-test", "name": "Test Agency", "type": "Independent Agency", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "employees": "~33,000 (federal judiciary)", "children": [
            {"id": "jud-tax", "name": "U.S. Tax Court", "type": "Specialized Court", "children": []},
        ]},
    ],
}
HEADER = "DATECODE\tAGY\tAGYT\tAGYSUB\tAGYSUBT\tEMPCOUNT\tAVGSAL\tAVGLOS"
ROWS_202503 = [
    ("TR", "DEPARTMENT OF TREASURY", "TR93", "INTERNAL REVENUE SERVICE", 101312),
    ("TR", "DEPARTMENT OF TREASURY", "TR40", "OFFICE OF THE INSPECTOR GENERAL", 150),
    ("TR", "DEPARTMENT OF TREASURY", "TR10", "BUREAU OF THE FISCAL SERVICE", 3000),
    ("TR", "DEPARTMENT OF TREASURY", "TR01", "SECRETARY OF THE TREASURY", 50),
    ("IN", "DEPARTMENT OF INTERIOR", "IN07", "OFFICE OF THE INSPECTOR GENERAL", 295),
    ("IN", "DEPARTMENT OF INTERIOR", "IN10", "NATIONAL PARK SERVICE", 17980),
    ("DD", "DEPARTMENT OF DEFENSE", "DD10", "DEFENSE LOGISTICS AGENCY", 23896),
    ("DD", "DEPARTMENT OF DEFENSE", "DD21", "WASHINGTON HEADQUARTERS SERVICES", 1653),
    ("DD", "DEPARTMENT OF DEFENSE", "DD06", "OFFICE OF THE INSPECTOR GENERAL", 1832),
    ("AR", "DEPARTMENT OF THE ARMY", "ARCE", "U.S. ARMY CORPS OF ENGINEERS", 38650),
    ("DN", "DEPARTMENT OF ENERGY", "DN00", "DEPARTMENT OF ENERGY", 15891),
    ("DN", "DEPARTMENT OF ENERGY", "DNFE", "FEDERAL ENERGY REGULATORY COMMISSION", 1581),
    ("SZ", "SOCIAL SECURITY ADMINISTRATION", "SZ00", "SOCIAL SECURITY ADMINISTRATION", 56263),
    ("NQ", "NAT ARCHIVES AND RECORDS ADMINISTRATION", "NQ00", "NATIONAL ARCHIVES AND RECORDS ADMINISTRATION", 2810),
    ("NN", "NAT AERONAUTICS AND SPACE ADMINISTRATION", "NN51", "GODDARD SPACE FLIGHT CENTER", 3042),
    ("NN", "NAT AERONAUTICS AND SPACE ADMINISTRATION", "NN06", "OFFICE OF THE INSPECTOR GENERAL", 200),
    ("XX", "TEST AGENCY", "XX00", "TEST AGENCY", 300),
    ("XX", "TEST AGENCY", "XX01", "UNIT ONE", 100),
    ("XX", "TEST AGENCY", "XX02", "UNIT TWO", 200),
    ("JL", "JUDICIAL BRANCH", "JL03", "U.S. TAX COURT", 165),
    ("LP", "GOVERNMENT PRINTING OFFICE", "LP00", "GOVERNMENT PRINTING OFFICE", 1649),
    ("10_OR_LESS", "10_OR_LESS", "10_OR_LESS", "10_OR_LESS", 127),
]
ROWS_202409 = [
    ("TR", "DEPARTMENT OF TREASURY", "TR93", "INTERNAL REVENUE SERVICE", 99001),
    ("TR", "DEPARTMENT OF TREASURY", "TR40", "OFFICE OF THE INSPECTOR GENERAL", 140),
    ("DD", "DEPARTMENT OF DEFENSE", "DD10", "DEFENSE LOGISTICS AGENCY", 24000),
    ("DD", "DEPARTMENT OF DEFENSE", "DD21", "WASHINGTON HEADQUARTERS SERVICES", 1600),
    ("DD", "DEPARTMENT OF DEFENSE", "DD06", "OFFICE OF THE INSPECTOR GENERAL", 1800),
    ("SZ", "SOCIAL SECURITY ADMINISTRATION", "SZ00", "SOCIAL SECURITY ADMINISTRATION", 57000),
    ("NQ", "NAT ARCHIVES AND RECORDS ADMIN", "NQ00", "NATIONAL ARCHIVES AND RECORDS ADMINISTRATION", 2900),
    ("JL", "JUDICIAL BRANCH", "JL03", "U.S. TAX COURT", 160),
]
META = {"fetched_at": "2026-09-08T19:50:51Z", "url": "https://www.opm.gov/data/datasets/Files/753/test.zip", "sha256": "abc", "file": "summary.zip"}


def write_fixture(directory: Path, rows_2503=ROWS_202503, rows_2409=ROWS_202409, *, member="Status Employment by Agency and SubAgency_202503_and_202409.txt") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    lines = [HEADER]
    for datecode, rows in (("202503", rows_2503), ("202409", rows_2409)):
        for agy, agyt, sub, subt, count in rows:
            lines.append(f"{datecode}\t{agy}\t{agyt}\t{sub}\t{subt}\t{count}\t100000\t10.0")
    path = directory / "summary.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "﻿" + "\n".join(lines) + "\n")
        archive.writestr("FedScope Employment.pdf", b"%PDF-1.6 not read")
    (directory / "summary.zip.meta.json").write_text(json.dumps(META), encoding="utf-8")
    return path


class SyntheticFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"headcounts-{uuid.uuid4().hex}"
        self.zip = write_fixture(self.tmp)
        self.periods = load_fedscope_agency_subagency(self.zip)
        self.tree = json.loads(json.dumps(BASE))
        self.node_map, self.parent_map = index_tree(self.tree)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _match(self, **kwargs):
        meta = load_fedscope_meta(self.zip)
        return match_fedscope(self.periods, self.node_map, self.parent_map, root_id=ROOT_ID, url=meta["url"], fetched_at=meta["fetched_at"], file="summary.zip", **kwargs)

    # -- parser --------------------------------------------------------------

    def test_the_parser_reads_the_zip_in_place_and_keys_rows_by_period(self) -> None:
        self.assertEqual(sorted(self.periods), ["2024-09", "2025-03"])
        self.assertEqual(len(self.periods["2025-03"]), len(ROWS_202503))
        irs = next(r for r in self.periods["2025-03"] if r["subagency_code"] == "TR93")
        self.assertEqual(irs, {"datecode": "202503", "agency_code": "TR", "agency_name": "DEPARTMENT OF TREASURY",
                               "subagency_code": "TR93", "subagency_name": "INTERNAL REVENUE SERVICE", "employees": 101312})
        self.assertIsInstance(irs["employees"], int)
        self.assertEqual(period_label("202409"), "2024-09")
        meta = load_fedscope_meta(self.zip)
        self.assertEqual((meta["url"], meta["fetched_at"]), (META["url"], META["fetched_at"]))

    def test_a_count_that_is_not_a_number_is_an_error_never_a_zero(self) -> None:
        bad = write_fixture(self.tmp / "bad", rows_2503=[("TR", "DEPARTMENT OF TREASURY", "TR93", "INTERNAL REVENUE SERVICE", "REDACTED")], rows_2409=[])
        with self.assertRaises(ValueError):
            load_fedscope_agency_subagency(bad)

    def test_agency_totals_are_the_sum_of_sub_agency_rows_and_a_total_row_is_not_counted_twice(self) -> None:
        totals = agency_totals(self.periods["2025-03"])
        self.assertEqual(totals["TR"]["employees"], 101312 + 150 + 3000 + 50)
        self.assertEqual(totals["TR"]["rows"], 4)
        self.assertIsNone(totals["TR"]["total_row"])
        self.assertIsNone(totals["TR"]["self_named_row"])
        # A row named as the agency, equal to the sum of the others: a total row, so the total is 300, not 600.
        self.assertEqual(totals["XX"]["employees"], 300)
        self.assertEqual(totals["XX"]["total_row"]["subagencyCode"], "XX00")
        self.assertEqual([c["subagencyCode"] for c in totals["XX"]["components"]], ["XX02", "XX01"])
        # A row named as the agency that is not a total is the agency's own element, and is summed.
        self.assertEqual(totals["DN"]["employees"], 15891 + 1581)
        self.assertEqual(totals["DN"]["self_named_row"]["subagencyCode"], "DN00")
        self.assertIsNone(totals["DN"]["total_row"])
        # A single self-named row is the agency.
        self.assertEqual((totals["SZ"]["employees"], totals["SZ"]["rows"]), (56263, 1))

    # -- name keys ------------------------------------------------------------

    def test_department_of_x_and_department_of_the_x_are_one_key_and_nothing_else_is_rewritten(self) -> None:
        self.assertIn("department of the treasury", headcount_name_keys("DEPARTMENT OF TREASURY"))
        self.assertIn("department of interior", headcount_name_keys("Department of the Interior (DOI)"))
        # The table truncates a leading NATIONAL to fit its column; expanding
        # it undoes the file's own abbreviation rather than guessing at a unit,
        # and it matters because an agency that fails to match leaves its rows
        # with no scope — which is how three NASA centres were once stamped on
        # nodes with nothing tying them to NASA.
        self.assertEqual(headcount_name_keys("NAT ARCHIVES AND RECORDS ADMINISTRATION"),
                         {"nat archives and records administration", "national archives and records administration"})
        self.assertEqual(headcount_name_keys("Natural Resources Council"), {"natural resources council"}, "only a whole NAT token")
        self.assertEqual(headcount_name_keys(""), set())
        self.assertTrue(listed_name_still_names("Department of the Treasury", "DEPARTMENT OF TREASURY"))
        self.assertFalse(listed_name_still_names("Office of Basic Research", "INTERNAL REVENUE SERVICE"))

    # -- matching -------------------------------------------------------------

    def test_agencies_and_sub_agencies_match_one_name_to_one_node_with_the_table_s_own_words(self) -> None:
        records, report = self._match()
        self.assertEqual(report["period"], "2025-03")
        self.assertEqual(report["previous_period"], "2024-09")
        self.assertEqual(report["agency_total_rows_found"], 1)
        self.assertEqual(report["suppressed_rows"], [{"listedName": "10_OR_LESS", "employees": 127}])
        treasury = records["exec-dept-treasury"]
        self.assertEqual(treasury["level"], LEVEL_AGENCY)
        self.assertEqual((treasury["listedName"], treasury["agencyCode"], treasury["subagencyCode"]), ("DEPARTMENT OF TREASURY", "TR", None))
        self.assertEqual(treasury["employees"], 104512)
        self.assertEqual(treasury["previous"], {"period": "2024-09", "employees": 99141})
        self.assertEqual(treasury["coverage"], COVERAGE_STATEMENT)
        self.assertEqual((treasury["url"], treasury["checkedAt"], treasury["source"]), (META["url"], META["fetched_at"], "opm_fedscope_employment"))
        irs = records["treasury-irs"]
        self.assertEqual(irs["level"], LEVEL_SUBAGENCY)
        self.assertEqual((irs["listedName"], irs["subagencyCode"], irs["employees"], irs["agencyMatched"]), ("INTERNAL REVENUE SERVICE", "TR93", 101312, "exec-dept-treasury"))
        self.assertEqual(irs["previous"], {"period": "2024-09", "employees": 99001})
        self.assertEqual(irs["agencyEmployees"], 104512)
        self.assertNotIn("treasury-secretary", records, "a position is never an organisation")
        self.assertIn({"agencyCode": "TR", "agencyListedName": "DEPARTMENT OF TREASURY", "agencyMatched": "exec-dept-treasury",
                       "subagencyCode": "TR10", "listedName": "BUREAU OF THE FISCAL SERVICE", "employees": 3000}, report["unmatched_subagencies"])
        self.assertEqual(report["largest_unmatched"][0]["listedName"], "U.S. ARMY CORPS OF ENGINEERS")

    def test_a_sub_agency_is_scoped_beneath_its_agency_s_node(self) -> None:
        records, report = self._match()
        # Three curated "Office of the Inspector General": each department's row reaches its own.
        self.assertEqual((records["treasury-oig"]["employees"], records["treasury-oig"]["subagencyCode"]), (150, "TR40"))
        self.assertEqual((records["doi-oig"]["employees"], records["doi-oig"]["subagencyCode"]), (295, "IN07"))
        self.assertNotIn("leg-house-ig", records)
        # Defense's row has no OIG beneath Defense here: the name exists elsewhere, and that is reported, not resolved.
        defense_oig = next(s for s in report["scoped_out"] if s["subagencyCode"] == "DD06")
        self.assertEqual(defense_oig["nodesElsewhere"], ["doi-oig", "leg-house-ig", "treasury-oig"])
        self.assertEqual(defense_oig["agencyNode"], "exec-dept-defense")
        # FERC is under Energy in the table and an independent commission in the graph: filed elsewhere.
        ferc = next(s for s in report["scoped_out"] if s["subagencyCode"] == "DNFE")
        self.assertEqual(ferc["nodesElsewhere"], ["exec-regulatory-ferc"])
        self.assertNotIn("exec-regulatory-ferc", records)

    def test_a_row_whose_agency_matched_nothing_is_refused_however_unique_its_name(self) -> None:
        records, report = self._match()
        # NASA's abbreviated agency name now matches, so its rows are scoped and
        # its OIG row is refused for being filed under an agency the graph puts
        # those nodes outside of.
        self.assertEqual(records["exec-ind-nasa"]["level"], LEVEL_AGENCY)
        self.assertIn("NAT AERONAUTICS AND SPACE ADMINISTRATION", [f["agencyListedName"] for f in report["scoped_out"]])
        # And where an agency really does match nothing, a unique sub-agency
        # name is no longer enough: nothing verifies the node is the unit the
        # row describes, so it is refused rather than stamped.
        self.assertIn("unscoped_refused", report)
        # An unscoped name one node has does match, and a row with no earlier snapshot has no previous.
        goddard = records["nasa-goddard"]
        self.assertEqual((goddard["employees"], goddard["agencyMatched"], goddard["previous"]), (3042, "exec-ind-nasa", None))

    def test_a_sub_agency_that_is_the_agency_itself_is_carried_once(self) -> None:
        records, report = self._match()
        ssa = records["exec-ind-ssa"]
        self.assertEqual((ssa["level"], ssa["employees"], ssa["subagencyRows"]), (LEVEL_AGENCY, 56263, 1))
        self.assertEqual(sum(1 for r in records.values() if r["agencyCode"] == "SZ"), 1)
        self.assertIn({"agencyCode": "SZ", "subagencyCode": "SZ00", "listedName": "SOCIAL SECURITY ADMINISTRATION", "employees": 56263,
                       "carriedBy": "exec-ind-ssa", "agencyRows": 1}, report["self_named_rows"])
        # Energy's own element beside FERC: the agency record carries the total and names the element.
        doe = records["exec-dept-doe"]
        self.assertEqual(doe["employees"], 17472)
        self.assertEqual(doe["selfNamedRow"], {"subagencyCode": "DN00", "listedName": "DEPARTMENT OF ENERGY", "employees": 15891})
        # The table abbreviates NARA's agency name; expanding the truncation
        # matches it, so it is now an agency record whose one self-named row
        # the record carries, rather than a sub-agency record standing alone.
        nara = records["exec-ind-nara"]
        self.assertEqual((nara["level"], nara["employees"]), (LEVEL_AGENCY, 2810))
        self.assertEqual(nara["selfNamedRow"], {"subagencyCode": "NQ00", "listedName": "NATIONAL ARCHIVES AND RECORDS ADMINISTRATION", "employees": 2810})
        # September's file abbreviates the name further; the record says so
        # rather than presenting the two periods as one unchanging name.
        self.assertEqual(nara["previous"], {"period": "2024-09", "employees": 2900, "listedName": "NAT ARCHIVES AND RECORDS ADMIN"})
        # A detected total row is on the record, and the count is not doubled.
        test = records["exec-ind-test"]
        self.assertEqual((test["employees"], test["totalRow"]["subagencyCode"]), (300, "XX00"))
        self.assertIn("WASHINGTON HEADQUARTERS SERVICES", [h["listedName"] for h in report["headquarters_rows"]])

    def test_an_agency_the_table_lists_apart_from_a_node_the_graph_files_beneath_another_is_named_on_the_record(self) -> None:
        records, report = self._match()
        defense = records["exec-dept-defense"]
        self.assertEqual(defense["employees"], 23896 + 1653 + 1832)
        self.assertEqual(defense["previous"], {"period": "2024-09", "employees": 27400})
        # The Army is not published at all here, and for the reason that
        # matters: the table's whole entry for "DEPARTMENT OF THE ARMY" is one
        # row for the Corps of Engineers, so 38,650 is the Corps' number and
        # naming it the department's would be false. The flag that names a
        # separately-listed agency beneath a node therefore has nothing to say
        # about Defense in this fixture; the refusal is the stronger statement.
        self.assertNotIn("exec-dept-defense-army", records)
        refused = next(x for x in report["agency_is_one_other_unit"] if x["agencyCode"] == "AR")
        self.assertEqual((refused["node"], refused["employees"]), ("exec-dept-defense-army", 38650))
        self.assertNotIn("agenciesListedSeparatelyBeneath", records["exec-dept-defense"])
        self.assertNotIn("agenciesListedSeparatelyBeneath", records["exec-dept-treasury"])

    def test_a_match_outside_the_executive_branch_is_flagged_against_the_stated_coverage(self) -> None:
        records, report = self._match()
        # The judicial branch itself gets no record: the table's entire entry
        # for the agency it calls JUDICIAL BRANCH is one row for the U.S. Tax
        # Court, and "the judicial branch employs 165" is not a thing any
        # caveat makes true. The Tax Court's own row still lands on the Tax
        # Court, flagged as outside the coverage the dictionary states.
        self.assertNotIn("judicial-branch", records)
        refused = next(x for x in report["agency_is_one_other_unit"] if x["agencyCode"] == "JL")
        self.assertEqual((refused["node"], refused["employees"], refused["onlyRow"]["listedName"]), ("judicial-branch", 165, "U.S. TAX COURT"))
        self.assertIs(records["jud-tax"]["outsideStatedCoverage"], True)
        self.assertNotIn("outsideStatedCoverage", records["exec-dept-treasury"])
        self.assertEqual({m["node"] for m in report["matched_outside_executive_branch"]}, {"jud-tax"})
        # "Government Printing Office" is not "Government Publishing Office": no tolerance, reported unmatched.
        self.assertIn("GOVERNMENT PRINTING OFFICE", [a["listedName"] for a in report["unmatched_agencies"]])

    def test_a_chosen_period_stands_and_an_earliest_period_has_no_previous(self) -> None:
        records, report = self._match(period="2024-09")
        self.assertEqual((report["period"], report["previous_period"]), ("2024-09", None))
        self.assertEqual(records["treasury-irs"]["employees"], 99001)
        self.assertIsNone(records["treasury-irs"]["previous"])

    # -- comparison ----------------------------------------------------------

    def test_the_comparison_parses_the_curated_figure_the_way_the_cascade_does(self) -> None:
        records, _ = self._match()
        comparison = compare_with_curated(records, self.node_map)
        by_node = {r["node"]: r for r in comparison["rows"]}
        # Nine, not eight: every matched node that carries a curated `employees`
        # string. The ninth is exec-dept-doi — the table gives Interior 18,275
        # (295 OIG + 17,980 NPS, the only two IN rows in this fixture) against a
        # curated "~67,000", a factor of 3.67 and so a fifth entry beyond 2x.
        # compared + no_curated_figure is len(records), and the set asserted just
        # below fixes no_curated_figure at 7, so eight would mean fifteen records.
        # One fewer than before: the judicial branch's record is refused now,
        # and it was the fifth beyond-2x entry.
        self.assertEqual(comparison["compared"], 8)
        self.assertEqual(comparison["no_curated_figure"], 7)
        self.assertEqual({r["node"] for r in comparison["no_curated_figure_nodes"]}, {"treasury-oig", "doi-oig", "doi-nps", "dod-dla", "nasa-goddard", "jud-tax", "exec-ind-test"})
        self.assertEqual(by_node["exec-dept-defense"]["curated"], 2_050_000, "civilian + military is summed, as get_node_weight sums it")
        self.assertEqual(by_node["exec-dept-doe"]["curated"], 109_000, "federal + contractor likewise")
        self.assertAlmostEqual(by_node["exec-dept-treasury"]["ratio"], 104512 / 100000, places=4)
        # Four, not five: the judicial branch's record is refused now.
        self.assertEqual(comparison["bands"], {"within_10pct": 3, "10_to_25pct": 0, "25pct_to_2x": 1, "beyond_2x": 4})
        self.assertEqual(sum(comparison["bands"].values()), comparison["compared"])
        self.assertEqual(comparison["cumulative"]["within_2x"], 4)
        # Defense heads the list now that the judicial branch's record is
        # refused: a curated "~750,000 civilian + 1.3M active military"
        # against the table's civilians-only figure for its own rows.
        self.assertEqual(comparison["largest_discrepancies"][0]["node"], "exec-dept-defense")
        # Neither the judicial branch nor the Army is compared any more: each
        # was an "agency" whose whole entry is one row for a different unit.
        self.assertEqual([r["node"] for r in comparison["largest_discrepancies"][:3]], ["exec-dept-defense", "exec-dept-doe", "exec-ind-nasa"])


class ScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"headcounts-script-{uuid.uuid4().hex}"
        self.zip = write_fixture(self.tmp)
        self.base = self.tmp / "base.json"; self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.out = self.tmp / "headcount_evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_prints_the_report_and_writes_nothing(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_headcount_evidence.main(["d", "--base-graph", str(self.base), "--fedscope", str(self.zip), "--out", str(self.out), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertFalse(self.out.exists())
        # Eight sub-agency rows reach a node, not five. Five is the count of rows
        # under an agency that itself matched and inside the Executive Branch
        # (TR93 IRS, TR40 and IN07 OIG, IN10 NPS, DD10 DLA); the other three are
        # matches this file pins elsewhere: JL03 U.S. TAX COURT -> jud-tax (its
        # agency matched, but outside the stated coverage), and the two rows whose
        # agency name the table abbreviates so no scope applies and the name is
        # unique in the graph — NQ00 -> exec-ind-nara and NN51 -> nasa-goddard.
        self.assertIn("matched: agencies 8  sub-agencies 7", buf.getvalue())
        self.assertIn(COVERAGE_STATEMENT, buf.getvalue())
        self.assertIn("15 largest discrepancies", buf.getvalue())

    def test_the_script_writes_the_source_the_report_and_the_records(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_headcount_evidence.main(["d", "--base-graph", str(self.base), "--fedscope", str(self.zip), "--out", str(self.out)])
        self.assertEqual(code, 0, buf.getvalue())
        store = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual((store["source"]["url"], store["source"]["fetched_at"], store["source"]["period"]), (META["url"], META["fetched_at"], "2025-03"))
        self.assertEqual(store["source"]["coverage"], COVERAGE_STATEMENT)
        self.assertIn("never edit by hand", store["_note"])
        # 8 agency records + 8 sub-agency records. The three beyond thirteen are
        # the three named in the dry-run test above (jud-tax, exec-ind-nara,
        # nasa-goddard), less the judicial branch's refused record; eight of
        # the fifteen carry a curated figure to compare.
        self.assertEqual(len(store["nodes"]), 15)
        self.assertEqual(store["report"]["comparison"]["compared"], 8)
        self.assertEqual(load_headcount_evidence(self.out)["treasury-irs"]["employees"], 101312)
        self.assertEqual(load_headcount_evidence(self.tmp / "missing.json"), {})


@unittest.skipUnless(DEFAULT_FEDSCOPE_ZIP.exists(), "the verbatim FedScope fixture is not present")
class RealFixturePinTests(unittest.TestCase):
    """Counts observed in the committed March 2025 summary (fetched
    2026-09-08), pinned so a parser or matcher change is noticed."""

    @classmethod
    def setUpClass(cls) -> None:
        from data_pipeline.exporter.build_graph import load_base_graph

        cls.periods = load_fedscope_agency_subagency(DEFAULT_FEDSCOPE_ZIP)
        root = load_base_graph(Path(__file__).resolve().parents[1] / "data" / "federal_gov_complete_1.json")
        cls.node_map, cls.parent_map = index_tree(root)
        cls.records, cls.report = match_fedscope(cls.periods, cls.node_map, cls.parent_map, root_id=str(root["id"]))

    def test_the_table_as_served(self) -> None:
        self.assertEqual(sorted(self.periods), ["2024-09", "2025-03"])
        self.assertEqual((len(self.periods["2025-03"]), len(self.periods["2024-09"])), (499, 517))
        self.assertEqual(sum(r["employees"] for r in self.periods["2025-03"]), 2_289_472)
        self.assertEqual(sum(r["employees"] for r in self.periods["2024-09"]), 2_313_216)
        self.assertEqual(len({r["agency_code"] for r in self.periods["2025-03"]}), 116)
        totals = agency_totals([r for r in self.periods["2025-03"] if r["agency_code"] != "10_OR_LESS"])
        self.assertEqual(len(totals), 115)
        self.assertEqual(totals["VA"]["employees"], 474_532)
        self.assertEqual(totals["TR"]["employees"], 116_073)
        self.assertEqual(sum(1 for t in totals.values() if t["total_row"]), 0, "the table carries no agency total row")
        self.assertEqual(self.report["suppressed_rows"], [{"listedName": "10_OR_LESS", "employees": 127}])

    def test_what_matched(self) -> None:
        # Seven fewer than the first derivation: two agencies whose whole entry
        # is one row for another unit (Federal Reserve/CFPB, Judicial Branch/Tax
        # Court) and five sub-agency rows whose agency matched no node, so
        # nothing verified that the node answering to the name is the unit.
        self.assertEqual((self.report["agencies_matched"], self.report["subagencies_matched"], len(self.records)), (54, 79, 133))
        self.assertEqual((len(self.report["ambiguous_agencies"]), len(self.report["ambiguous_subagencies"])), (0, 0))
        # Two fewer unmatched agencies: NASA and NARA, whose names the table
        # truncates ("NAT ...") and whose truncation is now undone, so their
        # rows are scoped against the right agency instead of floating.
        self.assertEqual((len(self.report["unmatched_agencies"]), len(self.report["unmatched_subagencies"])), (59, 363))
        self.assertEqual(len(self.report["scoped_out"]), 9)
        # One more: NARA's agency name now matches, so its single self-named
        # row is carried by the agency record instead of standing alone.
        self.assertEqual(len(self.report["self_named_rows"]), 41)
        irs = self.records["exec-dept-treasury-irs"]
        self.assertEqual((irs["employees"], irs["previous"]["employees"], irs["agencyMatched"]), (101_312, 99_001, "exec-dept-treasury"))
        va = self.records["exec-dept-va"]
        self.assertEqual((va["employees"], va["previous"]["employees"], va["subagencyRows"]), (474_532, 482_831, 31))
        self.assertEqual(self.records["exec-dept-defense"]["employees"], 158_689)
        self.assertEqual(self.records["exec-dept-dhs-uscg"]["employees"], 9_583, "the shared name resolves beneath DHS")
        self.assertNotIn("exec-dept-defense-cg", self.records)
        self.assertNotIn("leg-house-ig", self.records)
        self.assertEqual({a["listedName"] for a in self.report["unmatched_agencies"][:3]}, {"DEPARTMENT OF THE ARMY", "DEPARTMENT OF THE NAVY", "DEPARTMENT OF THE AIR FORCE"})
        # Only the Tax Court now: the agency the table calls JUDICIAL BRANCH
        # is one Tax Court row, so no record is made for the branch itself.
        self.assertEqual({m["node"] for m in self.report["matched_outside_executive_branch"]}, {"jud-specialized-tax"})
        self.assertNotIn("judicial-branch", self.records)
        self.assertNotIn("exec-regulatory-fed", self.records, "its whole entry is the CFPB's row")

    def test_the_comparison_with_the_curated_figures(self) -> None:
        comparison = compare_with_curated(self.records, self.node_map)
        # Seven fewer compared than the first derivation: two agency records
        # refused for being one other unit, five sub-agency rows refused for
        # having no matched agency to be scoped against.
        self.assertEqual((comparison["compared"], comparison["no_curated_figure"]), (124, 9))
        self.assertEqual(sum(comparison["bands"].values()), 124)
        # Defense heads the list now that the judicial branch's record is
        # refused: a curated "~750,000 civilian + 1.3M active military"
        # against the table's civilians-only figure for its own rows.
        # The Defense Health Agency heads it: the table gives DHA 6,118 while
        # a separate row it names "MILITARY TREATMENT FACILITIES UNDER DHA"
        # (44,777) reaches no node — a coverage split, not a bad match.
        self.assertEqual(comparison["largest_discrepancies"][0]["node"], "exec-dept-defense-agency-dha")


if __name__ == "__main__":
    unittest.main()
