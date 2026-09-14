"""The Senate's own salary schedule: the parser, exactly which three
leadership nodes it prices and why nothing else, and every way a forged
rate could reach the release gate.

Both directions throughout: an honest rate is published, and each way of
forging one is caught.
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
from data_pipeline.verification.congressional_pay import (
    DEFAULT_TABLE_HTML,
    LEADERSHIP_NODE_IDS,
    Unreadable,
    apply_pay_evidence,
    build_records,
    load_senate_salary_table,
    parse_senate_salary_table,
)
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, apply_evidence_to_tree
from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes
from scripts import derive_congressional_pay_evidence
from scripts.validate_published_graph import (
    SENATE_LEADERSHIP_RATE,
    SENATE_SALARY_BASE_RATE,
    SENATE_SALARY_YEAR,
    STATUTORY_PAY_NODE_TIERS,
    statutory_pay_violations,
)
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ID = "the-constitution-of-the-united-states"


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _label(node):
    return f"[{node.get('id')}]"


PAGE = """
<html><body>
<table id="SortableData_table"><thead><tr><th>Years</th><th>Salary</th></tr></thead>
<tbody>
<tr><td><span style="display:none">1789_1815</span>1789&#150;1815</td><td>$6.00 per diem</td></tr>
<tr><td><span style="display:none">2025</span>2025</td><td>$174,000 per annum</td></tr>
<tr><td><span style="display:none">2026</span>2026</td><td>$174,000 per annum</td></tr>
</tbody></table>
<footer><p>Note: Since the early 1980s, Senate leaders&ndash;majority and minority leaders, and the president pro tempore&ndash;have received higher salaries than other members. Currently, leaders earn $193,400 per year. </p></footer>
<footer><p>Contact | Content Responsibility | Usage Policy</p></footer>
</body></html>
"""

BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-senate", "name": "United States Senate", "type": "Chamber", "children": [
                {"id": "leg-senate-leadership", "name": "Senate Leadership", "type": "Division", "children": [
                    {"id": "leg-senate-leadership-president-of-the-senate-vice-president", "name": "President of the Senate (Vice President)", "type": "Position", "children": []},
                    {"id": "leg-senate-leadership-president-pro-tempore", "name": "President Pro Tempore", "type": "Position", "children": []},
                    {"id": "leg-senate-leadership-majority-leader", "name": "Majority Leader", "type": "Position", "children": []},
                    {"id": "leg-senate-leadership-minority-leader", "name": "Minority Leader", "type": "Position", "children": []},
                    {"id": "leg-senate-leadership-assistant-majority-leader", "name": "Assistant Majority Leader", "type": "Position", "children": []},
                    {"id": "leg-senate-leadership-assistant-minority-leader", "name": "Assistant Minority Leader", "type": "Position", "children": []},
                ]},
                {"id": "leg-senate-offices", "name": "Individual Senator Offices (100)", "type": "Division", "children": [
                    {"id": "leg-senate-offices-regional-representative-4", "name": "Regional Representative (×4)", "type": "Position",
                     "representsPosts": {"text": "×4", "kind": "exact", "count": 4}, "children": []},
                ]},
            ]},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

TABLE_URL = "https://www.senate.gov/senators/SenateSalariesSince1789.htm"


class ParserTestCase(unittest.TestCase):
    def test_it_reads_the_current_year_base_rate_and_the_leadership_footnote(self):
        table = parse_senate_salary_table(PAGE)
        self.assertEqual(table["currentYear"], "2026")
        self.assertEqual(table["baseYears"]["2026"]["amount"], 174_000.0)
        self.assertEqual(table["leadershipAmount"], 193_400.0)
        self.assertIn("president pro tempore", table["footnote"].casefold())

    def test_the_site_wide_footer_further_down_the_page_never_wins(self):
        # Confirms the parser reads the FIRST <footer><p> after the table,
        # not the last one anywhere on the page.
        table = parse_senate_salary_table(PAGE)
        self.assertNotIn("Content Responsibility", table["footnote"])

    def test_the_hidden_sort_key_span_does_not_corrupt_the_year(self):
        # <span style="display:none">2026</span>2026 must read as "2026",
        # not "20262026".
        table = parse_senate_salary_table(PAGE)
        self.assertIn("2026", table["baseYears"])
        self.assertNotIn("20262026", table["baseYears"])

    def test_a_reshaped_table_is_refused(self):
        page = PAGE.replace("<th>Salary</th>", "<th>Compensation</th>")
        with self.assertRaises(Unreadable):
            parse_senate_salary_table(page)

    def test_a_missing_footnote_is_refused(self):
        page = PAGE.replace(
            '<footer><p>Note: Since the early 1980s, Senate leaders&ndash;majority and minority leaders, '
            'and the president pro tempore&ndash;have received higher salaries than other members. '
            'Currently, leaders earn $193,400 per year. </p></footer>',
            "",
        )
        with self.assertRaises(Unreadable):
            parse_senate_salary_table(page)

    def test_the_real_committed_fixture_matches_the_gate_s_mirror(self):
        loaded = load_senate_salary_table(DEFAULT_TABLE_HTML)
        table = loaded["table"]
        self.assertEqual(table["currentYear"], SENATE_SALARY_YEAR)
        self.assertEqual(table["baseYears"][table["currentYear"]]["amount"], SENATE_SALARY_BASE_RATE)
        self.assertEqual(table["leadershipAmount"], SENATE_LEADERSHIP_RATE)
        self.assertEqual(loaded["url"], TABLE_URL)

    def test_a_tampered_fixture_is_refused_by_its_own_digest(self):
        tmp = TEST_TMP_ROOT / f"cong-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, tmp, True)
        html_path = tmp / "table.html"
        html_path.write_text(PAGE, encoding="utf-8")
        meta = json.loads((PROJECT_ROOT / "tests/fixtures/congress/senate_salaries_since_1789.html.meta.json").read_text())
        meta_path = tmp / "table.html.meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(Unreadable):
            load_senate_salary_table(html_path)


class BuildAndValidateTests(unittest.TestCase):
    def test_build_records_prices_exactly_the_three_named_leaders(self):
        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, report = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        self.assertEqual(set(records), {
            "leg-senate-leadership-president-pro-tempore",
            "leg-senate-leadership-majority-leader",
            "leg-senate-leadership-minority-leader",
        })
        self.assertEqual(records["leg-senate-leadership-majority-leader"]["amount"], 193_400.0)
        self.assertEqual(records["leg-senate-leadership-majority-leader"]["scopeMatch"], "proxy")
        self.assertEqual(report["priced"], 3)

    def test_the_whip_positions_and_the_vice_president_are_never_priced(self):
        # The footnote names three roles; whips and the VP are not among
        # them, and this module must never guess that an unnamed role gets
        # either the leaders' rate or the base rate.
        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        self.assertNotIn("leg-senate-leadership-assistant-majority-leader", records)
        self.assertNotIn("leg-senate-leadership-assistant-minority-leader", records)
        self.assertNotIn("leg-senate-leadership-president-of-the-senate-vice-president", records)

    def test_a_multi_post_leadership_id_would_be_refused_if_one_existed(self):
        # Defence in depth: LEADERSHIP_NODE_IDS names only single-holder
        # nodes today, but if one were ever curated with a multiplicity,
        # build_records must still refuse it rather than price a group.
        table = parse_senate_salary_table(PAGE)
        tree = json.loads(json.dumps(BASE))
        node_map = index_tree(tree)[0]
        node_map["leg-senate-leadership-majority-leader"]["representsPosts"] = {"text": "×2", "kind": "exact", "count": 2}
        records, report = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        self.assertNotIn("leg-senate-leadership-majority-leader", records)
        self.assertEqual(report["refused"]["stands_for_several_posts"], 1)

    def test_every_priced_record_validates_and_is_never_verified(self):
        from data_pipeline.verification import financial_evidence as fe

        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        for node_id, record in records.items():
            out = fe.validate_record(record, node_map[node_id])
            self.assertEqual(fe.classify(out), "partial")


class ApplyTests(unittest.TestCase):
    def test_stamps_positionStatutoryPay_and_never_touches_existence_fields(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        stats = apply_pay_evidence(tree, records)
        self.assertEqual(stats["priced"], 3)
        node_map = index_tree(tree)[0]
        pay = node_map["leg-senate-leadership-majority-leader"]["positionStatutoryPay"]
        self.assertEqual(pay["amount"], 193_400.0)
        self.assertEqual(pay["source"], "senate_salary_schedule")
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod", "verificationStatus"):
            self.assertNotIn(field, node_map["leg-senate-leadership-majority-leader"])

    def test_multi_post_withdrawal_strips_positionStatutoryPay_too(self):
        tree = json.loads(json.dumps(BASE))
        node_map = index_tree(tree)[0]
        node_map["leg-senate-offices-regional-representative-4"]["positionStatutoryPay"] = {"amount": 193_400.0}
        withdrawn = withdraw_pay_from_multi_post_nodes(tree)
        self.assertEqual(withdrawn, 1)
        self.assertNotIn("positionStatutoryPay", index_tree(tree)[0]["leg-senate-offices-regional-representative-4"])

    def test_positionStatutoryPay_is_withdrawn_when_evidence_no_longer_supports_it(self):
        self.assertIn("positionStatutoryPay", EVIDENCE_OWNED_FIELDS)
        tree = json.loads(json.dumps(BASE))
        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        self.assertIn("positionStatutoryPay", index_tree(tree)[0]["leg-senate-leadership-majority-leader"])
        apply_evidence_to_tree(tree, {})
        self.assertNotIn("positionStatutoryPay", index_tree(tree)[0]["leg-senate-leadership-majority-leader"])


class GateTests(unittest.TestCase):
    def _apply(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_senate_salary_table(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        node_map = index_tree(tree)[0]
        for node_id in LEADERSHIP_NODE_IDS:
            pay = node_map[node_id].get("positionStatutoryPay")
            if pay:
                pay["url"] = TABLE_URL
                pay["checkedAt"] = "2026-09-14T00:00:00Z"
        return tree, node_map

    def test_every_priced_node_has_a_known_tier_in_the_gate_s_mirror(self):
        for node_id in LEADERSHIP_NODE_IDS:
            self.assertIn(node_id, STATUTORY_PAY_NODE_TIERS)

    def test_an_honest_record_passes(self):
        _, node_map = self._apply()
        node = node_map["leg-senate-leadership-majority-leader"]
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertEqual(violations, [])

    def test_a_role_swap_between_two_equal_pay_leadership_nodes_is_caught(self):
        # All three Senate leaders share one figure, so an amount check
        # alone cannot catch the Majority Leader's record being filed as
        # the President Pro Tempore's; only a check tied to the node's own
        # identity can.
        _, node_map = self._apply()
        node = node_map["leg-senate-leadership-majority-leader"]
        pay = dict(node["positionStatutoryPay"])
        pay["seatTier"] = "president pro tempore"
        violations = statutory_pay_violations(node, pay, "2026-09-15", _label)
        self.assertTrue(any("on a node that is a" in v for v in violations))

    def test_every_forgery_this_module_makes_possible_is_caught(self):
        _, node_map = self._apply()
        node = node_map["leg-senate-leadership-majority-leader"]
        base_pay = node["positionStatutoryPay"]
        attacks = {
            "wrong amount": {**base_pay, "amount": 1.0},
            "wrong year": {**base_pay, "year": "1999", "effective": "1999-01-01"},
            "fabricated footnote": {**base_pay, "footnotes": ["nothing like this was on the page"]},
            "wrong url": {**base_pay, "url": "https://example.com/"},
            "future retrieval date": {**base_pay, "checkedAt": "2099-01-01T00:00:00Z"},
            "unknown source": {**base_pay, "source": "made_up_source"},
            "quote without the figure": {**base_pay, "quote": "irrelevant text"},
            "rate text disagrees with the amount": {**base_pay, "rateText": "$1"},
        }
        for name, pay in attacks.items():
            with self.subTest(attack=name):
                violations = statutory_pay_violations(node, pay, "2026-09-15", _label)
                self.assertTrue(violations, f"{name} was not caught")

    def test_the_sourceUrls_leak_this_module_must_never_repeat_is_caught(self):
        _, node_map = self._apply()
        node = node_map["leg-senate-leadership-majority-leader"]
        node["sourceUrls"] = [TABLE_URL]
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertTrue(any("among the sources that it exists" in v for v in violations))

    def test_a_node_from_the_wrong_branch_is_caught(self):
        _, node_map = self._apply()
        node = dict(node_map["leg-senate-leadership-majority-leader"])
        node["id"] = "exec-dept-doe"
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertTrue(any("outside the" in v for v in violations))


class DeriveScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"cong-derive-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_dry_run_writes_nothing_and_reports_the_split(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_congressional_pay_evidence.main([
                "d", "--base-graph", str(base), "--table", str(DEFAULT_TABLE_HTML), "--dry-run",
            ])
        self.assertEqual(code, 0)
        self.assertIn("priced", out.getvalue())

    def test_the_gate_passes_on_a_graph_carrying_only_this_module_s_evidence(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out_path = self.tmp / "congressional_pay_evidence.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_congressional_pay_evidence.main([
                "d", "--base-graph", str(base), "--table", str(DEFAULT_TABLE_HTML), "--out", str(out_path),
            ])
        self.assertEqual(code, 0, out.getvalue())
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True,
            evidence_path=None, sites_path=None, congressional_pay_evidence_path=out_path,
        )
        out2 = io.StringIO()
        with redirect_stdout(out2):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out2.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        priced = [n for n in _walk(graph) if isinstance(n.get("positionStatutoryPay"), dict)]
        self.assertEqual(len(priced), 3)


if __name__ == "__main__":
    unittest.main()
