"""USAJOBS vacancy announcements as a LISTING of a title family's pay plan and
grade, the range `gs_pay` hangs off it, and every way the join could publish
something false.

Both directions throughout. An honest listing is published and a GS-15 base
range hangs off it; each way of forging one is refused: a grade the
announcements do not all print, a single announcement standing for a title, a
range that is not the table's, an announcement's locality salary or its HR
contact anywhere in a block, a listing on a non-post or outside the reviewed
family, and a listing dressed as evidence that the node exists.

The contact rule is pinned the way `tests/test_plum_current.py` pins the
PLUM export's incumbent columns: a sentinel is planted in the agency-contact
section of every committed announcement, and it must appear nowhere in what
the module returns, what the derive script writes, or what it prints.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, build_graph, index_tree, load_base_graph
from data_pipeline.verification import pay_documents
from data_pipeline.verification import usajobs
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.gs_pay import (
    METHOD_GS_FROM_VACANCIES,
    VACANCY_LISTING_FIELD,
    VACANCY_LISTING_SOURCE,
    apply_grade_pay,
    build_records,
    load_all_tables,
)
from data_pipeline.verification.usajobs import (
    FIELD,
    FIXTURE_DIR,
    SOURCE,
    VACANCY_FAMILIES,
    Unreadable,
    adjudicate_family,
    apply_vacancy_listing,
    build_listings,
    load_announcement,
    overview_slice,
    parse_announcement,
)
from scripts import derive_gs_pay_evidence, derive_usajobs_evidence
from scripts import validate_published_graph as gate
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
SENTINEL = "SENTINELCONTACTNAME"
SALARY_SENTINEL = "987,654"

ASSOCIATE_IDS = ("848110500", "848756100", "860101900", "863018500", "880101300")
CFO_ID = "880695200"
ALL_IDS = ASSOCIATE_IDS + (CFO_ID,)
ASSOCIATE_FAMILY = next(f for f in VACANCY_FAMILIES if f["family"] == "vamc_associate_director_administrative")
CFO_FAMILY = next(f for f in VACANCY_FAMILIES if f["family"] == "network_cfo_visn")
GS15 = (126_384.0, 164_301.0)


def _visn(number: str, name: str) -> dict:
    visn_id = f"visn-{number}"
    return {"id": visn_id, "name": f"VISN {number} — {name}", "type": "VISN", "children": [
        {"id": f"{visn_id}-cfo", "name": f"Network CFO, VISN {number} — {name}", "type": "Position", "children": []},
        {"id": f"{visn_id}-vamc", "name": "VA Medical Centers", "type": "Division", "children": [
            {"id": f"{visn_id}-vamc-ad", "name": "VAMC Associate Director (Administrative)", "type": "Position", "children": []},
            {"id": f"{visn_id}-vamc-cno", "name": "Associate Director for Patient Care Services (CNO)",
             "type": "Position", "children": []},
        ]},
    ]}


BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet", "type": "Division", "children": [
                {"id": "exec-dept-va", "name": "Department of Veterans Affairs (VA)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-va-vha", "name": "Veterans Health Administration", "type": "Administration", "children": [
                        _visn("15", "Heartland"),
                        _visn("17", "Texas"),
                        # A grouping that is NOT a VISN: its medical-centre
                        # template is outside the family by the rule.
                        {"id": "other", "name": "Other Programs", "type": "Division", "children": [
                            {"id": "other-vamc", "name": "VA Medical Centers", "type": "Division", "children": [
                                {"id": "other-vamc-ad", "name": "VAMC Associate Director (Administrative)",
                                 "type": "Position", "children": []},
                            ]},
                        ]},
                    ]},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
MEMBERS = ["visn-15-vamc-ad", "visn-17-vamc-ad"]


def _tree() -> dict:
    return json.loads(json.dumps(BASE))


def copy_fixtures(target: Path, mutate=None) -> Path:
    """The committed announcements, copied, each optionally rewritten, with
    the .meta.json digest recomputed so only the content changes."""
    target.mkdir(parents=True, exist_ok=True)
    for announcement_id in ALL_IDS:
        page = (FIXTURE_DIR / f"{announcement_id}.html").read_text(encoding="utf-8")
        meta = json.loads((FIXTURE_DIR / f"{announcement_id}.html.meta.json").read_text(encoding="utf-8"))
        if mutate is not None:
            page = mutate(announcement_id, page)
        raw = page.encode("utf-8")
        meta["sha256"] = hashlib.sha256(raw).hexdigest()
        meta["bytes"] = len(raw)
        (target / f"{announcement_id}.html").write_bytes(raw)
        (target / f"{announcement_id}.html.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return target


def plant_sentinels(_id: str, page: str) -> str:
    """A name in the agency contact, and a figure in the Salary cell."""
    page = re.sub(r"(Agency contact information)", r"\1 " + SENTINEL + " " + SENTINEL.lower() + "@va.gov", page, count=1)
    page = re.sub(r"(>Salary</dt>\s*<dd>)", r"\1 $" + SALARY_SENTINEL + " ", page, count=1)
    return page


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TEST_TMP_ROOT / f"usajobs-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# The committed announcements, read.


class CommittedAnnouncementTestCase(unittest.TestCase):
    def test_every_associate_director_announcement_prints_gs_15_in_series_0670(self):
        for announcement_id in ASSOCIATE_IDS:
            record = load_announcement(announcement_id)
            self.assertEqual(record["payScaleAndGrade"], "GS 15", announcement_id)
            self.assertEqual((record["payPlan"], record["grade"]), ("GS", "15"))
            self.assertEqual([s["code"] for s in record["series"]], ["0670"])
            self.assertEqual(record["department"], "Department of Veterans Affairs")
            self.assertEqual(record["agency"], "Veterans Health Administration")
            self.assertIn("Associate", record["title"])
            self.assertTrue(record["locations"])
            self.assertLessEqual(record["openDate"], record["closeDate"])

    def test_the_cfo_announcement_is_one_vacancy_filed_under_the_office_of_management(self):
        record = load_announcement(CFO_ID)
        self.assertEqual(record["title"], "Chief Financial Officer (CFO)")
        self.assertEqual(record["agency"], "Immediate Office of the Assistant Secretary for Management")
        self.assertEqual(record["payScaleAndGrade"], "GS 15")

    def test_every_reviewed_row_is_what_its_page_prints(self):
        for family in VACANCY_FAMILIES:
            for row in family["announcements"]:
                record = load_announcement(row["id"])
                for key in ("title", "agency", "hiringOrganization"):
                    self.assertEqual(record[key], row[key], (row["id"], key))

    def test_no_salary_is_read_off_any_committed_announcement(self):
        for announcement_id in ALL_IDS:
            page = (FIXTURE_DIR / f"{announcement_id}.html").read_text(encoding="utf-8")
            salary = re.search(r">Salary</dt>\s*<dd>(.*?)</dd>", page, re.S).group(1)
            figures = re.findall(r"\$([0-9][0-9,]+)", salary)
            self.assertTrue(figures, announcement_id)
            record = json.dumps(load_announcement(announcement_id))
            for figure in figures:
                self.assertNotIn(figure, record)
                self.assertNotIn(figure.replace(",", ""), record)

    def test_the_overview_slice_ends_before_any_contact(self):
        for announcement_id in ALL_IDS:
            page = (FIXTURE_DIR / f"{announcement_id}.html").read_text(encoding="utf-8")
            piece = overview_slice(page)
            self.assertNotIn("mailto:", piece)
            self.assertNotIn("agency contact", piece.casefold())
            # ...and the page DOES carry one, further down, which is the
            # whole point of cutting the slice where it is cut.
            self.assertIn("Agency contact information", page[page.find(piece) + len(piece):])

    def test_the_gates_reader_agrees_with_the_modules(self):
        for announcement_id in ALL_IDS:
            ours = load_announcement(announcement_id)
            theirs = gate.usajobs_announcement(announcement_id)
            self.assertIsNotNone(theirs, announcement_id)
            for key in ("title", "department", "agency", "hiringOrganization", "payScaleAndGrade", "locations",
                        "openDate", "closeDate", "documentSha256", "url", "fetchedAt"):
                self.assertEqual(ours[key], theirs[key], (announcement_id, key))
            self.assertEqual(sorted(s["code"] for s in ours["series"]), theirs["series"])
            self.assertTrue(theirs["salaryFigures"], announcement_id)

    def test_the_gate_mirrors_exactly_the_families_the_module_lists(self):
        records, report = build_listings(_tree())
        listed = {name for name, entry in report["families"].items() if entry["verdict"] == "listed"}
        self.assertEqual(listed, set(gate.USAJOBS_VACANCY_FAMILIES))
        for name in listed:
            family = next(f for f in VACANCY_FAMILIES if f["family"] == name)
            mirror = gate.USAJOBS_VACANCY_FAMILIES[name]
            self.assertEqual(sorted(mirror["announcements"]), sorted(r["id"] for r in family["announcements"]))
            for key in ("nodeName", "parentName", "grandparentType", "payPlan", "grade", "series"):
                self.assertEqual(mirror[key], family[key], key)
        self.assertEqual(gate.USAJOBS_SOURCE, SOURCE)
        self.assertEqual(gate.USAJOBS_METHOD, usajobs.METHOD)
        self.assertEqual(gate.USAJOBS_GRADE_PAY_METHOD, METHOD_GS_FROM_VACANCIES)
        self.assertEqual(gate.USAJOBS_MINIMUM_ANNOUNCEMENTS, usajobs.MINIMUM_ANNOUNCEMENTS)


# ---------------------------------------------------------------------------
# The parser and the loader refuse what they cannot read.


class RefusalTestCase(TmpCase):
    def _load(self, mutate, announcement_id=ASSOCIATE_IDS[0]):
        copy_fixtures(self.tmp, mutate)
        return load_announcement(announcement_id, self.tmp)

    def test_a_page_that_is_not_the_file_that_was_served_is_refused(self):
        copy_fixtures(self.tmp)
        path = self.tmp / f"{ASSOCIATE_IDS[0]}.html"
        path.write_bytes(path.read_bytes().replace(b"GS 15", b"GS 14"))
        with self.assertRaises(Unreadable):
            load_announcement(ASSOCIATE_IDS[0], self.tmp)

    def test_a_fetch_that_landed_somewhere_else_is_refused(self):
        copy_fixtures(self.tmp)
        meta_path = self.tmp / f"{ASSOCIATE_IDS[0]}.html.meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["final_url"] = "https://www.usajobs.gov/"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(Unreadable):
            load_announcement(ASSOCIATE_IDS[0], self.tmp)

    def test_a_ladder_of_grades_is_not_one_grade(self):
        with self.assertRaises(Unreadable):
            self._load(lambda _i, p: p.replace("<div>GS 15</div>", "<div>GS 13 - 15</div>"))

    def test_two_copies_of_the_overview_printing_different_grades_are_refused(self):
        def mutate(_id, page):
            # A second pay-scale cell inside the overview, disagreeing.
            return page.replace(
                "Pay scale &amp; grade</dt>",
                "Pay scale &amp; grade</dt><dd><div>GS 14</div></dd></dl><dl><dt>Pay scale &amp; grade</dt>", 1)
        with self.assertRaises(Unreadable):
            self._load(mutate)

    def test_an_overview_carrying_a_contact_is_refused_not_read_around(self):
        with self.assertRaises(Unreadable):
            self._load(lambda _i, p: p.replace("<h2>Overview</h2>", "<h2>Overview</h2><a href=\"mailto:x@y.gov\">x</a>", 1))

    def test_a_page_with_no_end_to_its_overview_is_refused(self):
        with self.assertRaises(Unreadable):
            self._load(lambda _i, p: p.replace('id="joa-hiring-paths"', 'id="elsewhere"'))

    def test_a_series_that_is_not_a_code_and_a_name_is_refused(self):
        with self.assertRaises(Unreadable):
            self._load(lambda _i, p: p.replace("0670 Health System Administration", "Health System Administration"))

    def test_an_announcement_number_that_is_not_one_is_refused(self):
        with self.assertRaises(Unreadable):
            load_announcement("../etc/passwd")


# ---------------------------------------------------------------------------
# The sentinel: no contact and no salary, anywhere.


class SentinelTestCase(TmpCase):
    def test_a_name_in_the_contact_and_a_figure_in_the_salary_reach_nothing(self):
        fixtures = copy_fixtures(self.tmp / "fx", plant_sentinels)
        page = (fixtures / f"{ASSOCIATE_IDS[0]}.html").read_text(encoding="utf-8")
        self.assertIn(SENTINEL, page)
        self.assertIn(SALARY_SENTINEL, page)
        for announcement_id in ALL_IDS:
            self.assertNotIn(SENTINEL, json.dumps(load_announcement(announcement_id, fixtures)))
            self.assertNotIn(SALARY_SENTINEL, json.dumps(load_announcement(announcement_id, fixtures)))
        records, report = build_listings(_tree(), fixture_dir=fixtures)
        self.assertEqual(sorted(records), MEMBERS)
        for text in (json.dumps(records), json.dumps(report)):
            self.assertNotIn(SENTINEL, text)
            self.assertNotIn(SENTINEL.lower(), text)
            self.assertNotIn(SALARY_SENTINEL, text)

        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out = self.tmp / "usajobs_evidence.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = derive_usajobs_evidence.main(["d", "--base-graph", str(base), "--fixtures", str(fixtures), "--out", str(out)])
        self.assertEqual(code, 0, buf.getvalue())
        for text in (buf.getvalue(), out.read_text(encoding="utf-8")):
            self.assertNotIn(SENTINEL, text)
            self.assertNotIn(SENTINEL.lower(), text)
            self.assertNotIn(SALARY_SENTINEL, text)


# ---------------------------------------------------------------------------
# Families: the table proposes, the pages decide.


class FamilyTestCase(TmpCase):
    def test_the_associate_director_family_is_listed_on_its_five_announcements(self):
        announcements, verdict, _ = adjudicate_family(ASSOCIATE_FAMILY)
        self.assertEqual(verdict, "listed")
        self.assertEqual(sorted(a["id"] for a in announcements), sorted(ASSOCIATE_IDS))

    def test_one_announcement_is_one_vacancy_and_lists_nothing(self):
        announcements, verdict, _ = adjudicate_family(CFO_FAMILY)
        self.assertIsNone(announcements)
        self.assertEqual(verdict, "fewer_than_two_announcements")

    def test_announcements_that_disagree_on_the_grade_list_nothing(self):
        fixtures = copy_fixtures(self.tmp, lambda i, p: p.replace("<div>GS 15</div>", "<div>GS 14</div>") if i == ASSOCIATE_IDS[2] else p)
        announcements, verdict, _ = adjudicate_family(ASSOCIATE_FAMILY, fixtures)
        self.assertIsNone(announcements)
        self.assertEqual(verdict, "announcements_disagree_on_the_grade")

    def test_announcements_agreeing_on_another_grade_than_the_row_list_nothing(self):
        fixtures = copy_fixtures(self.tmp, lambda _i, p: p.replace("<div>GS 15</div>", "<div>GS 14</div>"))
        _, verdict, _ = adjudicate_family(ASSOCIATE_FAMILY, fixtures)
        self.assertEqual(verdict, "announcements_state_another_grade_than_the_row")

    def test_a_page_that_no_longer_prints_the_reviewed_title_lists_nothing(self):
        fixtures = copy_fixtures(self.tmp, lambda i, p: p.replace(
            "Health Systems Administrator (Associate Director)", "Supervisory Program Analyst") if i == ASSOCIATE_IDS[0] else p)
        _, verdict, _ = adjudicate_family(ASSOCIATE_FAMILY, fixtures)
        self.assertEqual(verdict, "announcement_no_longer_prints_the_reviewed_row")

    def test_an_announcement_in_another_series_lists_nothing(self):
        fixtures = copy_fixtures(self.tmp, lambda _i, p: p.replace("0670 Health System Administration", "0340 Program Management"))
        _, verdict, _ = adjudicate_family(ASSOCIATE_FAMILY, fixtures)
        self.assertEqual(verdict, "announcement_is_in_another_series")

    def test_membership_is_the_rule_off_the_tree(self):
        self.assertEqual(usajobs.family_members(_tree(), ASSOCIATE_FAMILY), MEMBERS)
        tree = _tree()
        index_tree(tree)[0]["visn-15-vamc-ad"]["name"] = "VAMC Associate Director (Administrative) (×3)"
        self.assertEqual(usajobs.family_members(tree, ASSOCIATE_FAMILY), ["visn-17-vamc-ad"])

    def test_the_real_graph_has_eighteen_members_and_no_cno(self):
        from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH

        members = usajobs.family_members(load_base_graph(DEFAULT_BASE_GRAPH), ASSOCIATE_FAMILY)
        self.assertEqual(len(members), 18)
        self.assertTrue(all(m.endswith("-vamc-vamc-associate-director-administrative") for m in members))
        cno = [d for d in usajobs.DECLINED_FAMILIES if "CNO" in d["nodeName"]]
        self.assertEqual(len(cno), 1)
        self.assertIn("Nurse V", cno[0]["reason"])


# ---------------------------------------------------------------------------
# The listing on the tree, and the range that hangs off it.


class ApplyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.listings, cls.report = build_listings(_tree())
        cls.tables = load_all_tables()

    def _ranges(self, listings=None):
        from data_pipeline.verification import financial_evidence as fe

        raw, _ = build_records(listings or self.listings, self.tables)
        node_map = index_tree(_tree())[0]
        out = {}
        for node_id, record in raw.items():
            kept = dict(record)
            kept["bounds"] = {}
            for name, bound in record["bounds"].items():
                checked = fe.validate_record(bound, node_map[node_id])
                checked["financialEvidenceStatus"] = fe.classify(checked)
                kept["bounds"][name] = checked
            out[node_id] = kept
        return out

    def test_the_listing_is_published_and_verifies_nothing(self):
        tree = _tree()
        stats = apply_vacancy_listing(tree, self.listings)
        self.assertEqual(stats["listed"], 2)
        node = index_tree(tree)[0]["visn-15-vamc-ad"]
        block = node[FIELD]
        self.assertEqual((block["payPlan"], block["payLevel"]), ("GS", "15"))
        self.assertEqual(block["announcementCount"], 5)
        self.assertIn("none names this node", block["statement"])
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod", "placementMethod", "evidenceUrls"):
            self.assertNotIn(field, node)
        self.assertNotIn(FIELD, index_tree(tree)[0]["other-vamc-ad"])
        self.assertNotIn(FIELD, index_tree(tree)[0]["visn-15-vamc-cno"])

    def test_a_re_parented_node_loses_its_listing(self):
        tree = _tree()
        node_map = index_tree(tree)[0]
        node_map["visn-15-vamc"]["name"] = "Community Clinics"
        stats = apply_vacancy_listing(tree, self.listings)
        self.assertEqual(stats["listed"], 1)
        self.assertEqual(stats["not_a_member"], 1)

    def test_a_record_resting_on_one_announcement_is_refused(self):
        listings = json.loads(json.dumps(self.listings))
        for record in listings.values():
            record["announcements"] = record["announcements"][:1]
        stats = apply_vacancy_listing(_tree(), listings)
        self.assertEqual(stats["listed"], 0)
        self.assertEqual(stats["malformed"], 2)

    def test_the_range_is_the_tables_gs_15_base_range_named_for_the_listing(self):
        ranges = self._ranges()
        self.assertEqual(sorted(ranges), MEMBERS)
        tree = _tree()
        apply_vacancy_listing(tree, self.listings)
        stats = apply_grade_pay(tree, ranges)
        self.assertEqual(stats["ranged"], 2)
        self.assertEqual(stats["ranged_from_vacancy_listings"], 2)
        node = index_tree(tree)[0]["visn-17-vamc-ad"]
        pay = node["positionGradePay"]
        self.assertEqual((pay["minimum"], pay["maximum"]), GS15)
        self.assertEqual(pay["grade"], "15")
        self.assertEqual(pay["method"], METHOD_GS_FROM_VACANCIES)
        self.assertEqual(pay["listingSource"]["source"], VACANCY_LISTING_SOURCE)
        self.assertEqual(pay["listingSource"]["announcementCount"], 5)
        self.assertIn("5 USAJOBS announcements", pay["vacancyStatement"])
        self.assertIn("not anyone's pay", pay["vacancyStatement"])
        self.assertEqual(VACANCY_LISTING_FIELD, FIELD)
        for field in ("sourceUrls", "verificationMethod", "lastVerified"):
            self.assertNotIn(field, node)

    def test_no_listing_no_range(self):
        tree = _tree()
        stats = apply_grade_pay(tree, self._ranges())
        self.assertEqual(stats["ranged"], 0)
        self.assertEqual(stats["no_listing_published"], 2)

    def test_a_listing_resting_on_other_announcements_withdraws_the_range(self):
        tree = _tree()
        apply_vacancy_listing(tree, self.listings)
        index_tree(tree)[0]["visn-15-vamc-ad"][FIELD]["announcements"].pop()
        stats = apply_grade_pay(tree, self._ranges())
        self.assertEqual(stats["ranged"], 1)
        self.assertNotIn("positionGradePay", index_tree(tree)[0]["visn-15-vamc-ad"])

    def test_the_document_count_counts_the_listing_once(self):
        tree = _tree()
        apply_vacancy_listing(tree, self.listings)
        apply_grade_pay(tree, self._ranges())
        pay_documents.annotate_pay_documents(tree)
        verification = index_tree(tree)[0]["visn-15-vamc-ad"]["positionGradePay"]["verification"]
        self.assertEqual(verification["documents"], 2)
        self.assertEqual(verification["percent"], 80)
        self.assertEqual(verification["documentsStatingTheFigure"], 1)
        self.assertIn("vacancy announcements", verification["caution"])
        self.assertIn("counted once", verification["caution"])

    def test_the_fields_are_owned_and_reach_the_viewer(self):
        self.assertIn(FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(FIELD, MINIMAL_GRAPH_FIELDS)


# ---------------------------------------------------------------------------
# The two scripts, a real build, and the gate both ways.


class ScriptAndGateTestCase(TmpCase):
    def setUp(self):
        super().setUp()
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.vacancies = self.tmp / "usajobs_evidence.json"
        self.grade = self.tmp / "grade_pay_evidence.json"
        self.empty = self.tmp / "empty.json"
        self.empty.write_text(json.dumps({"nodes": {}}), encoding="utf-8")

    def _derive(self, dry_run=False):
        buf = io.StringIO()
        extra = ["--dry-run"] if dry_run else []
        with redirect_stdout(buf):
            first = derive_usajobs_evidence.main(["d", "--base-graph", str(self.base), "--out", str(self.vacancies), *extra])
            second = 0 if dry_run else derive_gs_pay_evidence.main([
                "d", "--base-graph", str(self.base), "--positions", str(self.empty),
                "--current-listings", str(self.empty), "--vacancy-listings", str(self.vacancies),
                "--out", str(self.grade),
            ])
        return first, second, buf.getvalue()

    def _build(self):
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=False,
            enforce_export_gate=True, evidence_path=None, sites_path=None,
            directory_evidence_path=None, headcount_evidence_path=None,
            position_evidence_path=None, pay_evidence_path=None, plum_current_evidence_path=None,
            grade_pay_evidence_path=self.grade, vacancy_listing_evidence_path=self.vacancies,
        )

    def _gate(self, path):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = gate_main(["gate", str(path)])
        return code, buf.getvalue()

    def test_dry_run_writes_nothing(self):
        first, _, out = self._derive(dry_run=True)
        self.assertEqual(first, 0, out)
        self.assertFalse(self.vacancies.exists())
        self.assertIn("listed 2 node(s)", out)
        self.assertIn("fewer_than_two_announcements", out)

    def test_the_scripts_derive_the_build_publishes_and_the_gate_passes(self):
        first, second, out = self._derive()
        self.assertEqual((first, second), (0, 0), out)
        self.assertIn("2 from USAJOBS vacancy announcements", out)
        result = self._build()
        self.assertEqual(result.validation["vacancy_listing_evidence"]["listed"], 2)
        self.assertEqual(result.validation["grade_pay_evidence"]["ranged"], 2)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node = index_tree(graph)[0]["visn-15-vamc-ad"]
        self.assertEqual((node["positionGradePay"]["minimum"], node["positionGradePay"]["maximum"]), GS15)
        self.assertNotIn("positionGradePay", index_tree(graph)[0]["visn-15-cfo"])
        self.assertNotIn("positionGradePay", index_tree(graph)[0]["visn-15-vamc-cno"])
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("vacancy listings     : 2 positions carry a USAJOBS vacancy listing", out)
        self.assertIn("(2 ranged from it)", out)

    def _corrupt(self, mutate, node_id="visn-15-vamc-ad"):
        first, second, out = self._derive()
        self.assertEqual((first, second), (0, 0), out)
        result = self._build()
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node_map = index_tree(graph)[0]
        mutate(node_map[node_id], node_map)
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return self._gate(path)

    def assertRefused(self, mutate, phrase, node_id="visn-15-vamc-ad"):
        code, out = self._corrupt(mutate, node_id)
        self.assertEqual(code, 1, out)
        self.assertIn(phrase, out)

    def test_the_gate_refuses_a_grade_the_announcements_do_not_all_print(self):
        def mutate(node, _):
            node[FIELD]["announcements"][1]["payScaleAndGrade"] = "GS 14"
        self.assertRefused(mutate, "payScaleAndGrade")

    def test_the_gate_refuses_a_listing_at_another_grade(self):
        def mutate(node, _):
            node[FIELD]["payLevel"] = "14"
        self.assertRefused(mutate, "lists pay plan")

    def test_the_gate_refuses_fewer_than_two_announcements(self):
        def mutate(node, _):
            node[FIELD]["announcements"] = node[FIELD]["announcements"][:1]
            node[FIELD]["announcementCount"] = 1
        self.assertRefused(mutate, "one posting is one vacancy")

    def test_the_gate_refuses_a_range_that_is_not_the_tables_gs_15(self):
        def mutate(node, _):
            node["positionGradePay"]["minimum"] = 126_385.0
            node["positionGradePay"]["minimumPrinted"] = "126,385"
        self.assertRefused(mutate, "which the table prints as")

    def test_the_gate_refuses_a_locality_salary_published(self):
        figure = gate.usajobs_announcement(ASSOCIATE_IDS[0])["salaryFigures"][0]

        def mutate(node, _):
            node["positionGradePay"]["listingSource"]["salary"] = f"${figure} per year"
        self.assertRefused(mutate, "locality salary")

        def mutate_listing(node, _):
            node[FIELD]["announcements"][0]["salary"] = f"${figure}"
        self.assertRefused(mutate_listing, "locality salary")

    def test_the_gate_refuses_a_contact_anywhere_in_either_block(self):
        def mutate(node, _):
            node[FIELD]["contact"] = "hr.specialist@va.gov"
        self.assertRefused(mutate, "contact-shaped")

        def mutate_range(node, _):
            node["positionGradePay"]["listingSource"]["phone"] = "(816) 555-0100"
        self.assertRefused(mutate_range, "contact-shaped")

        def mutate_quote(node, _):
            # A string the overview does not print -- the shape a name lifted
            # from the contact section would have -- quoted as the facility.
            node[FIELD]["announcements"][0]["locations"] = [SENTINEL]
        self.assertRefused(mutate_quote, "which its overview does not print")

    def test_the_gate_refuses_a_listing_on_a_non_post(self):
        def mutate(node, _):
            node["type"] = "Office"
        self.assertRefused(mutate, "not a post")

    def test_the_gate_refuses_a_listing_outside_the_reviewed_family(self):
        def move(node, node_map):
            node_map["visn-15-vamc-cno"][FIELD] = node.pop(FIELD)
            node_map["visn-15-vamc-cno"]["positionGradePay"] = node.pop("positionGradePay")
        self.assertRefused(move, "is not a 'VAMC Associate Director (Administrative)'")

        def declined_family(node, _):
            node[FIELD]["family"] = "network_cfo_visn"
        self.assertRefused(declined_family, "not a reviewed family")

    def test_the_gate_refuses_a_listing_dressed_as_existence_evidence(self):
        def mutate(node, _):
            node["sourceUrls"] = [node[FIELD]["url"]]
            node["sourceCount"] = 1
        self.assertRefused(mutate, "source of the post's existence")

    def test_the_gate_refuses_a_range_that_does_not_say_it_is_nobodys_pay(self):
        def mutate(node, _):
            node["positionGradePay"]["vacancyStatement"] = "GS-15."
        self.assertRefused(mutate, "not anyone's pay")

    def test_the_gate_refuses_a_range_naming_other_announcements_than_its_listing(self):
        def mutate(node, _):
            node["positionGradePay"]["listingSource"]["announcements"].pop()
        self.assertRefused(mutate, "the listing beneath it rests on")

    def test_the_gate_refuses_a_range_with_no_listing_beneath_it(self):
        def mutate(node, _):
            node.pop(FIELD)
        self.assertRefused(mutate, "no position listing beneath it")


if __name__ == "__main__":
    unittest.main()
