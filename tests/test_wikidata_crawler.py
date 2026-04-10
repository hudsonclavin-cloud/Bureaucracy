from __future__ import annotations

import unittest

from data_pipeline.crawler.wikidata import WikidataCrawler


def make_binding(value: str) -> dict[str, dict[str, str]]:
    return {"value": value}


class WikidataCrawlerTests(unittest.TestCase):
    def test_build_records_skips_blank_labels_instead_of_emitting_unnamed_nodes(self) -> None:
        crawler = WikidataCrawler(request_delay=0.0)
        prefetched = (
            [
                {
                    "agencyLabel": make_binding(""),
                    "parentLabel": make_binding("Department of Energy"),
                    "agency": make_binding("https://www.wikidata.org/entity/Q100"),
                    "parent": make_binding("https://www.wikidata.org/entity/Q200"),
                    "officialWebsite": make_binding("https://www.energy.gov"),
                },
                {
                    "agencyLabel": make_binding("Agency Alpha"),
                    "parentLabel": make_binding(""),
                    "agency": make_binding("https://www.wikidata.org/entity/Q101"),
                    "parent": make_binding("https://www.wikidata.org/entity/Q200"),
                    "officialWebsite": make_binding("https://www.agency.gov"),
                },
            ],
            [
                {
                    "officeLabel": make_binding("Office Beta"),
                    "parentLabel": make_binding(""),
                    "office": make_binding("https://www.wikidata.org/entity/Q300"),
                    "parent": make_binding("https://www.wikidata.org/entity/Q200"),
                }
            ],
            [
                {
                    "agencyLabel": make_binding(""),
                    "positionLabel": make_binding("Director"),
                    "position": make_binding("https://www.wikidata.org/entity/Q400"),
                }
            ],
        )

        nodes, edges = crawler.build_records(_prefetched=prefetched)

        self.assertEqual([node["name"] for node in nodes], ["Agency Alpha"])
        self.assertEqual(edges, [])
        self.assertTrue(all(node["name"] != "Unnamed Node" for node in nodes))

    def test_build_discovery_records_keeps_country_label_only_for_explicit_agency_rows(self) -> None:
        crawler = WikidataCrawler(request_delay=0.0)
        prefetched = (
            [
                {
                    "agencyLabel": make_binding("Agency Alpha"),
                    "parentLabel": make_binding("Department of Energy"),
                    "agency": make_binding("https://www.wikidata.org/entity/Q101"),
                    "parent": make_binding("https://www.wikidata.org/entity/Q200"),
                    "officialWebsite": make_binding("https://www.agency.gov"),
                }
            ],
            [
                {
                    "officeLabel": make_binding("Office Beta"),
                    "parentLabel": make_binding(""),
                    "office": make_binding("https://www.wikidata.org/entity/Q300"),
                    "parent": make_binding("https://www.wikidata.org/entity/Q200"),
                }
            ],
            [
                {
                    "agencyLabel": make_binding(""),
                    "positionLabel": make_binding("Director"),
                    "position": make_binding("https://www.wikidata.org/entity/Q400"),
                }
            ],
        )

        records = crawler.build_discovery_records(_prefetched=prefetched)
        records_by_label = {record["label"]: record for record in records}

        self.assertEqual(records_by_label["Agency Alpha"].get("countryLabel"), "United States")
        self.assertNotIn("countryLabel", records_by_label["Office Beta"])
        self.assertNotIn("countryLabel", records_by_label["Director"])


if __name__ == "__main__":
    unittest.main()
