"""The White House Office's statutory personnel report: the stdlib PDF
reader, which posts it prices and which it honestly refuses, the name column
it must never carry, and every way a forged rate could reach the release gate.

Both directions throughout: an honest rate is published, and each way of
forging one is caught.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import unittest
import uuid
import zlib
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes
from data_pipeline.verification.whitehouse_pay import (
    DEFAULT_REPORT_PDF,
    SCOPE_NODE_ID,
    Unreadable,
    apply_pay_evidence,
    as_of_date,
    build_records,
    canonical,
    classify_row,
    content_streams,
    index_report_titles,
    load_staff_report,
    parse_staff_report,
    scoped_node_ids,
    title_core,
)
from scripts import derive_whitehouse_pay_evidence
from scripts.validate_published_graph import (
    WHITEHOUSE_REPORT_AS_OF_TEXT,
    WHITEHOUSE_REPORT_URL,
    reported_pay_violations,
    whitehouse_canonical,
    whitehouse_roster,
    whitehouse_title_core,
)
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
TODAY = "2026-09-14"


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _label(node):
    return f"[{node.get('id')}]"


BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-eop", "name": "Executive Office of the President", "type": "Office", "children": [
                {"id": SCOPE_NODE_ID, "name": "White House Office", "type": "Office", "children": [
                    {"id": "exec-eop-who-chief-of-staff", "name": "Chief of Staff", "type": "Position", "children": []},
                    {"id": "exec-eop-who-press-secretary", "name": "Press Secretary", "type": "Position", "children": []},
                    {"id": "exec-eop-who-cabinet-secretary", "name": "Cabinet Secretary", "type": "Position", "children": []},
                    {"id": "exec-eop-who-deputy-chief-of-staff-for-operations",
                     "name": "Deputy Chief of Staff for Operations", "type": "Position", "children": []},
                    {"id": "exec-eop-who-director-of-intergovernmental-affairs",
                     "name": "Director of Intergovernmental Affairs", "type": "Position", "children": []},
                    {"id": "exec-eop-who-national-security-advisor",
                     "name": "National Security Advisor", "type": "Position", "children": []},
                    {"id": "exec-eop-who-senior-advisor-to-the-president-multiple",
                     "name": "Senior Advisor to the President (×multiple)", "type": "Position",
                     "representsPosts": {"text": "×multiple", "kind": "unstated"}, "children": []},
                ]},
                {"id": "exec-eop-omb", "name": "Office of Management and Budget", "type": "Office", "children": [
                    {"id": "exec-eop-omb-press-secretary", "name": "Press Secretary", "type": "Position", "children": []},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}


def _pdf(rows, as_of="Wednesday, July 1, 2026", header=True):
    """A minimal PDF carrying the rows this parser reads, built the way the
    real one is: FlateDecode content streams of BT/Tm/TJ text blocks."""
    lines = []
    y = 900.0
    lines.append(f"BT /F0 1 Tf 10 0 0 10 100 {y:.1f} Tm [(As of Date: {as_of})]TJ ET")
    y -= 20
    if header:
        cells = "".join(f"({c})Tj " for c in ("NAME", "STATUS", "SALARY", "PAY BASIS", "POSITION TITLE"))
        lines.append(f"BT /F0 1 Tf 10 0 0 10 100 {y:.1f} Tm {cells} ET")
    for row in rows:
        y -= 15
        cells = "".join(f"({c})Tj " for c in row)
        lines.append(f"BT /F0 1 Tf 10 0 0 10 100 {y:.1f} Tm {cells} ET")
    body = zlib.compress("\n".join(lines).encode("latin-1"))
    return b"%PDF-1.6\r\n1 0 obj\r\n<< /Filter /FlateDecode >>\r\nstream\n" + body + b"\nendstream\r\nendobj\r\n%%EOF\r\n"


ROWS = [
    ("ACRA, ELLIE G.", "EMPLOYEE", "$74,500.00", "Per Annum", "PRESS ASSISTANT"),
    ("SMITH, JOHN Q.", "EMPLOYEE", "$195,200.00", "Per Annum", "ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF"),
    ("DOE, JANE A.", "EMPLOYEE", "$195,200.00", "Per Annum", "ASSISTANT TO THE PRESIDENT AND PRESS SECRETARY"),
    ("ROE, RICHARD", "DETAILEE", "$155,000.00", "Per Annum",
     "DEPUTY ASSISTANT TO THE PRESIDENT AND DIRECTOR OF INTERGOVERNMENTAL AFFAIRS"),
    ("POE, PAT", "EMPLOYEE", "$0.00", "Per Annum", "ASSISTANT TO THE PRESIDENT AND NATIONAL SECURITY ADVISOR"),
    ("ONE, ALICE", "EMPLOYEE", "$120,000.00", "Per Annum", "SENIOR POLICY ADVISOR"),
    ("TWO, BOB", "EMPLOYEE", "$130,000.00", "Per Annum", "SENIOR POLICY ADVISOR"),
]


class PdfReaderTests(unittest.TestCase):
    def test_it_reads_rows_and_the_as_of_date(self):
        parsed = parse_staff_report(_pdf(ROWS))
        self.assertEqual(parsed["asOfText"], "Wednesday, July 1, 2026")
        titles = {r["title"] for r in parsed["rows"]}
        self.assertIn("ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF", titles)
        self.assertEqual(len(parsed["rows"]), len(ROWS))

    def test_an_encrypted_document_is_refused_rather_than_guessed_at(self):
        with self.assertRaises(Unreadable):
            content_streams(b"%PDF-1.6\r\n/Encrypt 1 0 R\r\nstream\n" + zlib.compress(b"x") + b"\nendstream")

    def test_a_file_that_is_not_a_pdf_is_refused(self):
        with self.assertRaises(Unreadable):
            content_streams(b"<html><body>not a pdf</body></html>")

    def test_a_report_without_the_header_row_is_refused(self):
        with self.assertRaises(Unreadable):
            parse_staff_report(_pdf(ROWS, header=False))

    def test_a_report_without_an_as_of_date_is_refused(self):
        raw = _pdf(ROWS, as_of="")
        with self.assertRaises(Unreadable):
            parse_staff_report(raw)

    def test_the_real_fixture_parses_and_its_as_of_matches_the_gate_mirror(self):
        loaded = load_staff_report(DEFAULT_REPORT_PDF)
        self.assertEqual(loaded["report"]["asOfText"], WHITEHOUSE_REPORT_AS_OF_TEXT)
        self.assertEqual(loaded["url"], WHITEHOUSE_REPORT_URL)
        self.assertGreater(len(loaded["report"]["rows"]), 300)

    def test_a_tampered_fixture_is_refused_by_its_own_digest(self):
        tmp = TEST_TMP_ROOT / f"wh-digest-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, tmp, True)
        pdf = tmp / "staff_report_2026.pdf"
        pdf.write_bytes(_pdf(ROWS))
        meta = {"url": WHITEHOUSE_REPORT_URL, "fetched_at": "2026-09-14T00:00:00Z",
                "status": 200, "error": None, "sha256": "0" * 64}
        pdf.with_name(pdf.name + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(Unreadable):
            load_staff_report(pdf)

    def test_the_as_of_date_parser_refuses_what_it_cannot_read(self):
        self.assertEqual(as_of_date("Wednesday, July 1, 2026").isoformat(), "2026-07-01")
        self.assertEqual(as_of_date("July 1, 2026").isoformat(), "2026-07-01")
        for bad in ("sometime in 2026", "Wednesday, Smarch 1, 2026", "Wednesday, February 30, 2026"):
            with self.assertRaises(Unreadable):
                as_of_date(bad)


class RowShapeTests(unittest.TestCase):
    def test_a_row_is_classified_by_shape_not_by_order(self):
        shuffled = ["Per Annum", "ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF", "$195,200.00",
                    "SMITH, JOHN Q.", "EMPLOYEE"]
        row, reason = classify_row(shuffled)
        self.assertEqual(reason, "ok")
        self.assertEqual(row["title"], "ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF")
        self.assertEqual(row["amount"], 195_200.0)

    def test_the_name_is_never_returned(self):
        row, _ = classify_row(list(ROWS[1]))
        self.assertNotIn("SMITH", json.dumps(row))
        self.assertNotIn("name", row)

    def test_a_row_missing_a_column_is_refused_rather_than_guessed_at(self):
        row, reason = classify_row(["SMITH, JOHN Q.", "EMPLOYEE", "$1.00", "Per Annum"])
        self.assertIsNone(row)
        self.assertEqual(reason, "row_does_not_carry_one_name_and_one_title")

    def test_a_row_with_two_salaries_is_refused(self):
        row, reason = classify_row(["SMITH, JOHN Q.", "EMPLOYEE", "$1.00", "$2.00", "Per Annum", "A TITLE"])
        self.assertIsNone(row)
        self.assertEqual(reason, "row_does_not_carry_one_salary_status_and_pay_basis")


class TitleFoldTests(unittest.TestCase):
    def test_a_leading_rank_is_folded_and_nothing_else_is(self):
        self.assertEqual(title_core("ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF"), "CHIEF OF STAFF")
        self.assertEqual(
            title_core("DEPUTY ASSISTANT TO THE PRESIDENT AND DIRECTOR OF INTERGOVERNMENTAL AFFAIRS"),
            "DIRECTOR OF INTERGOVERNMENTAL AFFAIRS")
        # Not a leading prefix: a deputy stays a deputy.
        self.assertEqual(title_core("ASSISTANT PRESS SECRETARY"), "ASSISTANT PRESS SECRETARY")
        self.assertEqual(
            title_core("SPECIAL ASSISTANT TO THE PRESIDENT AND DEPUTY PRESS SECRETARY"),
            "DEPUTY PRESS SECRETARY")

    def test_a_principal_is_never_matched_by_a_deputy_s_row(self):
        index = index_report_titles([
            {"title": "SPECIAL ASSISTANT TO THE PRESIDENT AND DEPUTY PRESS SECRETARY", "amount": 1.0},
            {"title": "ASSISTANT PRESS SECRETARY", "amount": 2.0},
        ])
        self.assertNotIn(canonical("Press Secretary"), index)

    def test_a_fold_leaving_one_token_is_not_taken(self):
        self.assertEqual(title_core("ASSISTANT TO THE PRESIDENT AND COUNSEL"),
                         "ASSISTANT TO THE PRESIDENT AND COUNSEL")

    def test_the_gate_mirrors_the_module_s_fold_exactly(self):
        for title in [r[4] for r in ROWS] + [
            "ASSISTANT PRESS SECRETARY",
            "SPECIAL ASSISTANT TO THE PRESIDENT AND DEPUTY SOCIAL SECRETARY",
            "ASSISTANT TO THE PRESIDENT AND COUNSEL",
        ]:
            self.assertEqual(whitehouse_title_core(title), title_core(title), title)
            self.assertEqual(whitehouse_canonical(title), canonical(title), title)


class BuildRecordTests(unittest.TestCase):
    def setUp(self):
        from data_pipeline.exporter.build_graph import index_tree
        self.root = json.loads(json.dumps(BASE))
        self.node_map, _ = index_tree(self.root)
        self.parsed = parse_staff_report(_pdf(ROWS))
        self.scope = scoped_node_ids(self.root)

    def _records(self):
        return build_records(
            self.node_map, self.parsed, url=WHITEHOUSE_REPORT_URL,
            sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z", scope_ids=self.scope,
        )

    def test_it_prices_the_unambiguous_posts_only(self):
        records, report = self._records()
        self.assertEqual(
            set(records),
            {"exec-eop-who-chief-of-staff", "exec-eop-who-press-secretary",
             "exec-eop-who-director-of-intergovernmental-affairs"},
        )
        self.assertEqual(report["refused"]["reported_rate_is_zero"], 1)

    def test_a_zero_rate_is_refused(self):
        records, _ = self._records()
        self.assertNotIn("exec-eop-who-national-security-advisor", records)

    def test_a_multi_post_node_is_refused(self):
        records, report = self._records()
        self.assertNotIn("exec-eop-who-senior-advisor-to-the-president-multiple", records)
        self.assertEqual(report["refused"]["stands_for_several_posts"], 1)

    def test_a_like_named_node_outside_the_white_house_office_is_never_priced(self):
        records, _ = self._records()
        self.assertNotIn("exec-eop-omb-press-secretary", records)

    def test_a_title_two_people_hold_is_refused(self):
        root = json.loads(json.dumps(BASE))
        who = next(n for n in _walk(root) if n["id"] == SCOPE_NODE_ID)
        who["children"].append(
            {"id": "exec-eop-who-senior-policy-advisor", "name": "Senior Policy Advisor",
             "type": "Position", "children": []})
        from data_pipeline.exporter.build_graph import index_tree
        node_map, _ = index_tree(root)
        records, report = build_records(
            node_map, self.parsed, url=WHITEHOUSE_REPORT_URL, sha256="a" * 64,
            retrieved_at="2026-09-14T00:00:00Z", scope_ids=scoped_node_ids(root))
        self.assertNotIn("exec-eop-who-senior-policy-advisor", records)
        self.assertEqual(report["refused"]["title_held_by_several_people"], 1)

    def test_no_record_carries_a_name_from_the_roster(self):
        records, _ = self._records()
        blob = json.dumps(records)
        for surname in ("SMITH", "DOE", "ROE", "ACRA", "POE"):
            self.assertNotIn(surname, blob)

    def test_the_records_validate_as_partial_and_never_verified(self):
        from data_pipeline.verification import financial_evidence as fe
        records, _ = self._records()
        self.assertTrue(records)
        for node_id, record in records.items():
            out = fe.validate_record(record, self.node_map[node_id])
            self.assertEqual(fe.classify(out), "partial", node_id)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        from data_pipeline.exporter.build_graph import index_tree
        self.root = json.loads(json.dumps(BASE))
        node_map, _ = index_tree(self.root)
        self.records, _ = build_records(
            node_map, parse_staff_report(_pdf(ROWS)), url=WHITEHOUSE_REPORT_URL,
            sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z",
            scope_ids=scoped_node_ids(self.root))

    def test_it_stamps_the_field_and_writes_no_existence_claim(self):
        apply_pay_evidence(self.root, self.records)
        node = next(n for n in _walk(self.root) if n["id"] == "exec-eop-who-press-secretary")
        pay = node["positionReportedPay"]
        self.assertEqual(pay["amount"], 195_200.0)
        self.assertEqual(pay["payBasis"], "Per Annum")
        for forbidden in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(forbidden, node, forbidden)

    def test_a_renamed_node_loses_the_figure(self):
        node = next(n for n in _walk(self.root) if n["id"] == "exec-eop-who-press-secretary")
        node["name"] = "Deputy Press Secretary"
        stats = apply_pay_evidence(self.root, self.records)
        self.assertNotIn("positionReportedPay", node)
        self.assertEqual(stats["name_no_longer_matches"], 1)

    def test_the_multi_post_sweep_strips_this_field_too(self):
        apply_pay_evidence(self.root, self.records)
        node = next(n for n in _walk(self.root) if n["id"] == "exec-eop-who-press-secretary")
        node["representsPosts"] = {"text": "×2", "kind": "exact", "count": 2}
        self.assertEqual(withdraw_pay_from_multi_post_nodes(self.root), 1)
        self.assertNotIn("positionReportedPay", node)

    def test_the_field_is_withdrawn_by_the_evidence_sweep(self):
        self.assertIn("positionReportedPay", EVIDENCE_OWNED_FIELDS)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.node = {
            "id": "exec-eop-who-press-secretary", "name": "Press Secretary", "type": "Position",
            "positionReportedPay": {
                "source": "whitehouse_staff_report",
                "sourceLabel": "the White House Office's own annual report to Congress on its personnel",
                "method": "rate_reported_for_the_one_person_listed_under_this_title",
                "amount": 195_200.0,
                "rateText": "$195,200.00",
                "payBasis": "Per Annum",
                "reportedTitle": "ASSISTANT TO THE PRESIDENT AND PRESS SECRETARY",
                "reportedStatus": "EMPLOYEE",
                "titleFolded": True,
                "asOf": WHITEHOUSE_REPORT_AS_OF_TEXT,
                "costBasis": "basic_pay",
                "scopeMatch": "proxy",
                "financialEvidenceStatus": "partial",
                "amountScope": "ASSISTANT TO THE PRESIDENT AND PRESS SECRETARY",
                "quote": ("ASSISTANT TO THE PRESIDENT AND PRESS SECRETARY; $195,200.00; Per Annum; "
                          "EMPLOYEE (As of Date: Wednesday, July 1, 2026)"),
                "url": WHITEHOUSE_REPORT_URL,
                "checkedAt": "2026-09-14T00:00:00Z",
            },
        }

    def _check(self, mutate=None):
        node = json.loads(json.dumps(self.node))
        pay = node["positionReportedPay"]
        if mutate:
            mutate(node, pay)
        return reported_pay_violations(node, pay, TODAY, _label)

    def test_an_honest_record_passes(self):
        self.assertEqual(self._check(), [])

    def test_the_role_swap_between_equally_paid_posts_is_caught(self):
        # Four of the five priced posts are paid the identical $195,200, so a
        # record moved between them keeps a correct figure, quote and basis.
        def swap(node, pay):
            node["id"] = "exec-eop-who-cabinet-secretary"
            node["name"] = "Cabinet Secretary"
        self.assertTrue(self._check(swap))

    def test_a_zero_rate_is_refused_by_the_gate_too(self):
        self.assertTrue(self._check(lambda n, p: (p.update({"amount": 0.0, "rateText": "$0.00"}))))

    def test_a_self_consistently_inflated_figure_is_caught(self):
        def inflate(node, pay):
            pay["amount"] = 300_000.0
            pay["rateText"] = "$300,000.00"
            pay["quote"] = pay["quote"].replace("$195,200.00", "$300,000.00")
        self.assertTrue(self._check(inflate))

    def test_a_title_that_is_not_this_node_s_is_caught(self):
        self.assertTrue(self._check(
            lambda n, p: p.__setitem__("reportedTitle", "ASSISTANT TO THE PRESIDENT AND STAFF SECRETARY")))

    def test_a_renamed_node_is_caught(self):
        self.assertTrue(self._check(lambda n, p: n.__setitem__("name", "Deputy Press Secretary")))

    def test_a_forged_url_is_caught(self):
        for url in ("https://whitehouse-archive.example.com/staff.pdf",
                    "https://www.whitehouse.gov/disclosures/"):
            self.assertTrue(self._check(lambda n, p, u=url: p.__setitem__("url", u)), url)

    def test_a_roster_name_in_any_field_is_caught(self):
        self.assertTrue(self._check(lambda n, p: p.__setitem__("sourceLabel", "ACRA, ELLIE G.")))

    def test_the_as_of_text_is_not_accepted_as_a_name(self):
        # The detector must not fire on the report's own date wording.
        self.assertEqual(self._check(), [])

    def test_it_cannot_be_used_as_proof_the_post_exists_or_is_placed(self):
        self.assertTrue(self._check(lambda n, p: n.__setitem__("verificationMethod", p["method"])))
        self.assertTrue(self._check(lambda n, p: n.__setitem__("placementMethod", p["method"])))
        self.assertTrue(self._check(
            lambda n, p: n.__setitem__("sourceUrls", [p["url"]])))

    def test_it_cannot_sit_beside_a_measured_cost(self):
        self.assertTrue(self._check(lambda n, p: n.__setitem__("cost_status", "official")))
        self.assertTrue(self._check(lambda n, p: n.__setitem__("costVerificationStatus", "verified")))

    def test_a_multi_post_node_or_a_non_post_is_caught(self):
        self.assertTrue(self._check(
            lambda n, p: n.__setitem__("representsPosts", {"text": "×3", "kind": "exact", "count": 3})))
        self.assertTrue(self._check(lambda n, p: n.__setitem__("type", "Office")))

    def test_a_node_outside_the_white_house_office_is_caught(self):
        self.assertTrue(self._check(lambda n, p: n.__setitem__("id", "exec-dept-dod-secretary")))

    def test_a_wrong_status_or_pay_basis_is_caught(self):
        self.assertTrue(self._check(lambda n, p: p.__setitem__("reportedStatus", "CONTRACTOR")))
        self.assertTrue(self._check(lambda n, p: p.__setitem__("payBasis", "Per Diem")))

    def test_a_future_date_is_caught(self):
        self.assertTrue(self._check(lambda n, p: p.__setitem__("checkedAt", "2027-01-01T00:00:00Z")))
        self.assertTrue(self._check(lambda n, p: p.__setitem__("asOf", "Thursday, July 1, 2027")))

    def test_a_quote_missing_the_figure_or_the_title_is_caught(self):
        self.assertTrue(self._check(lambda n, p: p.__setitem__("quote", "Per Annum; EMPLOYEE")))

    def test_dropping_the_cents_is_caught(self):
        self.assertTrue(self._check(lambda n, p: p.__setitem__("rateText", "$195,200")))

    def test_the_gates_own_reader_agrees_with_the_modules_parser(self):
        """The gate re-reads the report with a second, independent stdlib
        extraction — it imports nothing from data_pipeline by design. The two
        must agree exactly, or one of them is wrong about the source."""
        from collections import defaultdict
        roster = whitehouse_roster()
        rows = load_staff_report(DEFAULT_REPORT_PDF)["report"]["rows"]
        by_title = defaultdict(list)
        for row in rows:
            by_title[canonical(str(row["title"]))].append(float(row["amount"]))
        self.assertEqual(set(roster), set(by_title))
        for title, amounts in by_title.items():
            self.assertEqual(roster[title][1], len(amounts), title)
            if len(amounts) == 1:
                self.assertAlmostEqual(roster[title][0], amounts[0], places=2, msg=title)

    def test_every_published_record_is_a_title_one_person_holds(self):
        evidence = json.loads(
            (Path(__file__).resolve().parents[1] / "data" / "verification"
             / "whitehouse_pay_evidence.json").read_text(encoding="utf-8"))
        roster = whitehouse_roster()
        self.assertTrue(evidence["nodes"])
        for node_id, record in evidence["nodes"].items():
            entry = roster.get(whitehouse_canonical(record["reportedTitle"]))
            self.assertIsNotNone(entry, node_id)
            self.assertEqual(entry[1], 1, f"{node_id} prices a title {entry[1]} people hold")
            self.assertAlmostEqual(entry[0], float(record["amount"]), places=2, msg=node_id)
            self.assertGreater(float(record["amount"]), 0, node_id)


class DeriveScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"wh-derive-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_dry_run_writes_nothing_and_reports_the_split(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_whitehouse_pay_evidence.main([
                "d", "--base-graph", str(base), "--report", str(DEFAULT_REPORT_PDF), "--dry-run",
            ])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("priced", out.getvalue())
        self.assertFalse((self.tmp / "whitehouse_pay_evidence.json").exists())

    def test_the_gate_passes_on_a_graph_carrying_only_this_module_s_evidence(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out_path = self.tmp / "whitehouse_pay_evidence.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_whitehouse_pay_evidence.main([
                "d", "--base-graph", str(base), "--report", str(DEFAULT_REPORT_PDF), "--out", str(out_path),
            ])
        self.assertEqual(code, 0, out.getvalue())
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {
                "government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "n.json", edges_output_path=self.tmp / "e.json",
            validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True,
            evidence_path=None, sites_path=None, whitehouse_pay_evidence_path=out_path,
        )
        out2 = io.StringIO()
        with redirect_stdout(out2):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out2.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        priced = [n for n in _walk(graph) if isinstance(n.get("positionReportedPay"), dict)]
        self.assertEqual(len(priced), 5)
        # And the published artefact carries no roster name anywhere.
        blob = result.graph_path.read_text(encoding="utf-8")
        for surname in ("ACRA", "ADAMIAN", "GEBBIA", "ADKISSON"):
            self.assertNotIn(surname, blob)


class ExpansionScriptTests(unittest.TestCase):
    """The script that adds White House Office nodes from the same roster.

    It is the only writer of that subtree — the curated file is never
    hand-edited — so the properties that matter are: it adds what the report
    prints, it invents nothing, it never touches a curated node, and running
    it twice is a no-op.
    """

    def setUp(self) -> None:
        from scripts import expand_whitehouse_office as expand
        self.expand = expand
        self.tmp = TEST_TMP_ROOT / f"wh-expand-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")

    def _run(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.expand.main(["d", "--base-graph", str(self.base),
                                     "--report", str(DEFAULT_REPORT_PDF), *args])
        return code, out.getvalue()

    def _who(self):
        base = json.loads(self.base.read_text(encoding="utf-8"))
        return self.expand.find_node(base, SCOPE_NODE_ID)

    def test_a_dry_run_writes_nothing(self):
        before = self.base.read_text(encoding="utf-8")
        code, output = self._run("--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.base.read_text(encoding="utf-8"), before)

    def test_it_adds_the_report_s_titles_and_is_idempotent(self):
        code, _ = self._run()
        self.assertEqual(code, 0)
        first = len(self._who()["children"])
        self.assertGreater(first, len(BASE["children"][1]["children"][0]["children"][0]["children"]))
        code, output = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(len(self._who()["children"]), first, "a second run added nodes")
        self.assertIn("nodes to add                          : 0", output)

    def test_a_curated_node_is_never_renamed_retyped_or_removed(self):
        before = {c["id"]: dict(c) for c in self._who()["children"]}
        self._run()
        after = {c["id"]: c for c in self._who()["children"]}
        for node_id, original in before.items():
            self.assertIn(node_id, after, f"{node_id} was removed")
            for field in ("name", "type", "desc"):
                self.assertEqual(after[node_id].get(field), original.get(field), f"{node_id}.{field}")

    def test_every_added_node_says_where_it_came_from(self):
        before = {c["id"] for c in self._who()["children"]}
        self._run()
        added = [c for c in self._who()["children"] if c["id"] not in before]
        self.assertTrue(added)
        for node in added:
            self.assertEqual(node["type"], "Position")
            self.assertEqual(node["descriptionSource"], "generated_from_whitehouse_staff_report")
            self.assertEqual(node["structureSource"], "listed_in_whitehouse_staff_report")
            # The description quotes the report's own title and either states a
            # rate or says the appointment is uncompensated; it never describes
            # duties, which the report does not give. A rate of $0.00 is never
            # printed as what the post pays: whitehouse_pay.py refuses to
            # publish a zero as a rate, and since 2026-09-18 this sentence does
            # too, attributing the arrangement to the person holding the post.
            self.assertIn(node["reportedTitle"], node["desc"])
            priced = "per annum" in node["desc"]
            unpaid = "uncompensated appointment" in node["desc"]
            self.assertTrue(priced or unpaid, node["desc"])
            self.assertNotIn("$0.00", node["desc"])

    def test_an_uncompensated_appointment_is_the_person_s_and_never_the_post_s_rate(self):
        """Ten of the report's 408 rows read $0.00.

        `whitehouse_pay.py` refuses to publish a zero as a rate, on the stated
        ground that an uncompensated arrangement is a fact about a person and
        not about the post. The generated description published it anyway, as
        "at $0.00 per annum", on 8 nodes — the same claim in prose, on the
        surface a reader actually sees. Pinned in both directions here: a paid
        title still prints its rate, an unpaid one says what it is instead, and
        a mixed group reports the range of what was actually paid rather than
        a band starting at nothing.
        """
        from scripts.expand_whitehouse_office import pay_sentence

        paid = pay_sentence(1, [195200.0])
        self.assertIn("at $195,200.00 per annum", paid)
        self.assertNotIn("uncompensated", paid)

        unpaid = pay_sentence(1, [0.0])
        self.assertIn("uncompensated appointment", unpaid)
        self.assertIn("rather than a rate the post pays", unpaid)
        self.assertNotIn("$0.00", unpaid)
        self.assertNotIn("per annum", unpaid)

        mixed = pay_sentence(5, [0.0, 0.0, 121785.0, 150000.0, 169279.0])
        self.assertIn("paid between $121,785.00 and $169,279.00 per annum", mixed,
                      "the range is what was actually paid, not a band starting at nothing")
        self.assertIn("with 2 serving without pay", mixed)
        self.assertNotIn("$0.00", mixed)

        one_paid = pay_sentence(2, [0.0, 90000.0])
        self.assertIn("one at $90,000.00 per annum", one_paid)
        self.assertIn("with one serving without pay", one_paid)

        none_paid = pay_sentence(3, [0.0, 0.0, 0.0])
        self.assertIn("uncompensated appointment", none_paid)
        self.assertIn("those people", none_paid)
        self.assertNotIn("$0.00", none_paid)

    def test_the_generated_descriptions_carry_no_zero_rate_in_the_published_graph(self):
        """The whole point, checked where a reader would see it."""
        graph_path = Path(__file__).resolve().parents[1] / "output" / "graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        found = []

        def walk(node):
            if node.get("descriptionSource") == "generated_from_whitehouse_staff_report":
                if "$0.00" in str(node.get("desc") or ""):
                    found.append(node.get("id"))
            for child in node.get("children") or []:
                walk(child)

        walk(graph)
        self.assertEqual(found, [], "a generated description still prints a rate of $0.00")

    def test_a_title_several_people_hold_becomes_one_node_with_the_count(self):
        self._run()
        multi = [c for c in self._who()["children"] if c.get("representsPosts")
                 and c.get("structureSource") == "listed_in_whitehouse_staff_report"]
        self.assertTrue(multi)
        roster = whitehouse_roster()
        for node in multi:
            held = node["representsPosts"]["count"]
            self.assertEqual(node["representsPosts"]["kind"], "exact")
            self.assertIn(f"(×{held})", node["name"])
            self.assertEqual(roster[whitehouse_canonical(node["reportedTitle"])][1], held)

    def test_added_ids_are_unique_and_scoped_to_the_office(self):
        self._run()
        ids = [c["id"] for c in self._who()["children"]]
        self.assertEqual(len(ids), len(set(ids)))
        for node_id in ids:
            self.assertTrue(node_id.startswith(SCOPE_NODE_ID + "-"), node_id)

    def test_no_added_node_carries_a_roster_name(self):
        self._run()
        blob = self.base.read_text(encoding="utf-8")
        # The roster's own "LAST, FIRST M." form, not bare substrings: "AGEN"
        # is inside "AGENCY" and would false-positive on honest text.
        self.assertIsNone(re.search(r"\b[A-Z][A-Z.'\-]{1,}, +[A-Z][A-Z.'\-]*\b", blob))

    def test_the_title_casing_is_mechanical_and_keeps_initialisms(self):
        self.assertEqual(self.expand.title_case("ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF"),
                         "Assistant to the President and Chief of Staff")
        self.assertEqual(self.expand.title_case("DIRECTOR OF OMB"), "Director of OMB")
        # A small word is still capitalised when it opens or closes the title.
        self.assertEqual(self.expand.title_case("THE SECRETARY"), "The Secretary")


class PublishedGraphTests(unittest.TestCase):
    def test_the_published_graph_carries_no_roster_name(self):
        path = Path(__file__).resolve().parents[1] / "output" / "graph.json"
        if not path.exists():  # pragma: no cover - the published graph is tracked
            self.skipTest("no published graph")
        graph = json.loads(path.read_text(encoding="utf-8"))
        for node in _walk(graph):
            pay = node.get("positionReportedPay")
            if not isinstance(pay, dict):
                continue
            for field, value in pay.items():
                if field in ("quote", "amountScope", "reportedTitle"):
                    continue
                if isinstance(value, str):
                    self.assertIsNone(
                        re.search(r"\b[A-Z][A-Z.'\-]{1,}, +[A-Z][A-Z.'\-]*\b", value),
                        f"{node.get('id')} {field}={value!r}")


if __name__ == "__main__":
    unittest.main()
