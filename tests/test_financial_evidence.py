"""The financial-evidence validator, pinned in both directions.

Every rule here exists because getting it wrong publishes a false number, so
each is tested twice: a good record passes, and the specific defect the rule
guards against is refused.

Most of these tests are the residue of a red team. The first draft of this
module was attacked with 178 executed records and 47 of them got a false
figure past it — including the exact 1000x units error the module's own
docstring said it existed to prevent. Where a test below looks paranoid, it
is because the attack it encodes actually worked.
"""

from __future__ import annotations

import json
import math
import unittest

from data_pipeline.verification import financial_evidence as fe


ORG = {"id": "gsa-cbca", "name": "Civilian Board of Contract Appeals", "type": "Board"}
POST = {"id": "doj-fbi-director", "name": "Director, FBI", "type": "Position"}
COMMITTEE = {"id": "leg-house-cmte-rules", "name": "House Committee on Rules", "type": "Committee"}

GOOD = {
    "nodeId": "gsa-cbca",
    "amount": 10248000.0,
    "amountRaw": "10,248",
    "units": "thousands_usd",
    "normalizedMultiplier": 1000,
    "unitsEvidence": "TABLE 3 — SUMMARY OF APPROPRIATIONS (Dollars in Thousands)",
    "costBasis": "budget_request",
    "fiscalYear": 2026,
    "periodCoverage": "full_fiscal_year",
    "amountScope": "Civilian Board of Contract Appeals",
    "scopeMatch": "exact",
    "rollupRole": "line",
    "sourceType": "congressional_justification",
    "sourceUrl": "https://www.gsa.gov/cdnstatic/fy2026-cj.pdf",
    "documentSha256": "a" * 64,
    "retrievedAt": "2026-09-01T00:00:00Z",
    "locator": {"pdfPage": 6, "table": "Summary of Appropriations", "row": "Civilian Board of Contract Appeals"},
    "quote": "Civilian Board of Contract Appeals .......... 10,248",
    "financialEvidenceStatus": "verified",
}


def rec(**overrides):
    out = dict(GOOD)
    out.update(overrides)
    return out


class ValidRecordTestCase(unittest.TestCase):
    def test_a_complete_record_passes(self):
        out = fe.validate_record(GOOD, ORG)
        self.assertEqual(out["amount"], 10248000.0)
        self.assertEqual(fe.classify(out), "verified")

    def test_the_result_is_strict_json(self):
        json.loads(json.dumps(fe.validate_record(GOOD, ORG)))


class UnitsAreEvidenceTestCase(unittest.TestCase):
    """The headline red-team finding: the first draft's units check compared
    the record only to itself, so a wrong `units` string passed in either
    direction."""

    def test_the_1000x_error_the_docstring_promises_to_catch(self):
        # thousands table declared as whole dollars -> 1000x low
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(units="usd", normalizedMultiplier=1, amount=10248.0), ORG)

    def test_the_mirror_image_1000x_high(self):
        # thousands table declared as millions -> 1000x high
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                rec(units="millions_usd", normalizedMultiplier=1_000_000, amount=10248000000.0), ORG
            )

    def test_units_evidence_is_required(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(unitsEvidence=""), ORG)

    def test_units_evidence_must_state_the_declared_units(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(unitsEvidence="Table 3 — Summary of Appropriations"), ORG)

    def test_units_evidence_contradicting_the_declaration_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(unitsEvidence="(Dollars in Millions)"), ORG)

    def test_a_doubly_applied_multiplier_is_caught_by_the_quote(self):
        # a parser already normalised 10,248 to 10248000 and still declared thousands
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountRaw="10248000", amount=10248000000.0), ORG)

    def test_the_printed_figure_must_appear_in_the_quote(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountRaw="99,999", amount=99999000.0), ORG)

    def test_amount_raw_must_be_text_from_the_page(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountRaw=10248.0), ORG)


class NumberHygieneTestCase(unittest.TestCase):
    """Every guard in the first draft was a comparison, and every comparison
    against NaN is False."""

    def test_nan_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amount=float("nan")), ORG)

    def test_infinity_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amount=float("inf")), ORG)

    def test_an_overflowing_printed_figure_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.parse_amount_text("9" * 400)

    def test_an_accounting_negative_that_also_prints_a_minus_is_refused(self):
        # "(-1,234)" used to be double-negated and published positive
        with self.assertRaises(fe.Rejected):
            fe.parse_amount_text("(-1,234)")

    def test_an_unbalanced_parenthesis_is_refused(self):
        # "(1,234" used to have its paren stripped and be published positive
        for text in ("(1,234", "1,234)", "((1,234))"):
            with self.assertRaises(fe.Rejected):
                fe.parse_amount_text(text)

    def test_a_well_formed_accounting_negative_still_works(self):
        self.assertEqual(fe.parse_amount_text("(1,234)"), -1234.0)

    def test_a_negative_record_passes_when_the_arithmetic_agrees(self):
        out = fe.validate_record(
            rec(amountRaw="(10,248)", amount=-10248000.0,
                quote="Civilian Board of Contract Appeals .......... (10,248)"),
            ORG,
        )
        self.assertEqual(out["amount"], -10248000.0)

    def test_the_multiplier_must_be_an_integer_not_a_bool_or_float(self):
        for bad in (True, 1000.0, "1000", None):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(normalizedMultiplier=bad), ORG)

    def test_zero_is_never_published(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountRaw="0", amount=0.0, quote="the board ...... 0"), ORG)

    def test_a_figure_larger_than_the_government_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                rec(units="billions_usd", normalizedMultiplier=1_000_000_000,
                    unitsEvidence="(Dollars in Billions)", amount=10248000000000.0),
                ORG,
            )


class ScopeIsSettledByLabelTestCase(unittest.TestCase):
    """`exact` used to be a free-text assertion, so any figure could be
    declared this unit's own."""

    def test_an_exact_claim_the_source_does_not_support_is_refused(self):
        # the documented Fish-and-Wildlife-and-Parks trap
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountScope="Fish and Wildlife and Parks"), ORG)

    def test_a_broader_account_may_be_recorded_honestly_as_partial(self):
        out = fe.validate_record(
            rec(amountScope="Fish and Wildlife and Parks", scopeMatch="broader_account",
                financialEvidenceStatus="partial"),
            ORG,
        )
        self.assertEqual(fe.classify(out), "partial")

    def test_the_scope_the_source_named_is_required(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(amountScope=""), ORG)


class NodeBindingTestCase(unittest.TestCase):
    def test_the_record_must_name_the_node_it_is_checked_against(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(nodeId="somewhere-else"), ORG)

    def test_a_rate_of_pay_cannot_sit_on_an_organisation(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(costBasis="basic_pay", sourceType="opm_pay_table"), ORG)

    def test_an_organisations_money_cannot_sit_on_a_position(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(nodeId="doj-fbi-director"), POST)

    def test_a_committee_is_a_non_organisation_exactly_as_the_release_gate_says(self):
        # the first draft's is_organisation() omitted "committee" while its
        # docstring claimed it was the same test the gate uses
        self.assertFalse(fe.is_organisation(COMMITTEE))
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(nodeId="leg-house-cmte-rules"), COMMITTEE)

    def test_a_pay_level_is_a_proxy_for_a_post_not_an_exact_match(self):
        out = fe.validate_record(
            {
                "nodeId": "doj-fbi-director",
                "amount": 225700.0, "amountRaw": "225,700", "units": "usd",
                "normalizedMultiplier": 1,
                "unitsEvidence": "Rates of basic pay, in whole dollars",
                "costBasis": "basic_pay", "fiscalYear": 2026,
                "periodCoverage": "full_fiscal_year",
                "amountScope": "Level II", "scopeMatch": "proxy", "rollupRole": "line",
                "sourceType": "opm_pay_table",
                "sourceUrl": "https://www.opm.gov/salary-tables/26Tables/exec/html/EX.aspx",
                "documentSha256": "b" * 64, "retrievedAt": "2026-09-01T00:00:00Z",
                "locator": {"table": "Executive Schedule", "row": "Level II"},
                "quote": "Level II .......... 225,700",
                "financialEvidenceStatus": "partial",
            },
            POST,
        )
        self.assertEqual(fe.classify(out), "partial")


class SourceAndBasisTestCase(unittest.TestCase):
    def test_a_source_cannot_report_a_basis_it_does_not_produce(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(costBasis="audited_net_cost"), ORG)

    def test_a_congressional_justification_may_report_a_prior_year_actual(self):
        out = fe.validate_record(
            rec(costBasis="net_outlays", fiscalYear=2024, financialEvidenceStatus="verified"), ORG
        )
        self.assertEqual(out["costBasis"], "net_outlays")

    def test_a_realized_figure_for_an_unfinished_year_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(costBasis="net_outlays", fiscalYear=2026), ORG)

    def test_a_realized_figure_for_a_year_that_had_not_begun_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(costBasis="obligations", fiscalYear=2028), ORG)

    def test_a_headcount_must_not_be_denominated_in_dollars(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(costBasis="full_time_equivalents"), ORG)

    def test_a_headcount_printed_in_thousands_has_a_unit_for_it(self):
        out = fe.validate_record(
            rec(costBasis="full_time_equivalents", units="thousands_count",
                normalizedMultiplier=1000, unitsEvidence="FTE in thousands",
                amountRaw="10,248", amount=10248000.0),
            ORG,
        )
        self.assertEqual(out["amount"], 10248000.0)


class PeriodTestCase(unittest.TestCase):
    def test_period_coverage_is_a_vocabulary_not_free_text(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(periodCoverage="full fiscal year"), ORG)

    def test_a_year_to_date_figure_needs_the_date_it_runs_to(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(periodCoverage="fiscal_year_to_date"), ORG)

    def test_a_full_year_figure_takes_no_as_of_date(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(periodAsOf="2026-07-31"), ORG)

    def test_fiscal_year_must_be_an_integer_and_plausible(self):
        for bad in ("2026", 1776, 2999, None, True):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(fiscalYear=bad), ORG)


class ProvenanceTestCase(unittest.TestCase):
    def test_a_non_government_host_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(sourceUrl="https://openomb.org/apportionment/123"), ORG)

    def test_a_query_string_cannot_smuggle_a_gov_host(self):
        # the first draft split the string and read this as a .gov host
        for bad in (
            "https://evil.com?x=www.gsa.gov",
            "https://evil.com#www.gsa.gov",
            "https://www.gsa.gov.attacker.net/x.pdf",
        ):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(sourceUrl=bad), ORG)

    def test_a_scheme_is_required(self):
        for bad in ("www.gsa.gov/x.pdf", "http://www.gsa.gov/x.pdf", "file:///etc/passwd"):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(sourceUrl=bad), ORG)

    def test_a_mil_host_is_accepted(self):
        out = fe.validate_record(rec(sourceUrl="https://www.dla.mil/fy2026-cj.pdf"), ORG)
        self.assertTrue(out["sourceUrl"].endswith(".pdf"))

    def test_a_digest_that_is_not_a_sha256_is_refused(self):
        for bad in ("", "deadbeef", "z" * 64, None):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(documentSha256=bad), ORG)

    def test_a_retrieval_date_in_the_future_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(retrievedAt="2099-01-01T00:00:00Z"), ORG)

    def test_a_locator_that_points_nowhere_is_refused(self):
        for bad in ({}, {"pdfPage": ""}, None, "page 6"):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(locator=bad), ORG)

    def test_a_quote_is_required(self):
        for bad in ("", "10,248", None):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(rec(quote=bad), ORG)


class StateTestCase(unittest.TestCase):
    def test_classify_never_promotes_an_authors_own_claim(self):
        out = fe.validate_record(rec(financialEvidenceStatus="unverified"), ORG)
        self.assertEqual(fe.classify(out), "unverified")

    def test_classify_still_lowers_an_overclaim(self):
        out = fe.validate_record(
            rec(scopeMatch="parent", amountScope="General Services Administration",
                financialEvidenceStatus="verified"),
            ORG,
        )
        self.assertEqual(fe.classify(out), "partial")

    def test_a_state_is_required(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(financialEvidenceStatus=""), ORG)

    def test_a_conflicted_record_must_name_what_it_conflicts_with(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(rec(financialEvidenceStatus="conflicted"), ORG)


class AbsenceTestCase(unittest.TestCase):
    ABSENT = {
        "nodeId": "gsa-cbca",
        "financialEvidenceStatus": "no_direct_amount_found",
        "searchNote": "FY2026 GSA CJ read in full; no line names this board.",
        "sourceType": "congressional_justification",
        "sourceUrl": "https://www.gsa.gov/cdnstatic/fy2026-cj.pdf",
        "documentSha256": "a" * 64,
        "retrievedAt": "2026-09-01T00:00:00Z",
    }

    def test_an_absence_record_passes_without_a_figure(self):
        out = fe.validate_record(self.ABSENT, ORG)
        self.assertEqual(fe.classify(out), "no_direct_amount_found")

    def test_an_absence_record_carrying_a_figure_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record({**self.ABSENT, "amount": 1.0}, ORG)

    def test_an_absence_record_still_proves_which_document_was_read(self):
        # the first draft returned early and skipped every provenance check
        for bad in ({"sourceUrl": "https://openomb.org/x"}, {"documentSha256": "nope"},
                    {"retrievedAt": "2099-01-01T00:00:00Z"}):
            with self.assertRaises(fe.Rejected):
                fe.validate_record({**self.ABSENT, **bad}, ORG)

    def test_an_absence_record_passes_no_stray_keys_through(self):
        out = fe.validate_record({**self.ABSENT, "rollup_total_amount": 999.0}, ORG)
        self.assertNotIn("rollup_total_amount", out)

    def test_an_absence_record_must_say_what_was_searched(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record({**self.ABSENT, "searchNote": "looked"}, ORG)


class ComparabilityTestCase(unittest.TestCase):
    def test_the_same_measurement_is_comparable(self):
        self.assertTrue(fe.comparable(GOOD, rec()).comparable)

    def test_a_request_and_an_outlay_are_not_comparable(self):
        self.assertFalse(fe.comparable(GOOD, rec(costBasis="net_outlays")).comparable)

    def test_different_fiscal_years_are_not_comparable(self):
        self.assertFalse(fe.comparable(GOOD, rec(fiscalYear=2025)).comparable)

    def test_different_coverage_is_not_comparable(self):
        self.assertFalse(fe.comparable(GOOD, rec(periodCoverage="fiscal_year_to_date")).comparable)

    def test_two_year_to_date_figures_cut_off_differently_are_not_comparable(self):
        july = rec(periodCoverage="fiscal_year_to_date", periodAsOf="2026-07-31")
        june = rec(periodCoverage="fiscal_year_to_date", periodAsOf="2026-06-30")
        self.assertFalse(fe.comparable(july, june).comparable)

    def test_a_units_figure_and_its_parents_figure_are_not_a_disagreement(self):
        # comparable() ignoring scope made the module's own documented example
        # report itself as two sources disagreeing
        parent_scope = rec(scopeMatch="broader_account")
        self.assertFalse(fe.comparable(GOOD, parent_scope).comparable)

    def test_a_count_and_a_sum_of_money_are_not_comparable(self):
        fte = rec(costBasis="full_time_equivalents", units="count")
        money = rec(costBasis="full_time_equivalents", units="thousands_usd")
        self.assertFalse(fe.comparable(fte, money).comparable)


class ConflictTestCase(unittest.TestCase):
    def test_two_comparable_figures_that_disagree_are_a_conflict(self):
        other = rec(amount=12000000.0, amountRaw="12,000", sourceUrl="https://www.gsa.gov/other.pdf")
        self.assertEqual(len(fe.detect_conflicts([GOOD, other])), 1)

    def test_tolerance_is_the_documents_rounding_not_a_flat_percentage(self):
        # a table in thousands rounds to 500 dollars; that is not a disagreement
        near = rec(amount=10248000.0 + 400.0)
        self.assertEqual(fe.detect_conflicts([GOOD, near]), [])
        # but 8 billion between two agency figures is, which 0.5% used to allow
        big_a = rec(units="millions_usd", normalizedMultiplier=1_000_000,
                    unitsEvidence="(Dollars in Millions)", amountRaw="1,600,000",
                    amount=1_600_000_000_000.0)
        big_b = dict(big_a, amount=1_608_000_000_000.0)
        self.assertEqual(len(fe.detect_conflicts([big_a, big_b])), 1)

    def test_a_nan_cannot_suppress_a_conflict(self):
        poisoned = rec(amount=float("nan"))
        other = rec(amount=99999999.0, sourceUrl="https://www.gsa.gov/other.pdf")
        self.assertEqual(len(fe.detect_conflicts([poisoned, other, GOOD])), 1)

    def test_figures_on_different_bases_are_not_a_conflict(self):
        self.assertEqual(fe.detect_conflicts([GOOD, rec(costBasis="net_outlays", amount=900000.0)]), [])

    def test_a_total_and_its_lines_are_not_reported_as_a_conflict(self):
        total = rec(rollupRole="total", amount=20000000.0)
        self.assertEqual(fe.detect_conflicts([GOOD, total]), [])

    def test_figures_for_different_nodes_are_not_a_conflict(self):
        self.assertEqual(fe.detect_conflicts([GOOD, rec(nodeId="elsewhere", amount=999.0)]), [])


class DoubleCountingTestCase(unittest.TestCase):
    def test_a_total_stored_beside_its_lines_is_flagged(self):
        findings = fe.double_counted([GOOD, rec(rollupRole="total", amount=20000000.0)])
        self.assertEqual(findings[0]["shape"], "total_beside_its_lines")

    def test_the_same_role_recorded_twice_is_flagged(self):
        # the shape that actually happens when a figure is re-extracted
        twice = rec(sourceUrl="https://www.gsa.gov/revised-cj.pdf", documentSha256="c" * 64)
        findings = fe.double_counted([GOOD, twice])
        self.assertEqual(findings[0]["shape"], "same_role_recorded_twice")

    def test_one_record_is_not_double_counted(self):
        self.assertEqual(fe.double_counted([GOOD]), [])

    def test_a_total_for_a_different_period_is_not_double_counted(self):
        self.assertEqual(fe.double_counted([GOOD, rec(rollupRole="total", fiscalYear=2025)]), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class CeilingIsTheCallersTestCase(unittest.TestCase):
    """A record must not be able to grant itself an exemption."""

    def test_a_record_cannot_raise_its_own_ceiling(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                rec(units="billions_usd", normalizedMultiplier=1_000_000_000,
                    unitsEvidence="(Dollars in Billions)", amount=10248000000000.0,
                    amountCeiling=1e30),
                ORG,
            )

    def test_the_caller_may_lower_it(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(GOOD, ORG, amount_ceiling=1000.0)
