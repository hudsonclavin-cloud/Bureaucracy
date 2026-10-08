"""The U.S. Attorneys' AD pay plan chart: the parser, exactly which two nodes it
bands and why nothing else, and every way a forged band could reach the gate.

Both directions throughout: an honest band is published and passes, and each
way of forging one is caught.
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification import doj_ad_pay as mod
from data_pipeline.verification.pay_documents import annotate_pay_documents
from data_pipeline.verification.pay_tables import BAND_HOLDERS_NOTE, withdraw_pay_from_multi_post_nodes
from scripts import validate_published_graph as gate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-10-08"
CIVIL = "exec-dept-doj-usao-assistant-u-s-attorney-civil-multiple"
CRIMINAL = "exec-dept-doj-usao-assistant-u-s-attorney-criminal-multiple"
USAO = "exec-dept-doj-usao"


def _label(node):
    return "node {!r}".format(node.get("id"))


def _tree():
    multiple = {"text": "×multiple", "kind": "unstated", "as_written": "multiple"}
    return {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [{
            "id": USAO,
            "name": "U.S. Attorneys Office (USAO — 94 Districts)",
            "type": "Bureau",
            "children": [
                {"id": CIVIL, "name": mod.AD_ROWS[CIVIL][0], "type": "Position", "representsPosts": dict(multiple)},
                {"id": CRIMINAL, "name": mod.AD_ROWS[CRIMINAL][0], "type": "Position", "representsPosts": dict(multiple)},
                {"id": "exec-dept-doj-usao-civil-division-chief", "name": "Civil Division Chief", "type": "Position"},
                {"id": "exec-dept-doj-usao-first-assistant-u-s-attorney", "name": "First Assistant U.S. Attorney",
                 "type": "Position"},
            ],
        }],
    }


def _parents(root):
    parents = {}

    def walk(node):
        for child in node.get("children") or []:
            parents[child["id"]] = node["id"]
            walk(child)

    walk(root)
    return parents


def _validated(tree):
    node_map, _ = index_tree(tree)
    records, report = mod.build_records(node_map, _parents(tree), mod.load_documents())
    out = {}
    for node_id, record in records.items():
        checked = fe.validate_record(record, node_map[node_id])
        checked["financialEvidenceStatus"] = fe.classify(checked)
        for key in ("rangeMinimum", "rangeMaximum", "rangeMinimumRaw", "rangeMaximumRaw", "gradeLow", "gradeHigh",
                    "rangeText", "planUrl", "planSha256", "planRetrievedAt"):
            checked[key] = record[key]
        out[node_id] = checked
    return out, report


def _built():
    tree = _tree()
    records, _ = _validated(tree)
    mod.apply_pay_evidence(tree, records, index_tree=index_tree)
    withdraw_pay_from_multi_post_nodes(tree)
    annotate_pay_documents(tree)
    node_map, _ = index_tree(tree)
    return tree, node_map


class DocumentTests(unittest.TestCase):
    def test_the_chart_yields_the_ausa_table_as_printed(self):
        parsed = mod.load_documents()["parsed"]
        self.assertEqual(parsed["table"], "Assistant United States Attorneys (AUSA)")
        self.assertEqual([g["grade"] for g in parsed["grades"]],
                         ["AD-21", "AD-23", "AD-25", "AD-26", "AD-27", "AD-28", "AD-29"])
        self.assertEqual(parsed["grades"][0]["minimum"], 63_163.0)
        self.assertEqual(parsed["grades"][-1]["maximum"], 165_209.0)

    def test_the_gate_s_mirror_equals_the_module_and_the_page(self):
        parsed = mod.load_documents()["parsed"]
        from_module = {g["grade"]: (g["minimum"], g["maximum"]) for g in parsed["grades"]}
        self.assertEqual(gate.DOJ_AD_GRADES, from_module)
        self.assertEqual(gate.doj_ad_chart_grades(), from_module, "the gate's own reader disagrees with the module")
        self.assertEqual(gate.DOJ_AD_ROWS, mod.AD_ROWS)
        for name in ("TABLE_HEADING", "EFFECTIVE_TEXT", "EFFECTIVE_DATE", "LOCALITY_TEXT", "PLAN_QUOTE",
                     "TEMPORARY_PROMOTION_QUOTE"):
            gate_name = {"TABLE_HEADING": "DOJ_AD_TABLE_HEADING", "EFFECTIVE_DATE": "DOJ_AD_EFFECTIVE"}.get(
                name, "DOJ_AD_" + name)
            self.assertEqual(getattr(gate, gate_name), getattr(mod, name), name)
        self.assertEqual(gate.DOJ_AD_EXCLUDED_TABLE, mod.EXCLUDED_TABLE_HEADING)
        self.assertEqual(gate.DOJ_AD_SOURCE, mod.PAY_SOURCE)
        self.assertEqual(gate.DOJ_AD_KIND, mod.BAND_KIND)
        loaded = mod.load_documents()
        self.assertEqual(gate.DOJ_AD_CHART_URL, loaded["chart"]["url"])
        self.assertEqual(gate.DOJ_AD_PLAN_URL, loaded["plan"]["url"])

    def test_the_chart_says_its_tables_are_before_locality_and_dated_2025(self):
        text = mod.page_text(mod.DEFAULT_CHART.read_bytes())
        self.assertIn(mod.EFFECTIVE_TEXT, text)
        self.assertIn(mod.LOCALITY_TEXT, text)
        self.assertIn(mod.EXCLUDED_TABLE_HEADING, text)

    def test_the_chart_names_no_division_chief_no_first_assistant_and_no_us_attorney_row(self):
        text = mod.page_text(mod.DEFAULT_CHART.read_bytes())
        for absent in ("Division Chief", "First Assistant", "United States Attorneys (USA)"):
            self.assertNotIn(absent, text)

    def test_a_tampered_fixture_is_refused_by_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            for source in (mod.DEFAULT_CHART, mod.DEFAULT_PLAN_PAGE):
                shutil.copy(source, Path(tmp) / source.name)
                shutil.copy(str(source) + ".meta.json", Path(tmp) / (source.name + ".meta.json"))
            chart = Path(tmp) / mod.DEFAULT_CHART.name
            chart.write_bytes(chart.read_bytes().replace(b"$165,209", b"$265,209"))
            with self.assertRaises(mod.Unreadable):
                mod.load_documents(chart, Path(tmp) / mod.DEFAULT_PLAN_PAGE.name)

    def test_a_reshaped_chart_yields_nothing(self):
        raw = mod.DEFAULT_CHART.read_bytes()
        for broken in (
            raw.replace(b"Assistant United States Attorneys (AUSA)</h2>", b"Attorneys</h2>"),
            raw.replace(b"These tables are for 2025", b"These tables are for 2031"),
            raw.replace(b"do not include locality", b"include locality"),
            raw.replace(b"$107,376", b"107,376"),
        ):
            with self.subTest():
                with self.assertRaises(mod.Unreadable):
                    mod.parse_chart(broken)


class ScopeTests(unittest.TestCase):
    def test_only_the_two_ausa_nodes_are_banded(self):
        records, report = _validated(_tree())
        self.assertEqual(set(records), {CIVIL, CRIMINAL})
        self.assertEqual({r["financialEvidenceStatus"] for r in records.values()}, {"partial"})
        self.assertIn("exec-dept-doj-usao-civil-division-chief", report["notPriced"])
        self.assertIn("exec-dept-doj-usao-u-s-attorney-94-appointed-by-president", report["notPriced"])

    def test_a_renamed_node_is_refused(self):
        tree = _tree()
        tree["children"][0]["children"][0]["name"] = "Assistant U.S. Attorney — Appellate (×multiple)"
        records, report = _validated(tree)
        self.assertNotIn(CIVIL, records)
        self.assertIn(CIVIL, report["refused"])

    def test_the_right_name_under_the_wrong_parent_is_refused(self):
        tree = _tree()
        moved = tree["children"][0]["children"].pop(0)
        tree["children"].append(moved)
        records, report = _validated(tree)
        self.assertNotIn(CIVIL, records)

    def test_the_band_lands_on_a_multi_post_node_with_a_band_s_holders_sentence(self):
        _, node_map = _built()
        band = node_map[CIVIL]["positionTierPay"]
        self.assertEqual((band["minimum"], band["maximum"]), (63_163.0, 165_209.0))
        self.assertEqual(band["holders"]["note"], BAND_HOLDERS_NOTE)
        self.assertTrue(band["holders"]["appliesToEachHolder"])
        self.assertNotIn("amount", band)
        self.assertNotIn("positionTierPay", node_map["exec-dept-doj-usao-civil-division-chief"])
        self.assertNotIn("sourceUrls", node_map[CIVIL])
        self.assertNotIn("verificationMethod", node_map[CIVIL])

    def test_two_documents_one_of_which_states_the_bounds(self):
        _, node_map = _built()
        verification = node_map[CIVIL]["positionTierPay"]["verification"]
        self.assertEqual(verification["documents"], 2)
        self.assertEqual(verification["percent"], 80)
        self.assertEqual(verification["documentsStatingTheFigure"], 1)
        self.assertIn("before locality", verification["caution"])

    def test_a_node_already_banded_is_left_alone(self):
        tree = _tree()
        records, _ = _validated(tree)
        node_map, _ = index_tree(tree)
        node_map[CIVIL]["positionTierPay"] = {"source": "something_earlier"}
        stats = mod.apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(stats["already_banded"], 1)
        self.assertEqual(node_map[CIVIL]["positionTierPay"], {"source": "something_earlier"})


class GateTests(unittest.TestCase):
    def setUp(self):
        _, node_map = _built()
        self.node = node_map[CIVIL]
        self.base = self.node["positionTierPay"]

    def _check(self, band, node=None, parent_id=USAO):
        node = node or self.node
        return gate.tier_pay_violations(node, band, TODAY, _label, "U.S. Attorneys Office (USAO — 94 Districts)",
                                        parent_id=parent_id)

    def test_an_honest_band_passes(self):
        self.assertEqual(self._check(self.base), [])
        self.assertEqual(gate.pay_document_violations(self.node, "positionTierPay", self.base, _label), [])
        self.assertEqual(gate.holders_violations(self.node, self.base, "positionTierPay", _label), [])

    def test_every_forgery_is_caught(self):
        base = self.base
        plan = base["planDocument"]
        attacks = {
            "wrong kind": {**base, "kind": "title_38_tier"},
            "wrong minimum": {**base, "minimum": 1.0},
            "wrong maximum": {**base, "maximum": 195_100.0},
            "range text disagrees": {**base, "rangeText": "$63,163 – $195,100"},
            "wrong grade span": {**base, "gradeHigh": "AD-37"},
            "wrong table": {**base, "table": mod.EXCLUDED_TABLE_HEADING},
            "excluded table dropped": {k: v for k, v in base.items() if k != "excludedTable"},
            "scope sentence dropped": {**base, "scopeNote": ""},
            "unknown match rule": {**base, "matchRule": "vibes"},
            "quote without the locality sentence": {**base, "quote": base["quote"].replace(mod.LOCALITY_TEXT, "")},
            "quote without the year": {**base, "quote": base["quote"].replace(mod.EFFECTIVE_TEXT, "")},
            "redated": {**base, "effective": "2026-01-11"},
            "locality sentence dropped": {**base, "localityText": ""},
            "wrong url": {**base, "url": "https://www.justice.gov/legal-careers"},
            "wrong digest": {**base, "documentSha256": "0" * 64},
            "salary page dropped": {k: v for k, v in base.items() if k != "planDocument"},
            "salary page misquoted": {**base, "planDocument": {**plan, "quote": "AUSAs are paid on the GS."}},
            "temporary-promotion sentence dropped": {**base, "planDocument": {**plan, "temporaryPromotionQuote": ""}},
            "salary page digest wrong": {**base, "planDocument": {**plan, "sha256": "f" * 64}},
            "future retrieval date": {**base, "checkedAt": "2099-01-01T00:00:00Z"},
            "published as a rate": {**base, "amount": 100_000.0},
            "carries a rateText": {**base, "rateText": "$100,000"},
            "no sentence saying it is a band": {**base, "note": ""},
            "claims more than a proxy": {**base, "scopeMatch": "exact"},
            "graded verified": {**base, "financialEvidenceStatus": "verified"},
            "not basic pay": {**base, "costBasis": "net_outlays"},
        }
        for name, band in attacks.items():
            with self.subTest(attack=name):
                self.assertTrue(self._check(band), f"{name} was not caught")

    def test_the_band_moved_to_a_post_the_chart_does_not_name_is_caught(self):
        chief = {"id": "exec-dept-doj-usao-civil-division-chief", "name": "Civil Division Chief", "type": "Position"}
        self.assertTrue(any("no reviewed row" in v for v in self._check(self.base, node=chief)))

    def test_a_renamed_node_is_caught(self):
        renamed = {**self.node, "name": "Assistant U.S. Attorney (×multiple)"}
        self.assertTrue(any("is now called" in v for v in self._check(self.base, node=renamed)))

    def test_a_re_parented_node_is_caught(self):
        self.assertTrue(any("sits under" in v for v in self._check(self.base, parent_id="exec-dept-doj")))

    def test_a_measured_cost_or_a_source_leak_is_caught(self):
        for name, node in {
            "measured cost": {**self.node, "cost_status": "official"},
            "source leak": {**self.node, "sourceUrls": [gate.DOJ_AD_CHART_URL]},
            "verification method": {**self.node, "verificationMethod": self.base["method"]},
            "placement method": {**self.node, "placementMethod": self.base["method"]},
        }.items():
            with self.subTest(attack=name):
                self.assertTrue(self._check(self.base, node=node), f"{name} was not caught")

    def test_a_document_count_that_outlives_its_second_document_is_caught(self):
        forged = copy.deepcopy(self.base)
        forged["planDocument"]["url"] = ""
        self.assertTrue(gate.pay_document_violations(self.node, "positionTierPay", forged, _label))

    def test_a_band_without_holders_on_a_multi_post_node_is_caught(self):
        forged = {k: v for k, v in self.base.items() if k != "holders"}
        self.assertTrue(gate.holders_violations(self.node, forged, "positionTierPay", _label))


class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        if not path.exists():
            raise unittest.SkipTest("no published graph to check")
        cls.by_id = {}

        def walk(node):
            cls.by_id[node["id"]] = node
            for child in node.get("children") or []:
                walk(child)

        walk(json.loads(path.read_text(encoding="utf-8")))

    def test_both_ausa_nodes_carry_the_band(self):
        for node_id in (CIVIL, CRIMINAL):
            band = self.by_id[node_id].get("positionTierPay")
            self.assertIsInstance(band, dict, node_id)
            self.assertEqual(band["source"], mod.PAY_SOURCE)
            self.assertEqual(band["rangeText"], "$63,163 – $165,209")
            self.assertEqual(band["verification"]["documents"], 2)

    def test_the_declined_posts_carry_no_band(self):
        for node_id in mod.NOT_PRICED:
            if node_id in self.by_id:
                self.assertNotIn("positionTierPay", self.by_id[node_id], node_id)

    def test_no_node_counts_the_chart_among_its_sources(self):
        for node_id, node in self.by_id.items():
            for url in node.get("sourceUrls") or []:
                self.assertNotIn("justice.gov/usao/career-center", str(url), node_id)


if __name__ == "__main__":
    unittest.main()
