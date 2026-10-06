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
import unittest.mock
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, index_tree
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.derived_pay import (
    MAGISTRATE_BASIS_QUOTE,
    MAGISTRATE_JUDGE_QUOTE,
    STATUTE_HOSTS,
    USSC_CHAIR_QUOTE,
    compensation_page_text,
    joined_quote,
    page_text,
    quote_parts,
    statute_publisher,
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
import scripts.validate_published_graph as gate
from scripts.validate_published_graph import (
    DERIVED_PAY_CEILING_BASIS,
    DERIVED_PAY_STATUTE_HOSTS,
    DERIVED_PAY_METHOD,
    DERIVED_PAY_PERCENT_OF,
    DERIVED_PAY_PROVISIONS,
    DERIVED_PAY_REPEALED_TEXT,
    DERIVED_PAY_SOURCE,
    DERIVED_PAY_STRENGTH_BY_COUNT,
    DERIVED_PAY_TABLE_FIXTURE,
    DERIVED_PAY_TABLE_URL,
    JUDICIAL_COMPENSATION_TIERS,
    derived_pay_table_text,
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
                            {"id": "jud-specialized-tax-special-trial-judge-multiple", "name": "Special Trial Judge (×multiple)",
                             "type": "Position",
                             "representsPosts": {"text": "×multiple", "kind": "unstated"}},
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
            # caps at 92 percent ("up to") and which is priced, since
            # 2026-10-06, through the compensation page's own sentence that
            # the salary IS 92 percent.
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
            # Director, two for the FJC's (28 U.S.C. 626 -> 603); since
            # 2026-10-05 the deputies are priced too, at 92 percent of a join.
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
            # The Sentencing Commission, since 2026-10-06: its Chair is paid at
            # the circuit-judge rate by 28 U.S.C. 992(c); its bench of six
            # bundles Vice Chairs at that annual rate with members paid by the
            # day, and is never priced.
            {
                "id": "jud-support-ussc",
                "name": "U.S. Sentencing Commission (USSC)",
                "type": "Agency",
                "children": [
                    {"id": "jud-support-ussc-chair-ussc", "name": "Chair, USSC", "type": "Position"},
                    {"id": "jud-support-ussc-commissioner-6", "name": "Commissioner (×6)", "type": "Position",
                     "representsPosts": {"text": "×6", "kind": "exact", "count": 6}},
                    {"id": "jud-support-ussc-staff-director", "name": "Staff Director", "type": "Position"},
                ],
            },
        ],
    }


def _table_text():
    return compensation_page_text(DEFAULT_TABLE_HTML)


def _records(table_text="default"):
    loaded, compensation = _compensation()
    node_map, _ = index_tree(_base_tree())
    return build_records(
        node_map,
        compensation,
        table_url=loaded["url"],
        table_sha256=loaded["sha256"],
        table_retrieved_at=loaded["fetched_at"],
        table_text=_table_text() if table_text == "default" else table_text,
    )


class OperativeTextTests(unittest.TestCase):
    """The statute as it reads now, separated from the history beneath it."""

    def test_every_parity_sentence_is_in_its_sections_operative_text(self):
        for node_id, provision in PARITY_PROVISIONS.items():
            with self.subTest(node_id):
                section = load_section(provision["fixture"])
                for part in quote_parts(provision["quote"]):
                    self.assertIn(part, section["operative"])
                via = provision.get("via")
                if via:
                    via_section = load_section(via["fixture"])
                    for part in quote_parts(via["quote"]):
                        self.assertIn(part, via_section["operative"])

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
                self.assertTrue(any(section["url"].startswith(f"https://{host}/") for host in STATUTE_HOSTS), section["url"])


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
            self.assertEqual(joined_quote(provision["quote"]), sentence)
            via = provision.get("via")
            if via:
                # A chain row mirrors its middle statute too.
                self.assertEqual(4, len(mirrored), node_id)
                self.assertEqual((via["citation"], joined_quote(via["quote"])), mirrored[3])
            else:
                self.assertEqual(3, len(mirrored), node_id)

    def test_the_three_chains_and_what_each_passes_through(self):
        """28 U.S.C. 626 pays the FJC's Director what the AO's Director is
        paid, and 28 U.S.C. 603 pays that Director as a district judge; since
        2026-10-05 the FJC's Deputy chains through the same section, and the
        Tax Court's special trial judges through 26 U.S.C. 7443(c)(1)."""
        chains = {n: p["via"]["citation"] for n, p in PARITY_PROVISIONS.items() if p.get("via")}
        self.assertEqual({
            "jud-support-fjc-director-fjc": "28 U.S.C. 603",
            "jud-support-fjc-deputy-director": "28 U.S.C. 603",
            "jud-specialized-tax-special-trial-judge-multiple": "26 U.S.C. 7443(c)(1)",
        }, chains)
        self.assertEqual("28 U.S.C. 603", PARITY_PROVISIONS["jud-support-aousc-director-aousc"]["citation"])

    def test_the_percentage_rows_and_the_gate_mirror_them(self):
        """28 U.S.C. 153(a): 92 percent OF the district-judge rate; since
        2026-10-05 three percentages of a JOIN beside them. Keyed by node id
        in both places, so a parity row cannot acquire a percentage and a
        percentage row cannot lose one."""
        percent_rows = {n: p["percentOf"] for n, p in PARITY_PROVISIONS.items() if p.get("percentOf")}
        self.assertEqual({
            "jud-district-sdny-bankruptcy-judge-12": 92,
            "jud-district-structure-bankruptcy-judge-varies": 92,
            "jud-specialized-tax-special-trial-judge-multiple": 90,
            "jud-support-aousc-deputy-director": 92,
            "jud-support-fjc-deputy-director": 92,
            # Since 2026-10-06: 28 U.S.C. 634(a)'s ceiling, read through the
            # compensation page's own sentence (see the ceiling test below).
            "jud-district-sdny-magistrate-judge-13": 92,
            "jud-district-structure-magistrate-judge-varies": 92,
        }, percent_rows)
        self.assertEqual(percent_rows, DERIVED_PAY_PERCENT_OF)
        # A ceiling basis sits on exactly the magistrate rows, in both tables.
        basis_rows = {n: p["basisQuote"] for n, p in PARITY_PROVISIONS.items() if p.get("basisQuote")}
        self.assertEqual({
            "jud-district-sdny-magistrate-judge-13": MAGISTRATE_BASIS_QUOTE,
            "jud-district-structure-magistrate-judge-varies": MAGISTRATE_BASIS_QUOTE,
        }, basis_rows)
        self.assertEqual(basis_rows, DERIVED_PAY_CEILING_BASIS)
        for node_id in basis_rows:
            self.assertTrue(PARITY_PROVISIONS[node_id].get("basisReading"), node_id)
            self.assertTrue(PARITY_PROVISIONS[node_id].get("percentOfWhat"), node_id)
        for node_id in ("jud-district-sdny-bankruptcy-judge-12", "jud-district-structure-bankruptcy-judge-varies"):
            self.assertEqual("28 U.S.C. 153(a)", PARITY_PROVISIONS[node_id]["citation"])
            self.assertEqual("district judges", PARITY_PROVISIONS[node_id]["tier"])
            self.assertIn("92 percent of the salary of a judge of the district court", PARITY_PROVISIONS[node_id]["quote"])
            self.assertFalse(PARITY_PROVISIONS[node_id].get("via"))
        # Every percentage of a join says in words what the percentage is of.
        for node_id in ("jud-specialized-tax-special-trial-judge-multiple", "jud-support-aousc-deputy-director",
                        "jud-support-fjc-deputy-director"):
            self.assertTrue(PARITY_PROVISIONS[node_id].get("percentOfWhat"), node_id)

    def test_the_special_trial_judges_statute_says_ninety_percent_of_a_tax_court_judge(self):
        """Read off the GPO's 2024-edition rendering of 26 U.S.C. 7443A, the
        host the OLRC's prelim edition was down for; both sentences of the
        chain are in the operative text of their sections."""
        section = load_section("tax_special_trial_26_usc_7443A_govinfo2024.html")
        self.assertIn("www.govinfo.gov", section["url"])
        self.assertIn("USCODE-2024", section["url"])
        self.assertIn("90 percent of the rate for judges of the Tax Court", section["operative"])
        self.assertEqual(("U.S. Government Publishing Office", "2024 edition of the United States Code"),
                         statute_publisher(section["url"]))
        self.assertEqual("Office of the Law Revision Counsel, U.S. House of Representatives",
                         statute_publisher(load_section("tax_court_26_usc_7443.html")["url"])[0])
        self.assertEqual(("uscode.house.gov", "www.govinfo.gov"), STATUTE_HOSTS)
        self.assertEqual(tuple(STATUTE_HOSTS), tuple(DERIVED_PAY_STATUTE_HOSTS))

    def test_the_two_sentences_of_28_usc_603_are_each_in_the_law_and_not_contiguous(self):
        """The Deputy's row needs the Director's sentence and the Deputy's,
        and an unrelated sentence sits between them, which is why a quote may
        be a tuple checked part by part rather than one span."""
        operative = load_section("aousc_28_usc_603.html")["operative"]
        parts = quote_parts(PARITY_PROVISIONS["jud-support-aousc-deputy-director"]["quote"])
        self.assertEqual(2, len(parts))
        for part in parts:
            self.assertIn(part, operative)
        self.assertNotIn(" ".join(parts), operative)
        self.assertIn(" … ", joined_quote(parts))

    def test_the_magistrate_ceiling_is_pinned_and_the_compensation_page_resolves_it(self):
        """28 U.S.C. 634(a) pays full-time magistrate judges "up to" 92
        percent, fixed by the Judicial Conference: a ceiling, not a rate, and
        the distinction from 28 U.S.C. 153(a)'s "equal to" is still pinned
        against both committed sections. What changed on 2026-10-06 is that
        the Administrative Office's own Judicial Compensation page -- the
        document the tier is read from -- prints beneath its table that the
        salary IS 92 percent, which is the document saying what the
        Conference fixed under the ceiling. The rows carry that sentence as
        their basis and are no longer in NOT_PRICED."""
        operative = load_section("magistrate_judges_28_usc_634.html")["operative"]
        self.assertIn("up to an annual rate equal to 92 percent of the salary of a judge of the district court", operative)
        self.assertIn("salaries to be fixed by the conference pursuant to section 633", operative)
        self.assertIn("not less than an annual salary of $100, nor more than one-half the maximum salary", operative)
        self.assertIn(MAGISTRATE_JUDGE_QUOTE, operative)
        self.assertIn("up to an annual rate", MAGISTRATE_JUDGE_QUOTE)
        # And the bankruptcy section says "equal to", with no ceiling word.
        bankruptcy = load_section("bankruptcy_judges_28_usc_153.html")["operative"]
        self.assertIn("equal to 92 percent of the salary of a judge of the district court", bankruptcy)
        self.assertNotIn("up to an annual rate", bankruptcy)
        # The page's own sentence, in its bytes -- by the module's reader and
        # by the gate's independent one -- and in the table's Explanatory
        # Notes rather than in any row the table parser carries.
        text = _table_text()
        self.assertIn(MAGISTRATE_BASIS_QUOTE, text)
        self.assertEqual(1, text.count(MAGISTRATE_BASIS_QUOTE))
        self.assertIn(MAGISTRATE_BASIS_QUOTE, derived_pay_table_text())
        self.assertEqual(text, derived_pay_table_text())
        self.assertEqual(DEFAULT_TABLE_HTML.resolve(), Path(DERIVED_PAY_TABLE_FIXTURE).resolve())
        self.assertIn("Explanatory Notes", text[: text.find(MAGISTRATE_BASIS_QUOTE)])
        loaded = load_judicial_compensation(DEFAULT_TABLE_HTML)
        self.assertNotIn("92 percent", " ".join(loaded["table"]["footnotes"]))
        for node_id in ("jud-district-sdny-magistrate-judge-13", "jud-district-structure-magistrate-judge-varies"):
            self.assertIn(node_id, PARITY_PROVISIONS)
            self.assertNotIn(node_id, NOT_PRICED)
            provision = PARITY_PROVISIONS[node_id]
            self.assertEqual(("28 U.S.C. 634(a)", "district judges", 92), (provision["citation"], provision["tier"], provision["percentOf"]))
            self.assertEqual(MAGISTRATE_BASIS_QUOTE, provision["basisQuote"])
            self.assertIn("CEILING", provision["basisReading"])
            self.assertIn("full-time", provision["basisReading"])
            self.assertFalse(provision.get("via"))

    def test_the_sentencing_commission_chair_and_the_bench_it_does_not_price(self):
        """28 U.S.C. 992(c), read from GPO's 2024 edition: the Chair and Vice
        Chairs at the annual circuit-judge rate -- an office row, no
        percentage, no chain -- and the other voting members "at the daily
        rate", which is why the Commissioner (×6) bench is refused with that
        reason and the Vice Chairs, who have no nodes, reach nothing."""
        provision = PARITY_PROVISIONS["jud-support-ussc-chair-ussc"]
        self.assertEqual(("28 U.S.C. 992(c)", "circuit judges"), (provision["citation"], provision["tier"]))
        self.assertFalse(provision.get("percentOf"))
        self.assertFalse(provision.get("via"))
        self.assertFalse(provision.get("basisQuote"))
        self.assertEqual(USSC_CHAIR_QUOTE, provision["quote"])
        section = load_section(provision["fixture"])
        self.assertIn("www.govinfo.gov", section["url"])
        self.assertIn("USCODE-2024-title28", section["final_url"])
        self.assertEqual(("U.S. Government Publishing Office", "2024 edition of the United States Code"),
                         statute_publisher(section["url"], section["final_url"]))
        self.assertIn(USSC_CHAIR_QUOTE, section["operative"])
        # Both directions on the bench: the sentence that refuses it is the law.
        self.assertIn("shall be paid at the daily rate at which judges of the United States courts of appeals "
                      "are compensated", section["operative"])
        self.assertNotIn("jud-support-ussc-commissioner-6", PARITY_PROVISIONS)
        self.assertIn("daily rate", NOT_PRICED["jud-support-ussc-commissioner-6"])
        self.assertIn("Vice Chairs", NOT_PRICED["jud-support-ussc-commissioner-6"])
        self.assertEqual(DERIVED_PAY_PROVISIONS["jud-support-ussc-chair-ussc"],
                         ("28 U.S.C. 992(c)", "circuit judges", USSC_CHAIR_QUOTE))
        self.assertNotIn("jud-support-ussc-chair-ussc", DERIVED_PAY_PERCENT_OF)
        self.assertNotIn("jud-support-ussc-chair-ussc", DERIVED_PAY_CEILING_BASIS)

    def test_the_deputies_are_priced_and_no_longer_refused(self):
        for node_id in ("jud-support-aousc-deputy-director", "jud-support-fjc-deputy-director"):
            self.assertIn(node_id, PARITY_PROVISIONS)
            self.assertNotIn(node_id, NOT_PRICED)
            self.assertEqual(92, PARITY_PROVISIONS[node_id]["percentOf"])

    def test_the_gate_mirrors_the_repealed_sentence(self):
        self.assertEqual(REPEALED_CAVC_CHIEF_JUDGE_TEXT, DERIVED_PAY_REPEALED_TEXT)

    def test_six_provisions_price_the_identical_figure(self):
        """Which is why the mirror is keyed by node id and not by figure:
        three courts' chief judges and their benches, six nodes, one rate."""
        district = [n for n, p in PARITY_PROVISIONS.items() if p["tier"] == "district judges"]
        # six judges' seats, the two directors since 2026-09-28, the two
        # bankruptcy benches since 2026-09-30 (a percentage of the same tier),
        # since 2026-10-05 the special trial judges and the two deputies (a
        # percentage of a join to the same tier), and since 2026-10-06 the two
        # magistrate benches (the same percentage, through a ceiling)
        self.assertEqual(15, len(district))
        at_the_rate = [n for n in district if not PARITY_PROVISIONS[n].get("percentOf")]
        self.assertEqual(8, len(at_the_rate))
        # And at the circuit tier: the CAAF's chief judge and bench, and since
        # 2026-10-06 the Sentencing Commission's Chair -- three nodes, two
        # statutes, one $264,900.
        circuit = sorted(n for n, p in PARITY_PROVISIONS.items() if p["tier"] == "circuit judges")
        self.assertEqual(["jud-specialized-caaf-chief-judge-caaf", "jud-specialized-caaf-judge-4", "jud-support-ussc-chair-ussc"],
                         circuit)

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
        """Four chief judges, the Tax Court's two benches, the bankruptcy and
        magistrate benches of one district, two directors, two deputies and
        the Sentencing Commission's Chair reach the fixture tree; the CIT, the
        Commission's bench and its Staff Director never."""
        records, report = _records()
        self.assertEqual(13, len(records))
        self.assertEqual(13, report["priced"])
        self.assertIn("jud-district-sdny-magistrate-judge-13", records)
        self.assertIn("jud-support-ussc-chair-ussc", records)
        self.assertNotIn("jud-support-ussc-commissioner-6", records)
        self.assertNotIn("jud-support-ussc-staff-director", records)
        self.assertEqual(["jud-district-sdny-magistrate-judge-13"], report["ceilingBasisRows"])
        chair = records["jud-support-ussc-chair-ussc"]
        self.assertEqual(JUDICIAL_COMPENSATION_TIERS["circuit judges"], chair["amount"])
        self.assertEqual("$264,900", chair["rateText"])
        self.assertEqual(2, len(chair["documents"]))
        self.assertEqual("U.S. Government Publishing Office", chair["documents"][0]["publisher"])
        self.assertEqual("2024 edition of the United States Code", chair["documents"][0]["edition"])
        self.assertIsNone(chair["arithmetic"])
        self.assertIsNone(chair["ceilingBasis"])
        self.assertEqual("the Chair of the United States Sentencing Commission", chair["subject"])
        magistrates = records["jud-district-sdny-magistrate-judge-13"]
        self.assertEqual(round(JUDICIAL_COMPENSATION_TIERS["district judges"] * 0.92, 2), magistrates["amount"])
        self.assertEqual(magistrates["amount"], records["jud-district-sdny-bankruptcy-judge-12"]["amount"])
        self.assertEqual(MAGISTRATE_BASIS_QUOTE, magistrates["ceilingBasis"]["quote"])
        self.assertIs(True, magistrates["ceilingBasis"]["statuteStatesACeiling"])
        self.assertEqual(DERIVED_PAY_TABLE_URL, magistrates["ceilingBasis"]["url"])
        self.assertIn("CEILING", magistrates["ceilingBasis"]["reading"])
        self.assertIn(MAGISTRATE_BASIS_QUOTE, magistrates["derivation"])
        self.assertIn("caps the rate at 92 percent", magistrates["arithmetic"]["note"])
        self.assertIn("ceiling", magistrates["documents"][0]["role"])
        self.assertIsNone(records["jud-district-sdny-bankruptcy-judge-12"]["ceilingBasis"])
        self.assertNotIn("ceiling", records["jud-district-sdny-bankruptcy-judge-12"]["documents"][0]["role"])
        self.assertIn("jud-support-aousc-deputy-director", records)
        self.assertIn("jud-support-fjc-deputy-director", records)
        self.assertIn("jud-specialized-tax-special-trial-judge-multiple", records)
        self.assertNotIn("jud-specialized-intl-trade-chief-judge-cit", records)
        special = records["jud-specialized-tax-special-trial-judge-multiple"]
        self.assertEqual(round(records["jud-specialized-tax-judge-18"]["amount"] * 0.9, 2), special["amount"])
        self.assertEqual(3, len(special["documents"]))
        self.assertEqual("26 U.S.C. 7443(c)(1)", special["viaStatute"])
        self.assertEqual("U.S. Government Publishing Office", special["documents"][0]["publisher"])
        self.assertEqual(2, len(records["jud-support-aousc-deputy-director"]["documents"]))
        self.assertEqual(3, len(records["jud-support-fjc-deputy-director"]["documents"]))
        self.assertEqual(records["jud-support-aousc-deputy-director"]["amount"],
                         records["jud-support-fjc-deputy-director"]["amount"])
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
                self.assertTrue(any(url.startswith(f"https://{host}/") for url in hosts for host in STATUTE_HOSTS), hosts)
                self.assertIn(DERIVED_PAY_TABLE_URL, hosts)

    def test_a_ceiling_row_falls_when_the_page_no_longer_prints_the_sentence(self):
        """The basis is re-found on every run, never trusted: strip the
        Explanatory Note from the page's text and the magistrate row is
        refused with the reason, while the bankruptcy row beside it -- whose
        statute states the rate -- stands. Pass no page text at all and the
        row is refused too, because the sentence is half of what it rests on."""
        text = _table_text()
        self.assertIn(MAGISTRATE_BASIS_QUOTE, text)
        stripped = text.replace(MAGISTRATE_BASIS_QUOTE, "")
        records, report = _records(table_text=stripped)
        self.assertNotIn("jud-district-sdny-magistrate-judge-13", records)
        self.assertIn("no longer prints the sentence", report["refused"]["jud-district-sdny-magistrate-judge-13"])
        self.assertIn("jud-district-sdny-bankruptcy-judge-12", records)
        self.assertEqual(12, len(records))
        records, report = _records(table_text=None)
        self.assertNotIn("jud-district-sdny-magistrate-judge-13", records)
        self.assertIn("was not supplied", report["refused"]["jud-district-sdny-magistrate-judge-13"])
        self.assertEqual(12, len(records))
        # A doctored copy of the page itself, read the way the derive script
        # reads the committed one.
        raw = DEFAULT_TABLE_HTML.read_text(encoding="utf-8")
        self.assertEqual(text, page_text(raw))
        doctored = page_text(raw.replace("is equal to 92 percent of the salary of a district judge", "is set by the Judicial Conference"))
        self.assertNotIn(MAGISTRATE_BASIS_QUOTE, doctored)
        records, report = _records(table_text=doctored)
        self.assertNotIn("jud-district-sdny-magistrate-judge-13", records)
        self.assertIn("jud-support-ussc-chair-ussc", records)

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
        self.assertEqual(13, stats["priced"])
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
        # The ceiling basis reaches the block on the magistrate bench and on
        # nothing else.
        self.assertEqual(MAGISTRATE_BASIS_QUOTE, node_map["jud-district-sdny-magistrate-judge-13"]["positionDerivedPay"]["ceilingBasis"]["quote"])
        for node_id in records:
            if node_id != "jud-district-sdny-magistrate-judge-13":
                self.assertIsNone(node_map[node_id]["positionDerivedPay"]["ceilingBasis"], node_id)

    def test_a_node_another_source_already_priced_is_left_alone(self):
        records, _ = _records()
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["jud-specialized-tax-chief-judge-tax-court"]["positionStatutoryPay"] = {"source": "elsewhere"}
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(12, stats["priced"])
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
        # The magistrate bench the same way: 634(a) says "full-time United
        # States magistrate judges", and the ceiling basis rides through.
        magistrates = node_map["jud-district-sdny-magistrate-judge-13"]["positionDerivedPay"]
        self.assertEqual(13, magistrates["holders"]["count"])
        self.assertEqual(MAGISTRATE_BASIS_QUOTE, magistrates["ceilingBasis"]["quote"])
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

    def test_the_percentage_of_a_join_passes_and_each_link_and_the_arithmetic_are_checked(self):
        """The special trial judges: 90 percent of a Tax Court judge's rate,
        which 26 U.S.C. 7443(c)(1) sets at a district judge's -- three
        documents, 90%, none stating the figure, the statute read from the
        GPO's edition. The FJC's Deputy chains through 603's two sentences."""
        node_map, _ = index_tree(self.tree)
        special = node_map["jud-specialized-tax-special-trial-judge-multiple"]
        self.assertEqual([], self._check(special))
        pay = special["positionDerivedPay"]
        self.assertEqual(3, pay["verification"]["documents"])
        self.assertEqual(90, pay["verification"]["percent"])
        self.assertEqual(0, pay["verification"]["documentsStatingTheFigure"])
        self.assertEqual(90, pay["arithmetic"]["percent"])
        self.assertEqual(round(249_900.0 * 0.9, 2), pay["amount"])
        self.assertIn("www.govinfo.gov", pay["url"])
        self.assertIn("holders", pay)
        # The chain's middle document dropped.
        forged = copy.deepcopy(pay)
        forged["documents"] = [d for d in forged["documents"] if d["citation"] != "26 U.S.C. 7443(c)(1)"]
        forged["verification"]["documents"] = 2
        forged["verification"]["percent"] = 80
        self.assertTrue(any("document list does not carry" in v for v in self._check(special, forged)))
        # The percentage dropped: the tier's own rate published as the figure.
        forged = copy.deepcopy(pay)
        forged["amount"] = 249_900.0
        forged["rateText"] = "$249,900"
        self.assertTrue(self._check(special, forged))
        # The statute read from a host this pipeline does not read the Code from.
        forged = copy.deepcopy(pay)
        forged["documents"][0]["url"] = forged["documents"][0]["url"].replace("www.govinfo.gov", "law.cornell.edu")
        forged["url"] = forged["documents"][0]["url"]
        self.assertTrue(any("host this pipeline does not read" in v for v in self._check(special, forged)))
        # Moved onto the Tax Court's own bench, whose provision is the parity.
        bench = node_map["jud-specialized-tax-judge-18"]
        out = self._check(bench, pay)
        self.assertTrue(any("not the one" in v for v in out), out)
        # The two Deputies.
        for node_id, documents in (("jud-support-aousc-deputy-director", 2), ("jud-support-fjc-deputy-director", 3)):
            node = node_map[node_id]
            self.assertEqual([], self._check(node), node_id)
            self.assertEqual(documents, node["positionDerivedPay"]["verification"]["documents"])
            self.assertEqual(round(249_900.0 * 0.92, 2), node["positionDerivedPay"]["amount"])
            self.assertIn(" … ", node["positionDerivedPay"]["derivation"])

    def test_a_percentage_record_moved_to_the_magistrate_bench_is_caught(self):
        """Same court, same count shape, the same $229,908 -- and a different
        statute: the bankruptcy record on the magistrate bench cites 153(a)
        where the node's provision is 634(a), and carries no ceiling basis."""
        node_map, _ = index_tree(self.tree)
        magistrates = node_map["jud-district-sdny-magistrate-judge-13"]
        moved = copy.deepcopy(node_map["jud-district-sdny-bankruptcy-judge-12"]["positionDerivedPay"])
        moved["holders"]["count"] = 13
        moved["holders"]["text"] = "×13"
        out = self._check(magistrates, moved)
        self.assertTrue(any("this node's parity provision is '28 U.S.C. 634(a)'" in v for v in out), out)
        self.assertTrue(any("without the compensation page's sentence" in v for v in out), out)
        # And the other way: the magistrate record on the bankruptcy bench
        # carries a ceiling basis the bankruptcy statute does not need.
        bankruptcy = node_map["jud-district-sdny-bankruptcy-judge-12"]
        moved = copy.deepcopy(magistrates["positionDerivedPay"])
        moved["holders"]["count"] = 12
        moved["holders"]["text"] = "×12"
        out = self._check(bankruptcy, moved)
        self.assertTrue(any("states the rate itself, not a ceiling" in v for v in out), out)
        self.assertTrue(any("this node's parity provision is '28 U.S.C. 153(a)'" in v for v in out), out)

    def test_the_magistrate_row_passes_and_each_part_of_the_ceiling_basis_is_checked(self):
        """The ceiling the compensation page resolves: the honest block
        passes; the basis dropped, misquoted, unread, unexplained, cited
        elsewhere, or standing beside a statute with no ceiling in it is
        refused; and the sentence is checked against the committed page's
        bytes rather than the block's own copy."""
        node_map, _ = index_tree(self.tree)
        bench = node_map["jud-district-sdny-magistrate-judge-13"]
        self.assertEqual([], self._check(bench))
        honest = bench["positionDerivedPay"]
        self.assertEqual(round(JUDICIAL_COMPENSATION_TIERS["district judges"] * 0.92, 2), honest["amount"])
        self.assertEqual(2, honest["verification"]["documents"])
        self.assertEqual(80, honest["verification"]["percent"])
        self.assertEqual(0, honest["verification"]["documentsStatingTheFigure"])
        self.assertEqual(13, honest["holders"]["count"])
        self.assertIn("up to", honest["statuteQuote"])

        pay = copy.deepcopy(honest)
        pay["ceilingBasis"] = None
        self.assertTrue(any("without the compensation page's sentence" in v for v in self._check(bench, pay)))

        pay = copy.deepcopy(honest)
        pay["ceilingBasis"]["quote"] = "By statute, the salary of a magistrate judge is 92 percent of a district judge's."
        self.assertTrue(any("not the one the Judicial Compensation page prints" in v for v in self._check(bench, pay)))

        pay = copy.deepcopy(honest)
        pay["ceilingBasis"]["reading"] = ""
        self.assertTrue(any("without saying in words" in v for v in self._check(bench, pay)))

        pay = copy.deepcopy(honest)
        pay["ceilingBasis"]["url"] = "https://example.gov/elsewhere"
        self.assertTrue(any("not the compensation page this pipeline reads" in v for v in self._check(bench, pay)))

        pay = copy.deepcopy(honest)
        pay["ceilingBasis"]["statuteStatesACeiling"] = False
        self.assertTrue(any("does not say the statute states a ceiling" in v for v in self._check(bench, pay)))

        pay = copy.deepcopy(honest)
        pay["derivation"] = pay["derivation"].replace(MAGISTRATE_BASIS_QUOTE, "")
        self.assertTrue(any("the ceiling is read through" in v for v in self._check(bench, pay)))

        # The bankruptcy sentence -- a rate, no "up to" -- quoted as this
        # node's statute: wrong sentence for the provision, and no ceiling.
        pay = copy.deepcopy(honest)
        pay["statuteQuote"] = DERIVED_PAY_PROVISIONS["jud-district-sdny-bankruptcy-judge-12"][2]
        out = self._check(bench, pay)
        self.assertTrue(any("not the one 28 U.S.C. 634(a) prints now" in v for v in out), out)
        self.assertTrue(any("states no ceiling" in v for v in out), out)

        # The committed page no longer printing the sentence: the gate reads
        # the bytes, not the block.
        with unittest.mock.patch.object(gate, "derived_pay_table_text", return_value="a page with no such note"):
            self.assertTrue(any("committed Judicial Compensation page does not print" in v for v in self._check(bench)))
        self.assertEqual([], self._check(bench))

    def test_the_sentencing_commission_chair_passes_and_is_tied_to_its_own_node(self):
        """The Chair at the circuit-judge rate: two documents, 80%, the
        statute read from govinfo. The CAAF's chief judge prices the identical
        $264,900 from a different statute, so a record moved between the two
        keeps a correct figure and a correct tier, and only the node's own id
        tells them apart; and the Commission's bench has no provision at all."""
        node_map, _ = index_tree(self.tree)
        chair = node_map["jud-support-ussc-chair-ussc"]
        self.assertEqual([], self._check(chair))
        pay = chair["positionDerivedPay"]
        self.assertEqual(JUDICIAL_COMPENSATION_TIERS["circuit judges"], pay["amount"])
        self.assertEqual("$264,900", pay["rateText"])
        self.assertEqual("circuit judges", pay["seatTier"])
        self.assertEqual(2, pay["verification"]["documents"])
        self.assertEqual(80, pay["verification"]["percent"])
        self.assertIsNone(pay["arithmetic"])
        self.assertIsNone(pay["ceilingBasis"])
        self.assertNotIn("holders", pay)
        self.assertIn("www.govinfo.gov", pay["url"])
        caaf = node_map["jud-specialized-caaf-chief-judge-caaf"]
        self.assertEqual(pay["amount"], caaf["positionDerivedPay"]["amount"])
        out = self._check(caaf, pay)
        self.assertTrue(any("this node's parity provision is '10 U.S.C. 942(d)'" in v for v in out), out)
        out = self._check(chair, caaf["positionDerivedPay"])
        self.assertTrue(any("this node's parity provision is '28 U.S.C. 992(c)'" in v for v in out), out)
        # The bench of six: no provision, by decision, and the gate says so.
        commissioners = node_map["jud-support-ussc-commissioner-6"]
        self.assertNotIn("positionDerivedPay", commissioners)
        moved = copy.deepcopy(pay)
        moved["holders"] = {"text": "×6", "kind": "exact", "count": 6, "appliesToEachHolder": True, "note": "each"}
        self.assertTrue(any("no parity provision" in v for v in self._check(commissioners, moved)))
        # A percentage block on the Chair's parity row is refused as on any other.
        forged = copy.deepcopy(pay)
        forged["percentOf"] = 92
        self.assertTrue(any("arithmetic on a parity provision" in v for v in self._check(chair, forged)))

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



class SectionHeadingLettersTests(unittest.TestCase):
    """A section number may carry two letters -- 42 U.S.C. 2000ee, the Privacy
    and Civil Liberties Oversight Board -- and both operative-text readers
    must find its heading, or the section is refused as carrying none (which
    the first version of the pattern did, admitting one letter)."""

    FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "uscode" / "pclob_42_usc_2000ee_govinfo2024.html"
    SENTENCE = ("The chairman of the Board shall be compensated at the rate of pay payable for a position at level III of the "
                "Executive Schedule under section 5314 of title 5.")

    @unittest.skipUnless(FIXTURE.exists(), "the PCLOB section is not committed")
    def test_both_readers_find_the_two_letter_heading(self):
        from scripts.validate_published_graph import uscode_operative_text

        module_text = operative_text(self.FIXTURE.read_text(encoding="utf-8"))
        gate_text = uscode_operative_text(self.FIXTURE)
        self.assertIn(self.SENTENCE, module_text)
        self.assertIn(self.SENTENCE, gate_text)
        self.assertEqual(module_text, gate_text)

    def test_a_heading_without_a_number_is_still_refused(self):
        from data_pipeline.verification.derived_pay import Unreadable

        with self.assertRaises(Unreadable):
            operative_text("<html><body><p>No section here.</p><p>Editorial Notes</p></body></html>")
        # Three letters are not a section number this pattern knows.
        with self.assertRaises(Unreadable):
            operative_text("<html><body><h3>§2000abc. Not a section</h3><p>Text.</p></body></html>")

if __name__ == "__main__":
    unittest.main()
