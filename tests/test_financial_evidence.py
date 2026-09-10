"""The financial-evidence validator, pinned in both directions.

Every rule here exists because getting it wrong publishes a false number, so
each is tested twice: a good record passes, and the specific defect the rule
guards against is refused. That convention is not decorative — this repository
has shipped validators that "ran happily and were wrong" three times in one
week, and every one of them passed a one-directional test.

The units rule is the one worth reading. A Congressional Justification prints
`10,248` under a heading that says dollars in thousands. Read as dollars it is
wrong by a factor of a thousand and looks completely plausible on the page.
"""

from __future__ import annotations

import unittest

from data_pipeline.verification import financial_evidence as fe


ORG = {"id": "gsa-cbca", "name": "Civilian Board of Contract Appeals", "type": "Board"}
POST = {"id": "gsa-administrator", "name": "Administrator", "type": "Position"}

GOOD = {
    "nodeId": "gsa-cbca",
    "amount": 10248000.0,
    "amountRaw": "10,248",
    "units": "thousands_usd",
    "normalizedMultiplier": 1000,
    "costBasis": "budget_request",
    "fiscalYear": 2026,
    "periodCoverage": "full fiscal year",
    "amountScope": "Civilian Board of Contract Appeals",
    "scopeMatch": "exact",
    "rollupRole": "line",
    "sourceType": "congressional_justification",
    "sourceUrl": "https://www.gsa.gov/cdnstatic/fy2026-cj.pdf",
    "documentSha256": "a" * 64,
    "retrievedAt": "2026-09-01T00:00:00Z",
    "locator": {"pdfPage": 6, "table": "Summary of Appropriations", "row": "Civilian Board of Contract Appeals"},
    "quote": "Civilian Board of Contract Appeals .......... 10,248",
    "costVerificationStatus": "verified",
}


def without(**overrides):
    record = dict(GOOD)
    record.update(overrides)
    return record


class ValidRecordTestCase(unittest.TestCase):
    def test_a_complete_record_passes(self):
        out = fe.validate_record(GOOD, ORG)
        self.assertEqual(out["amount"], 10248000.0)
        self.assertEqual(out["costBasis"], "budget_request")

    def test_an_exact_scope_is_verified_and_anything_else_is_partial(self):
        self.assertEqual(fe.classify(GOOD), "verified")
        for scope in ("parent", "child", "broader_account", "proxy", "ambiguous"):
            self.assertEqual(fe.classify(without(scopeMatch=scope)), "partial", scope)


class UnitsTestCase(unittest.TestCase):
    """The 1000x error, from every direction it can arrive."""

    def test_amount_must_equal_the_printed_figure_times_the_multiplier(self):
        # the classic: thousands read as dollars
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(amount=10248.0), ORG)

    def test_multiplier_must_match_the_declared_units(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(normalizedMultiplier=1), ORG)

    def test_a_missing_multiplier_is_refused_rather_than_assumed(self):
        record = dict(GOOD)
        del record["normalizedMultiplier"]
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, ORG)

    def test_units_outside_the_vocabulary_are_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(units="dollars"), ORG)

    def test_accounting_negatives_are_read_as_negative(self):
        self.assertEqual(fe.parse_amount_text("(1,234)"), -1234.0)
        self.assertEqual(fe.parse_amount_text("1,234"), 1234.0)

    def test_prose_is_not_read_as_a_figure(self):
        for text in ("about 10,248", "10,248 (est.)", "", "n/a", "—"):
            with self.assertRaises(fe.Rejected):
                fe.parse_amount_text(text)

    def test_a_negative_record_is_allowed_when_the_arithmetic_agrees(self):
        out = fe.validate_record(without(amountRaw="(10,248)", amount=-10248000.0), ORG)
        self.assertEqual(out["amount"], -10248000.0)

    def test_zero_is_never_published(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(amountRaw="0", amount=0.0), ORG)


class BasisAndUnitKindTestCase(unittest.TestCase):
    def test_a_headcount_must_not_be_denominated_in_dollars(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                without(costBasis="full_time_equivalents", units="thousands_usd"), ORG
            )

    def test_a_headcount_in_counts_passes(self):
        out = fe.validate_record(
            without(
                costBasis="full_time_equivalents",
                units="count",
                normalizedMultiplier=1,
                amountRaw="42",
                amount=42.0,
            ),
            ORG,
        )
        self.assertEqual(out["amount"], 42.0)

    def test_money_must_not_be_denominated_in_counts(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(units="count", normalizedMultiplier=1), ORG)

    def test_a_basis_outside_the_vocabulary_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(costBasis="cost"), ORG)


class NodeKindTestCase(unittest.TestCase):
    """The mirror of the release gate's rule that a measured cost sits only on
    an organisation."""

    def test_a_rate_of_pay_cannot_sit_on_an_organisation(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(costBasis="basic_pay"), ORG)

    def test_an_organisations_money_cannot_sit_on_a_position(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(nodeId="gsa-administrator"), POST)

    def test_a_rate_of_pay_on_a_position_passes(self):
        out = fe.validate_record(
            without(
                nodeId="gsa-administrator",
                costBasis="basic_pay",
                sourceType="opm_pay_table",
                amountScope="Level II",
                amountRaw="225,700",
                units="usd",
                normalizedMultiplier=1,
                amount=225700.0,
                sourceUrl="https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/EX.aspx",
                quote="Level II .......... $225,700",
            ),
            POST,
        )
        self.assertEqual(out["amount"], 225700.0)


class PeriodTestCase(unittest.TestCase):
    def test_a_fiscal_year_alone_is_not_enough(self):
        record = dict(GOOD)
        del record["periodCoverage"]
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, ORG)

    def test_fiscal_year_must_be_an_integer_and_plausible(self):
        for bad in ("2026", 1776, 2999, None, True):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(without(fiscalYear=bad), ORG)


class ProvenanceTestCase(unittest.TestCase):
    def test_a_non_government_host_is_refused(self):
        # OpenOMB is a real, useful project and not a government source.
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(sourceUrl="https://openomb.org/apportionment/123"), ORG)

    def test_a_mil_host_is_accepted(self):
        out = fe.validate_record(without(sourceUrl="https://www.dla.mil/budget.pdf"), ORG)
        self.assertTrue(out["sourceUrl"].endswith("budget.pdf"))

    def test_a_digest_that_is_not_a_sha256_is_refused(self):
        for bad in ("", "deadbeef", "z" * 64, None):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(without(documentSha256=bad), ORG)

    def test_a_retrieval_date_in_the_future_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(retrievedAt="2099-01-01T00:00:00Z"), ORG)

    def test_a_locator_that_points_nowhere_is_refused(self):
        for bad in ({}, {"pdfPage": ""}, None, "page 6"):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(without(locator=bad), ORG)

    def test_a_quote_is_required(self):
        for bad in ("", "10,248", None):
            with self.assertRaises(fe.Rejected):
                fe.validate_record(without(quote=bad), ORG)

    def test_the_scope_the_source_named_is_required(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(without(amountScope=""), ORG)


class AbsenceTestCase(unittest.TestCase):
    """"We searched and found nothing" is an answer, and a different one from
    "nobody looked"."""

    def test_an_absence_record_passes_without_a_figure(self):
        record = {
            "nodeId": "gsa-cbca",
            "costVerificationStatus": "no_direct_amount_found",
            "searchNote": "FY2026 GSA CJ read in full; no line names this board.",
        }
        out = fe.validate_record(record, ORG)
        self.assertEqual(fe.classify(out), "no_direct_amount_found")

    def test_an_absence_record_carrying_a_figure_is_refused(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                {
                    "nodeId": "gsa-cbca",
                    "costVerificationStatus": "no_direct_amount_found",
                    "searchNote": "looked",
                    "amount": 1.0,
                },
                ORG,
            )

    def test_an_absence_record_must_say_what_was_searched(self):
        with self.assertRaises(fe.Rejected):
            fe.validate_record(
                {"nodeId": "gsa-cbca", "costVerificationStatus": "no_direct_amount_found"}, ORG
            )


class ComparabilityTestCase(unittest.TestCase):
    """The rule the module exists for."""

    def test_the_same_basis_period_and_unit_kind_are_comparable(self):
        self.assertTrue(fe.comparable(GOOD, without(amount=10249000.0, amountRaw="10,249")).comparable)

    def test_a_request_and_an_outlay_are_not_comparable(self):
        other = without(costBasis="net_outlays")
        self.assertFalse(fe.comparable(GOOD, other).comparable)
        self.assertIn("basis", fe.comparable(GOOD, other).reason)

    def test_different_fiscal_years_are_not_comparable(self):
        self.assertFalse(fe.comparable(GOOD, without(fiscalYear=2025)).comparable)

    def test_a_year_to_date_figure_is_not_a_full_year_figure(self):
        self.assertFalse(fe.comparable(GOOD, without(periodCoverage="year to date")).comparable)

    def test_a_count_and_a_sum_of_money_are_not_comparable(self):
        fte = without(costBasis="full_time_equivalents", units="count")
        self.assertFalse(fe.comparable(without(costBasis="full_time_equivalents"), fte).comparable)


class ConflictTestCase(unittest.TestCase):
    def test_two_comparable_figures_that_disagree_are_a_conflict(self):
        other = without(
            amount=12000000.0, amountRaw="12,000", sourceUrl="https://www.gsa.gov/other.pdf"
        )
        conflicts = fe.detect_conflicts([GOOD, other])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["nodeId"], "gsa-cbca")

    def test_rounding_is_not_a_conflict(self):
        other = without(amount=10248001.0, amountRaw="10,248.001")
        self.assertEqual(fe.detect_conflicts([GOOD, other]), [])

    def test_figures_on_different_bases_are_not_a_conflict(self):
        other = without(costBasis="net_outlays", amount=900000.0, amountRaw="900")
        self.assertEqual(fe.detect_conflicts([GOOD, other]), [])

    def test_figures_for_different_nodes_are_not_a_conflict(self):
        other = without(nodeId="somewhere-else", amount=999.0, amountRaw="1")
        self.assertEqual(fe.detect_conflicts([GOOD, other]), [])


class DoubleCountingTestCase(unittest.TestCase):
    def test_a_total_stored_beside_its_lines_is_flagged(self):
        total = without(rollupRole="total", amount=20000000.0, amountRaw="20,000")
        findings = fe.double_counted([GOOD, total])
        self.assertEqual(len(findings), 1)
        self.assertEqual(sorted(findings[0]["roles"]), ["line", "total"])

    def test_lines_alone_are_not_double_counted(self):
        other = without(amount=5000000.0, amountRaw="5,000")
        self.assertEqual(fe.double_counted([GOOD, other]), [])

    def test_a_total_for_a_different_period_is_not_double_counted(self):
        total = without(rollupRole="total", fiscalYear=2025)
        self.assertEqual(fe.double_counted([GOOD, total]), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
