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
    DERIVED_PAY_PERCENT_OF,
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
            # A district court's bankruptcy bench, paid 92 percent of a
            # district judge's salary by 28 U.S.C. 153(a) -- a percentage OF
            # the tier -- and its magistrate bench, which 28 U.S.C. 634(a)
            # caps at 92 percent ("up to") and which stays unpriced.
            {
                "id": "jud-district",
                "name": "U.S. District Courts (94 Districts)",
                "type": "Court",
                "children": [
                    {
                        "id": "jud-district-sdny",
                        "name": "Southern District of New York (S.D.N.Y.)",
                        "type": "District Court",
                        "children": [
                            {"id": "jud-district-sdny-bankruptcy-judge-12", "name": "Bankruptcy Judge (×12)",
                             "type": "Position",
                             "representsPosts": {"text": "×12", "kind": "exact", "count": 12}},
                            {"id": "jud-district-sdny-magistrate-judge-13", "name": "Magistrate Judge (×13)",
                             "type": "Position",
                             "representsPosts": {"text": "×13", "kind": "exact", "count": 13}},
                        ],
                    },
                ],
            },
            # The two offices: one statute each to the tier for the AO's
            # Director, two for the FJC's (28 U.S.C. 626 -> 603); the deputies
            # are 92 percent of a join and stay unpriced.
            {
                "id": "jud-support-aousc",
                "name": "Administrative Office of U.S. Courts (AOUSC)",
                "type": "Judicial Support",
                "children": [
                    {"id": "jud-support-aousc-director-aousc", "name": "Director, AOUSC", "type": "Position"},
                    {"id": "jud-support-aousc-deputy-director", "name": "Deputy Director", "type": "Position"},
                ],
            },
            {
                "id": "jud-support-fjc",
                "name": "Federal Judicial Center (FJC)",
                "type": "Judicial Support",
                "children": [
                    {"id": "jud-support-fjc-director-fjc", "name": "Director, FJC", "type": "Position"},
                    {"id": "jud-support-fjc-deputy-director", "name": "Deputy Director", "type": "Position"},
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
            mirrored = DERIVED_PAY_PROVISIONS[node_id]
            citation, tier, sentence = mirrored[:3]
            self.assertEqual(provision["citation"], citation)
            self.assertEqual(provision["tier"], tier)
            self.assertEqual(" ".join(provision["quote"].split()), sentence)
            via = provision.get("via")
            if via:
                # A chain row mirrors its middle statute too.
                self.assertEqual(4, len(mirrored), node_id)
                self.assertEqual((via["citation"], " ".join(via["quote"].split())), mirrored[3])
            else:
                self.assertEqual(3, len(mirrored), node_id)

    def test_exactly_one_provision_is_a_chain(self):
        """28 U.S.C. 626 pays the FJC's Director what the AO's Director is
        paid, and 28 U.S.C. 603 pays that Director as a district judge."""
        chains = [n for n, p in PARITY_PROVISIONS.items() if p.get("via")]
        self.assertEqual(["jud-support-fjc-director-fjc"], chains)
        self.assertEqual("28 U.S.C. 603", PARITY_PROVISIONS["jud-support-fjc-director-fjc"]["via"]["citation"])
        self.assertEqual("28 U.S.C. 603", PARITY_PROVISIONS["jud-support-aousc-director-aousc"]["citation"])

    def test_the_bankruptcy_rows_are_the_only_percentage_rows_and_the_gate_mirrors_them(self):
        """28 U.S.C. 153(a): 92 percent OF the district-judge rate. Keyed by
        node id in both places, so a parity row cannot acquire a percentage
        and a percentage row cannot lose one."""
        percent_rows = {n: p["percentOf"] for n, p in PARITY_PROVISIONS.items() if p.get("percentOf")}
        self.assertEqual(
            {"jud-district-sdny-bankruptcy-judge-12": 92, "jud-district-structure-bankruptcy-judge-varies": 92},
            percent_rows)
        self.assertEqual(percent_rows, DERIVED_PAY_PERCENT_OF)
        for node_id in percent_rows:
            self.assertEqual("28 U.S.C. 153(a)", PARITY_PROVISIONS[node_id]["citation"])
            self.assertEqual("district judges", PARITY_PROVISIONS[node_id]["tier"])
            self.assertIn("92 percent of the salary of a judge of the district court", PARITY_PROVISIONS[node_id]["quote"])
            self.assertFalse(PARITY_PROVISIONS[node_id].get("via"))

    def test_the_magistrate_judges_are_refused_because_the_statute_sets_a_ceiling(self):
        """28 U.S.C. 634(a) pays full-time magistrate judges "up to" 92
        percent, fixed by the Judicial Conference: a ceiling, not a rate.
        Checked against the committed section, not asserted."""
        for node_id in ("jud-district-sdny-magistrate-judge-13", "jud-district-structure-magistrate-judge-varies"):
            self.assertNotIn(node_id, PARITY_PROVISIONS)
            self.assertIn("up to", NOT_PRICED[node_id])
            self.assertIn("ceiling", NOT_PRICED[node_id])
        operative = load_section("magistrate_judges_28_usc_634.html")["operative"]
        self.assertIn("up to an annual rate equal to 92 percent of the salary of a judge of the district court", operative)
        self.assertIn("salaries to be fixed by the conference pursuant to section 633", operative)
        self.assertIn("not less than an annual salary of $100, nor more than one-half the maximum salary", operative)
        # And the bankruptcy section says "equal to", with no ceiling word.
        bankruptcy = load_section("bankruptcy_judges_28_usc_153.html")["operative"]
        self.assertIn("equal to 92 percent of the salary of a judge of the district court", bankruptcy)
        self.assertNotIn("up to an annual rate", bankruptcy)

    def test_the_deputies_are_refused_and_say_why(self):
        for node_id in ("jud-support-aousc-deputy-director", "jud-support-fjc-deputy-director"):
            self.assertNotIn(node_id, PARITY_PROVISIONS)
            self.assertIn("92 percent", NOT_PRICED[node_id])

    def test_the_gate_mirrors_the_repealed_sentence(self):
        self.assertEqual(REPEALED_CAVC_CHIEF_JUDGE_TEXT, DERIVED_PAY_REPEALED_TEXT)

    def test_six_provisions_price_the_identical_figure(self):
        """Which is why the mirror is keyed by node id and not by figure:
        three courts' chief judges and their benches, six nodes, one rate."""
        district = [n for n, p in PARITY_PROVISIONS.items() if p["tier"] == "district judges"]
        # six judges' seats, the two directors since 2026-09-28, and the two
        # bankruptcy benches since 2026-09-30 (a percentage of the same tier)
        self.assertEqual(10, len(district))
        at_the_rate = [n for n in district if not PARITY_PROVISIONS[n].get("percentOf")]
        self.assertEqual(8, len(at_the_rate))

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
    def test_the_records_and_no_more(self):
        """Four chief judges, four benches and two directors. The bench nodes
        are in the tree only for the Tax Court here, so seven reach the
        fixture; the CIT and the two deputies never."""
        records, report = _records()
        self.assertEqual(8, len(records))
        self.assertEqual(8, report["priced"])
        self.assertNotIn("jud-district-sdny-magistrate-judge-13", records)
        self.assertNotIn("jud-support-aousc-deputy-director", records)
        self.assertNotIn("jud-support-fjc-deputy-director", records)
        self.assertNotIn("jud-specialized-intl-trade-chief-judge-cit", records)
        self.assertIn("jud-specialized-tax-judge-18", records)
        self.assertEqual(records["jud-specialized-tax-judge-18"]["amount"], records["jud-specialized-tax-chief-judge-tax-court"]["amount"])

    def test_each_record_carries_its_documents_none_stating_the_figure(self):
        records, _ = _records()
        for node_id, record in records.items():
            with self.subTest(node_id):
                expected = 3 if PARITY_PROVISIONS[node_id].get("via") else 2
                self.assertEqual(expected, len(record["documents"]))
                self.assertFalse(any(d["statesTheFigure"] for d in record["documents"]))
                hosts = {d["url"] for d in record["documents"]}
                self.assertTrue(any("uscode.house.gov" in url for url in hosts))
                self.assertIn(DERIVED_PAY_TABLE_URL, hosts)

    def test_the_figure_is_the_tables_own_for_the_tier_the_statute_names(self):
        records, _ = _records()
        for node_id, record in records.items():
            with self.subTest(node_id):
                tier_amount = JUDICIAL_COMPENSATION_TIERS[record["seatTier"]]
                percent = PARITY_PROVISIONS[node_id].get("percentOf")
                expected = round(tier_amount * percent / 100.0, 2) if percent else tier_amount
                self.assertAlmostEqual(expected, record["amount"], places=2)

    def test_the_bankruptcy_figure_is_the_arithmetic_shown_in_the_open(self):
        """$249,900 × 92% = $229,908: a figure no document prints, carried
        with its base, its percentage and its result, and filed through the
        validator's computed-from-a-marked-figure rule."""
        records, _ = _records()
        record = records["jud-district-sdny-bankruptcy-judge-12"]
        base = JUDICIAL_COMPENSATION_TIERS["district judges"]
        self.assertEqual(round(base * 0.92, 2), record["amount"])
        self.assertEqual(92, record["percentOf"])
        arithmetic = record["arithmetic"]
        self.assertEqual("percent_of", arithmetic["operation"])
        self.assertEqual(base, arithmetic["baseAmount"])
        self.assertEqual("district judges", arithmetic["baseTier"])
        self.assertEqual(record["amount"], arithmetic["result"])
        self.assertEqual(record["rateText"], arithmetic["resultText"])
        self.assertIn("No document prints", arithmetic["note"])
        self.assertIn("92 percent of", record["amountScope"])
        self.assertIn(" × 92% = ", record["derivation"])
        self.assertIn(record["rateText"], record["derivation"])
        # The validator files it under the computed-from-a-marked-figure
        # rule: the base is printed with its mark in the evidence, the result
        # is not, and the result is the arithmetic to the cent.
        from data_pipeline.verification import financial_evidence as fe

        node_map, _ = index_tree(_base_tree())
        out = fe.validate_record(record, node_map["jud-district-sdny-bankruptcy-judge-12"])
        self.assertEqual("currency_mark_on_the_figure_the_record_is_computed_from", out["unitsEvidenceKind"])
        self.assertEqual("partial", fe.classify(out))
        # The parity rows carry no arithmetic and take the printed-mark rule.
        parity = records["jud-specialized-tax-chief-judge-tax-court"]
        self.assertIsNone(parity["arithmetic"])
        self.assertIsNone(parity["percentOf"])
        parity_out = fe.validate_record(parity, node_map["jud-specialized-tax-chief-judge-tax-court"])
        self.assertNotEqual(out["unitsEvidenceKind"], parity_out["unitsEvidenceKind"])
        # And a result that is not the arithmetic is refused by the validator
        # itself, before any gate sees it.
        tampered = copy.deepcopy(record)
        tampered["amount"] = 230_000.0
        tampered["amountRaw"] = "230,000"
        tampered["arithmetic"]["result"] = 230_000.0
        with self.assertRaises(fe.Rejected):
            fe.validate_record(tampered, node_map["jud-district-sdny-bankruptcy-judge-12"])
        # Two documents, neither stating the figure -- and here it is literally
        # true of the table too, which prints the base and not the result.
        self.assertEqual(2, len(record["documents"]))
        self.assertTrue(all(not d["statesTheFigure"] for d in record["documents"]))

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
        self.assertEqual(8, stats["priced"])
        # The document count, the percentage and the sentence saying what the
        # percentage does not measure are stamped by the shared pass that does
        # the same for every other pay field -- one code path for one number.
        annotate_pay_documents(tree)
        node_map, _ = index_tree(tree)
        for node_id in records:
            node = node_map[node_id]
            pay = node["positionDerivedPay"]
            expected = 3 if PARITY_PROVISIONS[node_id].get("via") else 2
            self.assertEqual(expected, pay["verification"]["documents"])
            self.assertEqual({2: 80, 3: 90}[expected], pay["verification"]["percent"])
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
        self.assertEqual(7, stats["priced"])
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
        # The bankruptcy bench keeps its percentage figure the same way: the
        # statute says "each bankruptcy judge", and the block carries the
        # arithmetic through the sweep.
        bankruptcy = node_map["jud-district-sdny-bankruptcy-judge-12"]["positionDerivedPay"]
        self.assertEqual(12, bankruptcy["holders"]["count"])
        self.assertEqual(92, bankruptcy["percentOf"])
        self.assertEqual("percent_of", bankruptcy["arithmetic"]["operation"])
        # And the document-count pass words its caution for the arithmetic.
        annotate_pay_documents(tree)
        node_map, _ = index_tree(tree)
        caution = node_map["jud-district-sdny-bankruptcy-judge-12"]["positionDerivedPay"]["verification"]["caution"]
        self.assertIn("the percentage of a tier this post is paid", caution)
        self.assertIn("which neither prints", caution)
        parity_caution = node_map["jud-specialized-tax-judge-18"]["positionDerivedPay"]["verification"]["caution"]
        self.assertNotIn("which neither prints", parity_caution)

    def test_the_field_is_withdrawn_each_build_and_reaches_the_viewer(self):
        self.assertIn("positionDerivedPay", EVIDENCE_OWNED_FIELDS)
        self.assertIn("positionDerivedPay", MINIMAL_GRAPH_FIELDS)


class GateTests(unittest.TestCase):
    """Each dimension corrupted in turn, against a node the gate accepts."""

    def setUp(self):
        records, _ = _records()
        self.tree = _base_tree()
        apply_pay_evidence(self.tree, records, index_tree=index_tree)
        # The exporter's order: the multi-post sweep stamps `holders` on the
        # bench nodes, then the shared pass counts the documents.
        withdraw_pay_from_multi_post_nodes(self.tree)
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

    def test_the_chain_row_passes_and_each_link_is_checked(self):
        """The FJC's Director: three documents, 90%, and the middle statute
        quoted as 28 U.S.C. 603 prints it now."""
        node_map, _ = index_tree(self.tree)
        fjc = node_map["jud-support-fjc-director-fjc"]
        self.assertEqual([], self._check(fjc))
        self.assertEqual(3, fjc["positionDerivedPay"]["verification"]["documents"])
        self.assertEqual(90, fjc["positionDerivedPay"]["verification"]["percent"])
        self.assertEqual("28 U.S.C. 603", fjc["positionDerivedPay"]["viaStatute"])
        # The middle document dropped.
        pay = copy.deepcopy(fjc["positionDerivedPay"])
        pay["documents"] = [d for d in pay["documents"] if d["citation"] != "28 U.S.C. 603"]
        pay["verification"]["documents"] = 2
        pay["verification"]["percent"] = 80
        self.assertTrue(any("document list does not carry" in v for v in self._check(fjc, pay)))
        # The middle sentence misquoted.
        pay = copy.deepcopy(fjc["positionDerivedPay"])
        pay["viaQuote"] = "The salary of the Director shall be the same as the salary of a circuit judge."
        self.assertTrue(any("without quoting the sentence" in v for v in self._check(fjc, pay)))
        # A chain claimed on a node whose provision makes none.
        node_map, _ = index_tree(self.tree)
        ao = node_map["jud-support-aousc-director-aousc"]
        self.assertEqual([], self._check(ao))
        pay = copy.deepcopy(ao["positionDerivedPay"])
        pay["viaStatute"] = "28 U.S.C. 603"
        pay["viaQuote"] = "The salary of the Director shall be the same as the salary of a district judge."
        self.assertTrue(any("does not make" in v for v in self._check(ao, pay)))
        # The AO row is not a chain, and two documents is what it carries.
        self.assertEqual(2, ao["positionDerivedPay"]["verification"]["documents"])

    def test_the_percentage_row_passes_and_each_part_of_the_arithmetic_is_checked(self):
        """The bankruptcy bench: 92 percent of the tier, the arithmetic in
        the open, and every element of it tied to the mirror."""
        node_map, _ = index_tree(self.tree)
        bench = node_map["jud-district-sdny-bankruptcy-judge-12"]
        self.assertEqual([], self._check(bench))
        honest = bench["positionDerivedPay"]
        self.assertEqual(round(JUDICIAL_COMPENSATION_TIERS["district judges"] * 0.92, 2), honest["amount"])

        # The tier's own rate published as the figure: a parity claim wearing
        # a percentage row's citation.
        pay = copy.deepcopy(honest)
        pay["amount"] = JUDICIAL_COMPENSATION_TIERS["district judges"]
        pay["arithmetic"]["result"] = pay["amount"]
        self.assertTrue(any("as 92 percent of" in v for v in self._check(bench, pay)))

        # The arithmetic dropped.
        pay = copy.deepcopy(honest)
        pay["arithmetic"] = None
        self.assertTrue(any("without showing the arithmetic" in v for v in self._check(bench, pay)))

        # A different percentage, in the block and in its arithmetic.
        pay = copy.deepcopy(honest)
        pay["percentOf"] = 95
        pay["arithmetic"]["percent"] = 95
        self.assertTrue(any("claims 95 percent" in v for v in self._check(bench, pay)))

        # A base that is not the table's figure for the tier.
        pay = copy.deepcopy(honest)
        pay["arithmetic"]["baseAmount"] = 264_900.0
        self.assertTrue(any("takes its percentage of" in v for v in self._check(bench, pay)))

        # A result that is not the percentage of the base.
        pay = copy.deepcopy(honest)
        pay["arithmetic"]["result"] = 230_000.0
        self.assertTrue(any("shows a result" in v for v in self._check(bench, pay)))

        # The other operation the validator knows, on a row that is not it.
        pay = copy.deepcopy(honest)
        pay["arithmetic"]["operation"] = "plus_percent"
        self.assertTrue(any("not 'percent_of'" in v for v in self._check(bench, pay)))

        # A scope that does not say it is a percentage.
        pay = copy.deepcopy(honest)
        pay["amountScope"] = "District Judges"
        self.assertTrue(any("does not say it is 92 percent" in v for v in self._check(bench, pay)))

        # The note gone.
        pay = copy.deepcopy(honest)
        pay["arithmetic"]["note"] = ""
        self.assertTrue(any("no document prints the result" in v for v in self._check(bench, pay)))

        # And the arithmetic block moved onto a parity row is refused there.
        parity = copy.deepcopy(self.node["positionDerivedPay"])
        parity["arithmetic"] = copy.deepcopy(honest["arithmetic"])
        parity["percentOf"] = 92
        self.assertTrue(any("arithmetic on a parity provision" in v for v in self._check(pay=parity)))

    def test_a_percentage_record_moved_to_the_magistrate_bench_is_caught(self):
        """Same court, same count shape, a real statute -- and no provision:
        28 U.S.C. 634(a) is a ceiling."""
        node_map, _ = index_tree(self.tree)
        magistrates = node_map["jud-district-sdny-magistrate-judge-13"]
        moved = copy.deepcopy(node_map["jud-district-sdny-bankruptcy-judge-12"]["positionDerivedPay"])
        moved["holders"]["count"] = 13
        moved["holders"]["text"] = "×13"
        self.assertTrue(any("no parity provision" in v for v in self._check(magistrates, moved)))

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
