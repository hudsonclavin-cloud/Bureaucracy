"""The salary table, the level it is looked up by, and every way the join
could publish something false.

Both directions throughout, as everything in this repository is gated: an
honest rate is published, and each way of forging one is refused. The
attacks here are the ones the data actually makes possible — a General
Schedule grade priced as an Executive Schedule level, a Roman numeral on
another pay plan, a level whose listing has since changed, a figure that is
not the one the table prints, a footnote dropped, a rate dressed as a cost.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, apply_evidence_to_tree
from data_pipeline.verification.pay_tables import (
    DEFAULT_PAY_TABLE_HTML,
    EXECUTIVE_SCHEDULE_LEVELS,
    Unreadable,
    apply_pay_evidence,
    build_records,
    eligible,
    load_executive_schedule,
    parse_executive_schedule,
)
from data_pipeline.verification.positions import apply_position_evidence
from scripts import derive_pay_evidence
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_EFFECTIVE,
    EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT,
    EXECUTIVE_SCHEDULE_FOOTNOTES,
    EXECUTIVE_SCHEDULE_RATES,
    EXECUTIVE_SCHEDULE_TABLE,
)
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"

PAGE = """
<html><body>
<h2>Salary Table No. 2026-EX</h2>
<p>Rates of Basic Pay for the Executive Schedule (EX)</p>
<h3>Effective January 2026</h3>
<table class="DataTable">
  <thead><tr><th scope="col">Level</th><th scope="col">Rate</th></tr></thead>
  <tbody>
    <tr><td>Level I</td><td>$253,100</td></tr>
    <tr><td>Level II</td><td>$228,000</td></tr>
    <tr><td>Level III</td><td>$209,600</td></tr>
    <tr><td>Level IV</td><td>$197,200</td></tr>
    <tr><td>Level V</td><td>$184,900</td></tr>
  </tbody>
</table>
<p class="Footnote">Under a provision in the Continuing Appropriations Act, 2026, the freeze on the payable pay rates continues through January 30, 2026.</p>
</body></html>
"""

BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-dhs", "name": "Department of Homeland Security (DHS)", "type": "Cabinet Department", "children": [
                    # The parenthetical acronym is load-bearing: it is how
                    # positions.py strips the organisation out of the archive's
                    # "DIRECTOR, CYBERSECURITY AND ..." title to match a node
                    # the graph calls "Director, CISA". Same spelling as the
                    # curated file.
                    {"id": "dhs-cisa", "name": "Cybersecurity & Infrastructure Security Agency (CISA)", "type": "Component Agency", "children": [
                        {"id": "cisa-director", "name": "Director, CISA", "type": "Position", "children": []},
                        {"id": "cisa-counsel", "name": "Chief Counsel", "type": "Position", "children": []},
                    ]},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

ARCHIVE_URL = "https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/x.csv"
TABLE_URL = "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx"
EDITION = "Biden Administration (January 21, 2021 - January 20, 2025)"


def listing(**over):
    """A position-evidence record as positions.py writes one."""
    record = {
        "source": "opm_plum_archive", "edition": EDITION,
        "period": "January 21, 2021 - January 20, 2025",
        "listedTitle": "DIRECTOR, CYBERSECURITY AND INFRASTRUCTURE SECURITY AGENCY",
        "listedAgency": "DEPARTMENT OF HOMELAND SECURITY",
        "listedOrganization": "CYBERSECURITY AND INFRASTRUCTURE SECURITY AGENCY",
        "incumbencies": 1, "standing": 1, "status": "Filled", "valuesFrom": "standing_listings",
        "appointmentType": "PAS", "payPlan": "EX", "level": "II", "payLevel": "II",
        "reportedPay": None, "reportedPayText": None, "payPlanAndLevelOnOneRow": True,
        "url": ARCHIVE_URL, "checkedAt": "2026-09-08T19:49:47Z",
        "placement": {"status": "listed", "parentId": "dhs-cisa",
                      "parentListedName": "CYBERSECURITY AND INFRASTRUCTURE SECURITY AGENCY"},
    }
    record.update(over)
    return record


class ParserTestCase(unittest.TestCase):
    def test_it_reads_the_levels_the_rates_the_date_and_the_notes(self):
        table = parse_executive_schedule(PAGE)
        self.assertEqual(table["table"], "Salary Table No. 2026-EX")
        self.assertEqual(table["effectiveText"], "Effective January 2026")
        self.assertEqual(table["effective"], "2026-01-01")
        self.assertEqual(sorted(table["levels"]), sorted(EXECUTIVE_SCHEDULE_LEVELS))
        self.assertEqual(table["levels"]["II"]["amount"], 228_000.0)
        self.assertEqual(table["levels"]["II"]["amountRaw"], "228,000")
        self.assertEqual(table["levels"]["II"]["rowText"], "Level II $228,000")
        self.assertEqual(len(table["footnotes"]), 1)
        self.assertIn("freeze", table["footnotes"][0])

    def test_a_reshaped_table_is_refused_rather_than_read_anyway(self):
        page = PAGE.replace('<th scope="col">Rate</th>', '<th scope="col">Annual Salary</th>')
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)

    def test_an_undated_table_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_executive_schedule(PAGE.replace("<h3>Effective January 2026</h3>", ""))

    def test_an_unnumbered_table_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_executive_schedule(PAGE.replace("<h2>Salary Table No. 2026-EX</h2>", "<h2>Pay</h2>"))

    def test_a_sixth_level_is_refused(self):
        page = PAGE.replace("</tbody>", "<tr><td>Level VI</td><td>$170,000</td></tr></tbody>")
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)

    def test_a_level_printed_twice_is_refused(self):
        page = PAGE.replace("</tbody>", "<tr><td>Level II</td><td>$1</td></tr></tbody>")
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)

    def test_a_rate_that_is_not_a_figure_is_refused(self):
        page = PAGE.replace("<td>$228,000</td>", "<td>see note</td>")
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)

    def test_a_footnote_is_carried_verbatim(self):
        table = parse_executive_schedule(PAGE)
        self.assertEqual(
            table["footnotes"][0],
            "Under a provision in the Continuing Appropriations Act, 2026, the freeze on the "
            "payable pay rates continues through January 30, 2026.",
        )

    def test_an_unclosed_footnote_does_not_swallow_the_prose_after_it(self):
        # HTML5 lets a <p> be closed by the next block element, and html.parser
        # does not model that. A red team spliced unrelated text into the
        # footnote this way — and the panel prints a footnote in quotation
        # marks as OPM's own words, so the splice is a fabricated quotation.
        page = PAGE.replace(
            "continues through January 30, 2026.</p>",
            "continues through January 30, 2026.<p>UNRELATED PROSE ABOUT SOMETHING ELSE.</p>",
        )
        table = parse_executive_schedule(page)
        self.assertNotIn("UNRELATED", " ".join(table["footnotes"]))
        self.assertTrue(table["footnotes"][0].endswith("January 30, 2026."))

    def test_a_heading_below_the_table_does_not_date_it(self):
        # The date is the difference between a current rate and a historical
        # one, so it must be the table's own heading and not any heading that
        # happens to be on the page.
        page = PAGE.replace("<h3>Effective January 2026</h3>", "")
        page = page.replace("</table>", "</table><h3>Effective January 2019</h3>")
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)

    def test_the_nearest_heading_above_the_table_wins(self):
        page = PAGE.replace(
            "<h2>Salary Table No. 2026-EX</h2>",
            "<h2>Salary Table No. 2019-EX</h2><h3>Effective January 2019</h3>"
            "<h2>Salary Table No. 2026-EX</h2>",
        )
        table = parse_executive_schedule(page)
        self.assertEqual(table["table"], "Salary Table No. 2026-EX")
        self.assertEqual(table["effectiveText"], "Effective January 2026")

    def test_a_second_data_table_is_refused_rather_than_merged(self):
        page = PAGE.replace("</body>", """
          <table class="DataTable">
            <thead><tr><th>Level</th><th>Rate</th></tr></thead>
            <tbody><tr><td>Level I</td><td>$1</td></tr></tbody>
          </table></body>""")
        with self.assertRaises(Unreadable):
            parse_executive_schedule(page)


class CommittedArtifactTestCase(unittest.TestCase):
    """The real fetched page, pinned. A silent replacement must fail here."""

    def test_the_committed_table_is_the_one_this_code_was_written_against(self):
        table = parse_executive_schedule(DEFAULT_PAY_TABLE_HTML.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(table["table"], "Salary Table No. 2026-EX")
        self.assertEqual(table["effectiveText"], "Effective January 2026")
        self.assertEqual(
            {k: v["amount"] for k, v in table["levels"].items()},
            {"I": 253_100.0, "II": 228_000.0, "III": 209_600.0, "IV": 197_200.0, "V": 184_900.0},
        )

    def test_the_pay_freeze_note_is_on_the_committed_page(self):
        table = parse_executive_schedule(DEFAULT_PAY_TABLE_HTML.read_text(encoding="utf-8", errors="replace"))
        self.assertTrue(table["footnotes"], "the committed page carries a footnote and the parser found none")
        joined = " ".join(table["footnotes"])
        self.assertIn("freeze on the payable pay rates", joined)
        self.assertIn("Vice President", joined)

    def test_the_gate_mirrors_the_table_it_checks_against(self):
        # The gate is stdlib-only and cannot parse the fixture, so it carries a
        # copy of the rates. A copy that drifts from the page is worse than no
        # check at all: it would authoritatively confirm the wrong figure.
        table = parse_executive_schedule(DEFAULT_PAY_TABLE_HTML.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual({k: v["amount"] for k, v in table["levels"].items()}, EXECUTIVE_SCHEDULE_RATES)
        self.assertEqual(table["table"], EXECUTIVE_SCHEDULE_TABLE)

    def test_the_gate_mirrors_the_dates_and_the_notes_the_panel_prints(self):
        # Every one of these is printed verbatim on the page, so every one of
        # them has to be pinned to the page — including the notes, which the
        # panel prints in quotation marks as the table's own words.
        table = parse_executive_schedule(DEFAULT_PAY_TABLE_HTML.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(table["effective"], EXECUTIVE_SCHEDULE_EFFECTIVE)
        self.assertEqual(table["effectiveText"], EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT)
        self.assertEqual(tuple(table["footnotes"]), EXECUTIVE_SCHEDULE_FOOTNOTES)

    def test_the_gate_mirrors_the_rate_text_the_panel_prints(self):
        table = parse_executive_schedule(DEFAULT_PAY_TABLE_HTML.read_text(encoding="utf-8", errors="replace"))
        for level, rate in EXECUTIVE_SCHEDULE_RATES.items():
            self.assertEqual(table["levels"][level]["rateText"], "${:,.0f}".format(rate))
            self.assertEqual(table["levels"][level]["levelText"], "Level {}".format(level))

    def test_the_loader_refuses_a_fixture_that_is_not_the_file_that_was_served(self):
        tmp = TEST_TMP_ROOT / f"pay-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            page = tmp / "t.html"
            page.write_text(PAGE, encoding="utf-8")
            meta = page.with_name(page.name + ".meta.json")
            meta.write_text(json.dumps({"url": TABLE_URL, "fetched_at": "2026-09-11T03:05:36Z",
                                        "status": 200, "error": None, "sha256": "0" * 64}), encoding="utf-8")
            with self.assertRaises(Unreadable):
                load_executive_schedule(page)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_loader_refuses_a_fetch_that_served_nothing(self):
        tmp = TEST_TMP_ROOT / f"pay-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            import hashlib

            page = tmp / "t.html"
            page.write_text(PAGE, encoding="utf-8")
            digest = hashlib.sha256(page.read_bytes()).hexdigest()
            meta = page.with_name(page.name + ".meta.json")
            meta.write_text(json.dumps({"url": TABLE_URL, "fetched_at": "2026-09-11T03:05:36Z", "status": 403,
                                        "error": "Tunnel connection failed: 403 Forbidden", "sha256": digest}),
                            encoding="utf-8")
            with self.assertRaises(Unreadable):
                load_executive_schedule(page)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_committed_fixture_loads_with_its_recorded_provenance(self):
        loaded = load_executive_schedule()
        self.assertTrue(loaded["url"].startswith("https://www.opm.gov/"))
        self.assertEqual(len(loaded["sha256"]), 64)
        self.assertEqual(loaded["table"]["table"], EXECUTIVE_SCHEDULE_TABLE)


class EligibilityTestCase(unittest.TestCase):
    def setUp(self):
        self.table = parse_executive_schedule(PAGE)

    def test_an_executive_schedule_level_is_priced(self):
        ok, reason = eligible(listing(), self.table)
        self.assertTrue(ok)
        self.assertEqual(reason, "listed_at_an_executive_schedule_level")

    def test_a_general_schedule_grade_is_never_priced_as_a_level(self):
        # The archive files GS grades in the same column as EX levels; one of
        # the graph's own matched positions is a GS-15.
        ok, reason = eligible(listing(payPlan="GS", payLevel="15"), self.table)
        self.assertFalse(ok)
        self.assertEqual(reason, "pay_plan_is_gs_not_executive_schedule")

    def test_a_roman_numeral_on_another_pay_plan_is_refused(self):
        # Live in the data: "THE SECRETARY" carries level III on an AD pay
        # plan and "BOARD MEMBER - CHAIR" carries III on WC. Keying on the
        # numeral alone would price both from the Executive Schedule.
        for plan in ("AD", "WC", "ES", "SL", "OT"):
            ok, reason = eligible(listing(payPlan=plan, payLevel="III"), self.table)
            self.assertFalse(ok, plan)
            self.assertIn("not_executive_schedule", reason)

    def test_a_post_the_archive_states_a_rate_for_is_not_looked_up(self):
        ok, reason = eligible(listing(payLevel=None, reportedPay=225_700.0, reportedPayText="$225,700"), self.table)
        self.assertFalse(ok)
        self.assertEqual(reason, "archive_reports_a_rate")

    def test_a_listing_with_no_pay_plan_is_refused(self):
        # describe_listing leaves payPlan None when the rows disagreed; with no
        # pay plan there is nothing saying this is an Executive Schedule post.
        ok, reason = eligible(listing(payPlan=None), self.table)
        self.assertFalse(ok)
        self.assertEqual(reason, "no_pay_plan_reported")

    def test_a_level_the_table_does_not_print_is_refused(self):
        ok, reason = eligible(listing(payLevel="VII"), self.table)
        self.assertFalse(ok)
        self.assertIn("not_printed", reason)

    def test_a_pay_plan_and_level_assembled_from_two_rows_are_refused(self):
        # describe_listing aggregates payPlan and level independently and
        # ignores blanks, so rows of (EX, no level) and (no pay plan, IV) would
        # report EX and IV although no row printed both. No title in the
        # committed archive does that; the rule is what stops a later archive
        # introducing one silently.
        ok, reason = eligible(listing(payPlanAndLevelOnOneRow=False), self.table)
        self.assertFalse(ok)
        self.assertEqual(reason, "pay_plan_and_level_never_printed_on_one_row")

    def test_a_record_predating_the_co_occurrence_field_is_refused_not_assumed(self):
        record = listing()
        record.pop("payPlanAndLevelOnOneRow")
        ok, _ = eligible(record, self.table)
        self.assertFalse(ok)

    def test_an_arabic_numeral_is_never_read_as_a_roman_one(self):
        for grade in ("1", "5", "15", "2"):
            ok, _ = eligible(listing(payPlan="EX", payLevel=grade), self.table)
            self.assertFalse(ok, grade)


class RecordTestCase(unittest.TestCase):
    def setUp(self):
        self.table = parse_executive_schedule(PAGE)
        self.records, self.report = build_records(
            {"cisa-director": listing(), "cisa-counsel": listing(payPlan="GS", payLevel="15")},
            self.table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-11T03:05:36Z",
        )

    def test_only_the_executive_schedule_post_is_priced(self):
        self.assertEqual(sorted(self.records), ["cisa-director"])
        self.assertEqual(self.report["priced"], 1)
        self.assertEqual(self.report["refused"], {"pay_plan_is_gs_not_executive_schedule": 1})

    def test_the_record_carries_both_sources_with_their_own_dates(self):
        record = self.records["cisa-director"]
        self.assertEqual(record["sourceUrl"], TABLE_URL)
        self.assertEqual(record["retrievedAt"], "2026-09-11T03:05:36Z")
        self.assertEqual(record["levelClaim"]["url"], ARCHIVE_URL)
        self.assertEqual(record["levelClaim"]["checkedAt"], "2026-09-08T19:49:47Z")
        self.assertEqual(record["levelClaim"]["edition"], EDITION)

    def test_the_record_is_a_proxy_and_never_claims_the_source_named_the_unit(self):
        record = self.records["cisa-director"]
        self.assertEqual(record["scopeMatch"], "proxy")
        self.assertEqual(record["amountScope"], "Level II")
        self.assertEqual(record["financialEvidenceStatus"], "partial")

    def test_the_record_is_a_rate_and_not_a_fiscal_year_of_spending(self):
        record = self.records["cisa-director"]
        self.assertEqual(record["costBasis"], "basic_pay")
        self.assertEqual(record["periodCoverage"], "annual_rate")
        self.assertEqual(record["periodAsOf"], "2026-01-01")

    def test_the_footnotes_ride_on_every_record(self):
        self.assertTrue(self.records["cisa-director"]["tableFootnotes"])


class ApplyTestCase(unittest.TestCase):
    def setUp(self):
        self.table = parse_executive_schedule(PAGE)
        self.records, _ = build_records(
            {"cisa-director": listing()}, self.table,
            url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-11T03:05:36Z",
        )

    def _tree(self):
        return json.loads(json.dumps(BASE))

    def _with_listing(self, tree, **over):
        apply_position_evidence(tree, {"cisa-director": listing(**over)})
        return tree

    def test_a_rate_is_published_beside_the_listing_it_rests_on(self):
        tree = self._with_listing(self._tree())
        stats = apply_pay_evidence(tree, self.records)
        self.assertEqual(stats["priced"], 1)
        node = index_tree(tree)[0]["cisa-director"]
        self.assertEqual(node["positionPayRate"]["amount"], 228_000.0)
        self.assertEqual(node["positionPayRate"]["payLevel"], "II")
        self.assertEqual(node["positionPayRate"]["rateText"], "$228,000")
        self.assertTrue(node["positionPayRate"]["footnotes"])

    def test_a_rate_is_not_published_without_the_listing_that_gives_the_level(self):
        # The listing is the only thing asserting this post is at Level II. A
        # rate without it is a figure for a rank nothing says the post holds.
        stats = apply_pay_evidence(self._tree(), self.records)
        self.assertEqual(stats["priced"], 0)
        self.assertEqual(stats["no_listing_published"], 1)

    def test_a_listing_that_now_reports_a_different_level_withdraws_the_rate(self):
        tree = self._with_listing(self._tree(), level="IV", payLevel="IV")
        stats = apply_pay_evidence(tree, self.records)
        self.assertEqual(stats["priced"], 0)
        self.assertEqual(stats["listing_reports_a_different_level"], 1)
        self.assertNotIn("positionPayRate", index_tree(tree)[0]["cisa-director"])

    def test_a_listing_on_another_pay_plan_withdraws_the_rate(self):
        tree = self._with_listing(self._tree(), payPlan="AD")
        stats = apply_pay_evidence(tree, self.records)
        self.assertEqual(stats["priced"], 0)
        self.assertEqual(stats["listing_reports_a_different_level"], 1)

    def test_two_rates_for_one_post_are_refused(self):
        tree = self._with_listing(self._tree(), level="$225,700", payLevel=None,
                                  reportedPay=225_700.0, reportedPayText="$225,700")
        stats = apply_pay_evidence(tree, self.records)
        self.assertEqual(stats["listing_reports_a_rate"], 1)

    def test_a_node_standing_for_many_posts_is_not_given_one_holder_s_rate(self):
        tree = self._with_listing(self._tree())
        index_tree(tree)[0]["cisa-director"]["representsPosts"] = {"kind": "unstated", "text": "×multiple"}
        stats = apply_pay_evidence(tree, self.records)
        self.assertEqual(stats["priced"], 0)
        self.assertEqual(stats["stands_for_many_posts"], 1)

    def test_a_rate_never_lands_on_an_organisation(self):
        records, _ = build_records({"dhs-cisa": listing()}, self.table,
                                   url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-11T03:05:36Z")
        stats = apply_pay_evidence(self._tree(), records)
        self.assertEqual(stats["not_a_position"], 1)

    def test_a_withdrawn_record_leaves_nothing_behind(self):
        tree = self._with_listing(self._tree())
        apply_pay_evidence(tree, self.records)
        self.assertIn("positionPayRate", index_tree(tree)[0]["cisa-director"])
        # The next build: the page module sweeps every owned field first.
        apply_evidence_to_tree(tree, {})
        apply_pay_evidence(tree, {})
        self.assertNotIn("positionPayRate", index_tree(tree)[0]["cisa-director"])

    def test_the_field_is_owned_so_a_retraction_can_reach_the_site(self):
        self.assertIn("positionPayRate", EVIDENCE_OWNED_FIELDS)

    def test_the_table_never_verifies_that_the_post_exists(self):
        # A salary table names a rank, not a post. If it could set
        # verificationMethod or add a source URL, it would raise the node's
        # confidence — 29 positions were briefly published `verified` on
        # exactly that mistake.
        tree = self._tree()
        node = index_tree(tree)[0]["cisa-director"]
        node["sourceUrls"] = ["https://example.gov/a"]
        self._with_listing(tree)
        before = list(index_tree(tree)[0]["cisa-director"].get("sourceUrls") or [])
        method_before = index_tree(tree)[0]["cisa-director"].get("verificationMethod")
        apply_pay_evidence(tree, self.records)
        after = index_tree(tree)[0]["cisa-director"]
        self.assertEqual(list(after.get("sourceUrls") or []), before)
        self.assertEqual(after.get("verificationMethod"), method_before)
        self.assertNotIn(TABLE_URL, after.get("sourceUrls") or [])


class ScriptAndGateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TEST_TMP_ROOT / f"pay-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.positions = self.tmp / "position_evidence.json"
        self.positions.write_text(json.dumps({"nodes": {"cisa-director": listing()}}), encoding="utf-8")
        self.out = self.tmp / "pay_evidence.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _derive(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_pay_evidence.main([
                "d", "--base-graph", str(self.base), "--positions", str(self.positions),
                "--out", str(self.out), *extra,
            ])
        return code, buf.getvalue()

    def _build(self):
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=False,
            enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=None, headcount_evidence_path=None,
            position_evidence_path=self.positions, pay_evidence_path=self.out,
        )

    def _gate(self, path):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = gate_main(["gate", str(path)])
        return code, buf.getvalue()

    def test_the_script_derives_the_build_publishes_and_the_gate_passes(self):
        code, out = self._derive()
        self.assertEqual(code, 0, out)
        store = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(len(store["nodes"]), 1)
        self.assertEqual(store["source"]["table"], EXECUTIVE_SCHEDULE_TABLE)

        result = self._build()
        self.assertEqual(result.validation["pay_evidence"]["priced"], 1)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["cisa-director"]
        self.assertEqual(node["positionPayRate"]["amount"], 228_000.0)

        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("salary table         : 1 positions priced from Salary Table No. 2026-EX", out)

    def test_a_multi_post_node_is_not_priced_by_a_real_build(self):
        # The unit-level guard in apply_pay_evidence is not enough and this is
        # the test that says so: representsPosts is computed by
        # annotate_stated_counts, which runs AFTER the pay application, so on a
        # fresh build the guard tests a field that does not exist yet. A red
        # team published a rate on a node named "... (×4)" with the run record
        # reporting stands_for_many_posts: 0. Asserted through build_graph
        # rather than against the function, because the defect was the order.
        base = json.loads(json.dumps(BASE))
        index_tree(base)[0]["cisa-director"]["name"] = "Director, CISA (×4)"
        self.base.write_text(json.dumps(base), encoding="utf-8")
        code, out = self._derive()
        self.assertEqual(code, 0, out)
        result = self._build()
        node = index_tree(json.loads(result.graph_path.read_text(encoding="utf-8")))[0]["cisa-director"]
        self.assertTrue(node.get("representsPosts"), "the fixture no longer states a count")
        self.assertNotIn("positionPayRate", node)
        self.assertEqual(result.validation["pay_evidence"]["stands_for_many_posts"], 1)

    def test_dry_run_writes_nothing(self):
        code, out = self._derive("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.out.exists())

    def _corrupt(self, **fields):
        """Publish a graph whose pay block has been tampered with."""
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        block = index_tree(graph)[0]["cisa-director"]["positionPayRate"]
        for key, value in fields.items():
            if value is None:
                block.pop(key, None)
            else:
                block[key] = value
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return self._gate(path)

    def test_the_gate_refuses_a_figure_the_table_does_not_print(self):
        code, out = self._corrupt(amount=290_600.0, rateText="$290,600")
        self.assertEqual(code, 1, out)
        self.assertIn("which the table pays", out)

    def test_the_gate_refuses_a_printed_text_that_disagrees_with_the_number(self):
        code, out = self._corrupt(rateText="$253,100")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_level_the_schedule_does_not_have(self):
        code, out = self._corrupt(payLevel="VII")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_rate_on_another_pay_plan(self):
        code, out = self._corrupt(payPlan="AD")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_level_its_listing_does_not_report(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["cisa-director"]
        node["positionListing"]["payLevel"] = "IV"
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("its listing reports", out)

    def test_the_gate_refuses_a_rate_with_no_listing_behind_it(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        index_tree(graph)[0]["cisa-director"].pop("positionListing")
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("no position listing", out)

    def test_the_gate_refuses_one_post_s_rate_on_a_node_standing_for_many(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        index_tree(graph)[0]["cisa-director"]["representsPosts"] = {"kind": "unstated", "text": "×multiple"}
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("stands for several posts", out)

    def test_the_gate_refuses_a_dropped_footnote(self):
        code, out = self._corrupt(footnotes=[])
        self.assertEqual(code, 1, out)
        self.assertIn("without the notes the table prints", out)

    # The panel prints amountScope, rateText, effectiveText and the footnotes
    # verbatim. A gate that checked only the machine-readable amount would
    # vouch for a figure while the sentence beside it said something else.
    def test_the_gate_refuses_a_rate_attributed_to_the_wrong_level(self):
        code, out = self._corrupt(amountScope="Level I")
        self.assertEqual(code, 1, out)
        self.assertIn("while pricing level", out)

    def test_the_gate_refuses_text_riding_along_with_the_printed_rate(self):
        # "$228,000 per month" is digit-identical to the annual rate and
        # twelve times the claim.
        code, out = self._corrupt(rateText="$228,000 per month")
        self.assertEqual(code, 1, out)
        self.assertIn("the table prints", out)

    def test_the_gate_refuses_an_effective_heading_that_is_not_the_pages(self):
        code, out = self._corrupt(effectiveText="Effective January 2031")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_fabricated_note_attributed_to_the_table(self):
        code, out = self._corrupt(footnotes=[
            "The table's rates are payable in full to every Executive Schedule appointee; no pay freeze applies."])
        self.assertEqual(code, 1, out)
        self.assertIn("quotes notes the table does not carry", out)

    def test_the_gate_refuses_a_rate_from_another_table(self):
        code, out = self._corrupt(table="Salary Table No. 2025-EX")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_rate_with_no_effective_date(self):
        code, out = self._corrupt(effective=None)
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_rate_that_does_not_say_which_archive_gave_the_level(self):
        code, out = self._corrupt(levelSource={"edition": "", "url": ""})
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_future_retrieval_date(self):
        code, out = self._corrupt(checkedAt="2099-01-01T00:00:00Z")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_salary_table_used_as_proof_the_post_exists(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["cisa-director"]
        node["verificationMethod"] = node["positionPayRate"]["method"]
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_rate_of_pay_dressed_as_a_measured_cost(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["cisa-director"]
        node["cost_status"] = "official"
        node["costVerificationStatus"] = "verified"
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)

    def test_a_withdrawn_listing_takes_the_rate_off_the_published_graph(self):
        # The retraction has to reach the site: the previous graph.json is
        # re-fed as a payload on the next build, and a field outside
        # EVIDENCE_OWNED_FIELDS would survive as a fossil.
        self._derive()
        self._build()
        self.positions.write_text(json.dumps({"nodes": {}}), encoding="utf-8")
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=True,
            existing_graph_payload_path=self.tmp / "graph.json",
            enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=None, headcount_evidence_path=None,
            position_evidence_path=self.positions, pay_evidence_path=self.out,
        )
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["cisa-director"]
        self.assertNotIn("positionPayRate", node)
        self.assertNotIn("positionListing", node)


if __name__ == "__main__":
    unittest.main()
