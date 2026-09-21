"""OPM's General Schedule, SES and SL/ST tables, the pay plan they are looked up
by, and every way the join could publish something false.

Both directions throughout: an honest range is published, and each way of
forging one is refused. The attacks are the ones the data makes possible -- a
General Schedule grade priced from the wrong row, a range published where the
archive states a rate, a listing that has since moved to another grade, a
figure that is not the one the table prints, a SL/ST range citing the SES
table (identical figures, different document), a range dressed as a rate or a
cost, and a GS table whose only statement of scale -- the currency mark on
grade 1 -- is missing.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import unittest
import uuid
import zlib
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.gs_pay import (
    DEFAULT_GS_HTML,
    DEFAULT_GS_PDF,
    DEFAULT_SES_HTML,
    DEFAULT_SLST_HTML,
    GENERAL_SCHEDULE_GRADES,
    GS_BASE_BEFORE_LOCALITY,
    KIND_GS,
    KIND_SES,
    KIND_SLST,
    Unreadable,
    apply_grade_pay,
    build_records,
    eligible,
    load_all_tables,
    load_general_schedule,
    load_pay_structure,
    parse_general_schedule_html,
    parse_general_schedule_pdf,
    parse_pay_structure_table,
)
from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes
from data_pipeline.verification.positions import apply_position_evidence
from scripts import derive_gs_pay_evidence
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_FOOTNOTES,
    GENERAL_SCHEDULE_BASE_BEFORE_LOCALITY,
    GENERAL_SCHEDULE_EFFECTIVE,
    GENERAL_SCHEDULE_EFFECTIVE_TEXT,
    GENERAL_SCHEDULE_RANGES,
    GENERAL_SCHEDULE_TABLE,
    GRADE_PAY_FIXTURES,
    PAY_STRUCTURE_TABLES,
)
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ID = "the-constitution-of-the-united-states"

# ---------------------------------------------------------------------------
# Synthetic renderings of a GS table, for the parser tests. The figures are
# invented, so nothing here is checked against the gate's mirror; the
# committed fixtures are checked against it in CommittedArtifactTestCase.


def synthetic_steps(grade: int) -> list[int]:
    base = 20_000 + grade * 5_000
    return [base + step * 700 for step in range(10)]


def gs_pdf_blocks(*, mark_first_row: bool = True, grades=None, heads=None, headings=None) -> list[str]:
    grades = list(GENERAL_SCHEDULE_GRADES) if grades is None else grades
    heads = ["Grade"] + [f"Step {n}" for n in range(1, 11)] + ["WITHIN GRADE AMOUNTS"] if heads is None else heads
    headings = ["Salary Table 2026-GS", "Incorporating the 1% General Schedule Increase",
                "Effective January 2026", "Annual Rates by Grade and Step"] if headings is None else headings
    blocks = list(headings) + list(heads)
    for index, grade in enumerate(grades):
        blocks.append(f"{grade} ")
        for step in synthetic_steps(int(grade)):
            text = f"{step:,}"
            blocks.append((f"$  {text} " if index == 0 and mark_first_row else f"   {text} "))
        blocks.append("VARIES " if index == 0 else f"   {700:,} ")
    return blocks


def make_pdf(blocks: list[str]) -> bytes:
    content = b"".join(b"BT (" + t.encode("latin-1") + b") Tj ET\n" for t in blocks)
    stream = zlib.compress(content)
    return (b"%PDF-1.7\n1 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
            + stream + b"\nendstream\nendobj\n%%EOF\n")


def gs_html(grades=None, *, headings=None) -> str:
    grades = list(GENERAL_SCHEDULE_GRADES) if grades is None else grades
    headings = ["Salary Table 2026-GS", "Incorporating the 1% General Schedule Increase",
                "Effective January 2026", "Annual Rates by Grade and Step"] if headings is None else headings
    rows = []
    for grade in grades:
        cells = "".join(f"<td><p>{s}</p></td>" for s in synthetic_steps(int(grade)))
        rows.append(f'<tr><th scope="col">{grade}</th>{cells}<td>VARIES</td></tr>')
    heads = "".join(f'<th scope="col">{h}</th>' for h in ["Grade"] + [f"Step&nbsp;{n}" for n in range(1, 11)] + ["WGI"])
    paras = "".join(f"<p>{h}</p>" for h in headings)
    return f'<html><body><div>{paras}<table class="DataTable"><thead><tr>{heads}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></body></html>'


STRUCTURE_PAGE = """
<html><body>
<h2>Salary Table No. 2026-ES</h2>
<p>Rates of Basic Pay for Members of the Senior Executive Service (SES)</p>
<h3>Effective January 2026</h3>
<table class="DataTable">
  <thead><tr><th scope="col">Structure of the SES Pay System</th><th scope="col">Minimum</th><th scope="col">Maximum</th></tr></thead>
  <tbody>
    <tr><td>Agencies with a Certified SES Performance Appraisal System</td><td>$151,661</td><td>$228,000</td></tr>
    <tr><td>Agencies without a Certified SES Performance Appraisal System</td><td>$151,661</td><td>$209,600</td></tr>
  </tbody>
</table>
<p class="Footnote">Under a provision in the Continuing Appropriations Act, 2026, the freeze continues through January 30, 2026.</p>
</body></html>
"""

BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-ed", "name": "Department of Education (ED)", "type": "Cabinet Department", "children": [
                    {"id": "ed-ocr", "name": "Office for Civil Rights", "type": "Office", "children": [
                        {"id": "ed-ocr-das", "name": "Deputy Assistant Secretary", "type": "Position", "children": []},
                        {"id": "ed-ocr-director", "name": "Enforcement Director", "type": "Position", "children": []},
                        {"id": "ed-ocr-scientist", "name": "Senior Scientist", "type": "Position", "children": []},
                    ]},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

ARCHIVE_URL = "https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/x.csv"
EDITION = "Biden Administration (January 21, 2021 - January 20, 2025)"


def listing(**over):
    """A position-evidence record as positions.py writes one: a GS-15 post."""
    record = {
        "source": "opm_plum_archive", "edition": EDITION,
        "period": "January 21, 2021 - January 20, 2025",
        "listedTitle": "DEPUTY ASSISTANT SECRETARY",
        "listedAgency": "DEPARTMENT OF EDUCATION",
        "listedOrganization": "OFFICE FOR CIVIL RIGHTS",
        "incumbencies": 1, "standing": 1, "status": "Filled", "valuesFrom": "standing_listings",
        "appointmentType": "NA", "payPlan": "GS", "level": "15", "payLevel": "15",
        "reportedPay": None, "reportedPayText": None, "payPlanAndLevelOnOneRow": True,
        "url": ARCHIVE_URL, "checkedAt": "2026-09-08T19:49:47Z",
        "placement": {"status": "listed", "parentId": "ed-ocr", "parentListedName": "OFFICE FOR CIVIL RIGHTS"},
    }
    record.update(over)
    return record


def ses_listing(**over):
    fields = dict(listedTitle="ENFORCEMENT DIRECTOR", appointmentType="CA", payPlan="ES", level="",
                  payLevel=None, payPlanAndLevelOnOneRow=False)
    fields.update(over)
    return listing(**fields)


def sl_listing(**over):
    fields = dict(listedTitle="SENIOR SCIENTIST", appointmentType="XS", payPlan="SL", level="",
                  payLevel=None, payPlanAndLevelOnOneRow=False)
    fields.update(over)
    return listing(**fields)


LISTINGS = {"ed-ocr-das": listing(), "ed-ocr-director": ses_listing(), "ed-ocr-scientist": sl_listing()}


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


# ---------------------------------------------------------------------------


class GeneralSchedulePdfParserTestCase(unittest.TestCase):
    def test_it_reads_the_table_the_date_the_grades_and_the_column_heads(self):
        table = parse_general_schedule_pdf(make_pdf(gs_pdf_blocks()))
        self.assertEqual(table["table"], "Salary Table 2026-GS")
        self.assertEqual(table["effectiveText"], "Effective January 2026")
        self.assertEqual(table["effective"], "2026-01-01")
        self.assertEqual(set(table["grades"]), set(GENERAL_SCHEDULE_GRADES))
        self.assertEqual(table["grades"]["15"]["minimum"], float(synthetic_steps(15)[0]))
        self.assertEqual(table["grades"]["15"]["maximum"], float(synthetic_steps(15)[-1]))
        self.assertEqual(len(table["grades"]["15"]["steps"]), 10)
        # The column heads are grade 1's marked figures, one per step.
        self.assertEqual(table["columnHeads"]["Step 1"]["text"], f"$  {synthetic_steps(1)[0]:,}")
        self.assertEqual(table["columnHeads"]["Step 10"]["amountRaw"], f"{synthetic_steps(1)[-1]:,}")
        self.assertEqual(table["footnotes"], [])

    def test_a_first_row_without_the_currency_mark_is_refused(self):
        # The mark on grade 1 is the only statement of scale on the page.
        with self.assertRaises(Unreadable) as ctx:
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(mark_first_row=False)))
        self.assertIn("no currency mark", str(ctx.exception))

    def test_a_missing_grade_is_refused(self):
        grades = [g for g in GENERAL_SCHEDULE_GRADES if g != "7"]
        with self.assertRaises(Unreadable):
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(grades=grades)))

    def test_grades_out_of_order_are_refused(self):
        grades = list(GENERAL_SCHEDULE_GRADES)
        grades[3], grades[4] = grades[4], grades[3]
        with self.assertRaises(Unreadable) as ctx:
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(grades=grades)))
        self.assertIn("not in order", str(ctx.exception))

    def test_reshaped_column_heads_are_refused(self):
        heads = ["Grade"] + [f"Step {n}" for n in range(1, 10)] + ["Step 11", "WGI"]
        with self.assertRaises(Unreadable) as ctx:
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(heads=heads)))
        self.assertIn("reshaped", str(ctx.exception))

    def test_an_undated_table_is_refused(self):
        headings = ["Salary Table 2026-GS", "Incorporating the 1% General Schedule Increase", "Annual Rates by Grade and Step"]
        with self.assertRaises(Unreadable):
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(headings=headings)))

    def test_the_hourly_table_is_not_read_as_the_annual_one(self):
        headings = ["Salary Table 2026-GS", "Incorporating the 1% General Schedule Increase",
                    "Effective January 2026", "Hourly Basic (B) Rates by Grade and Step"]
        with self.assertRaises(Unreadable) as ctx:
            parse_general_schedule_pdf(make_pdf(gs_pdf_blocks(headings=headings)))
        self.assertIn("Annual Rates", str(ctx.exception))

    def test_a_step_1_above_step_10_is_refused(self):
        blocks = gs_pdf_blocks()
        # grade 2's row starts after 4 headings + 12 heads + 12 cells
        start = 4 + 12 + 12
        blocks[start + 1], blocks[start + 10] = blocks[start + 10], blocks[start + 1]
        with self.assertRaises(Unreadable) as ctx:
            parse_general_schedule_pdf(make_pdf(blocks))
        self.assertIn("not a range", str(ctx.exception))

    def test_an_encrypted_pdf_is_refused(self):
        raw = make_pdf(gs_pdf_blocks()).replace(b"1 0 obj", b"/Encrypt 1 0 obj")
        with self.assertRaises(Unreadable):
            parse_general_schedule_pdf(raw)

    def test_a_file_that_is_not_a_pdf_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_general_schedule_pdf(b"<html>not a pdf</html>")


class GeneralScheduleHtmlParserTestCase(unittest.TestCase):
    def test_it_reads_the_same_figures(self):
        page = parse_general_schedule_html(gs_html())
        self.assertEqual(page["table"], "Salary Table 2026-GS")
        self.assertEqual(page["effectiveText"], "Effective January 2026")
        self.assertEqual(page["grades"]["15"], [float(s) for s in synthetic_steps(15)])

    def test_a_reshaped_html_table_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_general_schedule_html(gs_html().replace(">WGI<", ">Locality<"))

    def test_a_missing_grade_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_general_schedule_html(gs_html(grades=[g for g in GENERAL_SCHEDULE_GRADES if g != "3"]))


class StructureTableParserTestCase(unittest.TestCase):
    def test_it_reads_both_rows_and_the_note(self):
        table = parse_pay_structure_table(STRUCTURE_PAGE, expected_suffix="ES")
        self.assertEqual(table["table"], "Salary Table No. 2026-ES")
        self.assertEqual(table["minimum"], 151_661.0)
        self.assertEqual(table["maximum"], 228_000.0)
        self.assertEqual([r["maximum"] for r in table["rows"]], [228_000.0, 209_600.0])
        self.assertEqual(len(table["footnotes"]), 1)

    def test_the_ses_page_cannot_be_read_as_the_sl_st_table(self):
        with self.assertRaises(Unreadable) as ctx:
            parse_pay_structure_table(STRUCTURE_PAGE, expected_suffix="SL/ST")
        self.assertIn("not the SL/ST table", str(ctx.exception))

    def test_a_bound_without_its_currency_mark_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_pay_structure_table(STRUCTURE_PAGE.replace("<td>$228,000</td>", "<td>228,000</td>"), expected_suffix="ES")

    def test_a_third_row_is_refused(self):
        page = STRUCTURE_PAGE.replace("</tbody>", "<tr><td>Agencies with something else</td><td>$1</td><td>$2</td></tr></tbody>")
        with self.assertRaises(Unreadable):
            parse_pay_structure_table(page, expected_suffix="ES")

    def test_rows_disagreeing_on_the_minimum_are_refused(self):
        page = STRUCTURE_PAGE.replace("<td>$151,661</td><td>$209,600</td>", "<td>$150,000</td><td>$209,600</td>")
        with self.assertRaises(Unreadable):
            parse_pay_structure_table(page, expected_suffix="ES")

    def test_a_reshaped_table_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_pay_structure_table(STRUCTURE_PAGE.replace(">Maximum<", ">Rate<"), expected_suffix="ES")


class CommittedArtifactTestCase(unittest.TestCase):
    """The committed fixtures load with their recorded provenance, and the
    gate's mirror is what they print."""

    @classmethod
    def setUpClass(cls):
        cls.tables = load_all_tables()

    def test_the_gate_mirrors_the_general_schedule_both_renderings_print(self):
        gs = self.tables[KIND_GS]["table"]
        parsed = {g: (r["minimum"], r["maximum"]) for g, r in gs["grades"].items()}
        self.assertEqual(parsed, GENERAL_SCHEDULE_RANGES)
        self.assertEqual(gs["table"], GENERAL_SCHEDULE_TABLE)
        self.assertEqual(gs["effective"], GENERAL_SCHEDULE_EFFECTIVE)
        self.assertEqual(gs["effectiveText"], GENERAL_SCHEDULE_EFFECTIVE_TEXT)
        self.assertEqual(GS_BASE_BEFORE_LOCALITY, GENERAL_SCHEDULE_BASE_BEFORE_LOCALITY)
        # The HTML rendering agrees, independently of the loader's own check.
        html = parse_general_schedule_html(DEFAULT_GS_HTML.read_text(encoding="utf-8"))
        self.assertEqual({g: (v[0], v[-1]) for g, v in html["grades"].items()}, GENERAL_SCHEDULE_RANGES)

    def test_the_gate_mirrors_the_structure_tables(self):
        for kind in (KIND_SES, KIND_SLST):
            table = self.tables[kind]["table"]
            mirror = PAY_STRUCTURE_TABLES[kind]
            self.assertEqual(table["table"], mirror["table"])
            self.assertEqual([(r["label"], r["minimum"], r["maximum"]) for r in table["rows"]], list(mirror["rows"]))
            self.assertEqual(tuple(table["footnotes"]), EXECUTIVE_SCHEDULE_FOOTNOTES)
            self.assertEqual(table["effectiveText"], GENERAL_SCHEDULE_EFFECTIVE_TEXT)

    def test_the_gate_names_the_committed_fixtures(self):
        self.assertEqual(GRADE_PAY_FIXTURES[KIND_GS], (DEFAULT_GS_PDF, DEFAULT_GS_HTML))
        self.assertEqual(GRADE_PAY_FIXTURES[KIND_SES], (DEFAULT_SES_HTML,))
        self.assertEqual(GRADE_PAY_FIXTURES[KIND_SLST], (DEFAULT_SLST_HTML,))
        for paths in GRADE_PAY_FIXTURES.values():
            for path in paths:
                meta = json.loads(path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"], path.name)
                self.assertEqual(meta["status"], 200)
                self.assertEqual(meta["final_url"].rstrip("/"), meta["url"].rstrip("/"), path.name)

    def test_the_gs_pdf_prints_the_mark_on_grade_1_only(self):
        # The whole reason for the fourth scale rule: the PDF marks each
        # column once, at its head. If OPM ever marks every row, the stronger
        # rule takes over by itself; if it marks none, the parser refuses.
        gs = self.tables[KIND_GS]["table"]
        self.assertTrue(gs["grades"]["1"]["minimumText"].startswith("$"))
        self.assertFalse(gs["grades"]["15"]["minimumText"].startswith("$"))

    def test_the_loader_refuses_a_fixture_that_is_not_the_file_that_was_served(self):
        tmp = TEST_TMP_ROOT / f"gs-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            for src in (DEFAULT_GS_PDF, DEFAULT_GS_HTML):
                shutil.copy(src, tmp / src.name)
                shutil.copy(src.with_name(src.name + ".meta.json"), tmp / (src.name + ".meta.json"))
            (tmp / DEFAULT_GS_HTML.name).write_bytes((tmp / DEFAULT_GS_HTML.name).read_bytes().replace(b"126384", b"126385"))
            with self.assertRaises(Unreadable) as ctx:
                load_general_schedule(tmp / DEFAULT_GS_PDF.name, tmp / DEFAULT_GS_HTML.name)
            self.assertIn("does not match the digest", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_loader_refuses_two_renderings_that_disagree(self):
        tmp = TEST_TMP_ROOT / f"gs-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            for src in (DEFAULT_GS_PDF, DEFAULT_GS_HTML):
                shutil.copy(src, tmp / src.name)
                shutil.copy(src.with_name(src.name + ".meta.json"), tmp / (src.name + ".meta.json"))
            page = tmp / DEFAULT_GS_HTML.name
            raw = page.read_bytes().replace(b"126384", b"126385")
            page.write_bytes(raw)
            meta_path = tmp / (DEFAULT_GS_HTML.name + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(raw).hexdigest()
            meta["bytes"] = len(raw)
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(Unreadable) as ctx:
                load_general_schedule(tmp / DEFAULT_GS_PDF.name, page)
            self.assertIn("disagree", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_loader_refuses_a_fetch_that_landed_somewhere_else(self):
        # The first attempt at the SES table "succeeded" with a 200 by
        # redirecting to OPM's homepage. That is not the table.
        tmp = TEST_TMP_ROOT / f"gs-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy(DEFAULT_SES_HTML, tmp / DEFAULT_SES_HTML.name)
            meta_path = tmp / (DEFAULT_SES_HTML.name + ".meta.json")
            meta = json.loads(DEFAULT_SES_HTML.with_name(DEFAULT_SES_HTML.name + ".meta.json").read_text(encoding="utf-8"))
            meta["final_url"] = "https://www.opm.gov/"
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(Unreadable) as ctx:
                load_pay_structure(tmp / DEFAULT_SES_HTML.name, kind=KIND_SES)
            self.assertIn("redirect", str(ctx.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_sl_st_fixture_cannot_be_loaded_as_the_ses_table(self):
        with self.assertRaises(Unreadable):
            load_pay_structure(DEFAULT_SLST_HTML, kind=KIND_SES)


class EligibilityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = {k: v["table"] for k, v in load_all_tables().items()}

    def test_a_general_schedule_grade_is_ranged(self):
        self.assertEqual(eligible(listing(), self.tables), (True, "listed_at_a_general_schedule_grade"))

    def test_an_ses_listing_without_a_rate_is_ranged(self):
        self.assertEqual(eligible(ses_listing(), self.tables), (True, "listed_on_the_senior_executive_service_pay_plan"))

    def test_sl_and_st_share_the_sl_st_table(self):
        self.assertTrue(eligible(sl_listing(), self.tables)[0])
        self.assertTrue(eligible(sl_listing(payPlan="ST"), self.tables)[0])

    def test_the_archives_own_rate_wins(self):
        ok, reason = eligible(ses_listing(reportedPay=225_700.0, reportedPayText="$225,700", level="$225,700"), self.tables)
        self.assertFalse(ok)
        self.assertEqual(reason, "archive_reports_a_rate")

    def test_an_executive_schedule_level_is_not_ranged_here(self):
        ok, reason = eligible(listing(payPlan="EX", level="IV", payLevel="IV"), self.tables)
        self.assertFalse(ok)
        self.assertEqual(reason, "pay_plan_ex_has_no_table_here")

    def test_a_pay_plan_with_no_table_is_refused_by_name(self):
        self.assertEqual(eligible(listing(payPlan="AD", level="III", payLevel="III"), self.tables)[1], "pay_plan_ad_has_no_table_here")

    def test_a_gs_listing_with_no_grade_is_refused(self):
        self.assertEqual(eligible(listing(level="", payLevel=None), self.tables)[1], "no_grade_reported")

    def test_a_grade_the_table_does_not_print_is_refused(self):
        self.assertEqual(eligible(listing(level="16", payLevel="16"), self.tables)[1], "grade_16_is_not_printed_in_this_table")

    def test_a_pay_plan_and_grade_from_two_rows_are_refused(self):
        self.assertEqual(eligible(listing(payPlanAndLevelOnOneRow=False), self.tables)[1], "pay_plan_and_grade_never_printed_on_one_row")

    def test_an_ses_listing_carrying_a_level_is_refused(self):
        # The SES has no levels; a row printing one is a row this module does
        # not understand, and three such rows exist in the current export.
        ok, reason = eligible(ses_listing(level="IV", payLevel="IV"), self.tables)
        self.assertFalse(ok)
        self.assertEqual(reason, "senior_executive_service_listing_carries_a_level")

    def test_a_listing_with_no_pay_plan_is_refused(self):
        self.assertEqual(eligible(listing(payPlan=None), self.tables)[1], "no_pay_plan_reported")


class RecordTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_all_tables()
        cls.records, cls.report = build_records(LISTINGS, cls.tables)
        cls.nodes = index_tree(json.loads(json.dumps(BASE)))[0]

    def test_every_listing_with_a_table_is_ranged(self):
        self.assertEqual(set(self.records), set(LISTINGS))
        self.assertEqual(self.report["ranged_by_kind"], {KIND_GS: 1, KIND_SES: 1, KIND_SLST: 1})

    def test_a_gs_record_is_a_range_of_the_grades_own_row_before_locality(self):
        record = self.records["ed-ocr-das"]
        self.assertEqual(record["grade"], "15")
        self.assertEqual((record["minimum"], record["maximum"]), GENERAL_SCHEDULE_RANGES["15"])
        self.assertEqual(record["baseBeforeLocality"], GS_BASE_BEFORE_LOCALITY)
        self.assertEqual(record["scopeMatch"], "proxy")
        self.assertIn("126,384", record["quote"])
        self.assertIn("164,301", record["quote"])

    def test_the_gs_record_cites_the_pdf_and_carries_the_html_as_corroboration(self):
        record = self.records["ed-ocr-das"]
        self.assertTrue(record["sourceUrl"].endswith("/pdf/2026/GS.pdf"))
        self.assertEqual(record["documentSha256"], hashlib.sha256(DEFAULT_GS_PDF.read_bytes()).hexdigest())
        self.assertEqual(record["corroboration"]["sha256"], hashlib.sha256(DEFAULT_GS_HTML.read_bytes()).hexdigest())

    def test_every_bound_validates_and_grades_partial(self):
        for node_id, record in self.records.items():
            for name, bound in record["bounds"].items():
                out = fe.validate_record(bound, self.nodes[node_id])
                self.assertEqual(fe.classify(out), "partial", (node_id, name))

    def test_a_gs_bound_beneath_the_first_row_rests_on_the_columns_first_figure(self):
        out = fe.validate_record(self.records["ed-ocr-das"]["bounds"]["minimum"], self.nodes["ed-ocr-das"])
        self.assertEqual(out["unitsEvidenceKind"], "currency_mark_on_the_columns_first_figure")

    def test_a_grade_1_bound_rests_on_its_own_printed_mark(self):
        # Grade 1 IS the column head; its figure carries the mark itself, so
        # the stronger rule applies and the weaker one is never recorded.
        records, _ = build_records({"ed-ocr-das": listing(level="1", payLevel="1")}, self.tables)
        out = fe.validate_record(records["ed-ocr-das"]["bounds"]["minimum"], self.nodes["ed-ocr-das"])
        self.assertEqual(out["unitsEvidenceKind"], "currency_mark_on_the_printed_figure")

    def test_a_structure_bound_rests_on_its_own_printed_mark(self):
        out = fe.validate_record(self.records["ed-ocr-director"]["bounds"]["maximumWithCertifiedSystem"], self.nodes["ed-ocr-director"])
        self.assertEqual(out["unitsEvidenceKind"], "currency_mark_on_the_printed_figure")
        self.assertEqual(out["amount"], 228_000.0)

    def test_a_structure_record_carries_both_rows_and_the_note(self):
        record = self.records["ed-ocr-director"]
        self.assertEqual([r["maximum"] for r in record["rows"]], [228_000.0, 209_600.0])
        self.assertEqual((record["minimum"], record["maximum"]), (151_661.0, 228_000.0))
        self.assertEqual(tuple(record["tableFootnotes"]), EXECUTIVE_SCHEDULE_FOOTNOTES)
        self.assertNotIn("baseBeforeLocality", record)

    def test_the_sl_record_cites_the_sl_st_table_not_the_ses_one(self):
        self.assertEqual(self.records["ed-ocr-scientist"]["table"], "Salary Table No. 2026-SL/ST")
        self.assertEqual(self.records["ed-ocr-director"]["table"], "Salary Table No. 2026-ES")

    def test_a_bound_on_an_organisation_is_refused_by_the_validator(self):
        org = {"id": "ed-ocr-das", "name": "Deputy Assistant Secretary", "type": "Office"}
        with self.assertRaises(fe.Rejected):
            fe.validate_record(self.records["ed-ocr-das"]["bounds"]["minimum"], org)


def validated_records(records, nodes):
    """What the derive script writes: every bound through the validator."""
    out = {}
    for node_id, record in records.items():
        kept = json.loads(json.dumps(record))
        kept["bounds"] = {name: fe.validate_record(bound, nodes[node_id]) for name, bound in record["bounds"].items()}
        out[node_id] = kept
    return out


class ApplyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_all_tables()
        raw, _ = build_records(LISTINGS, cls.tables)
        cls.raw_records = raw
        cls.records = validated_records(raw, index_tree(json.loads(json.dumps(BASE)))[0])

    def _tree(self):
        return json.loads(json.dumps(BASE))

    def test_a_record_that_never_went_through_the_validator_is_refused(self):
        # unitsEvidenceKind is written by validate_record and nothing else;
        # a record without it on every bound is a hand-edited or stale file.
        tree = self._with_listings(self._tree())
        stats = apply_grade_pay(tree, self.raw_records)
        self.assertEqual(stats["ranged"], 0)
        self.assertEqual(stats["bounds_not_validated"], 3)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-das"])

    def _with_listings(self, tree, **over):
        records = dict(LISTINGS)
        records.update(over)
        apply_position_evidence(tree, records)
        return tree

    def test_a_range_is_published_beside_the_listing_it_rests_on(self):
        tree = self._with_listings(self._tree())
        stats = apply_grade_pay(tree, self.records)
        self.assertEqual(stats["ranged"], 3)
        node = index_tree(tree)[0]["ed-ocr-das"]
        block = node["positionGradePay"]
        self.assertEqual(block["kind"], KIND_GS)
        self.assertEqual(block["grade"], "15")
        self.assertEqual((block["minimum"], block["maximum"]), GENERAL_SCHEDULE_RANGES["15"])
        self.assertEqual((block["minimumPrinted"], block["maximumPrinted"]), ("126,384", "164,301"))
        self.assertEqual(block["baseBeforeLocality"], GS_BASE_BEFORE_LOCALITY)
        self.assertEqual(block["unitsEvidenceKind"], "currency_mark_on_the_columns_first_figure")
        self.assertEqual(len(block["steps"]), 10)
        ses = index_tree(tree)[0]["ed-ocr-director"]["positionGradePay"]
        self.assertEqual(ses["kind"], KIND_SES)
        self.assertEqual(len(ses["rows"]), 2)
        self.assertNotIn("baseBeforeLocality", ses)

    def test_a_range_is_not_published_without_the_listing(self):
        tree = self._tree()
        stats = apply_grade_pay(tree, self.records)
        self.assertEqual(stats["ranged"], 0)
        self.assertEqual(stats["no_listing_published"], 3)

    def test_a_listing_now_at_another_grade_withdraws_the_range(self):
        tree = self._with_listings(self._tree(), **{"ed-ocr-das": listing(level="14", payLevel="14")})
        stats = apply_grade_pay(tree, self.records)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-das"])
        self.assertEqual(stats["listing_reports_a_different_plan_or_grade"], 1)

    def test_a_listing_now_on_another_pay_plan_withdraws_the_range(self):
        tree = self._with_listings(self._tree(), **{"ed-ocr-director": ses_listing(payPlan="SL")})
        apply_grade_pay(tree, self.records)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-director"])

    def test_a_listing_that_now_states_a_rate_withdraws_the_range(self):
        tree = self._with_listings(self._tree(), **{"ed-ocr-director": ses_listing(reportedPay=225_700.0, reportedPayText="$225,700", level="$225,700")})
        stats = apply_grade_pay(tree, self.records)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-director"])
        self.assertEqual(stats["listing_reports_a_rate"], 1)

    def test_a_published_gs_pair_never_on_one_row_withdraws_the_range(self):
        tree = self._with_listings(self._tree(), **{"ed-ocr-das": listing(payPlanAndLevelOnOneRow=False)})
        apply_grade_pay(tree, self.records)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-das"])

    def test_an_ses_listing_that_gained_a_level_withdraws_the_range(self):
        tree = self._with_listings(self._tree(), **{"ed-ocr-director": ses_listing(level="IV", payLevel="IV")})
        apply_grade_pay(tree, self.records)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-director"])

    def test_a_node_standing_for_many_posts_is_refused_twice(self):
        tree = self._with_listings(self._tree())
        node = index_tree(tree)[0]["ed-ocr-das"]
        node["representsPosts"] = 4
        stats = apply_grade_pay(tree, self.records)
        self.assertEqual(stats["stands_for_many_posts"], 1)
        # And the generic sweep strips the field too, after the counts exist.
        node["positionGradePay"] = {"minimum": 1.0}
        self.assertEqual(withdraw_pay_from_multi_post_nodes(tree), 1)
        self.assertNotIn("positionGradePay", node)

    def test_a_range_never_lands_on_an_organisation(self):
        tree = self._with_listings(self._tree())
        index_tree(tree)[0]["ed-ocr-das"]["type"] = "Office"
        stats = apply_grade_pay(tree, self.records)
        self.assertEqual(stats["not_a_position"], 1)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["ed-ocr-das"])

    def test_the_table_never_verifies_that_the_post_exists(self):
        tree = self._with_listings(self._tree())
        before = {n["id"]: (list(n.get("sourceUrls") or []), list(n.get("sourceTypes") or []), n.get("lastVerified"), n.get("verificationMethod"))
                  for n in _walk(tree)}
        apply_grade_pay(tree, self.records)
        after = {n["id"]: (list(n.get("sourceUrls") or []), list(n.get("sourceTypes") or []), n.get("lastVerified"), n.get("verificationMethod"))
                 for n in _walk(tree)}
        self.assertEqual(before, after)

    def test_the_field_is_owned_so_a_retraction_can_reach_the_site(self):
        self.assertIn("positionGradePay", EVIDENCE_OWNED_FIELDS)


class ScriptAndGateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TEST_TMP_ROOT / f"gs-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.positions = self.tmp / "position_evidence.json"
        self.positions.write_text(json.dumps({"nodes": LISTINGS}), encoding="utf-8")
        self.out = self.tmp / "grade_pay_evidence.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _derive(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_gs_pay_evidence.main([
                "d", "--base-graph", str(self.base), "--positions", str(self.positions),
                "--out", str(self.out), *extra,
            ])
        return code, buf.getvalue()

    def _build(self, reuse=False):
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=reuse,
            existing_graph_payload_path=self.tmp / "graph.json" if reuse else None,
            enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=None, headcount_evidence_path=None,
            position_evidence_path=self.positions, pay_evidence_path=None,
            grade_pay_evidence_path=self.out,
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
        self.assertEqual(len(store["nodes"]), 3)
        self.assertEqual(store["sources"][KIND_GS]["table"], GENERAL_SCHEDULE_TABLE)

        result = self._build()
        self.assertEqual(result.validation["grade_pay_evidence"]["ranged"], 3)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["ed-ocr-das"]
        self.assertEqual(node["positionGradePay"]["minimum"], 126_384.0)
        self.assertNotIn(node["positionGradePay"]["url"], [str(u) for u in (node.get("sourceUrls") or [])])

        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("pay ranges           : 3 positions carry a base-pay RANGE", out)
        self.assertIn("General Schedule grade 1, base pay before locality; SES 1; SL/ST 1", out)

    def test_dry_run_writes_nothing(self):
        code, out = self._derive("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.out.exists())
        self.assertIn("ranged 3", out)

    def test_a_multi_post_node_is_not_ranged_by_a_real_build(self):
        base = json.loads(json.dumps(BASE))
        index_tree(base)[0]["ed-ocr-das"]["name"] = "Deputy Assistant Secretary (×4)"
        self.base.write_text(json.dumps(base), encoding="utf-8")
        self._derive()
        result = self._build()
        node = index_tree(json.loads(result.graph_path.read_text(encoding="utf-8")))[0]["ed-ocr-das"]
        self.assertTrue(node.get("representsPosts"))
        self.assertNotIn("positionGradePay", node)

    def _corrupt(self, node_id="ed-ocr-das", node_fields=None, listing_fields=None, **fields):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0][node_id]
        block = node["positionGradePay"]
        for key, value in fields.items():
            if value is None:
                block.pop(key, None)
            else:
                block[key] = value
        for key, value in (node_fields or {}).items():
            node[key] = value
        for key, value in (listing_fields or {}).items():
            node["positionListing"][key] = value
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return self._gate(path)

    def test_the_gate_refuses_bounds_the_table_does_not_print(self):
        code, out = self._corrupt(minimum=126_385.0, minimumPrinted="126,385")
        self.assertEqual(code, 1, out)
        self.assertIn("which the table prints as", out)

    def test_the_gate_refuses_printed_digits_that_disagree_with_the_number(self):
        code, out = self._corrupt(maximumPrinted="164,310")
        self.assertEqual(code, 1, out)
        self.assertIn("prints the maximum as", out)

    def test_the_gate_refuses_a_grade_the_listing_no_longer_reports(self):
        code, out = self._corrupt(listing_fields={"payLevel": "14"})
        self.assertEqual(code, 1, out)
        self.assertIn("but its listing reports", out)

    def test_the_gate_refuses_a_range_beside_a_rate_the_archive_states(self):
        code, out = self._corrupt(node_id="ed-ocr-director", listing_fields={"reportedPay": 225_700.0, "reportedPayText": "$225,700"})
        self.assertEqual(code, 1, out)
        self.assertIn("two figures for one post", out)

    def test_the_gate_refuses_a_range_on_a_non_post(self):
        code, out = self._corrupt(node_fields={"type": "Office"})
        self.assertEqual(code, 1, out)
        self.assertIn("not a post", out)

    def test_the_gate_refuses_a_digest_the_committed_document_does_not_have(self):
        code, out = self._corrupt(documentSha256="0" * 64)
        self.assertEqual(code, 1, out)
        self.assertIn("digest that is not the committed", out)

    def test_the_gate_refuses_a_corroboration_digest_that_is_not_the_pages(self):
        code, out = self._corrupt(corroboration={"url": "https://www.opm.gov/x", "documentSha256": "0" * 64})
        self.assertEqual(code, 1, out)
        self.assertIn("HTML corroboration digest", out)

    def test_the_gate_refuses_a_range_beside_a_measured_cost(self):
        code, out = self._corrupt(node_fields={"cost_status": "official", "costVerificationStatus": "verified"})
        self.assertEqual(code, 1, out)
        self.assertIn("measured cost status", out)

    def test_the_gate_refuses_a_gs_range_that_does_not_say_before_locality(self):
        code, out = self._corrupt(baseBeforeLocality=None)
        self.assertEqual(code, 1, out)
        self.assertIn("before locality", out)

    def test_the_gate_refuses_a_note_attributed_to_the_gs_table(self):
        code, out = self._corrupt(footnotes=["No pay freeze applies."])
        self.assertEqual(code, 1, out)
        self.assertIn("notes the General Schedule table does not carry", out)

    def test_the_gate_refuses_a_structure_range_missing_the_tables_note(self):
        code, out = self._corrupt(node_id="ed-ocr-director", footnotes=[])
        self.assertEqual(code, 1, out)
        self.assertIn("without the notes the table prints", out)

    def test_the_gate_refuses_a_sl_st_range_citing_the_ses_table(self):
        # Identical figures, different document: only the table name and the
        # digest tell them apart, and both are checked.
        code, out = self._corrupt(node_id="ed-ocr-scientist", table="Salary Table No. 2026-ES")
        self.assertEqual(code, 1, out)
        self.assertIn("cites table", out)

    def test_the_gate_refuses_a_structure_row_the_table_does_not_print(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        block = index_tree(graph)[0]["ed-ocr-director"]["positionGradePay"]
        block["rows"][1]["maximum"] = 228_000.0
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("which the table prints as", out)

    def test_the_gate_refuses_the_wrong_scale_rule(self):
        code, out = self._corrupt(unitsEvidenceKind="currency_mark_on_the_printed_figure")
        self.assertEqual(code, 1, out)
        self.assertIn("rests its scale on", out)

    def test_the_gate_refuses_a_range_claiming_more_than_a_proxy(self):
        code, out = self._corrupt(scopeMatch="exact", financialEvidenceStatus="verified")
        self.assertEqual(code, 1, out)
        self.assertIn("more than a proxy", out)

    def test_the_gate_refuses_the_table_counted_as_proof_the_post_exists(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["ed-ocr-das"]
        node["sourceUrls"] = list(node.get("sourceUrls") or []) + [node["positionGradePay"]["url"]]
        node["sourceCount"] = len(node["sourceUrls"])
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("source of the post's existence", out)

    def test_the_gate_refuses_a_future_retrieval_date(self):
        code, out = self._corrupt(checkedAt="2999-01-01T00:00:00Z")
        self.assertEqual(code, 1, out)

    def test_the_gate_refuses_a_range_with_no_listing_behind_it(self):
        self._derive()
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["ed-ocr-das"]
        node.pop("positionListing")
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        code, out = self._gate(path)
        self.assertEqual(code, 1, out)
        self.assertIn("no position listing beneath it", out)

    def test_a_withdrawn_listing_takes_the_range_off_the_published_graph(self):
        self._derive()
        self._build()
        self.positions.write_text(json.dumps({"nodes": {}}), encoding="utf-8")
        result = self._build(reuse=True)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["ed-ocr-das"]
        self.assertNotIn("positionGradePay", node)
        self.assertNotIn("positionListing", node)


class DerivedEvidenceTestCase(unittest.TestCase):
    """The committed evidence file, if present, ranges only posts of the base
    graph, from the committed tables, with every bound validated."""

    EVIDENCE = PROJECT_ROOT / "data" / "verification" / "grade_pay_evidence.json"
    BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"

    def test_every_record_is_a_post_of_the_base_graph_and_a_proxy(self):
        if not self.EVIDENCE.exists():  # pragma: no cover - derived file is tracked
            self.skipTest("no derived evidence")
        from data_pipeline.exporter.build_graph import is_post_node, load_base_graph

        store = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        nodes = index_tree(load_base_graph(self.BASE_GRAPH))[0]
        self.assertTrue(store["nodes"])
        for node_id, record in store["nodes"].items():
            self.assertIn(node_id, nodes)
            self.assertTrue(is_post_node(nodes[node_id]), node_id)
            self.assertEqual(record["scopeMatch"], "proxy")
            self.assertIn(record["kind"], (KIND_GS, KIND_SES, KIND_SLST))
            for bound in record["bounds"].values():
                self.assertEqual(bound["financialEvidenceStatus"], "partial")
            if record["kind"] == KIND_GS:
                self.assertEqual((record["minimum"], record["maximum"]), GENERAL_SCHEDULE_RANGES[record["grade"]])


if __name__ == "__main__":
    unittest.main()
