"""OPM's CURRENT PLUM export as evidence for position nodes: only Filled and
Vacant rows, identical rows folded, the incumbent columns never read, one
title to one node or nothing, a second document beside the archive, a rate
that is the row's own figure and never a cost -- and a gate that re-reads the
committed file by the block's own keys and refuses every way of faking one."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, build_graph, index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification import gs_pay, pay_tables, plum_current, positions
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, clear_evidence_fields
from data_pipeline.verification.plum_current import (
    METHOD,
    PLACEMENT_METHOD,
    READ_COLUMNS,
    SOURCE,
    SOURCE_TYPE,
    Unreadable,
    apply_current_listing,
    apply_current_pay,
    build_pay_records,
    combine_listings,
    describe_listing,
    export_title_keys,
    load_evidence,
    load_plum_export,
    match_positions,
    split_scoped_agency,
)
from scripts import derive_plum_current_evidence
from scripts import validate_published_graph as gate
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
CSV_NAME = "escs_pbpub_download-data.csv"
CSV_URL = "https://escs.opm.gov/escs-net/api/pbpub/download-data"
FETCHED_AT = "2026-09-21T03:02:16Z"
HEADER = ('Agency,Organization,Position Title,Position Status,Appointment Type,Expiration Date,'
          '"Level, Grade, or Pay",Duty Location,First Name,Last Name,Individual Unique ID,Pay Plan,Tenure,Begin Date,Vacate Date')
#: Planted in the three incumbent columns of every fixture row. Nothing this
#: module or the gate returns, writes or prints may contain it.
SENTINEL = "SENTINELNAME"
INCUMBENT_COLUMNS = ("First Name", "Last Name", "Individual Unique ID")


def P(node_id: str, name: str) -> dict:
    return {"id": node_id, "name": name, "type": "Position", "children": []}


BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                    P("doe-secretary", "Secretary of Energy"),
                    P("doe-cos", "Chief of Staff"),
                    P("doe-gc", "General Counsel"),
                    {"id": "doe-science", "name": "Office of Science (SC)", "type": "Office", "children": [
                        P("doe-science-director", "Director, Office of Science"),
                        P("doe-science-deputy", "Deputy Director / Vice Chair"),
                        P("doe-science-adv", "Senior Advisor"),
                        P("doe-science-pd-1", "Program Director (×multiple)"),
                        P("doe-science-pd-2", "Program Director (×multiple)"),
                    ]},
                ]},
            ]},
            {"id": "exec-eop", "name": "Executive Office of the President (EOP)", "type": "Office", "children": [
                {"id": "exec-eop-who", "name": "White House Office", "type": "Office", "children": [
                    P("who-cos", "Assistant to the President and Chief of Staff"),
                    P("who-press", "Assistant to the President & Press Secretary"),
                ]},
            ]},
            {"id": "exec-independent", "name": "Independent Agencies", "type": "Division", "children": [
                {"id": "exec-ind-nasa", "name": "National Aeronautics & Space Administration (NASA)", "type": "Agency", "children": [
                    P("nasa-admin", "Administrator, NASA"),
                    P("nasa-cos", "Chief of Staff"),
                ]},
                {"id": "exec-ind-uspto", "name": "U.S. Patent & Trademark Office (USPTO)", "type": "Agency", "children": [
                    P("uspto-director", "Director, USPTO"),
                    P("uspto-deputy", "Deputy Director"),
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

DOE, EOP_WHO, WHO, NASA, USPTO, WAR = (
    "DEPARTMENT OF ENERGY", "EXECUTIVE OFFICE OF THE PRESIDENT - WHITE HOUSE OFFICE", "WHITE HOUSE OFFICE",
    "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION", "U.S. PATENT AND TRADEMARK OFFICE", "OFFICE OF THE SECRETARY OF WAR",
)


def row(agency: str, org: str, title: str, status: str = "Filled", appt: str = "PAS", level: str = "IV",
        plan: str = "EX", vacated: str = "") -> str:
    return (f'{agency},{org},"{title}",{status},{appt},,"{level}","Washington, DC",{SENTINEL},{SENTINEL},{SENTINEL}9,'
            f'{plan},5.0,01/21/2025,{vacated}')


ROWS = [
    row(DOE, DOE, "SECRETARY OF ENERGY", "Filled", "PAS", "I"),
    row(DOE, DOE, "SECRETARY OF ENERGY", "Historical", "PAS", "I", vacated="01/20/2025"),
    row(DOE, DOE, "CHIEF OF STAFF", "Filled", "NA", "$195,200", "ES"),
    row(DOE, DOE, "CHIEF OF STAFF", "Vacant", "NA", "$195,200", "ES"),
    row(DOE, DOE, "GENERAL COUNSEL", "Filled", "PAS", "IV"),
    row(DOE, DOE, "GENERAL COUNSEL", "Vacant", "PAS", "III"),
    row(DOE, "OFFICE OF SCIENCE", "DIRECTOR", "Filled", "PAS", "IV"),
    row(DOE, "OFFICE OF SCIENCE", "DEPUTY DIRECTOR", "Vacant", "CA", "", "ES"),
    row(DOE, "OFFICE OF SCIENCE", "SENIOR ADVISOR", "Filled", "SC", "15", "GS"),
    row(DOE, "OFFICE OF SCIENCE", "SENIOR ADVISOR, OFFICE OF SCIENCE", "Filled", "SC", "14", "GS"),
    row(DOE, "OFFICE OF SCIENCE", "PROGRAM DIRECTOR", "Filled", "CA", "$180,000", "ES"),
    row(EOP_WHO, WHO, "ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF", "Filled", "NA", "$195,200", "AD"),
    row(EOP_WHO, WHO, "ASSISTANT TO THE PRESIDENT &amp; PRESS SECRETARY", "Filled", "NA", "$0.00", "AD"),
    row(NASA, NASA, "ADMINISTRATOR", "Filled", "PAS", "II"),
    row(USPTO, "PATENT AND TRADEMARK OFFICE", "DIRECTOR", "Filled", "PAS", "III"),
    row(USPTO, "UNITED STATES PATENT AND TRADEMARK OFFICE", "DEPUTY DIRECTOR", "Filled", "NA", "$200,000", "ES"),
    row(WAR, WAR, "CHIEF OF STAFF", "Filled", "NA", "$190,000", "ES"),
]


def write_fixture(directory: Path, rows: list[str] | None = None, *, corrupt_digest: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / CSV_NAME
    body = ("﻿" + HEADER + "\r\n" + "\r\n".join(rows or ROWS) + "\r\n").encode("utf-8")
    csv_path.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    if corrupt_digest:
        digest = "0" * 64
    csv_path.with_name(CSV_NAME + ".meta.json").write_text(json.dumps({
        "fetched_at": FETCHED_AT, "url": CSV_URL, "final_url": CSV_URL, "status": 200, "content_type": "text/csv",
        "sha256": digest, "bytes": len(body), "error": None,
    }), encoding="utf-8")
    return csv_path


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


class FixtureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plumcur-{uuid.uuid4().hex}"
        self.csv = write_fixture(self.tmp)
        self.base = json.loads(json.dumps(BASE))
        self.node_map, self.parent_map = index_tree(self.base)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _match(self):
        export = load_plum_export(self.csv)
        return export, *match_positions(export, self.node_map, self.parent_map, root_id=ROOT_ID)


class ReadingTests(FixtureTestCase):
    def test_the_digest_is_recomputed_and_a_mismatch_is_refused(self) -> None:
        with self.csv.open("ab") as handle:
            handle.write(b"x")
        with self.assertRaises(Unreadable):
            load_plum_export(self.csv)

    def test_a_recorded_digest_that_is_not_the_files_is_refused(self) -> None:
        write_fixture(self.tmp, corrupt_digest=True)
        with self.assertRaises(Unreadable):
            load_plum_export(self.csv)

    def test_without_a_meta_file_nothing_is_read(self) -> None:
        self.csv.with_name(CSV_NAME + ".meta.json").unlink()
        with self.assertRaises(Unreadable):
            load_plum_export(self.csv)

    def test_historical_rows_are_counted_and_never_read(self) -> None:
        export = load_plum_export(self.csv)
        self.assertEqual(export["historical_rows"], 1)
        self.assertEqual(export["status_counts"], {"Filled": 13, "Vacant": 3, "Historical": 1})
        folds = [r for r in export["rows"] if r["title"] == "SECRETARY OF ENERGY"]
        self.assertEqual(len(folds), 1)
        self.assertEqual(dict(folds[0]["statusCounts"]), {"Filled": 1})

    def test_identical_rows_are_folded_before_anything_else(self) -> None:
        export = load_plum_export(self.csv)
        folds = [r for r in export["rows"] if r["title"] == "CHIEF OF STAFF" and r["agency"] == DOE]
        self.assertEqual(len(folds), 1)
        self.assertEqual(folds[0]["rowsListed"], 2)
        self.assertEqual(dict(folds[0]["statusCounts"]), {"Filled": 1, "Vacant": 1})
        self.assertEqual(export["live_rows"], 16)
        self.assertEqual(len(export["rows"]), 15)

    def test_only_the_named_columns_are_read_and_the_incumbent_columns_never(self) -> None:
        self.assertFalse(set(INCUMBENT_COLUMNS) & set(READ_COLUMNS))
        export = load_plum_export(self.csv)
        for fold in export["rows"]:
            self.assertFalse(set(fold) & set(INCUMBENT_COLUMNS))
            self.assertNotIn(SENTINEL, json.dumps(fold, default=str))
        _, records, report = self._match()
        self.assertNotIn(SENTINEL, json.dumps(records))
        self.assertNotIn(SENTINEL, json.dumps(report, default=str))
        pay, _ = build_pay_records(records)
        self.assertNotIn(SENTINEL, json.dumps(pay))
        source = (Path(__file__).resolve().parents[1] / "data_pipeline" / "verification" / "plum_current.py").read_text(encoding="utf-8")
        for column in INCUMBENT_COLUMNS:
            self.assertNotIn(f'"{column}"', source, f"the module names the {column!r} column")

    def test_the_gates_reader_projects_the_same_columns_and_never_the_incumbents(self) -> None:
        self.assertEqual(gate.PLUM_CURRENT_COLUMNS, tuple(READ_COLUMNS))
        self.assertFalse(set(INCUMBENT_COLUMNS) & set(gate.PLUM_CURRENT_COLUMNS))
        gate._PLUM_CURRENT_CACHE.clear()
        export = gate.plum_current_export(self.csv)
        self.assertIsNotNone(export)
        self.assertNotIn(SENTINEL, repr(export))
        entry = export["index"][(DOE, DOE, "SECRETARY OF ENERGY")]
        self.assertEqual(len(entry["live"]), 1)
        self.assertEqual(entry["historical"], 1)
        self.assertEqual(set(entry["live"][0]), set(gate.PLUM_CURRENT_COLUMNS))
        gate._PLUM_CURRENT_CACHE.clear()

    def test_the_gates_reader_refuses_a_digest_mismatch(self) -> None:
        write_fixture(self.tmp, corrupt_digest=True)
        gate._PLUM_CURRENT_CACHE.clear()
        self.assertIsNone(gate.plum_current_export(self.csv))
        gate._PLUM_CURRENT_CACHE.clear()


class MatchingTests(FixtureTestCase):
    def test_the_scoped_prefix_is_the_exports_own_filing_read_back(self) -> None:
        self.assertEqual(split_scoped_agency(EOP_WHO), ("EXECUTIVE OFFICE OF THE PRESIDENT", "WHITE HOUSE OFFICE"))
        self.assertIsNone(split_scoped_agency("EXPORT-IMPORT BANK"))
        _, records, report = self._match()
        self.assertEqual(report["agencies_matched_by_scoped_prefix"], 1)
        self.assertEqual(records["who-cos"]["agency"], EOP_WHO)
        self.assertEqual(records["who-cos"]["organization"], WHO)
        self.assertEqual(records["who-cos"]["agencyMatchedBy"], "scoped_prefix")
        self.assertEqual(records["who-cos"]["placement"]["parentId"], "exec-eop-who")

    def test_an_agency_the_graph_lacks_matches_nothing_and_is_reported(self) -> None:
        _, records, report = self._match()
        self.assertIn(WAR, report["agencies_unmatched"])
        self.assertEqual(report["unmatched_agencies_top"][0], {"agency": WAR, "rows": 1})
        self.assertFalse(any(r["agency"] == WAR for r in records.values()))

    def test_titles_are_scoped_to_the_matched_organisation(self) -> None:
        _, records, _ = self._match()
        self.assertEqual(records["doe-science-director"]["listedTitle"], "DIRECTOR")
        self.assertEqual(records["doe-science-director"]["organization"], "OFFICE OF SCIENCE")
        self.assertEqual(records["doe-science-director"]["placement"]["parentId"], "doe-science")
        self.assertEqual(records["doe-secretary"]["payLevel"], "I")
        self.assertEqual(records["doe-secretary"]["positionStatus"], "Filled")
        self.assertEqual(records["nasa-admin"]["listedTitle"], "ADMINISTRATOR")

    def test_a_title_two_siblings_share_claims_neither(self) -> None:
        _, records, report = self._match()
        self.assertNotIn("doe-science-pd-1", records)
        self.assertNotIn("doe-science-pd-2", records)
        self.assertEqual({s["id"] for s in report["positions_shared_title"]}, {"doe-science-pd-1", "doe-science-pd-2"})

    def test_two_spellings_collapsing_onto_one_key_claim_neither(self) -> None:
        _, records, report = self._match()
        self.assertNotIn("doe-science-adv", records)
        self.assertEqual(report["positions_title_ambiguous_in_export"][0]["titles"],
                         ["SENIOR ADVISOR", "SENIOR ADVISOR, OFFICE OF SCIENCE"])

    def test_folded_duplicates_are_one_listing_with_both_statuses(self) -> None:
        _, records, _ = self._match()
        listing = records["doe-cos"]
        self.assertIsNone(listing["positionStatus"])
        self.assertEqual(listing["positionStatusCounts"], {"Filled": 1, "Vacant": 1})
        self.assertEqual(listing["rowsListed"], 2)
        self.assertEqual((listing["reportedPay"], listing["reportedPayText"], listing["payLevel"]), (195200.0, "$195,200", None))

    def test_rows_that_disagree_publish_null_with_the_counts(self) -> None:
        _, records, _ = self._match()
        listing = records["doe-gc"]
        self.assertIsNone(listing["level"])
        self.assertEqual(listing["levelCounts"], {"IV": 1, "III": 1})
        self.assertIsNone(listing["payLevel"])
        self.assertFalse(listing["payPlanAndLevelOnOneRow"])

    def test_html_entities_are_resolved_for_keys_and_kept_as_served(self) -> None:
        self.assertEqual(export_title_keys("ASSISTANT TO THE PRESIDENT &amp; PRESS SECRETARY", WHO),
                         ["assistant to the president and press secretary"])
        _, records, _ = self._match()
        self.assertEqual(records["who-press"]["listedTitle"], "ASSISTANT TO THE PRESIDENT &amp; PRESS SECRETARY")

    def test_two_groups_that_are_both_the_agency_feed_one_index(self) -> None:
        _, records, report = self._match()
        self.assertEqual(report["organizations_ambiguous"], [])
        self.assertEqual(records["uspto-director"]["organization"], "PATENT AND TRADEMARK OFFICE")
        self.assertEqual(records["uspto-deputy"]["organization"], "UNITED STATES PATENT AND TRADEMARK OFFICE")

    def test_no_negative_records(self) -> None:
        _, records, report = self._match()
        self.assertTrue(all(r.get("placement", {}).get("status") == "listed" for r in records.values()))
        self.assertGreater(report["positions_unmatched"], 0)

    def test_the_gates_key_mirrors_are_the_modules(self) -> None:
        for name in (DOE, "DEPARTMENT OF THE TREASURY", "Department of Energy (DOE)", "OFFICE OF SCIENCE", "AMERICA&#039;S HERITAGE", ""):
            self.assertEqual(gate.plum_org_keys(name), positions.organisation_name_keys(plum_current.unescape(name)), name)
        for title, org in (("COMMISSIONER, UNITED STATES CUSTOMS AND BORDER PROTECTION", "U.S. CUSTOMS AND BORDER PROTECTION"),
                           ("SENIOR ADVISOR, OFFICE OF SCIENCE", "OFFICE OF SCIENCE"), ("CHIEF OF STAFF", DOE),
                           ("ASSISTANT TO THE PRESIDENT &amp; PRESS SECRETARY", WHO)):
            self.assertEqual(gate.plum_export_title_keys(title, org), export_title_keys(title, org), title)
        self.assertEqual(gate.plum_agency_unit(EOP_WHO), WHO)
        self.assertEqual((gate.PLUM_CURRENT_METHOD, gate.PLUM_CURRENT_PLACEMENT_METHOD, gate.PLUM_CURRENT_SOURCE), (METHOD, PLACEMENT_METHOD, SOURCE))


class PayRecordTests(FixtureTestCase):
    def test_a_rate_is_built_only_where_the_row_prints_one_and_never_zero(self) -> None:
        _, records, _ = self._match()
        pay, report = build_pay_records(records)
        self.assertEqual(set(pay), {"doe-cos", "who-cos", "uspto-deputy"})
        self.assertEqual(report["refused"]["rate_is_zero"], 1)
        self.assertNotIn("who-press", pay)
        record = pay["doe-cos"]
        self.assertEqual((record["amount"], record["amountRaw"], record["rateText"]), (195200.0, "195,200", "$195,200"))
        self.assertEqual(record["scopeMatch"], "proxy")
        self.assertEqual(record["periodCoverage"], "annual_rate")
        self.assertEqual(record["periodAsOf"], "2026-09-21")

    def test_every_record_passes_the_validator_as_a_proxy_graded_partial(self) -> None:
        _, records, _ = self._match()
        pay, _ = build_pay_records(records)
        for node_id, record in pay.items():
            out = fe.validate_record(record, self.node_map[node_id])
            self.assertEqual(fe.classify(out), "partial")
            self.assertEqual(out["unitsEvidenceKind"], "currency_mark_on_the_printed_figure")

    def test_the_validator_refuses_the_rate_on_an_organisation(self) -> None:
        _, records, _ = self._match()
        pay, _ = build_pay_records(records)
        record = dict(pay["doe-cos"], nodeId="exec-dept-doe")
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, self.node_map["exec-dept-doe"])


class ApplyTests(FixtureTestCase):
    def _records(self):
        _, records, _ = self._match()
        pay, _ = build_pay_records(records)
        validated = {}
        for node_id, record in pay.items():
            out = fe.validate_record(record, self.node_map[node_id])
            out["financialEvidenceStatus"] = fe.classify(out)
            validated[node_id] = out
        return records, validated

    def test_the_listing_is_stamped_beside_a_source_and_a_method_where_none_exists(self) -> None:
        records, _ = self._records()
        stats = apply_current_listing(self.base, records)
        node = self.node_map["doe-cos"]
        self.assertEqual(stats["listed"], len(records))
        self.assertEqual(node["positionCurrentListing"]["method"], METHOD)
        self.assertEqual(node["positionCurrentListing"]["exportFetchedAt"], FETCHED_AT)
        self.assertEqual(node["positionCurrentListing"]["checkedAt"], FETCHED_AT)
        self.assertIn(CSV_URL, node["sourceUrls"])
        self.assertIn(SOURCE_TYPE, node["sourceTypes"])
        self.assertEqual(node["verificationMethod"], METHOD)
        self.assertEqual(node["lastVerified"], FETCHED_AT)
        self.assertEqual(node["verificationStatus"], "partial")

    def test_a_post_listed_in_the_archive_too_reaches_verified_on_two_documents(self) -> None:
        records, _ = self._records()
        node = self.node_map["doe-cos"]
        node["sourceUrls"] = ["https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/plum-archive-biden-administration.csv"]
        node["sourceTypes"] = ["opm_plum_archive"]
        node["verificationMethod"] = positions.PLUM_METHOD
        apply_current_listing(self.base, records)
        self.assertEqual(node["verificationStatus"], "verified")
        self.assertEqual(node["verificationMethod"], positions.PLUM_METHOD, "an existing method is never overwritten")
        self.assertEqual(len(node["sourceUrls"]), 2)

    def test_placement_only_when_the_exports_organisation_is_the_tree_parent(self) -> None:
        records, _ = self._records()
        moved = self.node_map["doe-science"]["children"].pop(0)  # doe-science-director
        self.node_map["exec-dept-doe"]["children"].append(moved)
        stats = apply_current_listing(self.base, records)
        self.assertEqual(stats["placements_stale_parent"], 1)
        self.assertNotIn("placementMethod", moved)
        self.assertEqual(self.node_map["doe-cos"]["placementMethod"], PLACEMENT_METHOD)
        self.assertEqual(self.node_map["doe-cos"]["placementParentId"], "exec-dept-doe")
        self.assertEqual(self.node_map["doe-cos"]["placementMatchedText"], "CHIEF OF STAFF")

    def test_a_renamed_node_inherits_nothing(self) -> None:
        records, _ = self._records()
        self.node_map["doe-cos"]["name"] = "Deputy Chief of Staff"
        stats = apply_current_listing(self.base, records)
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("positionCurrentListing", self.node_map["doe-cos"])
        self.assertNotIn("sourceUrls", self.node_map["doe-cos"])

    def test_a_record_without_a_digest_or_date_is_refused(self) -> None:
        records, _ = self._records()
        bad = {k: dict(v) for k, v in records.items()}
        bad["doe-cos"]["documentSha256"] = "not-a-digest"
        bad["nasa-admin"]["exportFetchedAt"] = ""
        stats = apply_current_listing(self.base, bad)
        self.assertEqual(stats["undated"], 2)
        self.assertNotIn("positionCurrentListing", self.node_map["doe-cos"])

    def test_the_rate_is_stamped_only_where_the_listing_still_reports_it(self) -> None:
        records, validated = self._records()
        apply_current_listing(self.base, records)
        before = {k: (list(n.get("sourceUrls") or []), n.get("lastVerified"), n.get("verificationMethod")) for k, n in self.node_map.items()}
        stats = apply_current_pay(self.base, validated)
        self.assertEqual(stats["priced"], 3)
        node = self.node_map["doe-cos"]
        self.assertEqual(node["positionCurrentPay"]["amount"], 195200.0)
        self.assertEqual(node["positionCurrentPay"]["rateText"], "$195,200")
        self.assertEqual(node["positionCurrentPay"]["scopeMatch"], "proxy")
        self.assertEqual(node["positionCurrentPay"]["exportFetchedAt"], FETCHED_AT)
        after = {k: (list(n.get("sourceUrls") or []), n.get("lastVerified"), n.get("verificationMethod")) for k, n in self.node_map.items()}
        self.assertEqual(before, after, "a rate is never evidence that the post exists")
        # The listing changes its figure: the rate goes with it.
        node["positionCurrentListing"]["reportedPay"] = 200000.0
        node.pop("positionCurrentPay")
        stats = apply_current_pay(self.base, validated)
        self.assertEqual(stats["listing_reports_a_different_figure"], 1)
        self.assertNotIn("positionCurrentPay", node)

    def test_the_rate_is_refused_without_a_listing_on_a_multi_post_node_and_unvalidated(self) -> None:
        records, validated = self._records()
        stats = apply_current_pay(self.base, validated)
        self.assertEqual(stats["no_listing_published"], 3)
        apply_current_listing(self.base, records)
        self.node_map["doe-cos"]["representsPosts"] = 2
        unvalidated = {k: {kk: vv for kk, vv in v.items() if kk != "unitsEvidenceKind"} for k, v in validated.items()}
        stats = apply_current_pay(self.base, unvalidated)
        self.assertEqual(stats["stands_for_many_posts"], 1)
        self.assertEqual(stats["not_validated"], 2)
        self.assertEqual(stats["priced"], 0)

    def test_the_multi_post_sweep_takes_the_field(self) -> None:
        records, validated = self._records()
        apply_current_listing(self.base, records)
        apply_current_pay(self.base, validated)
        self.node_map["doe-cos"]["representsPosts"] = 2
        self.assertEqual(pay_tables.withdraw_pay_from_multi_post_nodes(self.base), 1)
        self.assertNotIn("positionCurrentPay", self.node_map["doe-cos"])

    def test_both_fields_are_owned_and_withdrawn_with_the_source_type(self) -> None:
        self.assertIn("positionCurrentListing", EVIDENCE_OWNED_FIELDS)
        self.assertIn("positionCurrentPay", EVIDENCE_OWNED_FIELDS)
        self.assertIn("positionCurrentListing", MINIMAL_GRAPH_FIELDS)
        self.assertIn("positionCurrentPay", MINIMAL_GRAPH_FIELDS)
        records, validated = self._records()
        apply_current_listing(self.base, records)
        apply_current_pay(self.base, validated)
        node = self.node_map["doe-cos"]
        self.assertTrue(clear_evidence_fields(node, set(node["evidenceUrls"])))
        self.assertNotIn("positionCurrentListing", node)
        self.assertNotIn("positionCurrentPay", node)
        self.assertNotIn(CSV_URL, node.get("sourceUrls") or [])
        self.assertNotIn(SOURCE_TYPE, node.get("sourceTypes") or [])


class ListingCombinationTests(unittest.TestCase):
    ARCHIVE = {"source": positions.PLUM_SOURCE, "edition": "Biden Administration (January 21, 2021 - January 20, 2025)",
               "listedTitle": "GENERAL COUNSEL", "payPlan": "EX", "payLevel": "IV", "reportedPay": None,
               "payPlanAndLevelOnOneRow": True, "url": "https://www.opm.gov/x.csv", "checkedAt": "2026-09-08T19:49:47Z"}
    CURRENT = {"source": SOURCE, "edition": "OPM PLUM Reporting current export (fetched 2026-09-21)", "listedTitle": "GENERAL COUNSEL",
               "payPlan": "EX", "payLevel": "III", "reportedPay": None, "reportedPayText": None, "payPlanAndLevelOnOneRow": True,
               "url": CSV_URL, "exportFetchedAt": FETCHED_AT}

    def test_the_current_listing_is_preferred_and_names_its_source(self) -> None:
        combined, stats = combine_listings({"a": self.ARCHIVE, "b": self.ARCHIVE}, {"a": self.CURRENT})
        self.assertEqual(stats, {"from_current": 1, "from_archive": 1, "either_reports_a_rate": 0})
        self.assertEqual((combined["a"]["source"], combined["a"]["payLevel"], combined["a"]["checkedAt"]), (SOURCE, "III", FETCHED_AT))
        self.assertEqual(combined["b"]["source"], positions.PLUM_SOURCE)

    def test_a_rate_stated_by_either_listing_refuses_a_table_rate_and_a_range(self) -> None:
        combined, stats = combine_listings({"a": dict(self.ARCHIVE, reportedPay=225700.0)}, {"a": self.CURRENT})
        self.assertEqual(stats["either_reports_a_rate"], 1)
        self.assertTrue(combined["a"]["anyListingReportsRate"])
        table = {"levels": {"III": {}}}
        self.assertEqual(pay_tables.eligible(combined["a"], table), (False, "a_listing_reports_a_rate"))
        self.assertEqual(gs_pay.eligible(dict(combined["a"], payPlan="ES", payLevel=""), {gs_pay.KIND_SES: {}}), (False, "a_listing_reports_a_rate"))
        clean, _ = combine_listings({"a": self.ARCHIVE}, {"a": self.CURRENT})
        self.assertEqual(pay_tables.eligible(clean["a"], table), (True, "listed_at_an_executive_schedule_level"))

    def test_the_listing_field_table_ties_each_source_to_its_own_field(self) -> None:
        self.assertEqual(positions.listing_field_for(SOURCE), "positionCurrentListing")
        self.assertEqual(positions.listing_field_for(positions.PLUM_SOURCE), "positionListing")
        self.assertIsNone(positions.listing_field_for("something_else"))

    def _priced_tree(self, listing_field, level="IV"):
        tree = {"id": ROOT_ID, "name": "Root", "type": "Foundation", "children": [
            {"id": "org", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                {"id": "gc", "name": "General Counsel", "type": "Position", "children": [],
                 listing_field: {"payPlan": "EX", "payLevel": level, "reportedPay": None, "payPlanAndLevelOnOneRow": True}},
            ]},
        ]}
        record = {"nodeId": "gc", "amount": 195200.0, "rateText": "$195,200", "table": "Salary Table No. 2026-EX",
                  "effectiveText": "Effective January 2026", "periodAsOf": "2026-01-01", "fiscalYear": 2026,
                  "costBasis": "basic_pay", "scopeMatch": "proxy", "financialEvidenceStatus": "partial",
                  "amountScope": "Level IV", "quote": "Level IV $195,200", "tableFootnotes": ["note"],
                  "levelClaim": {"source": SOURCE, "edition": "OPM PLUM Reporting current export (fetched 2026-09-21)",
                                 "period": None, "listedTitle": "GENERAL COUNSEL", "url": CSV_URL, "checkedAt": FETCHED_AT,
                                 "payLevel": "IV", "payPlan": "EX"},
                  "sourceUrl": "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx",
                  "retrievedAt": "2026-09-11T00:00:00Z"}
        return tree, {"gc": record}

    def test_a_table_rate_derived_from_the_current_listing_is_read_off_that_field_and_withdrawn_with_it(self) -> None:
        tree, records = self._priced_tree("positionCurrentListing")
        stats = pay_tables.apply_pay_evidence(tree, records)
        self.assertEqual(stats["priced"], 1)
        node = index_tree(tree)[0]["gc"]
        self.assertEqual(node["positionPayRate"]["levelSource"]["source"], SOURCE)
        # The archive's field alone does not satisfy a claim naming the current export.
        tree, records = self._priced_tree("positionListing")
        stats = pay_tables.apply_pay_evidence(tree, records)
        self.assertEqual(stats["no_listing_published"], 1)
        # The current listing now reports a different level: withdrawn.
        tree, records = self._priced_tree("positionCurrentListing", level="III")
        stats = pay_tables.apply_pay_evidence(tree, records)
        self.assertEqual(stats["listing_reports_a_different_level"], 1)
        # A rate stated by the OTHER listing refuses the join.
        tree, records = self._priced_tree("positionCurrentListing")
        index_tree(tree)[0]["gc"]["positionListing"] = {"payPlan": "ES", "payLevel": None, "reportedPay": 210000.0}
        stats = pay_tables.apply_pay_evidence(tree, records)
        self.assertEqual(stats["listing_reports_a_rate"], 1)


class ScriptBuildAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"plumcur-gate-{uuid.uuid4().hex}"
        self.csv = write_fixture(self.tmp)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.out = self.tmp / "plum_current_evidence.json"
        gate._PLUM_CURRENT_CACHE.clear()
        self._fixture_before = gate.PLUM_CURRENT_FIXTURE
        gate.PLUM_CURRENT_FIXTURE = self.csv

    def tearDown(self) -> None:
        gate.PLUM_CURRENT_FIXTURE = self._fixture_before
        gate._PLUM_CURRENT_CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _derive(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_plum_current_evidence.main(["d", "--base-graph", str(self.base), "--export", str(self.csv), "--out", str(self.out), *extra])
        return code, buf.getvalue()

    def _build(self):
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=False,
            enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=None, headcount_evidence_path=None, position_evidence_path=None,
            pay_evidence_path=None, grade_pay_evidence_path=None, plum_current_evidence_path=self.out,
            schedule_pay_evidence_path=None, judicial_pay_evidence_path=None, congressional_pay_evidence_path=None,
            whitehouse_pay_evidence_path=None, usaspending_evidence_path=None, net_cost_evidence_path=None,
            govman_evidence_path=None, omb_budget_evidence_path=None,
        )

    def _gate(self, path):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = gate_main(["gate", str(path)])
        return code, buf.getvalue()

    def test_dry_run_writes_nothing_and_reports_every_stage(self) -> None:
        code, out = self._derive("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.out.exists())
        self.assertIn("historical rows not read 1", out)
        self.assertIn("agencies matched 4 (of which 1 by the export's own", out)
        self.assertIn("unmatched agencies by live rows", out)
        self.assertIn(WAR, out)
        self.assertIn("pay: 3 rates built, 3 validated", out)
        self.assertNotIn(SENTINEL, out)

    def test_the_script_derives_the_build_publishes_and_the_gate_passes(self) -> None:
        code, out = self._derive()
        self.assertEqual(code, 0, out)
        store = load_evidence(self.out)
        self.assertEqual(len(store["nodes"]), 10)
        self.assertEqual(set(store["pay"]), {"doe-cos", "who-cos", "uspto-deputy"})
        self.assertNotIn(SENTINEL, self.out.read_text(encoding="utf-8"))
        result = self._build()
        self.assertEqual(result.validation["plum_current_evidence"]["listed"], 10)
        self.assertEqual(result.validation["plum_current_pay"]["priced"], 3)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["doe-cos"]
        self.assertEqual(node["positionCurrentListing"]["listedTitle"], "CHIEF OF STAFF")
        self.assertEqual(node["positionCurrentPay"]["rateText"], "$195,200")
        self.assertEqual(node["placementMethod"], PLACEMENT_METHOD)
        self.assertEqual(node["verificationMethod"], METHOD)
        who = index_tree(graph)[0]["who-cos"]
        self.assertEqual(who["placementParentId"], "exec-eop-who")
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("current Plum Book    : 10 positions listed in OPM's current PLUM export (fetched 2026-09-21); 10 placements from it; 3 carry the rate", out)
        viewer = json.loads((self.tmp / "graph.min.json").read_text(encoding="utf-8")) if (self.tmp / "graph.min.json").exists() else None
        if viewer is not None:
            self.assertIn("positionCurrentPay", index_tree(viewer)[0]["doe-cos"])

    def _corrupt(self, node_id="doe-cos", node_fields=None, listing_fields=None, pay_fields=None, mutate=None):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        by_id = index_tree(graph)[0]
        node = by_id[node_id]
        for key, value in (listing_fields or {}).items():
            if value is None:
                node["positionCurrentListing"].pop(key, None)
            else:
                node["positionCurrentListing"][key] = value
        for key, value in (pay_fields or {}).items():
            node["positionCurrentPay"][key] = value
        for key, value in (node_fields or {}).items():
            node[key] = value
        if mutate:
            mutate(graph, by_id)
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return self._gate(path)

    def test_the_gate_refuses_a_listing_on_a_non_post(self) -> None:
        code, out = self._corrupt(node_fields={"type": "Office"})
        self.assertEqual(code, 1, out)
        self.assertIn("not a post", out)

    def test_the_gate_refuses_a_renamed_node(self) -> None:
        code, out = self._corrupt(node_fields={"name": "Deputy Chief of Staff"})
        self.assertEqual(code, 1, out)
        self.assertIn("which does not name it", out)

    def test_the_gate_refuses_a_wrong_parent(self) -> None:
        def move(graph, by_id):
            by_id["exec-dept-doe"]["children"].remove(by_id["doe-cos"])
            by_id["doe-science"]["children"].append(by_id["doe-cos"])
        code, out = self._corrupt(mutate=move)
        self.assertEqual(code, 1, out)
        self.assertIn("but its parent in the tree is", out)

    def test_the_gate_refuses_a_historical_row(self) -> None:
        code, out = self._corrupt(node_id="doe-secretary", listing_fields={"positionStatus": "Historical"})
        self.assertEqual(code, 1, out)
        self.assertIn("publishes position status 'Historical'", out)

    def test_the_gate_refuses_a_row_the_export_does_not_carry(self) -> None:
        code, out = self._corrupt(listing_fields={"listedTitle": "DEPUTY CHIEF OF STAFF"}, node_fields={"name": "Deputy Chief of Staff"})
        self.assertEqual(code, 1, out)
        self.assertIn("carries no Filled or Vacant row for", out)

    def test_the_gate_refuses_a_digest_mismatch(self) -> None:
        code, out = self._corrupt(listing_fields={"documentSha256": "0" * 64})
        self.assertEqual(code, 1, out)
        self.assertIn("not the committed export's", out)

    def test_the_gate_refuses_a_figure_that_is_not_the_rows(self) -> None:
        code, out = self._corrupt(listing_fields={"reportedPay": 195300.0, "reportedPayText": "$195,300"},
                                  pay_fields={"amount": 195300.0, "rateText": "$195,300"})
        self.assertEqual(code, 1, out)
        self.assertIn("which no live row of this title prints", out)
        self.assertIn("which no Filled or Vacant row of this title prints", out)

    def test_the_gate_refuses_a_rate_its_listing_does_not_report(self) -> None:
        code, out = self._corrupt(pay_fields={"amount": 195300.0, "rateText": "$195,300"})
        self.assertEqual(code, 1, out)
        self.assertIn("publishes a rate its current listing does not report", out)

    def test_the_gate_refuses_zero_and_a_level_the_row_does_not_print(self) -> None:
        code, out = self._corrupt(pay_fields={"amount": 0})
        self.assertEqual(code, 1, out)
        self.assertIn("zero or a non-number is never a rate", out)
        code, out = self._corrupt(node_id="doe-secretary", listing_fields={"payLevel": "II"})
        self.assertEqual(code, 1, out)
        self.assertIn("as a pay level; the export's cell(s)", out)

    def test_the_gate_refuses_a_placement_on_a_node_whose_parent_is_not_the_exports_organisation(self) -> None:
        code, out = self._corrupt(listing_fields={"organization": "OFFICE OF SCIENCE"})
        self.assertEqual(code, 1, out)
        self.assertIn("is filed by the export under 'OFFICE OF SCIENCE', but its parent in the tree is", out)
        code, out = self._corrupt(node_id="nasa-admin", node_fields={"placementMethod": PLACEMENT_METHOD, "placementVerified": True,
                                                                     "placementUrl": CSV_URL, "placementVerifiedAt": FETCHED_AT,
                                                                     "placementParentId": "exec-ind-nasa", "placementMatchedText": "ADMINISTRATOR",
                                                                     "positionCurrentListing": None})
        self.assertEqual(code, 1, out)
        self.assertIn("claims a placement from the current PLUM export with no listing from it", out)

    def test_the_gate_refuses_a_rate_beside_a_measured_cost_or_more_than_a_proxy(self) -> None:
        code, out = self._corrupt(pay_fields={"scopeMatch": "exact", "financialEvidenceStatus": "verified"})
        self.assertEqual(code, 1, out)
        self.assertIn("claims more than a proxy graded partial", out)
        code, out = self._corrupt(node_fields={"cost_status": "official"})
        self.assertEqual(code, 1, out)
        self.assertIn("carries a rate of basic pay and a measured cost status", out)

    def test_the_gate_refuses_a_table_rate_beside_a_rate_the_other_listing_states(self) -> None:
        table_rate = {
            "source": "opm_executive_schedule", "payLevel": "II", "payPlan": "EX",
            "amount": gate.EXECUTIVE_SCHEDULE_RATES["II"], "rateText": "${:,.0f}".format(gate.EXECUTIVE_SCHEDULE_RATES["II"]),
            "table": gate.EXECUTIVE_SCHEDULE_TABLE, "effective": gate.EXECUTIVE_SCHEDULE_EFFECTIVE,
            "effectiveText": gate.EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT, "amountScope": "Level II", "checkedAt": "2026-09-11T00:00:00Z",
            "url": "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx",
            "footnotes": list(gate.EXECUTIVE_SCHEDULE_FOOTNOTES),
            "levelSource": {"source": "opm_plum_archive", "edition": "Biden Administration (January 21, 2021 - January 20, 2025)",
                            "url": "https://www.opm.gov/plum-archive.csv"},
        }
        archive_listing = {"payLevel": "II", "payPlan": "EX", "reportedPay": None, "payPlanAndLevelOnOneRow": True,
                           "edition": "Biden Administration (January 21, 2021 - January 20, 2025)",
                           "url": "https://www.opm.gov/plum-archive.csv", "checkedAt": "2026-09-08T19:49:47Z"}
        # The archive listing supports the table rate; the CURRENT listing states a rate: two rates for one post.
        code, out = self._corrupt(node_fields={"positionPayRate": table_rate, "positionListing": archive_listing})
        self.assertEqual(code, 1, out)
        self.assertIn("carries a table rate beside a rate a PLUM listing states", out)
        # Without the stated rate on the current listing (a level instead), the same block passes.
        code, out = self._corrupt(node_id="doe-secretary", node_fields={"positionPayRate": table_rate, "positionListing": archive_listing})
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
