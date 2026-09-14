"""The U.S. Courts' Judicial Compensation table: the parser, which nodes it
prices and which it honestly refuses, and every way a forged rate could
reach the release gate.

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
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, apply_evidence_to_tree
from data_pipeline.verification.judicial_pay import (
    DEFAULT_TABLE_HTML,
    DISTRICT_STRUCTURE_TEMPLATE_ID,
    Unreadable,
    apply_pay_evidence,
    build_records,
    classify_seat,
    load_judicial_compensation,
    parse_judicial_compensation,
)
from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes
from scripts import derive_judicial_pay_evidence
from scripts.validate_published_graph import (
    JUDICIAL_COMPENSATION_FOOTNOTES,
    JUDICIAL_COMPENSATION_TIERS,
    JUDICIAL_COMPENSATION_YEAR,
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
<table class="table usa-table"><tbody>
<tr><td><strong>Year</strong></td><td><strong>District Judges</strong></td><td><strong>Circuit Judges</strong></td><td><strong>Associate Justices</strong></td><td><strong>Chief Justice</strong></td></tr>
<tr><td>2026</td><td>$249,900</td><td>$264,900</td><td>$306,600</td><td>$320,700</td></tr>
<tr><td>2025</td><td>$247,400</td><td>$262,300</td><td>$303,600</td><td>$317,500</td></tr>
</tbody></table>
</body></html>
"""

BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": [
            {"id": "jud-scotus", "name": "Supreme Court", "type": "Court", "children": [
                {"id": "jud-scotus-chief-justice-of-the-united-states", "name": "Chief Justice of the United States", "type": "Position", "children": []},
                {"id": "jud-scotus-associate-justice-8", "name": "Associate Justice (×8)", "type": "Position",
                 "representsPosts": {"text": "×8", "kind": "exact", "count": 8}, "children": []},
            ]},
            {"id": "jud-circuit-1st-circuit", "name": "1st Circuit", "type": "Court", "children": [
                {"id": "jud-circuit-1st-circuit-chief-judge-1st-circuit", "name": "Chief Judge, 1st Circuit", "type": "Position", "children": []},
                {"id": "jud-circuit-1st-circuit-circuit-judge-5-active", "name": "Circuit Judge (×5 active + senior judges)", "type": "Position",
                 "representsPosts": {"text": "×5 active + senior judges", "kind": "unstated"}, "children": []},
            ]},
            {"id": "jud-district-sdny", "name": "SDNY", "type": "Court", "children": [
                {"id": "jud-district-sdny-chief-judge-sdny", "name": "Chief Judge, SDNY", "type": "Position", "children": []},
            ]},
            {"id": "jud-district-structure", "name": "All 94 District Courts — Standard Structure", "type": "Template", "children": [
                {"id": DISTRICT_STRUCTURE_TEMPLATE_ID, "name": "Chief Judge", "type": "Position", "children": []},
            ]},
            {"id": "jud-support", "name": "Support", "type": "Division", "children": [
                {"id": "jud-support-fjc-director-fjc", "name": "Director, FJC", "type": "Position", "children": []},
            ]},
        ]},
    ],
}

TABLE_URL = "https://www.uscourts.gov/about-federal-courts/about-federal-judges/judicial-compensation"


class ParserTestCase(unittest.TestCase):
    def test_it_reads_the_current_year_first_and_every_tier(self):
        table = parse_judicial_compensation(PAGE)
        self.assertEqual(table["currentYear"], "2026")
        self.assertEqual(table["years"]["2026"]["tiers"]["chief justice"]["amount"], 320_700.0)
        self.assertEqual(table["years"]["2026"]["tiers"]["district judges"]["amountRaw"], "249,900")
        self.assertEqual(table["years"]["2025"]["tiers"]["chief justice"]["amount"], 317_500.0)

    def test_a_reshaped_table_is_refused(self):
        page = PAGE.replace("<strong>Chief Justice</strong>", "<strong>Supreme Leader</strong>")
        with self.assertRaises(Unreadable):
            parse_judicial_compensation(page)

    def test_two_tables_on_the_page_is_refused(self):
        page = PAGE.replace("</body>", '<table class="table usa-table"><tbody><tr><td>x</td></tr></tbody></table></body>')
        with self.assertRaises(Unreadable):
            parse_judicial_compensation(page)

    def test_a_year_printed_twice_is_refused(self):
        page = PAGE.replace(
            '<tr><td>2025</td><td>$247,400</td><td>$262,300</td><td>$303,600</td><td>$317,500</td></tr>',
            '<tr><td>2026</td><td>$247,400</td><td>$262,300</td><td>$303,600</td><td>$317,500</td></tr>',
        )
        with self.assertRaises(Unreadable):
            parse_judicial_compensation(page)

    def test_the_real_committed_fixture_matches_the_gate_s_mirror(self):
        loaded = load_judicial_compensation(DEFAULT_TABLE_HTML)
        table = loaded["table"]
        self.assertEqual(table["currentYear"], JUDICIAL_COMPENSATION_YEAR)
        current = {k: v["amount"] for k, v in table["years"][table["currentYear"]]["tiers"].items()}
        self.assertEqual(current, JUDICIAL_COMPENSATION_TIERS)
        self.assertEqual(loaded["url"], TABLE_URL)

    def test_a_tampered_fixture_is_refused_by_its_own_digest(self):
        tmp = TEST_TMP_ROOT / f"jud-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, tmp, True)
        html_path = tmp / "table.html"
        html_path.write_text(PAGE, encoding="utf-8")
        meta = json.loads((PROJECT_ROOT / "tests/fixtures/uscourts/judicial_compensation.html.meta.json").read_text())
        meta_path = tmp / "table.html.meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(Unreadable):
            load_judicial_compensation(html_path)


class SeatClassificationTests(unittest.TestCase):
    def _node_map(self):
        return index_tree(json.loads(json.dumps(BASE)))[0]

    def test_the_chief_justice_a_circuit_s_chief_judge_and_a_district_s_chief_judge_are_priced(self):
        nodes = self._node_map()
        self.assertEqual(classify_seat("jud-scotus-chief-justice-of-the-united-states", nodes["jud-scotus-chief-justice-of-the-united-states"]),
                         ("chief justice", "the_chief_justice"))
        self.assertEqual(classify_seat("jud-circuit-1st-circuit-chief-judge-1st-circuit", nodes["jud-circuit-1st-circuit-chief-judge-1st-circuit"])[0],
                         "circuit judges")
        self.assertEqual(classify_seat("jud-district-sdny-chief-judge-sdny", nodes["jud-district-sdny-chief-judge-sdny"])[0], "district judges")

    def test_a_node_standing_for_several_posts_is_refused_however_its_id_looks(self):
        nodes = self._node_map()
        column, reason = classify_seat("jud-scotus-associate-justice-8", nodes["jud-scotus-associate-justice-8"])
        self.assertIsNone(column)
        self.assertEqual(reason, "stands_for_several_posts")
        column, reason = classify_seat("jud-circuit-1st-circuit-circuit-judge-5-active", nodes["jud-circuit-1st-circuit-circuit-judge-5-active"])
        self.assertIsNone(column)
        self.assertEqual(reason, "stands_for_several_posts")

    def test_the_generic_district_structure_template_is_refused_by_id(self):
        nodes = self._node_map()
        column, reason = classify_seat(DISTRICT_STRUCTURE_TEMPLATE_ID, nodes[DISTRICT_STRUCTURE_TEMPLATE_ID])
        self.assertIsNone(column)
        self.assertEqual(reason, "generic_structure_template_not_a_specific_court")

    def test_an_unrelated_position_is_refused(self):
        nodes = self._node_map()
        column, reason = classify_seat("jud-support-fjc-director-fjc", nodes["jud-support-fjc-director-fjc"])
        self.assertIsNone(column)
        self.assertEqual(reason, "not_a_seat_this_table_prices")

    def test_a_non_position_node_is_refused(self):
        nodes = self._node_map()
        column, reason = classify_seat("jud-scotus", nodes["jud-scotus"])
        self.assertIsNone(column)
        self.assertEqual(reason, "not_a_position")


class BuildAndValidateTests(unittest.TestCase):
    def test_build_records_prices_exactly_the_real_seats_and_refuses_the_rest(self):
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, report = build_records(
            node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z",
        )
        self.assertEqual(set(records), {
            "jud-scotus-chief-justice-of-the-united-states",
            "jud-circuit-1st-circuit-chief-judge-1st-circuit",
            "jud-district-sdny-chief-judge-sdny",
        })
        self.assertEqual(records["jud-scotus-chief-justice-of-the-united-states"]["amount"], 320_700.0)
        self.assertEqual(records["jud-scotus-chief-justice-of-the-united-states"]["scopeMatch"], "proxy")
        self.assertEqual(report["priced"], 3)
        self.assertEqual(report["refused"]["stands_for_several_posts"], 2)
        self.assertEqual(report["refused"]["generic_structure_template_not_a_specific_court"], 1)

    def test_every_priced_record_validates_and_is_never_verified(self):
        from data_pipeline.verification import financial_evidence as fe

        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        for node_id, record in records.items():
            out = fe.validate_record(record, node_map[node_id])
            self.assertEqual(fe.classify(out), "partial")


class ApplyTests(unittest.TestCase):
    def test_stamps_positionStatutoryPay_and_never_touches_existence_fields(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        stats = apply_pay_evidence(tree, records)
        self.assertEqual(stats["priced"], 3)
        node_map = index_tree(tree)[0]
        pay = node_map["jud-scotus-chief-justice-of-the-united-states"]["positionStatutoryPay"]
        self.assertEqual(pay["amount"], 320_700.0)
        self.assertEqual(pay["source"], "uscourts_judicial_compensation")
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod", "verificationStatus"):
            self.assertNotIn(field, node_map["jud-scotus-chief-justice-of-the-united-states"])

    def test_an_unknown_node_and_a_non_position_are_counted_not_stamped(self):
        tree = json.loads(json.dumps(BASE))
        fabricated = {
            "ghost-node": {"nodeId": "ghost-node", "amount": 1.0},
            "jud-scotus": {"nodeId": "jud-scotus", "amount": 1.0},
        }
        stats = apply_pay_evidence(tree, fabricated)
        self.assertEqual(stats["unknown_node"], 1)
        self.assertEqual(stats["not_a_position"], 1)
        self.assertEqual(stats["priced"], 0)

    def test_multi_post_withdrawal_strips_positionStatutoryPay_too(self):
        tree = json.loads(json.dumps(BASE))
        node_map = index_tree(tree)[0]
        # Simulate a mis-derived record slipping onto a multi-post node.
        node_map["jud-scotus-associate-justice-8"]["positionStatutoryPay"] = {"amount": 306_600.0}
        withdrawn = withdraw_pay_from_multi_post_nodes(tree)
        self.assertEqual(withdrawn, 1)
        self.assertNotIn("positionStatutoryPay", index_tree(tree)[0]["jud-scotus-associate-justice-8"])

    def test_positionStatutoryPay_is_withdrawn_when_evidence_no_longer_supports_it(self):
        self.assertIn("positionStatutoryPay", EVIDENCE_OWNED_FIELDS)
        tree = json.loads(json.dumps(BASE))
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        self.assertIn("positionStatutoryPay", index_tree(tree)[0]["jud-scotus-chief-justice-of-the-united-states"])
        apply_evidence_to_tree(tree, {})
        self.assertNotIn("positionStatutoryPay", index_tree(tree)[0]["jud-scotus-chief-justice-of-the-united-states"])


class GateTests(unittest.TestCase):
    def _pay(self):
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(json.loads(json.dumps(BASE)))[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        return dict(records["jud-scotus-chief-justice-of-the-united-states"])

    def test_every_priced_node_has_a_known_tier_in_the_gate_s_mirror(self):
        for node_id in ("jud-scotus-chief-justice-of-the-united-states",
                        "jud-circuit-1st-circuit-chief-judge-1st-circuit",
                        "jud-district-sdny-chief-judge-sdny"):
            self.assertIn(node_id, STATUTORY_PAY_NODE_TIERS)

    def test_an_honest_record_passes(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        node = index_tree(tree)[0]["jud-scotus-chief-justice-of-the-united-states"]
        node["positionStatutoryPay"]["url"] = TABLE_URL
        node["positionStatutoryPay"]["checkedAt"] = "2026-09-14T00:00:00Z"
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertEqual(violations, [])

    def test_every_forgery_this_module_makes_possible_is_caught(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        base_node = index_tree(tree)[0]["jud-scotus-chief-justice-of-the-united-states"]
        base_node["positionStatutoryPay"]["url"] = TABLE_URL
        base_node["positionStatutoryPay"]["checkedAt"] = "2026-09-14T00:00:00Z"
        base_pay = base_node["positionStatutoryPay"]

        attacks = {
            "wrong amount": {**base_pay, "amount": 1.0},
            "wrong tier for this node": {**base_pay, "seatTier": "district judges"},
            "wrong year": {**base_pay, "year": "2020", "effective": "2020-01-01"},
            "fabricated footnote": {**base_pay, "footnotes": ["nothing like this was on the page"]},
            "wrong url": {**base_pay, "url": "https://example.com/"},
            "future retrieval date": {**base_pay, "checkedAt": "2099-01-01T00:00:00Z"},
            "unknown source": {**base_pay, "source": "made_up_source"},
            "quote without the figure": {**base_pay, "quote": "irrelevant text"},
            "rate text disagrees with the amount": {**base_pay, "rateText": "$1"},
            "not a record at all": "not even a dict",
        }
        for name, pay in attacks.items():
            with self.subTest(attack=name):
                violations = statutory_pay_violations(base_node, pay, "2026-09-15", _label)
                self.assertTrue(violations, f"{name} was not caught")

    def test_the_sourceUrls_leak_this_module_must_never_repeat_is_caught(self):
        tree = json.loads(json.dumps(BASE))
        table = parse_judicial_compensation(PAGE)
        node_map = index_tree(tree)[0]
        records, _ = build_records(node_map, table, url=TABLE_URL, sha256="a" * 64, retrieved_at="2026-09-14T00:00:00Z")
        apply_pay_evidence(tree, records)
        node = index_tree(tree)[0]["jud-scotus-chief-justice-of-the-united-states"]
        node["positionStatutoryPay"]["url"] = TABLE_URL
        node["positionStatutoryPay"]["checkedAt"] = "2026-09-14T00:00:00Z"
        node["sourceUrls"] = [TABLE_URL]
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertTrue(any("among the sources that it exists" in v for v in violations))

    def test_a_multi_post_node_carrying_a_rate_is_caught(self):
        tree = json.loads(json.dumps(BASE))
        node = index_tree(tree)[0]["jud-scotus-associate-justice-8"]
        node["positionStatutoryPay"] = {
            "source": "uscourts_judicial_compensation", "amount": 306_600.0, "seatTier": "associate justices",
            "year": JUDICIAL_COMPENSATION_YEAR, "effective": "2026-01-01", "rateText": "$306,600",
            "quote": "$306,600", "footnotes": [], "url": TABLE_URL, "checkedAt": "2026-09-14T00:00:00Z",
        }
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-15", _label)
        self.assertTrue(any("stands for several posts" in v for v in violations))


class DeriveScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"jud-derive-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_dry_run_writes_nothing_and_reports_the_split(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_judicial_pay_evidence.main([
                "d", "--base-graph", str(base), "--table", str(DEFAULT_TABLE_HTML), "--dry-run",
            ])
        self.assertEqual(code, 0)
        self.assertIn("priced", out.getvalue())

    def test_the_gate_passes_on_a_graph_carrying_only_this_module_s_evidence(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(BASE), encoding="utf-8")
        out_path = self.tmp / "judicial_pay_evidence.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_judicial_pay_evidence.main([
                "d", "--base-graph", str(base), "--table", str(DEFAULT_TABLE_HTML), "--out", str(out_path),
            ])
        self.assertEqual(code, 0, out.getvalue())
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True,
            evidence_path=None, sites_path=None, judicial_pay_evidence_path=out_path,
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
