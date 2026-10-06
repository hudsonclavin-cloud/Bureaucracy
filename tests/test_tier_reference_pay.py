"""A rate set by REFERENCE to an Executive Schedule level, pinned in both
directions: what the committed sections print, what the module derives from
them, what the gate accepts, and every way a block can be faked."""

from __future__ import annotations

import copy
import json
import re
import unittest
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, canonical_name_key, index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.derived_pay import STATUTE_HOSTS, load_section, statute_publisher
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.pay_documents import PAY_DOCUMENT_FIELDS, annotate_pay_documents
from data_pipeline.verification.pay_tables import (
    OFFICE_RATE_PAY_FIELDS,
    federal_fiscal_year_of,
    load_executive_schedule,
    withdraw_pay_from_multi_post_nodes,
)
from data_pipeline.verification.tier_reference_pay import (
    FIELD,
    INSPECTOR_GENERAL_RULE,
    NOT_PRICED_KINDS,
    PAY_METHOD,
    PAY_METHOD_PERCENT,
    PAY_SOURCE,
    IES_COMPOSITION,
    TIER_REFERENCE_PROVISIONS,
    INSTRUMENT_PROVISIONS,
    apply_pay_evidence,
    build_records,
    parse_establishments,
)
from scripts.validate_published_graph import (
    DERIVED_PAY_STRENGTH_BY_COUNT,
    EXECUTIVE_SCHEDULE_RATES,
    OFFICE_RATE_PAY_FIELDS as GATE_OFFICE_RATE_PAY_FIELDS,
    PAY_DOCUMENT_STATES_FIGURE,
    PAY_DOCUMENT_URL_KEYS,
    TIER_REFERENCE_COMPOSED_ROWS,
    TIER_REFERENCE_FIELD,
    TIER_REFERENCE_IDENTIFICATIONS,
    TIER_REFERENCE_IES_COMPOSITION,
    TIER_REFERENCE_IG_RULE,
    TIER_REFERENCE_METHOD,
    TIER_REFERENCE_METHOD_PERCENT,
    TIER_REFERENCE_ROWS,
    TIER_REFERENCE_SOURCE,
    TIER_REFERENCE_TABLE_URL,
    US_CODE_BASIS_FIXTURE_DIR,
    is_us_code_document_url,
    tier_reference_establishments,
    tier_reference_pay_violations,
    uscode_operative_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = date.today().isoformat()


def _label(node):
    return "node {!r}".format(node.get("id"))


def _base_tree():
    """The GAO's two officers; the Department of Defense with its own IG and a
    Defense agency beneath it with a stamped one; a designated Federal entity
    with an IG; AmeriCorps; the FBI's qualified IG; a bench-shaped IG."""
    return {
        "id": "the-constitution-of-the-united-states", "name": "The Constitution", "type": "Foundation",
        "children": [
            # The GPO's two officers (44 U.S.C. 303) and the IES's Director
            # and a centre Commissioner (20 U.S.C. 9514, 9517): reviewed rows
            # since 2026-09-28. The NCER row rests on 9517(a)'s class sentence
            # and carries 9511(c)(3) as its third document.
            {"id": "leg-support-gpo", "name": "Government Publishing Office (GPO)", "type": "Agency",
             "children": [
                 {"id": "leg-support-gpo-director-gpo-public-printer", "name": "Director, GPO (Public Printer)", "type": "Position"},
                 {"id": "leg-support-gpo-deputy-director-coo", "name": "Deputy Director / COO", "type": "Position"},
             ]},
            {"id": "exec-dept-ed-ies", "name": "Institute of Education Sciences (IES)", "type": "Bureau",
             "children": [
                 {"id": "exec-dept-ed-ies-director-ies", "name": "Director, IES", "type": "Position"},
                 {"id": "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer",
                  "name": "Commissioner — National Center for Education Research (NCER)", "type": "Position"},
             ]},
            {"id": "leg-support-gao", "name": "Government Accountability Office (GAO)", "type": "Agency",
             "children": [
                 {"id": "leg-support-gao-comptroller-general-of-the-united-states",
                  "name": "Comptroller General of the United States", "type": "Position"},
                 {"id": "leg-support-gao-deputy-comptroller-general", "name": "Deputy Comptroller General", "type": "Position"},
                 {"id": "leg-support-gao-inspector-general", "name": "Inspector General", "type": "Position"},
             ]},
            {"id": "exec-dept-defense", "name": "Department of Defense (DoD)", "type": "Cabinet Department",
             "children": [
                 {"id": "exec-dept-defense-inspector-general", "name": "Inspector General", "type": "Position"},
                 {"id": "exec-dept-defense-agency-dia", "name": "Defense Intelligence Agency (DIA)", "type": "Defense Agency",
                  "children": [
                      {"id": "exec-dept-defense-agency-dia-inspector-general", "name": "Inspector General", "type": "Position"},
                  ]},
                 {"id": "exec-dept-defense-agency-nsa", "name": "National Security Agency (NSA)", "type": "Defense Agency",
                  "children": [
                      {"id": "exec-dept-defense-agency-nsa-inspector-general", "name": "Inspector General", "type": "Position"},
                  ]},
             ]},
            {"id": "exec-dept-doj", "name": "Department of Justice (DOJ)", "type": "Cabinet Department",
             "children": [
                 {"id": "exec-dept-doj-fbi", "name": "Federal Bureau of Investigation (FBI)", "type": "Bureau",
                  "children": [
                      {"id": "exec-dept-doj-fbi-inspector-general-doj-ig-covers-fbi",
                       "name": "Inspector General (DoJ IG covers FBI)", "type": "Position"},
                  ]},
             ]},
            {"id": "exec-ind-misc-nlrb", "name": "National Labor Relations Board (NLRB — independent)", "type": "Independent Agency",
             "children": [
                 {"id": "exec-ind-misc-nlrb-inspector-general", "name": "Inspector General", "type": "Position"},
             ]},
            {"id": "exec-ind-misc-americorps", "name": "AmeriCorps", "type": "Independent Agency",
             "children": [
                 {"id": "exec-ind-misc-americorps-inspector-general", "name": "Inspector General", "type": "Position"},
             ]},
            # Three bodies whose own section names the office under the
            # stamped title (2026-10-05): the USAGM's CEO, the EAC's and the
            # FEC's chair and vice chair.
            {"id": "exec-ind-misc-broadcasting-board-of-governors-usagm", "name": "U.S. Agency for Global Media", "type": "Independent Agency",
             "children": [
                 {"id": "exec-ind-misc-broadcasting-board-of-governors-usagm-director-administrator-chair-broadcasting-board-of-governors-usagm",
                  "name": "Director / Administrator / Chair, Broadcasting Board of Governors / USAGM", "type": "Position"},
             ]},
            {"id": "exec-ind-misc-election-assistance-commission-eac", "name": "Election Assistance Commission (EAC)", "type": "Independent Agency",
             "children": [
                 {"id": "exec-ind-misc-election-assistance-commission-eac-director-administrator-chair-election-assistance-commission",
                  "name": "Director / Administrator / Chair, Election Assistance Commission", "type": "Position"},
                 {"id": "exec-ind-misc-election-assistance-commission-eac-deputy-director-vice-chair",
                  "name": "Deputy Director / Vice Chair", "type": "Position"},
             ]},
            {"id": "exec-ind-misc-federal-election-commission-fec", "name": "Federal Election Commission (FEC)", "type": "Independent Agency",
             "children": [
                 {"id": "exec-ind-misc-federal-election-commission-fec-director-administrator-chair-federal-election-commission",
                  "name": "Director / Administrator / Chair, Federal Election Commission", "type": "Position"},
                 {"id": "exec-ind-misc-federal-election-commission-fec-deputy-director-vice-chair",
                  "name": "Deputy Director / Vice Chair", "type": "Position"},
             ]},
            {"id": "exec-ind-epa", "name": "Environmental Protection Agency (EPA)", "type": "Agency",
             "children": [
                 {"id": "exec-ind-epa-inspector-general-bench", "name": "Inspector General (×2)", "type": "Position",
                  "representsPosts": {"text": "×2", "kind": "exact", "count": 2}},
             ]},
            # 2026-10-06: two principals whose own section sets Level III --
            # the NOAA Administrator (15 U.S.C. 1503b, the NNSA shape with an
            # identifying sentence) and the Archivist of the United States
            # (44 U.S.C. 2103(b), the Librarian's shape).
            {"id": "exec-dept-doc-noaa", "name": "NOAA — National Oceanic & Atmospheric Administration", "type": "Bureau",
             "children": [
                 {"id": "exec-dept-doc-noaa-administrator-noaa", "name": "Administrator, NOAA", "type": "Position"},
             ]},
            {"id": "exec-ind-nara", "name": "National Archives & Records Administration (NARA)", "type": "Agency",
             "children": [
                 {"id": "exec-ind-nara-archivist-of-the-united-states", "name": "Archivist of the United States", "type": "Position"},
             ]},
        ],
    }


def _records(tree=None):
    loaded = load_executive_schedule()
    node_map, parent_map = index_tree(tree or _base_tree())
    fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
    return build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year)


PRICED_IN_BASE_TREE = {
    "leg-support-gao-comptroller-general-of-the-united-states",
    "leg-support-gao-deputy-comptroller-general",
    "leg-support-gpo-director-gpo-public-printer",
    "leg-support-gpo-deputy-director-coo",
    "exec-dept-ed-ies-director-ies",
    "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer",
    "exec-dept-defense-inspector-general",
    "exec-dept-defense-agency-nsa-inspector-general",
    "exec-ind-misc-broadcasting-board-of-governors-usagm-director-administrator-chair-broadcasting-board-of-governors-usagm",
    "exec-ind-misc-election-assistance-commission-eac-director-administrator-chair-election-assistance-commission",
    "exec-ind-misc-election-assistance-commission-eac-deputy-director-vice-chair",
    "exec-ind-misc-federal-election-commission-fec-director-administrator-chair-federal-election-commission",
    "exec-ind-misc-federal-election-commission-fec-deputy-director-vice-chair",
    "exec-dept-doc-noaa-administrator-noaa",
    "exec-ind-nara-archivist-of-the-united-states",
}
STAMPED_IN_BASE_TREE = {node_id for node_id in PRICED_IN_BASE_TREE if node_id in TIER_REFERENCE_IDENTIFICATIONS}
NOAA_ID = "exec-dept-doc-noaa-administrator-noaa"
ARCHIVIST_ID = "exec-ind-nara-archivist-of-the-united-states"


class SectionTests(unittest.TestCase):
    """What the committed bytes print, asserted in both directions."""

    def test_every_quoted_sentence_is_in_its_sections_operative_text_by_both_readers(self):
        for fixture, quote in (
            ("gao_31_usc_703.html", TIER_REFERENCE_PROVISIONS["leg-support-gao-comptroller-general-of-the-united-states"]["quote"]),
            ("gao_31_usc_703.html", TIER_REFERENCE_PROVISIONS["leg-support-gao-deputy-comptroller-general"]["quote"]),
            ("ig_5_usc_403.html", INSPECTOR_GENERAL_RULE["quote"]),
            ("ig_5_usc_401.html", INSPECTOR_GENERAL_RULE["definitionQuote"]),
            # 2026-10-06: NOAA's pay and identifying sentences, the Archivist's pay sentence.
            ("noaa_15_usc_1503b_govinfo2024.html", TIER_REFERENCE_PROVISIONS[NOAA_ID]["quote"]),
            ("noaa_15_usc_1503b_govinfo2024.html", TIER_REFERENCE_PROVISIONS[NOAA_ID]["identificationQuote"]),
            ("nara_44_usc_2103_govinfo2024.html", TIER_REFERENCE_PROVISIONS[ARCHIVIST_ID]["quote"]),
        ):
            with self.subTest(fixture=fixture, quote=quote[:40]):
                module_text = load_section(fixture)["operative"]
                gate_text = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / fixture)
                self.assertEqual(module_text, gate_text)
                self.assertIn(quote, module_text)

    def test_the_noaa_section_names_the_administrator_then_pays_the_under_secretary_at_level_iii(self):
        """15 U.S.C. 1503b (2026-10-06): one section, two sentences. The first
        makes the Under Secretary of Commerce for Oceans and Atmosphere the
        Administrator of NOAA -- the title this graph carries -- and the
        second pays the Under Secretary at Level III. The section prints no
        figure and prints "Level" with a capital L, which the row quotes as
        printed rather than normalising."""
        row = TIER_REFERENCE_PROVISIONS[NOAA_ID]
        section = load_section(row["fixture"])
        text = section["operative"]
        self.assertIn("who shall serve as the Administrator of the National Oceanic and Atmospheric Administration", text)
        self.assertIn("Level III of the Executive Schedule Pay Rates (5 U.S.C. 5314)", text)
        self.assertLess(text.index(row["identificationQuote"]), text.index(row["quote"]))
        self.assertNotIn("$", text)
        self.assertEqual("III", row["level"])
        self.assertEqual(0, row["percent"])
        # The Schedule's own §5314 lists the Under Secretary and says the same
        # thing; it is corroboration the row does not lean on.
        self.assertIn("Under Secretary of Commerce for Oceans and Atmosphere, the incumbent of which also serves as "
                      "Administrator of the National Oceanic and Atmospheric Administration",
                      load_section("exec_schedule_5314.html")["operative"])
        self.assertTrue(any(host in section["url"] for host in STATUTE_HOSTS))
        self.assertEqual("U.S. Government Publishing Office", statute_publisher(section["url"])[0])

    def test_the_archivists_section_states_level_iii_in_its_own_words_and_the_schedule_lists_the_title_twice(self):
        """44 U.S.C. 2103 (2026-10-06): (a) names the office in full, (b) pays
        "The Archivist" at Level III, and the section prints no figure. The
        Schedule itself prints "Archivist of the United States" at BOTH §5314
        and §5316, which is why `statutory_schedule.py` prices the post for
        nobody; this row rests on 2103(b) alone, and the test pins both the
        reason the other route is closed and the fact this one does not
        resolve it."""
        from data_pipeline.verification.statutory_schedule import load_schedule

        row = TIER_REFERENCE_PROVISIONS[ARCHIVIST_ID]
        section = load_section(row["fixture"])
        text = section["operative"]
        self.assertIn("(a) The Archivist of the United States shall be appointed by the President by and with the "
                      "advice and consent of the Senate.", text)
        self.assertIn("(b) The Archivist shall be compensated at the rate provided for level III of the Executive "
                      "Schedule under section 5314 of title 5.", text)
        self.assertNotIn("$", text)
        self.assertNotIn("identificationQuote", row)  # the node IS the office the section names
        self.assertEqual(canonical_name_key(row["nodeName"]), canonical_name_key(row["office"]))
        self.assertEqual("III", row["level"])
        for fixture in ("exec_schedule_5314.html", "exec_schedule_5316.html"):
            self.assertIn("Archivist of the United States.", load_section(fixture)["operative"], fixture)
        schedule = load_schedule()
        self.assertIn(canonical_name_key("Archivist of the United States"), schedule["ambiguous"])
        self.assertNotIn(canonical_name_key("Archivist of the United States"), schedule["index"])
        self.assertTrue(any(host in section["url"] for host in STATUTE_HOSTS))
        self.assertEqual("U.S. Government Publishing Office", statute_publisher(section["url"])[0])

    def test_the_inspector_general_act_states_level_iii_plus_three_percent_and_no_figure(self):
        text = load_section("ig_5_usc_403.html")["operative"]
        self.assertIn("plus 3 percent", text)
        self.assertNotIn("$", text)

    def test_the_gao_section_states_the_levels_and_no_figure(self):
        text = load_section("gao_31_usc_703.html")["operative"]
        self.assertIn("level II of the Executive Schedule", text)
        self.assertIn("level III of the Executive Schedule", text)
        self.assertNotIn("$", text)

    def test_the_establishment_list_parses_to_the_departments_and_agencies_by_name(self):
        names = parse_establishments(load_section("ig_5_usc_401.html")["operative"])
        self.assertEqual(35, len(names))
        for expected in ("Department of Agriculture", "Department of the Interior", "Department of Veterans Affairs",
                         "Environmental Protection Agency", "National Security Agency", "National Reconnaissance Office",
                         "Social Security Administration", "Tennessee Valley Authority",
                         "Corporation for National and Community Service", "Export-Import Bank of the United States"):
            self.assertIn(expected, names)
        # Not establishments, whatever a node here is called.
        for absent in ("Central Intelligence Agency", "Defense Intelligence Agency", "Government Accountability Office",
                       "National Labor Relations Board", "Smithsonian Institution"):
            self.assertNotIn(absent, names)
        self.assertEqual(names, tier_reference_establishments(uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "ig_5_usc_401.html")))

    def test_section_415_is_committed_and_prints_no_rate_for_a_designated_entitys_ig(self):
        """'Looked and it states no rate' and 'nobody looked' are different
        facts; the DFE IGs stay unpriced on the first."""
        text = load_section("ig_5_usc_415.html")["operative"]
        self.assertTrue(text)
        self.assertIsNone(re.search(r"rate of (basic )?pay|Executive Schedule", text))


class SectionNumberingTests(unittest.TestCase):
    """2 U.S.C. 136a–2 is numbered with an en-dash and a second number, and
    until 2026-09-28 none of the three operative-text readers found its
    heading, so the Librarian's section read as page chrome."""

    def test_the_en_dashed_section_is_read_by_every_reader(self):
        from data_pipeline.verification.statutory_schedule import load_basis_section

        quote = TIER_REFERENCE_PROVISIONS["leg-support-loc-librarian-of-congress"]["quote"]
        for name, text in (
            ("tier_reference_pay", load_section("loc_2_usc_136a-2.html")["operative"]),
            ("statutory_schedule", load_basis_section("loc_2_usc_136a-2.html")["operative"]),
            ("gate", uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "loc_2_usc_136a-2.html")),
        ):
            with self.subTest(reader=name):
                self.assertTrue(text.startswith("§136a–2."), text[:40])
                self.assertIn(quote, text)


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirrors_the_gao_rows_by_node_id(self):
        self.assertEqual(set(TIER_REFERENCE_ROWS), set(TIER_REFERENCE_PROVISIONS))
        for node_id, row in TIER_REFERENCE_PROVISIONS.items():
            mirrored = TIER_REFERENCE_ROWS[node_id]
            node_name, office, citation, fixture, level, sentence = mirrored[:6]
            # A seventh element is the percentage the row's statute adds
            # (AmeriCorps' CEO, 42 U.S.C. 12651c(b)); absent, zero.
            self.assertEqual(int(mirrored[6]) if len(mirrored) > 6 else 0, int(row["percent"]), node_id)
            self.assertEqual((row["nodeName"], row["office"], row["citation"], row["fixture"], row["level"], row["quote"]),
                             (node_name, office, citation, fixture, level, sentence))
            # A percentage is carried by the mirror exactly where the row has one.
            self.assertEqual(int(row["percent"]) > 0, len(mirrored) > 6, node_id)
            self.assertIn(level, EXECUTIVE_SCHEDULE_RATES)

    def test_the_gate_mirrors_the_identifying_sentence_of_every_stamped_row(self):
        with_identification = {n: row["identificationQuote"] for n, row in TIER_REFERENCE_PROVISIONS.items()
                               if row.get("identificationQuote")}
        self.assertEqual(with_identification, TIER_REFERENCE_IDENTIFICATIONS)
        # The USAGM's CEO, the EAC's and FEC's chairs and vice chairs, and --
        # since the twelfth batch -- the PCLOB's chairman, the ARC's Federal
        # Cochairman and AmeriCorps' CEO: every stamped title the module
        # prices carries the sentence of its own section naming the office.
        # Nine with the NNSA Administrator (2026-10-06), whose own section
        # says the Under Secretary for Nuclear Security it pays IS the
        # Administrator this graph names; ten with the NOAA Administrator the
        # same day, 15 U.S.C. 1503b's Under Secretary of Commerce for Oceans
        # and Atmosphere "who shall serve as the Administrator".
        self.assertEqual(10, len(with_identification))
        for node_id, sentence in with_identification.items():
            row = TIER_REFERENCE_PROVISIONS[node_id]
            with self.subTest(node=node_id):
                # The identifying sentence is in the SAME section as the pay
                # sentence, in its operative text, by both readers.
                section = load_section(row["fixture"])
                self.assertIn(sentence, section["operative"])
                self.assertIn(sentence, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / row["fixture"]))
                self.assertNotEqual(sentence, row["quote"])
                # A title the statute does not print -- the stamped
                # "Director / Administrator / Chair" family, or (the NNSA
                # Administrator) a graph title that is not the office the pay
                # sentence names -- which is why the row needs the sentence.
                self.assertNotEqual(canonical_name_key(row["nodeName"]), canonical_name_key(row["office"]))
                self.assertTrue(
                    row["nodeName"].startswith(("Director / Administrator / Chair", "Deputy Director / Vice Chair"))
                    or node_id in ("exec-dept-doe-nnsa-administrator-nnsa", NOAA_ID)
                )
                self.assertIn("www.govinfo.gov", section["url"])

    def test_a_code_granule_on_govinfo_is_a_statute_and_the_manual_on_govinfo_is_not(self):
        self.assertTrue(is_us_code_document_url("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title31-section703"))
        self.assertTrue(is_us_code_document_url("https://www.govinfo.gov/content/pkg/USCODE-2024-title52/html/USCODE-2024-title52-subtitleII-chap209-subchapII-partA-subpart1-sec20923.htm"))
        self.assertFalse(is_us_code_document_url("https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/GOVMAN-2025-12-31-072"))
        self.assertFalse(is_us_code_document_url("https://www.govinfo.gov/content/pkg/BUDGET-2027-DB/xls/BUDGET-2027-DB-2.xlsx"))
        self.assertFalse(is_us_code_document_url("https://www.law.cornell.edu/uscode/text/52/20923"))

    def test_the_three_sections_came_from_govinfo_and_say_so(self):
        for fixture in ("usagm_22_usc_6203_govinfo2024.html", "eac_52_usc_20923_govinfo2024.html", "fec_52_usc_30106_govinfo2024.html"):
            section = load_section(fixture)
            self.assertTrue(any(host in section["url"] for host in STATUTE_HOSTS))
            publisher, edition = statute_publisher(section["url"])
            self.assertEqual("U.S. Government Publishing Office", publisher)
            self.assertEqual("2024 edition of the United States Code", edition)
        # The two sections of 2026-10-06 came through govinfo's link service,
        # whose meta records the link URL: the publisher is read off it, and
        # the 2024 granule it resolved to is in `final_url` beside it.
        for fixture in ("noaa_15_usc_1503b_govinfo2024.html", "nara_44_usc_2103_govinfo2024.html"):
            section = load_section(fixture)
            self.assertTrue(any(host in section["url"] for host in STATUTE_HOSTS))
            self.assertIn("/link/uscode/", section["url"])
            self.assertEqual("U.S. Government Publishing Office", statute_publisher(section["url"])[0])
            meta = json.loads((US_CODE_BASIS_FIXTURE_DIR / (fixture + ".meta.json")).read_text(encoding="utf-8"))
            self.assertIn("USCODE-2024", str(meta.get("final_url")))
            self.assertEqual(200, meta.get("status"))
        # The pair reading: each statute creates a chairman and a vice
        # chairman together, and 30106 pays the members OTHER than the two
        # ex officio ones, whom (a)(5) also excludes from the chairmanship.
        fec = load_section("fec_52_usc_30106_govinfo2024.html")["operative"]
        self.assertIn("(other than the Secretary of the Senate and the Clerk of the House of Representatives) shall receive compensation", fec)
        self.assertIn("The staff director shall be paid at a rate not to exceed", fec)  # a ceiling, not priced

    def test_the_gate_mirrors_the_composing_section_and_which_rows_need_it(self):
        citation, fixture, sentence = TIER_REFERENCE_IES_COMPOSITION
        self.assertEqual((IES_COMPOSITION["citation"], IES_COMPOSITION["fixture"], IES_COMPOSITION["quote"]),
                         (citation, fixture, sentence))
        composed = {n for n, row in TIER_REFERENCE_PROVISIONS.items() if row.get("composition")}
        self.assertEqual(composed, TIER_REFERENCE_COMPOSED_ROWS)
        self.assertEqual(2, len(composed))
        for node_id in composed:
            self.assertIs(TIER_REFERENCE_PROVISIONS[node_id]["composition"], IES_COMPOSITION)
        # The NCES Commissioner is priced by 9517(b) by name and needs no such document.
        self.assertNotIn("exec-dept-ed-ies-commissioner-national-center-for-education-statistics-nces", composed)

    def test_the_gate_mirrors_the_inspector_general_rule(self):
        citation, fixture, level, percent, sentence, est_citation, est_fixture, definition = TIER_REFERENCE_IG_RULE
        rule = INSPECTOR_GENERAL_RULE
        self.assertEqual((citation, fixture, level, percent, sentence), (
            rule["citation"], rule["fixture"], rule["level"], rule["percent"], rule["quote"]))
        self.assertEqual((est_citation, est_fixture, definition), (
            rule["establishmentsCitation"], rule["establishmentsFixture"], rule["definitionQuote"]))

    def test_the_gate_mirrors_the_names_and_the_classes(self):
        self.assertEqual(TIER_REFERENCE_FIELD, FIELD)
        self.assertEqual(TIER_REFERENCE_SOURCE, PAY_SOURCE)
        self.assertEqual(TIER_REFERENCE_METHOD, PAY_METHOD)
        self.assertEqual(TIER_REFERENCE_METHOD_PERCENT, PAY_METHOD_PERCENT)
        self.assertIn(FIELD, OFFICE_RATE_PAY_FIELDS)
        self.assertIn(FIELD, GATE_OFFICE_RATE_PAY_FIELDS)
        self.assertIn(FIELD, PAY_DOCUMENT_URL_KEYS)
        self.assertEqual(0, PAY_DOCUMENT_STATES_FIGURE[FIELD])
        self.assertEqual(0, PAY_DOCUMENT_FIELDS[FIELD]["statesTheFigure"])
        self.assertIn(FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(FIELD, MINIMAL_GRAPH_FIELDS)
        self.assertIn(PAY_SOURCE, fe.SOURCE_TYPES)
        self.assertIn(PAY_SOURCE, fe.COMPUTED_FROM_MARKED_FIGURE_SOURCE_TYPES)


class BuildTests(unittest.TestCase):
    def test_the_gao_rows_and_the_establishments_igs_are_priced_and_nothing_else(self):
        records, report = _records()
        self.assertEqual(PRICED_IN_BASE_TREE, set(records))
        # A bench-shaped IG is refused outright: 403(e) prices "an Inspector
        # General", and a node standing for several is not one.
        self.assertEqual("stands for several posts", report["refused"]["exec-ind-epa-inspector-general-bench"])
        # The reviewed rows whose nodes this fixture tree does not carry are
        # refused for that and nothing else.
        # 2026-10-07: the instrument rows (Reorganization Plans, the chambers'
        # pay orders; tests/test_notes_instruments.py) name nodes this tree
        # does not carry either, and are refused for that alone.
        self.assertEqual({node_id: "node not in the graph" for node_id in {**TIER_REFERENCE_PROVISIONS, **INSTRUMENT_PROVISIONS}
                          if node_id not in PRICED_IN_BASE_TREE},
                         {k: v for k, v in report["refused"].items() if k != "exec-ind-epa-inspector-general-bench"})
        # 13 since 2026-10-06: the NOAA Administrator and the Archivist.
        self.assertEqual(13, report["pricedByReviewedRow"])
        for node_id in STAMPED_IN_BASE_TREE:
            record = records[node_id]
            self.assertEqual(2, len(record["documents"]))
            self.assertEqual(TIER_REFERENCE_IDENTIFICATIONS[node_id], record["identification"]["statuteIdentifies"])
            self.assertEqual(record["office"], record["identification"]["office"])
            self.assertEqual("U.S. Government Publishing Office", record["documents"][0]["publisher"])
            # Since 2026-10-06 the edition is read off the granule the fetch
            # resolved to: a fixture fetched through govinfo's link service
            # records the link URL as `url` and the USCODE-2024 granule as
            # `final_url`, and the record names the 2024 edition either way
            # rather than "an edition of the United States Code".
            self.assertIn("2024 edition of the United States Code", record["documents"][0]["title"])
            self.assertEqual("2024 edition of the United States Code", record["documents"][0]["edition"])
            if "USCODE-2024" not in record["documents"][0]["url"]:
                self.assertIn("/link/uscode/", record["documents"][0]["url"])
        self.assertNotIn("statuteIdentifies", records["leg-support-gao-comptroller-general-of-the-united-states"]["identification"])
        # The two rows of 2026-10-06: both Level III, two documents each, the
        # NOAA row carrying the sentence that makes the Under Secretary the
        # Administrator and the Archivist's carrying none.
        noaa, archivist = records[NOAA_ID], records[ARCHIVIST_ID]
        for record in (noaa, archivist):
            self.assertEqual(EXECUTIVE_SCHEDULE_RATES["III"], record["amount"])
            self.assertEqual("III", record["level"])
            self.assertIsNone(record["arithmetic"])
            self.assertEqual(PAY_METHOD, record["method"])
            self.assertEqual(2, len(record["documents"]))
            self.assertEqual("reviewed_row", record["identification"]["kind"])
        self.assertEqual(TIER_REFERENCE_PROVISIONS[NOAA_ID]["identificationQuote"], noaa["identification"]["statuteIdentifies"])
        self.assertEqual("15 U.S.C. 1503b", noaa["statute"])
        self.assertNotIn("statuteIdentifies", archivist["identification"])
        self.assertEqual("44 U.S.C. 2103(b)", archivist["statute"])
        self.assertIn(NOAA_ID, STAMPED_IN_BASE_TREE)
        self.assertNotIn(ARCHIVIST_ID, STAMPED_IN_BASE_TREE)
        # Two of the stamped-shape rows are Level III -- the USAGM's CEO and,
        # since 2026-10-06, NOAA's Under Secretary -- and the commissions' chairs
        # and vice chairs Level IV.
        level_iii = {"exec-ind-misc-broadcasting-board-of-governors-usagm-director-administrator-chair-broadcasting-board-of-governors-usagm", NOAA_ID}
        for node_id in level_iii:
            self.assertEqual(EXECUTIVE_SCHEDULE_RATES["III"], records[node_id]["amount"])
        for node_id in STAMPED_IN_BASE_TREE - level_iii:
            self.assertEqual(EXECUTIVE_SCHEDULE_RATES["IV"], records[node_id]["amount"])
        self.assertEqual(2, report["pricedInspectorsGeneral"])
        # The composed row carries three documents, the others two.
        ncer = records["exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer"]
        self.assertEqual(3, len(ncer["documents"]))
        self.assertEqual("20 U.S.C. 9511(c)(3)", ncer["documents"][2]["citation"])
        self.assertEqual(2, len(records["exec-dept-ed-ies-director-ies"]["documents"]))
        self.assertEqual(2, len(records["leg-support-gpo-director-gpo-public-printer"]["documents"]))
        # The stamped IG under DIA, the DFE's, the FBI's qualified one, the
        # bench, and AmeriCorps: each refused with the reason on the record.
        not_priced = report["notPriced"]
        self.assertIn("exec-dept-defense-agency-dia-inspector-general", not_priced)
        self.assertIn("exec-ind-misc-nlrb-inspector-general", not_priced)
        self.assertNotIn("exec-dept-doj-fbi-inspector-general-doj-ig-covers-fbi", records)
        self.assertNotIn("exec-ind-epa-inspector-general-bench", records)
        self.assertIn(NOT_PRICED_KINDS["americorps_named_only_in_the_alias_table"], not_priced["exec-ind-misc-americorps-inspector-general"])
        self.assertIn(NOT_PRICED_KINDS["not_an_establishment"], not_priced["exec-dept-defense-agency-dia-inspector-general"])

    def test_a_gao_row_is_the_levels_own_rate_and_an_ig_is_the_rate_plus_three_percent(self):
        records, _ = _records()
        cg = records["leg-support-gao-comptroller-general-of-the-united-states"]
        self.assertEqual(EXECUTIVE_SCHEDULE_RATES["II"], cg["amount"])
        self.assertIsNone(cg["arithmetic"])
        self.assertEqual(PAY_METHOD, cg["method"])
        self.assertEqual(2, len(cg["documents"]))
        ig = records["exec-dept-defense-inspector-general"]
        base = EXECUTIVE_SCHEDULE_RATES["III"]
        self.assertEqual(round(base * 1.03, 2), ig["amount"])
        self.assertEqual({"operation": "plus_percent", "baseAmount": base, "percent": 3, "result": ig["amount"]},
                         {k: ig["arithmetic"][k] for k in ("operation", "baseAmount", "percent", "result")})
        self.assertEqual(PAY_METHOD_PERCENT, ig["method"])
        self.assertEqual(3, len(ig["documents"]))
        self.assertEqual("Department of Defense", ig["identification"]["establishment"])
        self.assertEqual("exec-dept-defense", ig["identification"]["organisationId"])
        for record in records.values():
            self.assertEqual("proxy", record["scopeMatch"])
            self.assertTrue(all(document["statesTheFigure"] is False for document in record["documents"]))
            self.assertIn(record["rateText"].lstrip("$"), record["quote"])

    def test_every_record_passes_the_financial_validator_as_a_proxy(self):
        records, _ = _records()
        node_map, _ = index_tree(_base_tree())
        kinds = {}
        for node_id, record in records.items():
            out = fe.validate_record(record, node_map[node_id])
            self.assertEqual("partial", fe.classify(out))
            kinds[node_id] = out["unitsEvidenceKind"]
        self.assertEqual("currency_mark_on_the_printed_figure", kinds["leg-support-gao-comptroller-general-of-the-united-states"])
        self.assertEqual("currency_mark_on_the_printed_figure", kinds["exec-ind-misc-federal-election-commission-fec-deputy-director-vice-chair"])
        self.assertEqual("currency_mark_on_the_figure_the_record_is_computed_from", kinds["exec-dept-defense-inspector-general"])

    def test_a_stamped_row_falls_when_its_section_stops_naming_the_office(self):
        import shutil
        import tempfile
        from data_pipeline.verification.tier_reference_pay import FIXTURE_DIR
        node_id = "exec-ind-misc-election-assistance-commission-eac-deputy-director-vice-chair"
        row = TIER_REFERENCE_PROVISIONS[node_id]
        with tempfile.TemporaryDirectory() as tmp:
            for path in FIXTURE_DIR.iterdir():
                shutil.copy(path, Path(tmp) / path.name)
            doctored = Path(tmp) / row["fixture"]
            raw = doctored.read_bytes()
            needle = b"from among its members"
            self.assertIn(needle, raw)
            doctored.write_bytes(raw.replace(needle, b"from outside its membership"))
            import hashlib
            meta_path = Path(tmp) / (row["fixture"] + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(doctored.read_bytes()).hexdigest()
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            loaded = load_executive_schedule()
            node_map, parent_map = index_tree(_base_tree())
            fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
            records, report = build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year, directory=tmp)
        self.assertNotIn(node_id, records)
        self.assertIn("identifying the office", report["refused"][node_id])
        # The pay sentence is untouched, so the refusal is the identification's alone,
        # and the GAO row from another section stands.
        self.assertIn("leg-support-gao-comptroller-general-of-the-united-states", records)

    def _records_with_doctored_fixtures(self, replacements):
        """Rebuild against a copy of the fixture directory in which each
        (fixture, needle, replacement) has been applied, with the meta's
        digest recomputed so the doctoring is the only thing that changed."""
        import hashlib
        import shutil
        import tempfile
        from data_pipeline.verification.tier_reference_pay import FIXTURE_DIR
        with tempfile.TemporaryDirectory() as tmp:
            for path in FIXTURE_DIR.iterdir():
                shutil.copy(path, Path(tmp) / path.name)
            for fixture, needle, replacement in replacements:
                doctored = Path(tmp) / fixture
                raw = doctored.read_bytes()
                self.assertEqual(1, raw.count(needle), (fixture, needle))
                doctored.write_bytes(raw.replace(needle, replacement))
                meta_path = Path(tmp) / (fixture + ".meta.json")
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["sha256"] = hashlib.sha256(doctored.read_bytes()).hexdigest()
                meta_path.write_text(json.dumps(meta), encoding="utf-8")
            loaded = load_executive_schedule()
            node_map, parent_map = index_tree(_base_tree())
            fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
            return build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year, directory=tmp)

    def test_the_noaa_and_archivist_rows_fall_when_their_sections_state_another_level(self):
        """Both rows rest on the level their section states (2026-10-06). A
        section doctored to say Level IV no longer prints the quoted sentence,
        and the row is refused rather than re-priced; every other row stands."""
        records, report = self._records_with_doctored_fixtures([
            ("noaa_15_usc_1503b_govinfo2024.html",
             b"Level III of the Executive Schedule Pay Rates", b"Level IV of the Executive Schedule Pay Rates"),
            ("nara_44_usc_2103_govinfo2024.html",
             b"level III of the Executive Schedule under section 5314 of title 5",
             b"level IV of the Executive Schedule under section 5315 of title 5"),
        ])
        for node_id in (NOAA_ID, ARCHIVIST_ID):
            self.assertNotIn(node_id, records)
            self.assertIn("no longer carries the quoted sentence", report["refused"][node_id])
            self.assertIn("nowhere on the page", report["refused"][node_id])
        self.assertEqual(PRICED_IN_BASE_TREE - {NOAA_ID, ARCHIVIST_ID}, set(records))

    def test_the_noaa_row_falls_when_its_section_stops_making_the_under_secretary_the_administrator(self):
        """The pay sentence alone prices an Under Secretary of Commerce; what
        ties it to the node named "Administrator, NOAA" is the sentence before
        it, and the row falls with that sentence while the Archivist's,
        which needs none, stands."""
        records, report = self._records_with_doctored_fixtures([
            ("noaa_15_usc_1503b_govinfo2024.html",
             b"who shall serve as the Administrator of the National Oceanic and Atmospheric Administration",
             b"who shall serve as the Deputy Administrator of the National Oceanic and Atmospheric Administration"),
        ])
        self.assertNotIn(NOAA_ID, records)
        self.assertIn("identifying the office", report["refused"][NOAA_ID])
        self.assertIn(ARCHIVIST_ID, records)

    def test_the_validator_refuses_a_computed_figure_that_is_not_the_arithmetic(self):
        records, _ = _records()
        node_map, _ = index_tree(_base_tree())
        record = copy.deepcopy(records["exec-dept-defense-inspector-general"])
        record["amount"] = record["amount"] + 1000
        record["amountRaw"] = "{:,.0f}".format(record["amount"])
        record["quote"] = record["quote"] + " " + record["amountRaw"]
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, node_map["exec-dept-defense-inspector-general"])

    def test_a_renamed_gao_node_is_refused_not_guessed(self):
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["leg-support-gao-deputy-comptroller-general"]["name"] = "Deputy Comptroller"
        records, report = _records(tree)
        self.assertNotIn("leg-support-gao-deputy-comptroller-general", records)
        self.assertIn("renamed", report["refused"]["leg-support-gao-deputy-comptroller-general"])


class ApplyTests(unittest.TestCase):
    def test_the_block_is_stamped_and_no_source_url_is(self):
        records, _ = _records()
        tree = _base_tree()
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(15, stats["priced"])  # 13 + the NOAA Administrator and the Archivist (2026-10-06)
        self.assertEqual(2, stats["priced_inspectors_general"])
        annotate_pay_documents(tree)
        node_map, _ = index_tree(tree)
        for node_id in records:
            node = node_map[node_id]
            pay = node[FIELD]
            # An IG's third document is 401(1)'s list; a composed row's is
            # 9511(c)(3); every other row rests on the statute and the table.
            composed = bool((TIER_REFERENCE_PROVISIONS.get(node_id) or {}).get("composition"))
            expected = 3 if (pay["arithmetic"] or composed) else 2
            self.assertEqual(expected, pay["verification"]["documents"])
            self.assertEqual(DERIVED_PAY_STRENGTH_BY_COUNT[expected], pay["verification"]["percent"])
            self.assertEqual(0, pay["verification"]["documentsStatingTheFigure"])
            for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
                self.assertIsNone(node.get(field))
            self.assertIsNone(node.get("resolved_total_amount"))

    def test_a_node_another_source_already_priced_is_left_alone(self):
        records, _ = _records()
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-dept-defense-inspector-general"]["positionSchedulePay"] = {"source": "elsewhere"}
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(14, stats["priced"])
        self.assertEqual(1, stats["already_priced_by_another_source"])

    def test_an_ig_reparented_since_the_match_is_refused(self):
        records, _ = _records()
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        dod = node_map["exec-dept-defense"]
        ig = node_map["exec-dept-defense-inspector-general"]
        dod["children"].remove(ig)
        node_map["exec-dept-defense-agency-dia"]["children"].append(ig)
        stats = apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(1, stats["reparented_since_the_match"])
        self.assertNotIn(FIELD, ig)

    def test_the_multi_post_sweep_keeps_the_field_as_an_office_rate(self):
        records, _ = _records()
        tree = _base_tree()
        apply_pay_evidence(tree, records, index_tree=index_tree)
        self.assertEqual(0, withdraw_pay_from_multi_post_nodes(tree))
        node_map, _ = index_tree(tree)
        self.assertNotIn("holders", node_map["exec-dept-defense-inspector-general"][FIELD])


class GateTests(unittest.TestCase):
    """Each dimension corrupted in turn, against blocks the gate accepts."""

    def setUp(self):
        records, _ = _records()
        self.tree = _base_tree()
        apply_pay_evidence(self.tree, records, index_tree=index_tree)
        annotate_pay_documents(self.tree)
        self.node_map, self.parent_map = index_tree(self.tree)

    def _check(self, node_id, pay=None, parent_name="use-tree"):
        node = self.node_map[node_id]
        if parent_name == "use-tree":
            parent = self.node_map.get(self.parent_map.get(node_id) or "")
            parent_name = parent.get("name") if parent else None
        return tier_reference_pay_violations(node, pay if pay is not None else node[FIELD], TODAY, _label, parent_name)

    def test_every_honest_block_passes(self):
        for node_id in PRICED_IN_BASE_TREE:
            with self.subTest(node=node_id):
                self.assertEqual([], self._check(node_id))

    def test_each_way_a_block_can_be_faked_is_refused(self):
        ig_id = "exec-dept-defense-inspector-general"
        cg_id = "leg-support-gao-comptroller-general-of-the-united-states"
        ig = self.node_map[ig_id][FIELD]
        cg = self.node_map[cg_id][FIELD]
        ncer_id = "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer"
        ncer = self.node_map[ncer_id][FIELD]
        eac_vice_id = "exec-ind-misc-election-assistance-commission-eac-deputy-director-vice-chair"
        eac_vice = self.node_map[eac_vice_id][FIELD]
        noaa = self.node_map[NOAA_ID][FIELD]
        archivist = self.node_map[ARCHIVIST_ID][FIELD]
        good_arith = ig["arithmetic"]
        cases = {
            # 2026-10-06: the Archivist cannot be priced at the Schedule's
            # OTHER listing of the title (§5316, Level V) -- 2103(b) says III;
            # the two Level III blocks cannot swap, since the row is keyed by
            # id; and the NOAA row cannot drop or alter the sentence that
            # makes the Under Secretary the Administrator this graph names.
            "the Archivist priced at the Schedule's other listing, Level V": (ARCHIVIST_ID, {**archivist, "level": "V"}, "use-tree"),
            "the Archivist's block moved onto the NOAA Administrator": (NOAA_ID, archivist, "use-tree"),
            "the NOAA block moved onto the Archivist": (ARCHIVIST_ID, noaa, "use-tree"),
            "the NOAA row without the sentence making the Under Secretary the Administrator": (NOAA_ID, {**noaa, "identification": {k: v for k, v in noaa["identification"].items() if k != "statuteIdentifies"}}, "use-tree"),
            "the NOAA row quoting an identifying sentence the section does not print": (NOAA_ID, {**noaa, "identification": {**noaa["identification"], "statuteIdentifies": "The Under Secretary shall serve as the Deputy Administrator of the National Oceanic and Atmospheric Administration."}}, "use-tree"),
            "the NOAA row identifying another office": (NOAA_ID, {**noaa, "identification": {**noaa["identification"], "office": "Assistant Secretary of Commerce for Oceans and Atmosphere"}}, "use-tree"),
            "the Archivist's row given an identifying sentence it has none of": (ARCHIVIST_ID, {**archivist, "identification": {**archivist["identification"], "statuteIdentifies": "The Archivist of the United States shall be appointed by the President by and with the advice and consent of the Senate."}}, "use-tree"),
            "the NOAA row misquoting the pay sentence with a lower-case level": (NOAA_ID, {**noaa, "statuteQuote": noaa["statuteQuote"].replace("Level III", "level III")}, "use-tree"),
            # Scope: the parent the tree gives the node, never the block's word.
            "an IG under a Defense agency 401 does not list": (ig_id, ig, "Defense Intelligence Agency (DIA)"),
            "an IG under a designated Federal entity": (ig_id, ig, "National Labor Relations Board (NLRB — independent)"),
            "an IG block naming another establishment": (ig_id, {**ig, "identification": {**ig["identification"], "establishment": "Department of State"}}, "use-tree"),
            "an IG block with no arithmetic": (ig_id, {**ig, "arithmetic": None}, "use-tree"),
            "a percentage the Act does not state": (ig_id, {**ig, "percent": 5, "arithmetic": {**good_arith, "percent": 5}}, "use-tree"),
            "a result that is not the base plus the percentage": (ig_id, {**ig, "amount": ig["amount"] + 1, "arithmetic": {**good_arith, "result": ig["amount"] + 1}}, "use-tree"),
            "a base that is not the table's Level III": (ig_id, {**ig, "arithmetic": {**good_arith, "baseAmount": 1.0, "baseText": "$1"}}, "use-tree"),
            "the level's rate misquoted": (ig_id, {**ig, "levelRateText": "$1"}, "use-tree"),
            "the IG rule under the GAO method": (ig_id, {**ig, "method": PAY_METHOD}, "use-tree"),
            "a GAO row carrying arithmetic": (cg_id, {**cg, "arithmetic": good_arith}, "use-tree"),
            "a GAO row priced at the wrong level": (cg_id, {**cg, "level": "III"}, "use-tree"),
            "a GAO row moved onto the other officer": ("leg-support-gao-deputy-comptroller-general", cg, "use-tree"),
            "a GAO row quoting a sentence the section does not print": (cg_id, {**cg, "statuteQuote": "Comptroller General is paid at level I"}, "use-tree"),
            "a document claiming to state the figure": (ig_id, {**ig, "documents": [{**ig["documents"][0], "statesTheFigure": True}] + ig["documents"][1:]}, "use-tree"),
            "a dropped document": (ig_id, {**ig, "documents": ig["documents"][:2]}, "use-tree"),
            "an inflated percentage": (ig_id, {**ig, "verification": {**ig["verification"], "percent": 95}}, "use-tree"),
            "a summary claiming a document states the figure": (ig_id, {**ig, "verification": {**ig["verification"], "documentsStatingTheFigure": 1}}, "use-tree"),
            "a verified grade": (cg_id, {**cg, "financialEvidenceStatus": "verified"}, "use-tree"),
            "an exact scope": (cg_id, {**cg, "scopeMatch": "exact"}, "use-tree"),
            "another table": (cg_id, {**cg, "tableUrl": "https://www.opm.gov/other"}, "use-tree"),
            "a future retrieval": (cg_id, {**cg, "checkedAt": "2099-01-01T00:00:00Z"}, "use-tree"),
            "an unknown source": (cg_id, {**cg, "source": "somewhere"}, "use-tree"),
            # The composed row: 9517(a) names no centre, so 9511(c)(3) must
            # ride as the third document, quoted as printed.
            "a composed row without its composing document": (ncer_id, {**ncer, "documents": ncer["documents"][:2]}, "use-tree"),
            "a composed row misquoting the composing sentence": (ncer_id, {**ncer, "documents": ncer["documents"][:2] + [{**ncer["documents"][2], "quote": "The National Education Centers, which include the NCER"}]}, "use-tree"),
            "a composing document on a row 9517(b) prices by name": ("exec-dept-ed-ies-director-ies", {**self.node_map["exec-dept-ed-ies-director-ies"][FIELD], "documents": self.node_map["exec-dept-ed-ies-director-ies"][FIELD]["documents"] + [ncer["documents"][2]]}, "use-tree"),
            "a GPO row moved onto the other officer": ("leg-support-gpo-deputy-director-coo", self.node_map["leg-support-gpo-director-gpo-public-printer"][FIELD], "use-tree"),
            # The stamped rows: the identifying sentence must be quoted, must
            # be the section's, and a block cannot move between the two
            # bodies' identically named vice chairs.
            "a stamped row without the identifying sentence": (eac_vice_id, {**eac_vice, "identification": {k: v for k, v in eac_vice["identification"].items() if k != "statuteIdentifies"}}, "use-tree"),
            "a stamped row quoting an identifying sentence the section does not print": (eac_vice_id, {**eac_vice, "identification": {**eac_vice["identification"], "statuteIdentifies": "The Commission shall select a chair from outside its membership."}}, "use-tree"),
            "a stamped row identifying another office": (eac_vice_id, {**eac_vice, "identification": {**eac_vice["identification"], "office": "Executive Director of the Election Assistance Commission"}}, "use-tree"),
            "the EAC's vice chair block moved onto the FEC's identically named node": ("exec-ind-misc-federal-election-commission-fec-deputy-director-vice-chair", eac_vice, "use-tree"),
            "an identifying sentence on a row that has none": (cg_id, {**cg, "identification": {**cg["identification"], "statuteIdentifies": "Comptroller General is the head of the GAO"}}, "use-tree"),
            "a statute on a host this pipeline does not read": (eac_vice_id, {**eac_vice, "url": "https://www.law.cornell.edu/uscode/text/52/20923", "documents": [{**eac_vice["documents"][0], "url": "https://www.law.cornell.edu/uscode/text/52/20923"}] + eac_vice["documents"][1:]}, "use-tree"),
        }
        for name, (node_id, pay, parent_name) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual([], self._check(node_id, pay, parent_name), name)

    def test_a_block_on_a_node_named_otherwise_or_beside_another_rate_is_refused(self):
        ig_id = "exec-dept-defense-inspector-general"
        node = copy.deepcopy(self.node_map[ig_id])
        node["name"] = "Deputy Inspector General"
        self.assertNotEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, "Department of Defense (DoD)"))
        node = copy.deepcopy(self.node_map[ig_id])
        node["positionSchedulePay"] = {"amount": 1.0}
        self.assertNotEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, "Department of Defense (DoD)"))
        node = copy.deepcopy(self.node_map[ig_id])
        node["sourceUrls"] = [node[FIELD]["url"]]
        self.assertNotEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, "Department of Defense (DoD)"))
        node = copy.deepcopy(self.node_map[ig_id])
        node["cost_status"] = "official"
        self.assertNotEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, "Department of Defense (DoD)"))


class PublishedGraphTests(unittest.TestCase):
    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_the_published_blocks_are_the_gao_officers_and_the_establishments_igs(self):
        node_map, parent_map = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        priced = {node_id: node for node_id, node in node_map.items() if isinstance(node.get(FIELD), dict)}
        # 46 derived (the GAO's two, the GPO's two, the IES's four, the FCA
        # Board's Chairman, the Librarian of Congress, the USAGM's CEO, the
        # EAC's and the FEC's chair and vice chair, and -- since the twelfth
        # batch of 2026-10-05 -- the Secret Service Uniformed Division's
        # Chief, the PCLOB's chairman, the ARC's Federal Cochairman and
        # AmeriCorps' Chief Executive Officer, plus 27 IGs); a figure set by
        # reference never displaces a rate a PLUM listing's own level prices
        # (`positionPayRate`): the Department of Justice's IG from the
        # archive, and since the current export's office-named-for-the-post
        # rule of 2026-10-05 the GPO's Director (listed EX II, the same
        # $228,000) and the Treasury's, Commerce's and Energy's IGs -- which
        # the export lists at EX IV, EX IV and EX III where 5 U.S.C. 403(e)
        # sets Level III plus 3 percent, a disagreement between two official
        # documents this project surfaces rather than resolves. 41 published;
        # 44 since 2026-10-06, when the twelfth batch's legislative-branch
        # cluster added the Architect of the Capitol (2 U.S.C. 1802), the
        # Chief of the Capitol Police (2 U.S.C. 1902) and the GAO's General
        # Counsel (31 U.S.C. 731(c)) as reviewed rows; 45 with the NNSA
        # Administrator (42 U.S.C. 7132(c)) from the same batch's
        # remaining-departments cluster; 47 later on 2026-10-06, when the NOAA
        # Administrator (15 U.S.C. 1503b, whose Under Secretary of Commerce
        # for Oceans and Atmosphere "shall serve as the Administrator", at
        # Level III) and the Archivist of the United States (44 U.S.C.
        # 2103(b), Level III in the section's own words) landed as reviewed
        # rows -- neither node carried any pay field before, so the
        # leave-alone rule did not apply and both publish.
        # 54 since 2026-10-07 (passes only after the coordinator's regenerate):
        # seven posts whose pay an instrument the Code prints outside its
        # sections sets -- NOAA's Deputy Administrator and Chief Scientist
        # (Reorganization Plan No. 4 of 1970), the Deputy Secretary of
        # Commerce (No. 3 of 1979), the Secretary of the Senate and the
        # Senate's Sergeant at Arms (the Order of the President pro tempore of
        # March 25, 2024), the Clerk and the CAO of the House (the Order of
        # the Speaker of January 17, 2025). None carried a pay field before.
        self.assertEqual(54, len(priced), sorted(priced))
        for node_id in INSTRUMENT_PROVISIONS:
            self.assertIn(node_id, priced)
        for added in ("exec-dept-dhs-usss-chief-uniformed-division",
                      "exec-dept-doe-nnsa-administrator-nnsa",
                      NOAA_ID,
                      ARCHIVIST_ID,
                      "leg-support-aoc-architect-of-the-capitol",
                      "leg-support-uscp-chief-of-police",
                      "leg-support-gao-general-counsel",
                      "exec-ind-misc-privacy-civil-liberties-oversight-board-pclob-director-administrator-chair-privacy-civil-liberties-oversight-board",
                      "exec-ind-misc-appalachian-regional-commission-arc-director-administrator-chair-appalachian-regional-commission",
                      "exec-ind-misc-americorps-director-administrator-chair-americorps"):
            self.assertIn(added, priced)
        americorps = priced["exec-ind-misc-americorps-director-administrator-chair-americorps"][FIELD]
        self.assertEqual(americorps["percent"], 3)
        self.assertEqual(americorps["arithmetic"]["operation"], "plus_percent")
        self.assertEqual(americorps["amount"], 215888.0)
        for displaced in ("exec-dept-treasury-inspector-general", "exec-dept-doc-inspector-general",
                          "exec-dept-doe-inspector-general", "leg-support-gpo-director-gpo-public-printer"):
            self.assertNotIn(displaced, priced)
            self.assertIsInstance(node_map[displaced].get("positionPayRate"), dict, displaced)
        for node_id in TIER_REFERENCE_IDENTIFICATIONS:
            self.assertIn(node_id, priced)
        self.assertNotIn("exec-dept-doj-inspector-general", priced)
        self.assertIsInstance(node_map["exec-dept-doj-inspector-general"].get("positionPayRate"), dict)
        establishments = set(tier_reference_establishments(uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "ig_5_usc_401.html")))
        for node_id, node in priced.items():
            with self.subTest(node=node_id):
                parent = node_map.get(parent_map.get(node_id) or "")
                self.assertEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, parent.get("name") if parent else None))
                # The pay documents never among the node's own sources; OPM's
                # PLUM listings, a different document, may be.
                # A govinfo URL may sit there legitimately: the Government
                # Manual is published on the same host. A Code granule may not.
                self.assertFalse(any(is_us_code_document_url(u) or str(u) == TIER_REFERENCE_TABLE_URL
                                     for u in node.get("sourceUrls") or []))
                if node_id not in TIER_REFERENCE_PROVISIONS and node_id not in INSTRUMENT_PROVISIONS:
                    self.assertIn(node[FIELD]["identification"]["establishment"], establishments)
        # The stamped Defense-agency IGs, the DFEs' and the legislative ones
        # are not among them.
        for absent in ("exec-dept-defense-agency-dia-inspector-general", "exec-ind-misc-national-labor-relations-board-nlrb-independent-inspector-general",
                       "leg-support-gao-inspector-general", "exec-ind-cia-inspector-general", "exec-ind-misc-americorps-inspector-general"):
            self.assertNotIn(absent, priced)


if __name__ == "__main__":
    unittest.main()
