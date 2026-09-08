"""Congress's committee pages as a source of candidate sites: one listed
name to one node or nothing, the link as printed or not at all."""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree, load_base_graph
from data_pipeline.verification.congress import committee_key
from data_pipeline.verification.congress_sites import (
    REJECT_HOST_NOT_GOV,
    REJECT_NOT_HTTPS,
    house_committee_key,
    listed_committee_key,
    load_congress_site_proposals,
    parse_house_committees,
    parse_senate_committees,
)

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "directories"
REAL_HOUSE = FIXTURES / "house_gov_committees.html"
REAL_SENATE = FIXTURES / "senate" / "senate_committees_page.html"
BASE_GRAPH = Path(__file__).resolve().parents[1] / "data" / "federal_gov_complete_1.json"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-house", "name": "United States House of Representatives", "type": "Chamber", "children": [
                {"id": "leg-house-committees", "name": "House Committees", "type": "Division", "children": [
                    {"id": "leg-house-cmte-judiciary", "name": "House Committee on Judiciary", "type": "Committee", "children": [
                        {"id": "leg-house-cmte-judiciary-chair", "name": "Chair, Judiciary", "type": "Position", "children": []},
                    ]},
                    {"id": "leg-house-cmte-permanent-select-committee-on-intelligence", "name": "House Committee on Permanent Select Committee on Intelligence", "type": "Committee", "children": []},
                    {"id": "leg-house-cmte-ways-means", "name": "House Committee on Ways & Means", "type": "Committee", "children": []},
                    {"id": "leg-house-cmte-oversight-accountability", "name": "House Committee on Oversight & Accountability", "type": "Committee", "children": []},
                ]},
            ]},
            {"id": "leg-senate", "name": "United States Senate", "type": "Chamber", "children": [
                {"id": "leg-senate-committees", "name": "Senate Committees", "type": "Division", "children": [
                    {"id": "leg-senate-cmte-judiciary", "name": "Senate Committee on Judiciary", "type": "Committee", "children": []},
                    {"id": "leg-senate-cmte-select-committee-on-ethics", "name": "Senate Committee on Select Committee on Ethics", "type": "Committee", "children": []},
                    {"id": "leg-senate-cmte-budget", "name": "Senate Committee on Budget", "type": "Committee", "children": []},
                    {"id": "leg-senate-cmte-finance", "name": "Senate Committee on Finance", "type": "Committee", "children": []},
                    {"id": "leg-senate-cmte-finance-dup", "name": "Committee on Finance", "type": "Committee", "children": []},
                ]},
            ]},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": []},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

# The shape of https://www.house.gov/committees as served on 2026-09-08: a nav
# link to the page itself outside the body field, then the Drupal body field
# holding a <section> of <ul> columns, one <li data-list-item-id> per committee.
HOUSE_HTML = """<!DOCTYPE html><html><head><title>Committees | house.gov</title></head><body>
<nav><ul><li><a href="/committees" data-drupal-link-system-path="node/4" class="is-active" aria-current="page">Committees</a></li></ul></nav>
<div class="field field--name-field-page-body field--type-text-long field--label-hidden field--item"><p>The House’s committees consider bills and issues and oversee agencies, programs, and activities within their jurisdictions.</p><section><div class="row"><div class="col-xs-16 col-sm-8"><ul><li data-list-item-id="e0b5e47dac6d3e586bf452f33fb6069d4"><a href="https://ethics.house.gov/">Ethics</a></li><li data-list-item-id="ef0310867901ec3e1c6e777ed74f3a660"><a href="https://judiciary.house.gov/">Judiciary</a></li></ul></div><div class="col-xs-16 col-sm-8"><ul><li data-list-item-id="ec1e5fb5c580c22325f5d5b8c3ac757c7"><a href="https://example.com/waysandmeans">Ways and Means</a></li><li data-list-item-id="e9b0637a3c09ac052610a0d2f181a77b9"><a href="https://intelligence.house.gov/">Permanent Select Committee on Intelligence</a></li></ul></div></div></section><p><br><a href="/committees/committees-no-longer-standing" data-entity-type="node">View Committees No Longer Standing from previous Congresses</a></p></div>
</body></html>"""

# The shape of https://www.senate.gov/committees/ as served the same day: one
# <table id="listOfCommittees">, the committee link first in each row with the
# page's odd target="&quot;blank&quot;" and an http:// href, the chair and
# ranking member next, then the member-list link and a <ul> of subcommittees.
SENATE_ROW = """<tr>
<td style="white-space: nowrap;"><a target="&quot;blank&quot;" href="{href}">{name}</a></td><td style="white-space: nowrap;"><a href="https://www.grassley.senate.gov">Grassley, Chuck (R-IA) </a></td><td style="white-space: nowrap;"><a href="https://www.durbin.senate.gov">Durbin, Richard J. (D-IL)</a></td><td style="white-space: nowrap;">22<a target="&quot;_blank&quot;" href="/general/committee_membership/committee_memberships_{code}.htm"> (Committee Member List)</a></td><td>
<ul>
<li>
<a target="&quot;blank&quot;" href="/general/committee_membership/committee_memberships_{code}.htm#{code}02">Subcommittee on the Constitution</a>
</li>
</ul>
</td>
</tr>
"""
SENATE_HTML = """<!DOCTYPE html><html><head><title>U.S. Senate: Committees</title></head><body>
<h1>Committees </h1>
<table width="100%" id="listOfCommittees" class="display compact" cellspacing="0">
<thead>
<tr align="left">
<th style="color:#4B4B4B" align="left;">Committee</th><th style="color:#4B4B4B" align="left">Chair</th><th style="color:#4B4B4B" align="left">Ranking Member</th><th style="color:#4B4B4B" align="left">Total Members</th><th>Subcommittees:</th>
</tr>
</thead>
<tbody>
""" + "".join(SENATE_ROW.format(href=h, name=n, code=c) for h, n, c in [
    ("http://www.judiciary.senate.gov/", "Judiciary", "SSJU"),
    ("https://www.ethics.senate.gov/", "Select Committee on Ethics", "SLET"),
    ("https://budget.example.org/", "Budget", "SSBU"),
    ("http://www.finance.senate.gov/", "Finance", "SSFI"),
    ("http://www.jec.senate.gov/", "Joint Economic Committee", "JSEC"),
]) + """</tbody>
</table><div class="contenttext"><h3>About the Committee System </h3><p><a href="/committees/committees_home.htm">COMMITTEES</a></p></div>
</body></html>"""


def write_pages(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    house = directory / "house_gov_committees.html"
    senate = directory / "senate_committees_page.html"
    house.write_text(HOUSE_HTML, encoding="utf-8")
    senate.write_text(SENATE_HTML, encoding="utf-8")
    for path, url, when in ((house, "https://www.house.gov/committees", "2026-09-08T19:19:17Z"),
                            (senate, "https://www.senate.gov/committees/", "2026-09-08T19:19:19Z")):
        path.with_name(path.name + ".meta.json").write_text(json.dumps({
            "fetched_at": when, "url": url, "final_url": url, "status": 200,
        }), encoding="utf-8")
    return house, senate


class KeyTests(unittest.TestCase):
    def test_the_house_s_artifacts_and_its_own_names_share_a_key(self) -> None:
        self.assertEqual(house_committee_key("House Committee on Permanent Select Committee on Intelligence"),
                         house_committee_key("Permanent Select Committee on Intelligence"))
        self.assertEqual(house_committee_key("House Committee on Ways & Means"), house_committee_key("Committee on Ways and Means"))
        self.assertEqual(house_committee_key("House Committee on Budget"), house_committee_key("Committee on the Budget"))
        # Only the chamber prefix is stripped: the committee's own "House" stays.
        self.assertEqual(house_committee_key("House Committee on House Administration"), "committee on house administration")
        # A renamed committee is a different key: no fuzzing.
        self.assertNotEqual(house_committee_key("House Committee on Oversight & Accountability"),
                            house_committee_key("Committee on Oversight and Government Reform"))
        self.assertNotEqual(house_committee_key("House Committee on Education & the Workforce"),
                            house_committee_key("Committee on Education and Workforce"))

    def test_a_bare_listed_name_is_the_committee_on_that_name(self) -> None:
        self.assertEqual(listed_committee_key("Judiciary", committee_key), committee_key("Senate Committee on Judiciary"))
        self.assertEqual(listed_committee_key("Veterans’ Affairs", house_committee_key), house_committee_key("House Committee on Veterans' Affairs"))
        self.assertEqual(listed_committee_key("House Administration", house_committee_key), house_committee_key("House Committee on House Administration"))
        self.assertEqual(listed_committee_key("Select Committee on Ethics", committee_key), committee_key("Senate Committee on Select Committee on Ethics"))
        self.assertEqual(listed_committee_key("Joint Economic Committee", committee_key), "joint economic committee")


class ParserTests(unittest.TestCase):
    def test_the_house_list_is_read_from_the_body_field_only(self) -> None:
        links = parse_house_committees(HOUSE_HTML)
        self.assertEqual([l["name"] for l in links], ["Ethics", "Judiciary", "Ways and Means", "Permanent Select Committee on Intelligence"])
        self.assertEqual(links[1]["href"], "https://judiciary.house.gov/")

    def test_the_senate_table_gives_the_first_link_of_each_row_and_its_columns(self) -> None:
        links, columns = parse_senate_committees(SENATE_HTML)
        self.assertEqual(columns, ["Committee", "Chair", "Ranking Member", "Total Members", "Subcommittees:"])
        self.assertEqual([l["name"] for l in links], ["Judiciary", "Select Committee on Ethics", "Budget", "Finance", "Joint Economic Committee"])
        self.assertEqual(links[0]["href"], "http://www.judiciary.senate.gov/")


class ProposalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"congress-sites-{uuid.uuid4().hex}"
        self.house, self.senate = write_pages(self.tmp)
        self.node_map = index_tree(json.loads(json.dumps(BASE)))[0]

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_matched_artifact_matched_unmatched_and_refused_are_each_recorded(self) -> None:
        proposals, report = load_congress_site_proposals(self.house, self.senate, self.node_map)
        self.assertEqual(proposals, {
            "leg-house-cmte-judiciary": ["https://judiciary.house.gov/"],
            "leg-house-cmte-permanent-select-committee-on-intelligence": ["https://intelligence.house.gov/"],
            "leg-senate-cmte-select-committee-on-ethics": ["https://www.ethics.senate.gov/"],
        })
        house, senate = report["house"], report["senate"]
        self.assertEqual((house["listed"], house["matched"]), (4, 2))
        self.assertEqual(house["not_in_graph"], ["Ethics"])
        self.assertEqual(house["rejected_urls"], [{"name": "Ways and Means", "node_id": "leg-house-cmte-ways-means",
                                                   "url": "https://example.com/waysandmeans", "reason": REJECT_HOST_NOT_GOV}])
        # Ways and Means was reached by name and refused on its link; only Oversight is unlisted.
        self.assertEqual(house["graph_not_listed"], [{"id": "leg-house-cmte-oversight-accountability", "name": "House Committee on Oversight & Accountability"}])
        self.assertNotIn("leg-house-cmte-judiciary-chair", proposals, "positions are not committees")
        self.assertEqual((senate["listed"], senate["matched"]), (5, 1))
        self.assertEqual(senate["not_in_graph"], ["Joint Economic Committee"])
        self.assertEqual({(r["node_id"], r["reason"]) for r in senate["rejected_urls"]},
                         {("leg-senate-cmte-judiciary", REJECT_NOT_HTTPS), ("leg-senate-cmte-budget", REJECT_HOST_NOT_GOV)})
        self.assertEqual(senate["ambiguous"], [{"name": "Finance", "nodes": ["leg-senate-cmte-finance", "leg-senate-cmte-finance-dup"]}])
        self.assertTrue(senate["table_as_expected"])
        self.assertEqual((house["fetched_at"], senate["fetched_at"]), ("2026-09-08T19:19:17Z", "2026-09-08T19:19:19Z"))
        self.assertEqual(house["url"], "https://www.house.gov/committees")
        self.assertIn("example.com", house["hosts"])
        self.assertEqual(report["hosts"], sorted(set(house["hosts"]) | set(senate["hosts"])))

    def test_an_http_link_is_proposed_as_printed_only_when_asked(self) -> None:
        proposals, report = load_congress_site_proposals(self.house, self.senate, self.node_map, require_https=False)
        self.assertEqual(proposals["leg-senate-cmte-judiciary"], ["http://www.judiciary.senate.gov/"])
        self.assertEqual(report["senate"]["matched"], 2)
        self.assertEqual([r["node_id"] for r in report["senate"]["rejected_urls"]], ["leg-senate-cmte-budget"])
        self.assertFalse(report["require_https"])


class RealFixtureTests(unittest.TestCase):
    """The counts observed on the pages as fetched 2026-09-08, pinned so a
    change to either parser, or to the curated names, is noticed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.node_map = index_tree(load_base_graph(BASE_GRAPH))[0]

    def test_the_house_page_lists_26_and_18_reach_a_node(self) -> None:
        proposals, report = load_congress_site_proposals(REAL_HOUSE, REAL_SENATE, self.node_map)
        house = report["house"]
        self.assertEqual((house["listed"], house["matched"], house["fetched_at"]), (26, 18, "2026-09-08T19:19:17Z"))
        self.assertEqual(house["not_in_graph"], [
            "Education and Workforce", "Ethics", "Oversight and Government Reform",
            "Select Committee on the Strategic Competition Between the United States and the Chinese Communist Party",
            "Joint Economic Committee", "Joint Committee on the Library", "Joint Committee on Printing", "Joint Committee on Taxation",
        ])
        self.assertEqual([g["id"] for g in house["graph_not_listed"]], [
            "leg-house-cmte-education-the-workforce", "leg-house-cmte-intelligence",
            "leg-house-cmte-oversight-accountability", "leg-house-cmte-select-committee-on-the-chinese-communist-party",
        ])
        self.assertEqual((house["ambiguous"], house["rejected_urls"]), ([], []))
        self.assertEqual(proposals["leg-house-cmte-ways-means"], ["https://waysandmeans.house.gov/"])
        self.assertEqual(proposals["leg-house-cmte-house-administration"], ["https://cha.house.gov/"])
        self.assertEqual(proposals["leg-house-cmte-permanent-select-committee-on-intelligence"], ["https://intelligence.house.gov/"])
        self.assertEqual(len(house["hosts"]), 24)
        self.assertTrue(all(h.endswith(".gov") for h in house["hosts"]))
        self.assertIn("www.jec.senate.gov", house["hosts"], "the House page links the JEC to its senate.gov site")

    def test_the_senate_page_lists_24_names_20_nodes_and_links_them_over_http(self) -> None:
        proposals, report = load_congress_site_proposals(REAL_HOUSE, REAL_SENATE, self.node_map)
        senate = report["senate"]
        self.assertEqual((senate["listed"], senate["matched"], senate["fetched_at"]), (24, 0, "2026-09-08T19:19:19Z"))
        self.assertEqual(senate["columns"], ["Committee", "Chair", "Ranking Member", "Total Members", "Subcommittees:"])
        self.assertEqual(senate["not_in_graph"], ["Joint Economic Committee", "Joint Committee on the Library", "Joint Committee on Printing", "Joint Committee on Taxation"])
        self.assertEqual((senate["graph_not_listed"], senate["ambiguous"]), ([], []))
        self.assertEqual(len(senate["rejected_urls"]), 20)
        self.assertEqual({r["reason"] for r in senate["rejected_urls"]}, {REJECT_NOT_HTTPS})
        self.assertTrue(all(r["url"].startswith("http://www.") and r["url"].split("/")[2].endswith(".senate.gov") for r in senate["rejected_urls"]))
        self.assertEqual(len(senate["hosts"]), 23)
        self.assertEqual(report["proposed"], 18)
        self.assertFalse(any(k.startswith("leg-senate-") for k in proposals))
        # As printed, when the caller accepts the page's scheme.
        proposals, report = load_congress_site_proposals(REAL_HOUSE, REAL_SENATE, self.node_map, require_https=False)
        self.assertEqual((report["senate"]["matched"], report["proposed"]), (20, 38))
        self.assertEqual(proposals["leg-senate-cmte-banking-housing-urban-affairs"], ["http://www.banking.senate.gov/public"])
        self.assertEqual(proposals["leg-senate-cmte-special-committee-on-aging"], ["http://www.aging.senate.gov"])
