"""Producer contracts the rest of the pipeline silently depends on.

The Treasury crawler is the sole producer of the cost anchor and had no test;
the Federal Register unit pattern emitted sentence fragments as organisational
units; the Wikidata crawler cached partial results and returned every
historical office holder as a current manager; one knob meant "fiscal year" to
one source and "calendar year" to another.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from unittest import mock
from urllib.error import URLError

from data_pipeline.crawler import federal_register, treasury_outlays, usaspending, wikidata
from data_pipeline.exporter.build_graph import extract_budget_summary
from data_pipeline.run_pipeline import federal_fiscal_year, usable_budget_total


def _mts_rows():
    def row(desc, amount, level=1, order=0):
        return {
            "classification_desc": desc,
            "current_fytd_net_outly_amt": amount,
            "record_fiscal_year": "2026",
            "record_date": "2026-06-30",
            "sequence_level_nbr": str(level),
            "print_order_nbr": str(order),
        }

    return [
        row("Legislative Branch", "5000000000", 1, 1),
        row("Department of the Treasury", None, 1, 10),
        row("Internal Revenue Service", "12000000000", 2, 11),
        row("Total--Department of the Treasury", "300000000000", 1, 13),
        row("Undistributed Offsetting Receipts", "-50000000000", 1, 90),
        row("Total On-Budget", "4000000000000", 1, 98),
        row("Total Outlays", "5517917965556.91", 1, 99),
        row("Total Surplus (+) or Deficit (-)", "-1300000000000", 1, 100),
    ]


class TreasuryOutlaysCrawlerTests(unittest.TestCase):
    def test_parse_produces_the_anchor_the_exporter_and_guard_read(self) -> None:
        rows, summary = treasury_outlays.parse_outlay_rows(_mts_rows())
        self.assertIsNotNone(summary)
        self.assertEqual(summary["government_total_outlay_amount"], 5517917965556.91)
        self.assertEqual(summary["amount_kind"], "fytd_net_outlays")
        self.assertEqual(summary["record_date"], "2026-06-30")
        self.assertEqual(summary["label"], "FYTD net outlays through 2026-06-30")
        # The same dict must satisfy both consumers.
        self.assertEqual(extract_budget_summary([{"budgetSummary": summary}]), summary)
        self.assertEqual(usable_budget_total({"budgetSummary": summary}), 5517917965556.91)

    def test_parse_emits_agency_lines_and_skips_totals(self) -> None:
        rows, _ = treasury_outlays.parse_outlay_rows(_mts_rows())
        names = [(row["originalName"], row["rollup_total_amount"]) for row in rows]
        self.assertIn(("Legislative Branch", 5e9), names)
        self.assertIn(("Total--Department of the Treasury", 300e9), names)
        self.assertIn(("Undistributed Offsetting Receipts", -50e9), names)
        # Header line with no amount, and the summary totals, are not agency lines.
        self.assertNotIn("Total On-Budget", [n for n, _ in names])
        self.assertNotIn("Total Surplus (+) or Deficit (-)", [n for n, _ in names])
        self.assertTrue(all("Total Outlays" not in n for n, _ in names))
        treasury = next(row for row in rows if row["originalName"].startswith("Total--"))
        self.assertEqual(treasury["name"], "Department of the Treasury")
        self.assertEqual(treasury["sourceTypes"], ["treasury_outlays"])
        self.assertEqual(treasury["budget_as_of"], "2026-06-30")

    def test_a_relabelled_grand_total_is_missing_not_an_agency(self) -> None:
        for label in ("Total Outlays:", "Total outlays", "Total--Outlays"):
            with self.subTest(label=label):
                rows = [dict(r, classification_desc=label) if r["classification_desc"] == "Total Outlays" else r for r in _mts_rows()]
                parsed, summary = treasury_outlays.parse_outlay_rows(rows)
                self.assertIsNone(summary)
                self.assertFalse(any(abs(row["rollup_total_amount"]) > 1e12 for row in parsed))

    def test_crawl_returns_the_latest_statement_and_follows_pagination(self) -> None:
        calls = []

        def fake_request_json(url, *, params=None, timeout=30):
            calls.append(dict(params))
            if params.get("sort") == "-record_date":
                self.assertNotIn("filter", params)
                return {"data": [{"record_date": "2026-06-30"}]}
            page = params["page[number]"]
            if page == 1:
                return {"data": _mts_rows()[:4], "links": {"next": "yes"}}
            return {"data": _mts_rows()[4:], "links": {}}

        with mock.patch.object(treasury_outlays, "request_json", fake_request_json):
            payload = treasury_outlays.crawl(timeout=7)
        self.assertEqual(payload["budgetSummary"]["government_total_outlay_amount"], 5517917965556.91)
        self.assertEqual(len(payload["outlayRows"]), 4)
        self.assertEqual([c["page[number]"] for c in calls if "page[number]" in c], [1, 2])
        self.assertTrue(all(c.get("filter", "").startswith("record_date:eq:") for c in calls if "page[number]" in c))

    def test_crawl_with_no_statement_returns_no_anchor(self) -> None:
        with mock.patch.object(treasury_outlays, "request_json", return_value={"data": []}):
            payload = treasury_outlays.crawl()
        self.assertIsNone(payload["budgetSummary"])
        self.assertEqual(payload["outlayRows"], [])


class FiscalYearTests(unittest.TestCase):
    def test_federal_fiscal_year_rolls_over_in_october(self) -> None:
        self.assertEqual(federal_fiscal_year(datetime(2026, 9, 30, tzinfo=timezone.utc)), 2026)
        self.assertEqual(federal_fiscal_year(datetime(2026, 10, 1, tzinfo=timezone.utc)), 2027)
        self.assertEqual(usaspending.federal_fiscal_year(date(2026, 12, 15)), 2027)
        self.assertEqual(usaspending.federal_fiscal_year(date(2027, 1, 2)), 2027)

    def test_usaspending_window_is_october_to_september(self) -> None:
        captured = {}

        def fake_request_json(url, *, payload=None, timeout=30):
            captured["payload"] = payload
            captured["timeout"] = timeout
            return {"results": []}

        crawler = usaspending.USASpendingCrawler(request_delay=0.0, timeout=11)
        with mock.patch.object(usaspending, "request_json", fake_request_json):
            crawler.fetch_spending_by_award({"agency_name": "Department of the Treasury"}, limit=5, fiscal_year=2027)
        period = captured["payload"]["filters"]["time_period"][0]
        self.assertEqual(period, {"start_date": "2026-10-01", "end_date": "2027-09-30"})
        self.assertEqual(captured["timeout"], 11)


class FederalRegisterUnitTests(unittest.TestCase):
    def test_unit_names_are_bounded_titles_not_sentences(self) -> None:
        text = (
            "Agency Information Collection Activities; Submission to the Office of Management and Budget "
            "for Review and Approval. The Bureau of Land Management announces a meeting."
        )
        units = federal_register.extract_units(text)
        self.assertIn("Office of Management and Budget", units)
        self.assertNotIn("Office of Management and Budget for Review and Approval", units)
        self.assertTrue(all(len(unit) <= federal_register.MAX_UNIT_NAME_LENGTH for unit in units))
        self.assertTrue(all("announces" not in unit for unit in units))

    def test_abstract_fragments_stop_at_lowercase_prose(self) -> None:
        text = (
            "submitted to the Office of Management and Budget (OMB) for review and clearance in accordance "
            "with the Paperwork Reduction Act of 1995, on or after the date of publication of this notice"
        )
        units = federal_register.extract_units(text)
        self.assertEqual(units, ["Office of Management and Budget (OMB)"])

    def test_real_unit_names_survive(self) -> None:
        self.assertEqual(federal_register.extract_units("Office of the Secretary"), ["Office of the Secretary"])
        self.assertEqual(
            federal_register.extract_units("Bureau of Ocean Energy Management and Office of Natural Resources Revenue"),
            ["Bureau of Ocean Energy Management", "Office of Natural Resources Revenue"],
        )

    def test_fetch_failure_is_logged_not_swallowed(self) -> None:
        with mock.patch.object(federal_register, "request_json", side_effect=URLError("503")):
            with mock.patch("sys.stderr") as stderr:
                records = federal_register.crawl(pages=1, per_page=5, timeout=3)
        self.assertEqual(records, [])
        written = "".join(str(call.args[0]) for call in stderr.write.call_args_list)
        self.assertIn("warning: federal register fetch failed", written)


class WikidataContractTests(unittest.TestCase):
    def setUp(self) -> None:
        wikidata._ROW_CACHE.clear()

    def tearDown(self) -> None:
        wikidata._ROW_CACHE.clear()

    def test_queries_are_ordered_so_a_limit_is_a_stable_slice(self) -> None:
        for query in (wikidata.AGENCY_HIERARCHY_QUERY, wikidata.SUBUNIT_QUERY, wikidata.OFFICE_HOLDER_QUERY):
            self.assertIn("ORDER BY", query)
            self.assertLess(query.index("ORDER BY"), query.index("LIMIT"))

    def test_office_holders_are_current_ones(self) -> None:
        self.assertIn("FILTER NOT EXISTS {{ ?statement pq:P582 ?endTime . }}", wikidata.OFFICE_HOLDER_QUERY)
        self.assertIn("wikibase:DeprecatedRank", wikidata.OFFICE_HOLDER_QUERY)

    def test_a_partial_fetch_is_not_cached_and_is_reported(self) -> None:
        def flaky(query, *, timeout=45):
            if "P361" in query:
                raise URLError("timeout")
            return {"results": {"bindings": [{"agency": {"value": "http://www.wikidata.org/entity/Q1"}, "agencyLabel": {"value": "Agency"}}]}}

        with mock.patch.object(wikidata, "run_sparql", side_effect=flaky) as run:
            first = wikidata.WikidataCrawler(request_delay=0.0)
            with mock.patch("sys.stderr"):
                rows = first.fetch_all_rows(hierarchy_limit=5, office_holder_limit=5, subunit_limit=5)
            self.assertEqual(first.partial_queries, ["subunit"])
            self.assertEqual(len(rows[1]), 0)
            self.assertEqual(wikidata._ROW_CACHE, {})
            second = wikidata.WikidataCrawler(request_delay=0.0)
            with mock.patch("sys.stderr"):
                second.fetch_all_rows(hierarchy_limit=5, office_holder_limit=5, subunit_limit=5)
            # Retried, not served from a cache of the broken triple.
            self.assertEqual(run.call_count, 6)

    def test_crawl_payload_carries_the_partial_marker(self) -> None:
        def flaky(query, *, timeout=45):
            if "P361" in query:
                raise URLError("timeout")
            return {"results": {"bindings": []}}

        with mock.patch.object(wikidata, "run_sparql", side_effect=flaky):
            with mock.patch("sys.stderr"):
                payload = wikidata.crawl(hierarchy_limit=5, office_holder_limit=5, subunit_limit=5, timeout=9)
        self.assertEqual(payload.get("partial"), ["subunit"])

    def test_timeout_reaches_sparql(self) -> None:
        seen = {}

        def capture(query, *, timeout=45):
            seen["timeout"] = timeout
            return {"results": {"bindings": []}}

        with mock.patch.object(wikidata, "run_sparql", side_effect=capture):
            wikidata.WikidataCrawler(request_delay=0.0, timeout=99).fetch_bindings(wikidata.AGENCY_HIERARCHY_QUERY, limit=1)
        self.assertEqual(seen["timeout"], 99)


if __name__ == "__main__":
    unittest.main()
