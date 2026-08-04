from __future__ import annotations

import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from data_pipeline.crawler import lobbying, official_directory, usaspending, wikidata


class WikidataCrawlerTests(unittest.TestCase):
    def setUp(self) -> None:
        wikidata._ROW_CACHE.clear()

    def tearDown(self) -> None:
        wikidata._ROW_CACHE.clear()

    def test_extract_label_returns_empty_for_missing_binding(self):
        self.assertEqual(wikidata.extract_label({}, "parentLabel"), "")
        self.assertEqual(
            wikidata.extract_label({"parentLabel": {"value": "   "}}, "parentLabel"), ""
        )
        self.assertEqual(
            wikidata.extract_label(
                {"parentLabel": {"value": "Department of Energy"}}, "parentLabel"
            ),
            "Department of Energy",
        )

    def test_parentless_agency_creates_no_phantom_parent(self):
        crawler = wikidata.WikidataCrawler(request_delay=0.0)
        crawler.fetch_all_rows = lambda **kwargs: (
            [
                {"agencyLabel": {"value": "Lone Agency"}},
                {
                    "agencyLabel": {"value": "Child Agency"},
                    "parentLabel": {"value": "Department of Energy"},
                },
            ],
            [],
            [],
        )
        nodes, edges = crawler.build_records()
        names = [node["name"] for node in nodes]
        self.assertNotIn("Unnamed Node", names)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["target"], "department-of-energy")

    def test_queries_are_us_filtered(self):
        for query in (
            wikidata.AGENCY_HIERARCHY_QUERY,
            wikidata.SUBUNIT_QUERY,
            wikidata.OFFICE_HOLDER_QUERY,
        ):
            self.assertIn("wd:Q30", query)

    def test_discovery_records_use_country_binding(self):
        crawler = wikidata.WikidataCrawler(request_delay=0.0)
        crawler.fetch_all_rows = lambda **kwargs: (
            [
                {
                    "agencyLabel": {"value": "Us Agency"},
                    "countryLabel": {"value": "United States"},
                },
                {"agencyLabel": {"value": "Mystery Agency"}},
            ],
            [],
            [],
        )
        records = crawler.build_discovery_records()
        self.assertEqual(records[0]["countryLabel"], "United States")
        self.assertEqual(records[1]["countryLabel"], "")
        self.assertEqual(records[0]["parentName"], "")

    def test_sparql_failure_degrades_gracefully(self):
        crawler = wikidata.WikidataCrawler(request_delay=0.0)
        with mock.patch.object(wikidata, "run_sparql", side_effect=URLError("down")):
            self.assertEqual(
                crawler.fetch_bindings_safe(wikidata.AGENCY_HIERARCHY_QUERY, limit=5), []
            )

    def test_rows_fetched_once_for_both_record_shapes(self):
        payload = {
            "results": {"bindings": [{"agencyLabel": {"value": "Cached Agency"}}]}
        }
        with mock.patch.object(
            wikidata, "run_sparql", return_value=payload
        ) as mocked_sparql:
            first = wikidata.WikidataCrawler(request_delay=0.0)
            first.build_records(hierarchy_limit=5, office_holder_limit=5, subunit_limit=5)
            second = wikidata.WikidataCrawler(request_delay=0.0)
            second.build_discovery_records(
                hierarchy_limit=5, office_holder_limit=5, subunit_limit=5
            )
        self.assertEqual(mocked_sparql.call_count, 3)


class USASpendingCrawlerTests(unittest.TestCase):
    def test_award_request_shape(self):
        captured = {}

        def fake_request_json(url, *, payload=None, timeout=30):
            captured["payload"] = payload
            return {"results": []}

        crawler = usaspending.USASpendingCrawler(request_delay=0.0)
        with mock.patch.object(usaspending, "request_json", fake_request_json):
            crawler.fetch_spending_by_award(
                {
                    "agency_name": "Department of the Treasury",
                    "agency_id": 456,
                    "toptier_code": "020",
                },
                limit=5,
                fiscal_year=2025,
            )

        filters = captured["payload"]["filters"]
        self.assertEqual(filters["award_type_codes"], ["A", "B", "C", "D"])
        self.assertEqual(
            filters["agencies"],
            [{"type": "awarding", "tier": "toptier", "name": "Department of the Treasury"}],
        )
        self.assertNotIn("recipient_name", captured["payload"]["fields"])

    def test_agency_without_name_skips_award_search(self):
        crawler = usaspending.USASpendingCrawler(request_delay=0.0)
        with mock.patch.object(
            usaspending, "request_json", side_effect=AssertionError("should not be called")
        ):
            self.assertEqual(crawler.fetch_spending_by_award({}, limit=5), [])

    def test_build_records_uses_real_fields_and_skips_unnamed(self):
        crawler = usaspending.USASpendingCrawler(request_delay=0.0)
        crawler.fetch_top_tier_agencies = lambda *, limit=25: [
            {
                "agency_name": "Department of the Treasury",
                "obligated_amount": 1000.5,
                "budget_authority_amount": 2000.5,
            },
            {"agency_name": None},
        ]
        crawler.fetch_spending_by_award = lambda agency, **kwargs: [
            {
                "Recipient Name": "Acme Corp",
                "Award Amount": None,
                "generated_internal_id": "CONT_AWD_XYZ",
            },
            {"Recipient Name": "", "Award Amount": 10},
        ]

        nodes, edges = crawler.build_records(limit_agencies=2)

        names = [node["name"] for node in nodes]
        self.assertNotIn("Unnamed Node", names)
        agency_node = nodes[0]
        self.assertEqual(agency_node["budget"], "1000.5")
        contractor_nodes = [node for node in nodes if node["type"] == "Corporation"]
        self.assertEqual(len(contractor_nodes), 1)
        # The award identifier must never be presented as a dollar amount.
        self.assertNotIn("CONT_AWD_XYZ", contractor_nodes[0]["desc"])
        self.assertEqual(len(edges), 1)

    def test_toptier_failure_yields_empty_run(self):
        crawler = usaspending.USASpendingCrawler(request_delay=0.0)

        def boom(*, limit=25):
            raise HTTPError("https://api.usaspending.gov", 500, "boom", None, None)

        crawler.fetch_top_tier_agencies = boom
        nodes, edges = crawler.build_records(limit_agencies=2)
        self.assertEqual(nodes, [])
        self.assertEqual(edges, [])


class LobbyingCrawlerTests(unittest.TestCase):
    def test_activity_nested_entities_produce_edges(self):
        crawler = lobbying.LobbyingCrawler(request_delay=0.0)
        crawler.fetch_filings = lambda **kwargs: [
            {
                "client": {"name": "ACME CORP"},
                "lobbying_activities": [
                    {
                        "description": "Defense appropriations.",
                        "government_entities": [
                            {"id": 2, "name": "HOUSE OF REPRESENTATIVES"}
                        ],
                    },
                    {"description": None, "government_entities": []},
                ],
            }
        ]

        nodes, edges = crawler.build_records(year=2024)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["type"], "lobbies")
        agency_nodes = [node for node in nodes if node["type"] == "Agency"]
        self.assertEqual(len(agency_nodes), 1)
        self.assertIn("Filing issue", agency_nodes[0]["desc"])

    def test_missing_names_never_become_unnamed_nodes(self):
        crawler = lobbying.LobbyingCrawler(request_delay=0.0)
        crawler.fetch_filings = lambda **kwargs: [
            {"client": None, "lobbying_activities": []},
            {
                "client": {"name": "Real Client"},
                "lobbying_activities": [
                    {
                        "description": "Issue.",
                        "government_entities": [{"id": 5, "name": None}],
                    }
                ],
            },
        ]

        nodes, edges = crawler.build_records(year=2024)

        names = [node["name"] for node in nodes]
        self.assertNotIn("Unnamed Node", names)
        self.assertEqual(names, ["Real Client"])
        self.assertEqual(edges, [])

    def test_partial_pagination_keeps_collected_pages(self):
        def fake_request_json(url, *, params=None, timeout=30):
            if params["page"] == 1:
                return {"results": [{"filing_uuid": "abc"}]}
            raise HTTPError(url, 500, "server error", None, None)

        crawler = lobbying.LobbyingCrawler(request_delay=0.0)
        with mock.patch.object(lobbying, "request_json", fake_request_json), mock.patch(
            "data_pipeline.crawler.lobbying.time"
        ):
            filings = crawler.fetch_filings(year=2024, pages=3, page_size=5)

        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0]["filing_uuid"], "abc")

    def test_rate_limit_backs_off_once_then_retries(self):
        calls = []

        def fake_request_json(url, *, params=None, timeout=30):
            calls.append(params["page"])
            if len(calls) == 1:
                raise HTTPError(url, 429, "rate limited", None, None)
            return {"results": [{"filing_uuid": f"page-{params['page']}"}]}

        crawler = lobbying.LobbyingCrawler(request_delay=0.0)
        with mock.patch.object(lobbying, "request_json", fake_request_json), mock.patch(
            "data_pipeline.crawler.lobbying.time"
        ) as mocked_time:
            filings = crawler.fetch_filings(year=2024, pages=2, page_size=5)

        self.assertEqual(len(filings), 2)
        self.assertEqual(calls, [1, 1, 2])
        self.assertTrue(mocked_time.sleep.called)


class OfficialDirectoryTests(unittest.TestCase):
    SAMPLE_HTML = """
    <html>
    <head>
      <title>Office of Something | Energy.gov</title>
      <style>.hero { text-align: center; }</style>
      <script>var label = "Office of Widgets and Service Center";</script>
    </head>
    <body>
      <nav><a href="#">Office of Public Affairs</a></nav>
      <main>
        <h3>Office of Science</h3>
        <p>Bureau of Land Management</p>
        <div>Office of Environmental Management</div>
        <span>Learn more about our mission</span>
      </main>
      <footer>Office of Inspector General</footer>
    </body>
    </html>
    """

    def test_script_style_nav_fragments_are_skipped(self):
        records = official_directory.extract_directory_records(
            self.SAMPLE_HTML,
            agency_name="Department of Energy",
            directory_url="https://www.energy.gov/organization-chart",
        )
        names = [record["officeName"] for record in records]
        self.assertIn("Office of Science", names)
        self.assertIn("Office of Environmental Management", names)
        self.assertIn("Bureau of Land Management", names)
        self.assertNotIn("Office of Public Affairs", names)  # inside <nav>
        self.assertNotIn("Office of Inspector General", names)  # inside <footer>
        for name in names:
            self.assertNotIn("text-align", name.lower())
            self.assertNotIn("Widgets", name)

    def test_org_unit_pattern_rejects_loose_keyword_matches(self):
        self.assertFalse(official_directory.looks_like_org_unit("text-align: center"))
        self.assertFalse(
            official_directory.looks_like_org_unit("Customer support and service center")
        )
        self.assertTrue(official_directory.looks_like_org_unit("Office of Science"))
        self.assertTrue(
            official_directory.looks_like_org_unit("Division of Energy Research")
        )


if __name__ == "__main__":
    unittest.main()
