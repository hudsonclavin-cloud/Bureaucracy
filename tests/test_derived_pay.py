"""A figure no document states: the four statutory parity provisions, the join
that prices them, and every way a forged derivation could reach the gate.

Both directions throughout. The one this module exists for is the negative:
uscode.house.gov prints a section's REPEALED text beneath the law, in the same
prose, and a research pass this feature was built from read 38 U.S.C. 7253's
repealed subsection as though it were current — which would put the CAVC's
chief judge at the circuit-judge rate instead of the district-judge rate. So
the assertions here are that each current sentence IS in its section's
operative text, and that the repealed one is NOT, though it is on the page.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, index_tree
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.derived_pay import (
    NOT_PRICED,
    PARITY_PROVISIONS,
    REPEALED_CAVC_CHIEF_JUDGE_TEXT,
    STRENGTH_SCALE,
    Unreadable,
    apply_pay_evidence,
    build_records,
    document_strength_percent,
    load_section,
    operative_text,
)
from data_pipeline.verification.judicial_pay import DEFAULT_TABLE_HTML, load_judicial_compensation
from data_pipeline.verification.pay_documents import annotate_pay_documents
from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes
from scripts.validate_published_graph import (
    DERIVED_PAY_METHOD,
    DERIVED_PAY_PROVISIONS,
    DERIVED_PAY_REPEALED_TEXT,
    DERIVED_PAY_SOURCE,
    DERIVED_PAY_STRENGTH_BY_COUNT,
    DERIVED_PAY_TABLE_URL,
    JUDICIAL_COMPENSATION_TIERS,
    derived_pay_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TODAY = "2099-01-01"


def _label(node):
    return "node {!r}".format(node.get("id"))


def _compensation():
    loaded = load_judicial_compensation(DEFAULT_TABLE_HTML)
    table = loaded["table"]
    year = sorted(table["years"], reverse=True)[0]
    return loaded, dict(table["years"][year])


def _base_tree():
    """The four Article I chief judges, plus the CIT chief judge that must not
    be priced and a multi-post judge node that must not be either."""
    return {
        "id": "the-constitution-of-the-united-states",
        "name": "The Constitution",
        "type": "Foundation",
        "children": [
            {
                "id": "jud-specialized",
                "name": "Specialized Federal Courts",
                "type": "Court Group",
                "children": [
                    {
                        "id": "jud-specialized-tax",
                        "name": "U.S. Tax Court",
                        "type": "Specialized Court",
                        "children": [
                            {"id": "jud-specialized-tax-chief-judge-tax-court",
                             "name": "Chief Judge, Tax Court", "type": "Position"},
                            {"id": "jud-specialized-tax-judge-18", "name": "Judge (×18)", "type": "Position",
                             "representsPosts": {"text": "×18", "kind": "exact", "count": 18}},
                        ],
                    },
                    {
                        "id": "jud-specialized-claims",
                        "name": "U.S. Court of Federal Claims",
                        "type": "Specialized Court",
                        "children": [
                            {"id": "jud-specialized-claims-chief-judge-cfc",
                             "name": "Chief Judge, CFC", "type": "Position"},
                        ],
                    },
                    {
                        "id": "jud-specialized-caaf",
                        "name": "Court of Appeals for the Armed Forces (CAAF)",
                        "type": "Specialized Court",
                        "children": [
                            {"id": "jud-specialized-caaf-chief-judge-caaf",
                             "name": "Chief Judge, CAAF", "type": "Position"},
                        ],
                    },
                    {
                        "id": "jud-specialized-cavc",
                        "name": "Court of Appeals for Veterans Claims (CAVC)",
                        "type": "Specialized Court",
                        "children": [
                            {"id": "jud-specialized-cavc-chief-judge-cavc",
                             "name": "Chief Judge, CAVC", "type": "Position"},
                        ],
                    },
                    {
                        "id": "jud-specialized-intl-trade",
                        "name": "U.S. Court of International Trade (CIT)",
                        "type": "Specialized Court",
                        "children": [
                            {"id": "jud-specialized-intl-trade-chief-judge-cit",
                             "name": "Chief Judge, CIT", "type": "Position"},
                        ],
                    },
                ],
            },
        ],
    }


def _records():
    loaded, compensation = _compensation()
    node_map, _ = index_tree(_base_tree())
    return build_records(
        node_map,
        compensation,
        table_url=loaded["url"],
        table_sha256=loaded["sha256"],
        table_retrieved_at=loaded["fetched_at"],
    )


class OperativeTextTests(unittest.TestCase):
    """The statute as it reads now, separated from the history beneath it."""

    def test_every_parity_sentence_is_in_its_sections_operative_text(self):
        for node_id, provision in PARITY_PROVISIONS.items():
            with self.subTest(node_id):
                section = load_section(provision["fixture"])
                self.assertIn(provision["quote"], section["operative"])

    def test_the_repealed_cavc_sentence_is_on_the_page_and_not_in_the_law(self):
        """The whole reason `operative_text` exists.

        If this ever fails in the first direction the fixture is not the page
        this module was written against; if it fails in the second, a
        whole-page search would price the CAVC's chief judge at the circuit
        rate, which is what the research got wrong.
        """
        section = load_section("cavc_38_usc_7253.html")
        self.assertIn(REPEALED_CAVC_CHIEF_JUDGE_TEXT, section["whole"])
        self.assertNotIn(REPEALED_CAVC_CHIEF_JUDGE_TEXT, section["operative"])

    def test_a_page_with_no_notes_heading_is_refused(self):
        with self.assertRaises(Unreadable):
            operative_text("<html><body>§1. Something. Each judge shall be paid.</body></html>")

    def test_a_page_with_no_section_heading_is_refused(self):
        with self.assertRaises(Unreadable):
            operative_text("<html><body>Editorial Notes nothing above them</body></html>")

    def test_the_committed_digest_is_recomputed_from_the_bytes(self):
        for provision in PARITY_PROVISIONS.values():
            with self.subTest(provision["fixture"]):
                section = load_section(provision["fixture"])
                self.assertEqual(64, len(section["sha256"]))
                self.assertTrue(section["url"].startswith("https://uscode.house.gov/"))


class ScaleTests(unittest.TestCase):
    """The percentage is this project's own arithmetic, not a second scale."""

    def test_the_scale_is_verify_node_sources_own(self):
        self.assertEqual(70, document_strength_percent(1))
        self.assertEqual(80, document_strength_percent(2))
        self.assertEqual(90, document_strength_percent(3))
        self.assertEqual(100, document_strength_percent(4))
        self.assertEqual(0, document_strength_percent(0))

    def test_the_gate_mirrors_the_same_scale(self):
        for count, percent in DERIVED_PAY_STRENGTH_BY_COUNT.items():
            self.assertEqual(document_strength_percent(count), percent)

    def test_the_published_scale_names_the_function_it_reuses(self):
        self.assertIn("verify_node_sources", STRENGTH_SCALE)


class MirrorTests(unittest.TestCase):
    """The gate is stdlib-only and mirrors the table; the two cannot drift."""

    def test_the_gate_mirrors_every_provision_by_node_id(self):
        self.assertEqual(set(DERIVED_PAY_PROVISIONS), set(PARITY_PROVISIONS))
        for node_id, provision in PARITY_PROVISIONS.items():
            citation, tier, sentence = DERIVED_PAY_PROVISIONS[node_id]
            self.assertEqual(provision["citation"], citation)
            self.assertEqual(provision["tier"], tier)
            self.assertEqual(" ".join(provision["quote"].split()), sentence)

    def test_the_gate_mirrors_the_repealed_sentence(self):
        self.assertEqual(REPEALED_CAVC_CHIEF_JUDGE_TEXT, DERIVED_PAY_REPEALED_TEXT)

    def test_six_provisions_price_the_identical_figure(self):
        """Which is why the mirror is keyed by node id and not by figure:
        three courts' chief judges and their benches, six nodes, one rate."""
        district = [n for n, p in PARITY_PROVISIONS.items() if p["tier"] == "district judges"]
        self.assertEqual(6, len(district))

    def test_each_bench_takes_its_own_courts_provision(self):
        from data_pipeline.verification.derived_pay import BENCH_NODES

        for bench, chief in BENCH_NODES.items():
            self.assertEqual(PARITY_PROVISIONS[bench], PARITY_PROVISIONS[chief])

    def test_the_court_of_international_trade_is_refused_and_says_why(self):
        self.assertNotIn("jud-specialized-intl-trade-chief-judge-cit", PARITY_PROVISIONS)
        reason = NOT_PRICED["jud-specialized-intl-trade-chief-judge-cit"]
        self.assertIn("28 U.S.C. 252", reason)
        self.assertIn("no parity", reason)

    def test_the_cit_section_really_states_no_parity(self):
        """The refusal checked against the committed section rather than
        asserted in prose. 28 U.S.C. 252 sets the rate by reference to the
        Federal Salary Act of 1967, and names no other court's judges — so
        nothing here could price it without reading two more documents."""
        section = load_section("cit_28_usc_252.html")
        operative = section["operative"]
        self.assertIn("Federal Salary Act of 1967", operative)
        for tier in ("district courts of the United States", "United States Courts of Appeals",
                     "United States district courts"):
            self.assertNotIn(tier, operative)


class BuildTests(unittest.TestCase):
    def test_eight_records_and_no_more(self):
        """Four chief judges and four benches. The bench nodes are in the tree
        only for the Tax Court here, so five reach the fixture; the CIT never."""
        records, report = _records()
        self.assertEqual(5, len(records))
        self.assertEqual(5, report["priced"])
        self.assertNotIn("jud-specialized-intl-trade-chief-judge-cit", records)
        self.assertIn("jud-specialized-tax-judge-18", records)
        self.assertEqual(records["jud-specialized-tax-judge-18"]["amount"], records["jud-specialized-tax-chief-judge-tax-court"]["amount"])

    def test_each_record_carries_two_documents_neither_stating_the_figure(self):
        records, _ = _records()
        for node_id, record in records.items():
            with self.subTest(node_id):
                self.assertEqual(2, len(record["documents"]))
                self.assertFalse(any(d["statesTheFigure"] for d in record["documents"]))
                hosts = {d["url"] for d in record["documents"]}
                self.assertTrue(any("uscode.house.gov" in url for url in hosts))
                self.assertIn(DERIVED_PAY_TABLE_URL, hosts)

    def test_the_figure_is_the_tables_own_for_the_tier_the_statute_names(self):
        records, _ = _records()
        for node_id, record in records.items():
            with self.subTest(node_id):
                self.assertAlmostEqual(
                    JUDICIAL_COMPENSATION_TIERS[record["seatTier"]], record["amount"], places=2)

    def test_a_provision_whose_sentence_has_changed_is_refused_not_guessed(self):
        loaded, compensation = _compensation()
        node_map, _ = index_tree(_base_tree())
        original = PARITY_PROVISIONS["jud-specialized-cavc-chief-judge-cavc"]["quote"]
        PARITY_PROVISIONS["jud-specialized-cavc-chief-judge-cavc"]["quote"] = REPEALED_CAVC_CHIEF_JUDGE_TEXT
        try:
            records, report = build_records(
                node_map, compensation, table_url=loaded["url"],
                table_sha256=loaded["sha256"], table_retrieved_at=loaded["fetched_at"])
        finally:
            PARITY_PROVISIONS["jud-specialized-cavc-chief-judge-cavc"]["quote"] = original
        self.assertNotIn("jud-specialized-cavc-chief-judge-cavc", records)
        self.assertIn(
            "only in the publisher's notes",
            report["refused"]["jud-specialized-cavc-chief-judge-cavc"])


class ApplyTests(unittest.TestCase):
    def test_the_block_is_stamped_and_no_source_url_is(self):
        records, _ = _records()
        tree = _base_tree()
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(5, stats["priced"])
        # The document count, the percentage and the sentence saying what the
        # percentage does not measure are stamped by the shared pass that does
        # the same for every other pay field -- one code path for one number.
        annotate_pay_documents(tree)
        node_map, _ = index_tree(tree)
        for node_id in records:
            node = node_map[node_id]
            pay = node["positionDerivedPay"]
            self.assertEqual(2, pay["verification"]["documents"])
            self.assertEqual(80, pay["verification"]["percent"])
            self.assertEqual(0, pay["verification"]["documentsStatingTheFigure"])
            # The channel that carried 29 positions to `verified` off a
            # five-row table on 2026-09-11.
            for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
                self.assertIsNone(node.get(field))
            self.assertIsNone(node.get("resolved_total_amount"))

    def test_a_node_another_source_already_priced_is_left_alone(self):
        records, _ = _records()
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["jud-specialized-tax-chief-judge-tax-court"]["positionStatutoryPay"] = {"source": "elsewhere"}
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(4, stats["priced"])
        self.assertEqual(1, stats["already_priced_by_another_source"])
        node_map, _ = index_tree(tree)
        self.assertIsNone(node_map["jud-specialized-tax-chief-judge-tax-court"].get("positionDerivedPay"))

    def test_the_multi_post_sweep_keeps_it_and_stamps_holders(self):
        """A parity-derived rate is the tier's and holds for each judge, so the
        bench node keeps it with `holders` recomputed from its own count."""
        records, _ = _records()
        tree = _base_tree()
        apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(0, withdraw_pay_from_multi_post_nodes(tree))
        node_map, _ = index_tree(tree)
        bench = node_map["jud-specialized-tax-judge-18"]["positionDerivedPay"]
        self.assertEqual(18, bench["holders"]["count"])
        self.assertTrue(bench["holders"]["appliesToEachHolder"])
        self.assertNotIn("holders", node_map["jud-specialized-tax-chief-judge-tax-court"]["positionDerivedPay"])

    def test_the_field_is_withdrawn_each_build_and_reaches_the_viewer(self):
        self.assertIn("positionDerivedPay", EVIDENCE_OWNED_FIELDS)
        self.assertIn("positionDerivedPay", MINIMAL_GRAPH_FIELDS)


class GateTests(unittest.TestCase):
    """Each dimension corrupted in turn, against a node the gate accepts."""

    def setUp(self):
        records, _ = _records()
        self.tree = _base_tree()
        apply_pay_evidence(self.tree, records, index_tree=index_tree)
        annotate_pay_documents(self.tree)
        node_map, _ = index_tree(self.tree)
        self.node = node_map["jud-specialized-cavc-chief-judge-cavc"]

    def _check(self, node=None, pay=None):
        node = node or self.node
        return derived_pay_violations(node, pay if pay is not None else node["positionDerivedPay"], TODAY, _label)

    def test_an_honest_record_passes(self):
        self.assertEqual([], self._check())
        for node_id in ("jud-specialized-tax-chief-judge-tax-court",
                        "jud-specialized-claims-chief-judge-cfc",
                        "jud-specialized-caaf-chief-judge-caaf"):
            node_map, _ = index_tree(self.tree)
            self.assertEqual([], self._check(node_map[node_id]))

    def test_the_repealed_sentence_is_refused_wherever_it_is_quoted(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["documents"][0]["quote"] = REPEALED_CAVC_CHIEF_JUDGE_TEXT
        self.assertTrue(any("REPEALED" in v for v in self._check(pay=pay)))

    def test_a_record_moved_to_another_node_is_caught(self):
        """Three of the four price the identical $249,900 from three different
        statutes, so only the node's own identity tells them apart."""
        node_map, _ = index_tree(self.tree)
        victim = node_map["jud-specialized-claims-chief-judge-cfc"]
        moved = copy.deepcopy(self.node["positionDerivedPay"])
        self.assertTrue(self._check(victim, moved))

    def test_a_record_on_a_node_with_no_provision_is_caught(self):
        stranger = {"id": "jud-specialized-intl-trade-chief-judge-cit", "name": "Chief Judge, CIT", "type": "Position"}
        self.assertTrue(any("no parity provision" in v
                            for v in self._check(stranger, self.node["positionDerivedPay"])))

    def test_a_record_on_a_non_post_is_caught(self):
        organisation = dict(self.node, type="Specialized Court")
        self.assertTrue(any("not a post" in v for v in self._check(organisation)))

    def test_a_record_on_a_multi_post_node_needs_a_holders_block(self):
        many = dict(self.node, representsPosts={"text": "×8", "kind": "exact", "count": 8})
        self.assertTrue(any("does not say the figure applies to each holder" in v for v in self._check(many)))
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["holders"] = {"text": "×8", "kind": "exact", "count": 8, "appliesToEachHolder": True, "note": "each"}
        self.assertEqual([], self._check(many, pay))
        pay["holders"]["text"] = "×9"
        self.assertTrue(any("while its name states" in v for v in self._check(many, pay)))
        pay["holders"]["text"] = "×8"
        pay["holders"]["count"] = 7
        self.assertTrue(any("covers count 7" in v for v in self._check(many, pay)), "the count is what the panel prints first")
        pay["holders"]["count"] = 8
        pay["holders"]["kind"] = "unstated"
        self.assertTrue(any("files its" in v for v in self._check(many, pay)))

    def test_a_wrong_tier_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["seatTier"] = "circuit judges"
        pay["amount"] = JUDICIAL_COMPENSATION_TIERS["circuit judges"]
        pay["rateText"] = "$264,900"
        self.assertTrue(any("names 'district judges'" in v for v in self._check(pay=pay)))

    def test_a_figure_the_table_does_not_print_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["amount"] = 260_000.0
        self.assertTrue(self._check(pay=pay))

    def test_a_dropped_document_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["documents"] = pay["documents"][:1]
        self.assertTrue(any("not two" in v for v in self._check(pay=pay)))

    def test_a_document_claiming_to_state_the_figure_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["documents"][1]["statesTheFigure"] = True
        self.assertTrue(any("states the figure" in v for v in self._check(pay=pay)))

    def test_an_inflated_percentage_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["verification"]["percent"] = 95
        self.assertTrue(any("own scale gives" in v for v in self._check(pay=pay)))

    def test_a_document_count_the_list_does_not_support_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["verification"]["documents"] = 3
        self.assertTrue(any("documents verify it and lists" in v for v in self._check(pay=pay)))

    def test_claiming_a_document_states_the_figure_in_the_summary_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["verification"]["documentsStatingTheFigure"] = 2
        self.assertTrue(any("none of them does" in v for v in self._check(pay=pay)))

    def test_a_percentage_with_no_scale_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["verification"]["scale"] = ""
        self.assertTrue(any("what scale" in v for v in self._check(pay=pay)))

    def test_a_missing_digest_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["documents"][0]["documentSha256"] = ""
        self.assertTrue(any("no digest" in v for v in self._check(pay=pay)))

    def test_a_missing_compensation_table_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["documents"][1]["url"] = "https://example.gov/elsewhere"
        pay["tableUrl"] = "https://example.gov/elsewhere"
        self.assertTrue(any("no compensation table" in v for v in self._check(pay=pay)))

    def test_a_verified_grade_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["financialEvidenceStatus"] = "verified"
        self.assertTrue(any("not 'partial'" in v for v in self._check(pay=pay)))

    def test_an_exact_scope_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["scopeMatch"] = "exact"
        self.assertTrue(any("never more than a proxy" in v for v in self._check(pay=pay)))

    def test_a_future_retrieval_date_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["checkedAt"] = "2100-01-01T00:00:00Z"
        self.assertTrue(any("past retrieval date" in v for v in self._check(pay=pay)))

    def test_a_measured_cost_beside_it_is_caught(self):
        node = dict(self.node, cost_status="official")
        self.assertTrue(any("measured cost status" in v for v in self._check(node)))

    def test_verifying_its_own_existence_with_it_is_caught(self):
        node = dict(self.node, verificationMethod=DERIVED_PAY_METHOD)
        self.assertTrue(any("verifies its own existence" in v for v in self._check(node)))

    def test_placing_itself_with_it_is_caught(self):
        node = dict(self.node, placementMethod=DERIVED_PAY_METHOD)
        self.assertTrue(any("places itself" in v for v in self._check(node)))

    def test_a_pay_document_counted_among_the_nodes_sources_is_caught(self):
        node = dict(self.node, sourceUrls=[DERIVED_PAY_TABLE_URL])
        self.assertTrue(any("among the sources that it exists" in v for v in self._check(node)))

    def test_an_unknown_source_is_caught(self):
        pay = copy.deepcopy(self.node["positionDerivedPay"])
        pay["source"] = "somewhere_else"
        self.assertTrue(any("does not produce" in v for v in self._check(pay=pay)))
        self.assertEqual(DERIVED_PAY_SOURCE, self.node["positionDerivedPay"]["source"])


class PublishedGraphTests(unittest.TestCase):
    """What the committed graph actually carries."""

    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        cls.nodes = []
        if not path.exists():
            return
        root = json.loads(path.read_text(encoding="utf-8"))
        stack = [root]
        while stack:
            node = stack.pop()
            cls.nodes.append(node)
            stack.extend(node.get("children") or [])

    def test_every_published_block_passes_the_gate(self):
        if not self.nodes:
            self.skipTest("no published graph")
        for node in self.nodes:
            pay = node.get("positionDerivedPay")
            if isinstance(pay, dict):
                with self.subTest(node.get("id")):
                    self.assertEqual([], derived_pay_violations(node, pay, TODAY, _label))

    def test_no_priced_node_gained_a_uscode_url(self):
        if not self.nodes:
            self.skipTest("no published graph")
        for node in self.nodes:
            if isinstance(node.get("positionDerivedPay"), dict):
                for url in node.get("sourceUrls") or []:
                    self.assertNotIn("uscode.house.gov", str(url))


if __name__ == "__main__":
    unittest.main()
