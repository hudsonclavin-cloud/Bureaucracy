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

from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS, index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.derived_pay import load_section
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
    TIER_REFERENCE_IES_COMPOSITION,
    TIER_REFERENCE_IG_RULE,
    TIER_REFERENCE_METHOD,
    TIER_REFERENCE_METHOD_PERCENT,
    TIER_REFERENCE_ROWS,
    TIER_REFERENCE_SOURCE,
    TIER_REFERENCE_TABLE_URL,
    US_CODE_BASIS_FIXTURE_DIR,
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
            {"id": "exec-ind-epa", "name": "Environmental Protection Agency (EPA)", "type": "Agency",
             "children": [
                 {"id": "exec-ind-epa-inspector-general-bench", "name": "Inspector General (×2)", "type": "Position",
                  "representsPosts": {"text": "×2", "kind": "exact", "count": 2}},
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
}


class SectionTests(unittest.TestCase):
    """What the committed bytes print, asserted in both directions."""

    def test_every_quoted_sentence_is_in_its_sections_operative_text_by_both_readers(self):
        for fixture, quote in (
            ("gao_31_usc_703.html", TIER_REFERENCE_PROVISIONS["leg-support-gao-comptroller-general-of-the-united-states"]["quote"]),
            ("gao_31_usc_703.html", TIER_REFERENCE_PROVISIONS["leg-support-gao-deputy-comptroller-general"]["quote"]),
            ("ig_5_usc_403.html", INSPECTOR_GENERAL_RULE["quote"]),
            ("ig_5_usc_401.html", INSPECTOR_GENERAL_RULE["definitionQuote"]),
        ):
            with self.subTest(fixture=fixture):
                module_text = load_section(fixture)["operative"]
                gate_text = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / fixture)
                self.assertEqual(module_text, gate_text)
                self.assertIn(quote, module_text)

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
            node_name, office, citation, fixture, level, sentence = TIER_REFERENCE_ROWS[node_id]
            self.assertEqual((row["nodeName"], row["office"], row["citation"], row["fixture"], row["level"], row["quote"]),
                             (node_name, office, citation, fixture, level, sentence))
            self.assertEqual(0, row["percent"])
            self.assertIn(level, EXECUTIVE_SCHEDULE_RATES)

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
        self.assertEqual({node_id: "node not in the graph" for node_id in TIER_REFERENCE_PROVISIONS
                          if node_id not in PRICED_IN_BASE_TREE},
                         {k: v for k, v in report["refused"].items() if k != "exec-ind-epa-inspector-general-bench"})
        self.assertEqual(6, report["pricedByReviewedRow"])
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
        self.assertEqual("currency_mark_on_the_figure_the_record_is_computed_from", kinds["exec-dept-defense-inspector-general"])

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
        self.assertEqual(8, stats["priced"])
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
        self.assertEqual(7, stats["priced"])
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
        good_arith = ig["arithmetic"]
        cases = {
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
        # 37 derived (the GAO's two, the GPO's two, the IES's four, the FCA
        # Board's Chairman, the Librarian of Congress, and 27 IGs); the
        # Department of Justice's IG carries OPM's archived listing with a
        # printed level and rate (`positionPayRate`), which a figure set by
        # reference never displaces, so 36 are published.
        self.assertEqual(36, len(priced), sorted(priced))
        self.assertNotIn("exec-dept-doj-inspector-general", priced)
        self.assertIsInstance(node_map["exec-dept-doj-inspector-general"].get("positionPayRate"), dict)
        establishments = set(tier_reference_establishments(uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "ig_5_usc_401.html")))
        for node_id, node in priced.items():
            with self.subTest(node=node_id):
                parent = node_map.get(parent_map.get(node_id) or "")
                self.assertEqual([], tier_reference_pay_violations(node, node[FIELD], TODAY, _label, parent.get("name") if parent else None))
                # The pay documents never among the node's own sources; OPM's
                # PLUM listings, a different document, may be.
                self.assertFalse(any("uscode.house.gov" in str(u) or str(u) == TIER_REFERENCE_TABLE_URL
                                     for u in node.get("sourceUrls") or []))
                if node_id not in TIER_REFERENCE_PROVISIONS:
                    self.assertIn(node[FIELD]["identification"]["establishment"], establishments)
        # The stamped Defense-agency IGs, the DFEs' and the legislative ones
        # are not among them.
        for absent in ("exec-dept-defense-agency-dia-inspector-general", "exec-ind-misc-national-labor-relations-board-nlrb-independent-inspector-general",
                       "leg-support-gao-inspector-general", "exec-ind-cia-inspector-general", "exec-ind-misc-americorps-inspector-general"):
            self.assertNotIn(absent, priced)


if __name__ == "__main__":
    unittest.main()
