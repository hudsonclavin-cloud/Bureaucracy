"""3 U.S.C. 102, the one section of the Code read for an office's salary
stated in dollars, pinned in both directions: what the committed section
prints, what the module derives from it, what the gate accepts, and every
way a block can be faked."""

from __future__ import annotations

import copy
import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.derived_pay import load_section, statute_publisher
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.pay_documents import annotate_pay_documents
from data_pipeline.verification.pay_tables import OFFICE_RATE_PAY_FIELDS, withdraw_pay_from_multi_post_nodes
from data_pipeline.verification.us_code_stated_pay import (
    PAY_METHOD,
    PAY_SOURCE,
    PRESIDENT_AMENDMENT_CREDIT,
    PRESIDENT_SENTENCE,
    STATED_RATE_ROWS,
    apply_pay_evidence,
    build_records,
)
from scripts import derive_us_code_stated_pay_evidence
from scripts.validate_published_graph import (
    STATUTORY_PAY_NODE_TIERS,
    STATUTORY_PAY_SOURCES,
    US_CODE_BASIS_FIXTURE_DIR,
    US_CODE_STATED_RATE_FIXTURE,
    US_CODE_STATED_RATE_ROWS,
    US_CODE_STATED_RATE_SENTENCE,
    US_CODE_STATED_RATE_URL,
    US_CODE_STATED_RATE_YEAR,
    statutory_pay_violations,
    uscode_operative_text,
)
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
ROOT_ID = "the-constitution-of-the-united-states"
TODAY = date.today().isoformat()
READ_YEAR = int(US_CODE_STATED_RATE_YEAR)


def _label(node):
    return "node {!r}".format(node.get("id"))


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _base_tree():
    return {
        "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
        "children": [
            {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
            {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
                {"id": "exec-president", "name": "The President of the United States", "type": "Position", "children": []},
                {"id": "exec-vp", "name": "The Vice President of the United States", "type": "Position", "children": []},
            ]},
            {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
        ],
    }


def _records(tree=None):
    node_map, _ = index_tree(tree or _base_tree())
    return build_records(node_map, read_year=READ_YEAR, read_on=f"{READ_YEAR}-10-05")


class SectionTests(unittest.TestCase):
    def test_the_section_prints_the_sentence_in_its_operative_text_by_both_readers(self):
        section = load_section("president_3_usc_102_govinfo2024.html")
        self.assertIn(PRESIDENT_SENTENCE, section["operative"])
        self.assertIn(PRESIDENT_AMENDMENT_CREDIT, section["operative"])
        self.assertIn(PRESIDENT_SENTENCE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / US_CODE_STATED_RATE_FIXTURE))
        # The figure, and the allowance the module refuses to publish, are
        # both in the one sentence; the section says "dollars" nowhere.
        self.assertIn("$400,000 a year", PRESIDENT_SENTENCE)
        self.assertIn("expense allowance of $50,000", PRESIDENT_SENTENCE)
        self.assertNotIn("dollar", section["operative"].casefold())
        self.assertEqual(("U.S. Government Publishing Office", "2024 edition of the United States Code"), statute_publisher(section["url"]))
        self.assertEqual(US_CODE_STATED_RATE_URL, section["url"])


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirrors_the_row_by_node_id(self):
        self.assertEqual(set(STATED_RATE_ROWS), set(US_CODE_STATED_RATE_ROWS))
        for node_id, row in STATED_RATE_ROWS.items():
            node_name, office, tier, citation, amount = US_CODE_STATED_RATE_ROWS[node_id]
            self.assertEqual((row["nodeName"], row["office"], row["tier"], row["citation"], row["amount"]),
                             (node_name, office, tier, citation, amount))
            self.assertEqual(tier, STATUTORY_PAY_NODE_TIERS[node_id])
            self.assertEqual(US_CODE_STATED_RATE_FIXTURE, row["fixture"])
            self.assertEqual(US_CODE_STATED_RATE_SENTENCE, row["quote"])
        mirror = STATUTORY_PAY_SOURCES[PAY_SOURCE]
        self.assertEqual({"the president": 400_000.0}, mirror["tiers"])
        self.assertEqual("exec-", mirror["id_prefix"])
        self.assertIn(PAY_SOURCE, fe.SOURCE_TYPES)
        self.assertIn(PAY_SOURCE, fe.SCALE_PRINTED_SOURCE_TYPES)
        self.assertIn("positionStatutoryPay", OFFICE_RATE_PAY_FIELDS)
        self.assertIn("positionStatutoryPay", EVIDENCE_OWNED_FIELDS)


class BuildTests(unittest.TestCase):
    def test_the_president_is_priced_and_the_vice_president_is_not(self):
        records, report = _records()
        self.assertEqual({"exec-president"}, set(records))
        self.assertEqual({}, report["refused"])
        record = records["exec-president"]
        self.assertEqual(400_000.0, record["amount"])
        self.assertEqual("partial", record["financialEvidenceStatus"])
        self.assertEqual("proxy", record["scopeMatch"])
        self.assertTrue(record["statesTheOffice"])
        self.assertEqual("U.S. Government Publishing Office", record["publisher"])
        self.assertIn("50,000", record["notPublished"])

    def test_every_record_passes_the_financial_validator_as_a_proxy(self):
        records, _ = _records()
        node_map, _ = index_tree(_base_tree())
        out = fe.validate_record(records["exec-president"], node_map["exec-president"])
        self.assertEqual("partial", fe.classify(out))
        self.assertEqual("currency_mark_on_the_printed_figure", out["unitsEvidenceKind"])

    def test_the_allowance_cannot_be_filed_as_the_rate(self):
        records, _ = _records()
        node_map, _ = index_tree(_base_tree())
        record = copy.deepcopy(records["exec-president"])
        record["amount"] = 50_000.0
        record["amountRaw"] = "50,000"
        # The validator reads the digits off the quote, so this passes it --
        # the sentence does print $50,000 -- and only the gate's mirror
        # refuses it; see GateTests.
        fe.validate_record(record, node_map["exec-president"])
        record["amount"] = 450_000.0
        record["amountRaw"] = "450,000"
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, node_map["exec-president"])

    def test_a_renamed_or_multi_post_node_is_refused(self):
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-president"]["name"] = "President"
        records, report = _records(tree)
        self.assertNotIn("exec-president", records)
        self.assertIn("renamed", report["refused"]["exec-president"])
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-president"]["representsPosts"] = {"text": "×2", "kind": "exact", "count": 2}
        records, report = _records(tree)
        self.assertEqual("stands for several posts", report["refused"]["exec-president"])

    def test_a_doctored_section_refuses_the_row(self):
        from data_pipeline.verification.us_code_stated_pay import FIXTURE_DIR
        with __import__("tempfile").TemporaryDirectory() as tmp:
            for path in FIXTURE_DIR.iterdir():
                if path.name.startswith("president_3_usc_102"):
                    shutil.copy(path, Path(tmp) / path.name)
            doctored = Path(tmp) / US_CODE_STATED_RATE_FIXTURE
            raw = doctored.read_bytes()
            self.assertIn(b"$400,000 a year", raw)
            doctored.write_bytes(raw.replace(b"$400,000 a year", b"$500,000 a year"))
            import hashlib
            meta_path = Path(tmp) / (US_CODE_STATED_RATE_FIXTURE + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(doctored.read_bytes()).hexdigest()
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            node_map, _ = index_tree(_base_tree())
            records, report = build_records(node_map, read_year=READ_YEAR, read_on=TODAY, directory=tmp)
        self.assertEqual({}, records)
        self.assertIn("no longer carries the quoted sentence", report["refused"]["exec-president"])


class ApplyTests(unittest.TestCase):
    def _applied(self):
        records, _ = _records()
        tree = _base_tree()
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        annotate_pay_documents(tree)
        node_map, parent_map = index_tree(tree)
        return tree, node_map, stats

    def test_the_block_is_stamped_and_no_source_url_is(self):
        tree, node_map, stats = self._applied()
        self.assertEqual(1, stats["priced"])
        node = node_map["exec-president"]
        pay = node["positionStatutoryPay"]
        self.assertEqual(PAY_SOURCE, pay["source"])
        self.assertEqual(PAY_METHOD, pay["method"])
        self.assertTrue(pay["statesTheOffice"])
        self.assertEqual("the president", pay["seatTier"])
        self.assertEqual(1, pay["verification"]["documents"])
        self.assertEqual(1, pay["verification"]["documentsStatingTheFigure"])
        self.assertIn("names the office itself", pay["verification"]["caution"])
        self.assertEqual("names the office and states what it is paid", pay["verification"]["documentRoles"][0]["role"])
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, node)
        self.assertNotIn("positionStatutoryPay", node_map["exec-vp"])

    def test_a_node_another_source_already_priced_is_left_alone(self):
        records, _ = _records()
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-president"]["positionStatutoryPay"] = {"source": "elsewhere"}
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(0, stats["priced"])
        self.assertEqual(1, stats["already_priced_by_another_source"])

    def test_the_multi_post_sweep_keeps_the_field_as_an_office_rate(self):
        tree, node_map, _ = self._applied()
        withdraw_pay_from_multi_post_nodes(tree)
        self.assertIn("positionStatutoryPay", index_tree(tree)[0]["exec-president"])


class GateTests(unittest.TestCase):
    def setUp(self):
        records, _ = _records()
        self.tree = _base_tree()
        apply_pay_evidence(self.tree, records, index_tree=index_tree)
        annotate_pay_documents(self.tree)
        self.node_map, _ = index_tree(self.tree)

    def _check(self, node_id, pay=None):
        node = self.node_map[node_id]
        return statutory_pay_violations(node, pay if pay is not None else node["positionStatutoryPay"], TODAY, _label)

    def test_the_honest_block_passes(self):
        self.assertEqual([], self._check("exec-president"))

    def test_each_way_a_block_can_be_faked_is_refused(self):
        pay = self.node_map["exec-president"]["positionStatutoryPay"]
        cases = {
            "the expense allowance filed as the rate": {**pay, "amount": 50_000.0, "rateText": "$50,000 a year"},
            "a figure the section does not print": {**pay, "amount": 450_000.0, "rateText": "$450,000 a year", "quote": pay["quote"].replace("$400,000", "$450,000"), "footnotes": [pay["quote"].replace("$400,000", "$450,000")]},
            "a quote that is not the section's sentence": {**pay, "quote": "The President shall receive $400,000.", "footnotes": ["The President shall receive $400,000."]},
            "the office claim dropped": {**pay, "statesTheOffice": False},
            "another office named": {**pay, "office": "The Vice President"},
            "another section cited": {**pay, "statute": "3 U.S.C. 104"},
            "the identification dropped": {**pay, "identification": {}},
            "a statute on a host this pipeline does not read": {**pay, "url": "https://www.law.cornell.edu/uscode/text/3/102"},
            "a memberSeat block on the President": {**pay, "memberSeat": {"row": "Members"}},
            "a future retrieval date": {**pay, "checkedAt": "2099-01-01T00:00:00Z"},
            "a verified grade on the record": {**pay, "financialEvidenceStatus": "verified", "scopeMatch": "exact"},
            "the wrong year": {**pay, "year": "1999", "effective": "1999-01-01"},
            "an unknown source": {**pay, "source": "made_up_source"},
        }
        for name, faked in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual([], self._check("exec-president", faked), name)

    def test_the_block_moved_onto_the_vice_president_is_refused(self):
        pay = self.node_map["exec-president"]["positionStatutoryPay"]
        self.assertNotEqual([], self._check("exec-vp", pay))

    def test_a_tier_row_claiming_to_name_the_office_is_refused(self):
        # Only a Code section stating the rate may say its source names the
        # office; a Schedule 6 record that said so would be lying.
        pay = {**self.node_map["exec-president"]["positionStatutoryPay"], "source": "us_code_pay_schedules"}
        self.assertTrue(any("only a Code section stating the rate may" in v or "names the office" in v
                            for v in self._check("exec-president", pay)))

    def test_the_source_url_leak_is_refused(self):
        node = copy.deepcopy(self.node_map["exec-president"])
        node["sourceUrls"] = [node["positionStatutoryPay"]["url"]]
        self.assertTrue(any("among the sources that it exists" in v
                            for v in statutory_pay_violations(node, node["positionStatutoryPay"], TODAY, _label)))


class DeriveScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"stated-derive-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_dry_run_writes_nothing_and_the_gate_passes_on_a_graph_carrying_only_this_evidence(self) -> None:
        base = self.tmp / "base.json"
        base.write_text(json.dumps(_base_tree()), encoding="utf-8")
        out_path = self.tmp / "us_code_stated_pay_evidence.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_us_code_stated_pay_evidence.main(["d", "--base-graph", str(base), "--out", str(out_path), "--dry-run"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertFalse(out_path.exists())
        with redirect_stdout(out):
            code = derive_us_code_stated_pay_evidence.main(["d", "--base-graph", str(base), "--out", str(out_path), "--read-on", f"{READ_YEAR}-10-05"])
        self.assertEqual(code, 0, out.getvalue())
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True,
            evidence_path=None, sites_path=None, us_code_stated_pay_evidence_path=out_path,
            us_code_pay_schedule_evidence_path=None, congressional_pay_evidence_path=None, judicial_pay_evidence_path=None,
        )
        out2 = io.StringIO()
        with redirect_stdout(out2):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out2.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        priced = [n for n in _walk(graph) if isinstance(n.get("positionStatutoryPay"), dict)]
        self.assertEqual(["exec-president"], [n["id"] for n in priced])


class PublishedGraphTests(unittest.TestCase):
    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_the_president_is_priced_on_the_published_graph(self):
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        node = node_map["exec-president"]
        pay = node["positionStatutoryPay"]
        self.assertEqual(PAY_SOURCE, pay["source"])
        self.assertEqual(400_000.0, pay["amount"])
        self.assertEqual([], statutory_pay_violations(node, pay, TODAY, _label))
        self.assertFalse(any("USCODE-" in str(u) for u in node.get("sourceUrls") or []))
        # The Vice President keeps Schedule 6's row; one salary is never two.
        self.assertEqual("us_code_pay_schedules", node_map["exec-vp"]["positionStatutoryPay"]["source"])


if __name__ == "__main__":
    unittest.main()
