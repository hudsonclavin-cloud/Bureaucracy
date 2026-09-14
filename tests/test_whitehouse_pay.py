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
    WHITEHOUSE_REPORTED_PAY,
    WHITEHOUSE_REPORT_AS_OF_TEXT,
    WHITEHOUSE_REPORT_URL,
    reported_pay_violations,
    whitehouse_canonical,
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

    def test_the_mirror_matches_the_published_evidence(self):
        evidence = json.loads(
            (Path(__file__).resolve().parents[1] / "data" / "verification"
             / "whitehouse_pay_evidence.json").read_text(encoding="utf-8"))
        mirrored = {k: (v["reportedTitle"], float(v["amount"])) for k, v in evidence["nodes"].items()}
        self.assertEqual(mirrored, dict(WHITEHOUSE_REPORTED_PAY))


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
