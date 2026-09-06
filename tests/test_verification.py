"""Existence verification: fetched evidence only, and it reads as what it is.

The base graph has no source on any node. The only honest way one gets a
source is a page that NAMES the unit as a label of its own — a heading, a
link, a list item — read on a date. An adversarial review of the first
version of this module found three separate ways that searching the whole
page as one string manufactures confirmations, and two ways a claim outlives
the evidence for it. Every one of those has a test here.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification.evidence import (
    CONFIRMED,
    FETCH_FAILED,
    INCONCLUSIVE,
    REASON_ANCESTOR_PAGE,
    REASON_NAMED_NOT_LABELLED,
    METHOD_OWN_PAGE,
    METHOD_PARENT_PAGE,
    NOT_CHECKABLE,
    NOT_FOUND,
    PLACEMENT_LISTED,
    PLACEMENT_NOT_LISTED,
    apply_evidence_to_tree,
    candidate_urls,
    find_label,
    name_appears_unlabelled,
    placement_from_record,
    load_official_sites,
    page_fragments,
    uncheckable_reason,
    verify_node,
    verify_placement,
)
from urllib.robotparser import RobotFileParser

from urllib.robotparser import RobotFileParser

from data_pipeline.verification.politeness import RobotsPolicy
from scripts import verify_base_graph
from scripts.validate_published_graph import main as gate_main
from data_pipeline.verification.evidence import (  # noqa: E402
    EVIDENCE_OWNED_FIELDS,
    PLACEMENT_METHOD,
    PLACEMENT_ONLY,
    evidence_names_this_node,
)


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
BASE = {
    "id": ROOT_ID,
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "employees": "30,000", "children": []},
        {
            "id": "executive-branch",
            "name": "Executive Branch",
            "type": "Branch",
            "employees": "4,000,000",
            "children": [
                {
                    "id": "exec-dept-doe",
                    "name": "Department of Energy (DOE)",
                    "type": "Cabinet Department",
                    "children": [
                        {"id": "doe-science", "name": "Office of Science", "type": "Office", "children": [
                            {"id": "doe-science-director", "name": "Director", "type": "Position", "children": []},
                        ]},
                        {"id": "doe-nnsa", "name": "National Nuclear Security Administration", "type": "Component Agency", "children": []},
                        {"id": "doe-labs", "name": "National Laboratories (17)", "type": "Division", "children": []},
                    ],
                },
            ],
        },
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "employees": "30,000", "children": []},
    ],
}
DOE_PAGE = (
    "<html><head><title>Energy.gov</title></head><body>"
    "<nav><a href='/science'>Office of Science</a></nav>"
    "<h1>About the U.S. Department of Energy</h1>"
    "<p>We fund research in science and engineering across the nation, and our "
    "seventeen national laboratories are the backbone of that work. The Department "
    "was created in 1977 and today manages the nuclear stockpile, the power "
    "marketing administrations, and a research portfolio spanning basic science, "
    "applied energy and environmental management. This paragraph is long enough "
    "that the page counts as one a person could actually have read, which is the "
    "condition for saying a name was looked for and was not there.</p>"
    "<script>var x='National Nuclear Security Administration'</script>"
    "</body></html>"
)


class LabelMatchingTests(unittest.TestCase):
    """The three false-positive mechanisms an adversarial review found."""

    def test_a_common_word_in_prose_is_not_a_label(self) -> None:
        frags = page_fragments("<p>NSF supports research in science and engineering nationwide.</p>")
        self.assertIsNone(find_label("Engineering (ENG)", frags))
        self.assertIsNone(find_label("Science", frags))

    def test_a_shorter_name_is_not_confirmed_by_a_longer_one(self) -> None:
        frags = page_fragments("<h1>Office of Science and Technology Policy</h1><p>OSTP leads.</p>")
        self.assertIsNone(find_label("Office of Science", frags))
        self.assertEqual(find_label("Office of Science and Technology Policy", frags), "Office of Science and Technology Policy")

    def test_a_phrase_spanning_two_elements_is_not_on_the_page(self) -> None:
        frags = page_fragments("<span>Office of</span><span>Science</span>")
        self.assertIsNone(find_label("Office of Science", frags))

    def test_a_label_is_found_in_nav_headings_and_link_titles(self) -> None:
        """The directory crawler's parser skips nav, header and title, which is
        where an agency lists its offices. This one must not."""
        frags = page_fragments(DOE_PAGE)
        self.assertEqual(find_label("Office of Science", frags), "Office of Science")
        self.assertEqual(find_label("Department of Energy (DOE)", frags), "About the U.S. Department of Energy")
        self.assertIsNone(find_label("National Nuclear Security Administration", frags))  # only in a <script>
        self.assertEqual(find_label("Office of Science", page_fragments("<a title='Office of Science'><img/></a>")), "Office of Science")

    def test_metadata_that_renders_nothing_is_not_a_label(self) -> None:
        """The exact head markup www.fmc.gov and www.sba.gov serve.

        The separator split turns the feed title into the unit's name, so
        before this the page confirmed the Commission out of <head> — markup
        no visitor sees, and text no auditor can find on the live page.
        """
        head_only = (
            "<html><head><title>Page not about anyone</title>"
            "<link rel='alternate' type='application/rss+xml' "
            "title='Federal Maritime Commission &raquo; Feed' href='/feed/' />"
            "<meta name='application-name' aria-label='Federal Maritime Commission' />"
            "</head><body><p>Nothing here names it.</p></body></html>"
        )
        self.assertIsNone(find_label("Federal Maritime Commission (FMC)", page_fragments(head_only)))
        # The same name in something a reader can see is still evidence.
        self.assertEqual(
            find_label("Federal Maritime Commission (FMC)", page_fragments(head_only.replace(
                "<p>Nothing here names it.</p>", "<h1>Federal Maritime Commission</h1>"))),
            "Federal Maritime Commission",
        )

    def test_an_attribute_inside_skipped_markup_is_not_a_label(self) -> None:
        for markup in (
            "<svg><path aria-label='Office of Science'/></svg>",
            "<script><a title='Office of Science'>x</a></script>",
        ):
            with self.subTest(markup=markup):
                self.assertIsNone(find_label("Office of Science", page_fragments(markup)))

    def test_bounded_scaffolding_around_a_heading_still_matches(self) -> None:
        for heading in ("About the U.S. Department of Energy", "Department of Energy — Home", "Welcome to the Department of Energy"):
            with self.subTest(heading=heading):
                self.assertIsNotNone(find_label("Department of Energy (DOE)", page_fragments(f"<h1>{heading}</h1>")))
        # Not unbounded: a sentence is not a heading.
        self.assertIsNone(find_label("Department of Energy (DOE)", page_fragments(
            "<p>In 1977 Congress created what is now called the Department of Energy.</p>")))

    def test_a_separator_splits_a_label_from_its_tagline(self) -> None:
        self.assertEqual(find_label("Office of Science", page_fragments("<li>Office of Science — Advancing discovery</li>")),
                         "Office of Science — Advancing discovery")

    def test_names_that_could_never_be_evidence_are_named_as_such(self) -> None:
        for name, reason in (
            ("Individual Senator Offices (100)", "curated_count_label"),
            ("U.S. Embassies & Consulates (180+)", "curated_count_label"),
            ("VISN 1 — New England", "curated_count_label"),
            ("Energy", "name_too_generic"),
            ("Defense", "name_too_generic"),
            ("", "empty_name"),
        ):
            with self.subTest(name=name):
                self.assertEqual(uncheckable_reason(name), reason)
        for ok in ("Office of Science", "Department of Energy (DOE)", "National Nuclear Security Administration", "U.S. Mint"):
            with self.subTest(name=ok):
                self.assertIsNone(uncheckable_reason(ok))


class CandidatePageTests(unittest.TestCase):
    def test_pages_come_from_the_node_or_a_measured_number_of_ancestors(self) -> None:
        _, parent_map = index_tree(json.loads(json.dumps(BASE)))
        sites = {"exec-dept-doe": ["https://www.energy.gov/about-us"]}
        self.assertEqual(candidate_urls("exec-dept-doe", parent_map, sites), (["https://www.energy.gov/about-us"], "exec-dept-doe", 0))
        self.assertEqual(candidate_urls("doe-science", parent_map, sites), (["https://www.energy.gov/about-us"], "exec-dept-doe", 1))
        self.assertEqual(candidate_urls("doe-science-director", parent_map, sites)[2], 2)
        self.assertEqual(candidate_urls("legislative-branch", parent_map, sites), ([], None, 2))

    def test_a_name_many_agencies_share_is_scoped_by_ancestry_not_by_the_matcher(self) -> None:
        """The guard against confirming the wrong agency's office is ancestry.

        Found by sweeping every curated name over the pages the first live run
        fetched: NASA's real organization page labels "Office of the Inspector
        General", and the House's OIG is curated under exactly that name. The
        matcher cannot tell them apart -- both are the same string, and it is
        a true label on that page -- so nothing about find_label will ever
        prevent it. What prevents it is that candidate_urls walks only the
        node's OWN ancestors, so nasa.gov is never offered to a House office.
        If that ever changes, this test fails and a false VERIFIED with a live
        nasa.gov URL ships on a legislative-branch node.
        """
        tree = json.loads(json.dumps(BASE))
        tree["children"][0]["children"].append(
            {"id": "leg-house-ig", "name": "Office of the Inspector General", "type": "Office", "children": []}
        )
        _, parent_map = index_tree(tree)
        sites = {
            "exec-dept-doe": ["https://www.energy.gov/leadership-organization"],
            "legislative-branch": ["https://www.house.gov/"],
        }

        # The page really does label the name: the matcher offers no defence.
        nasa_page = "<h1>Organization</h1><ul><li>Office of the Inspector General</li></ul>"
        self.assertEqual(
            find_label("Office of the Inspector General", page_fragments(nasa_page)),
            "Office of the Inspector General",
        )

        # The defence is that NASA's page is never a candidate for this node.
        urls, site_from, _ = candidate_urls("leg-house-ig", parent_map, sites)
        self.assertEqual(urls, ["https://www.house.gov/"])
        self.assertEqual(site_from, "legislative-branch")
        for url in urls:
            self.assertNotIn("nasa.gov", url)

        # Other direction: a node inside NASA's subtree may use NASA's page.
        tree["children"][1]["children"].append(
            {"id": "exec-ind-nasa", "name": "NASA", "type": "Agency", "children": [
                {"id": "exec-ind-nasa-ig", "name": "Office of the Inspector General", "type": "Office", "children": []},
            ]}
        )
        _, parent_map = index_tree(tree)
        sites["exec-ind-nasa"] = ["https://www.nasa.gov/organization/"]
        urls, site_from, distance = candidate_urls("exec-ind-nasa-ig", parent_map, sites)
        self.assertEqual(urls, ["https://www.nasa.gov/organization/"])
        self.assertEqual((site_from, distance), ("exec-ind-nasa", 1))

    def test_candidate_file_keeps_only_urls_and_ignores_its_note(self) -> None:
        path = TEST_TMP_ROOT / f"sites-{uuid.uuid4().hex}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_note": "x", "a": "https://a.gov/", "b": ["https://b.gov/", 5, "nope"], "c": "not a url"}), encoding="utf-8")
        try:
            self.assertEqual(load_official_sites(path), {"a": ["https://a.gov/"], "b": ["https://b.gov/"]})
        finally:
            path.unlink()

    def test_every_seeded_candidate_url_is_an_official_https_host(self) -> None:
        from data_pipeline.processors.normalize_nodes import classify_source_url
        from data_pipeline.verification.evidence import DEFAULT_SITES_PATH

        sites = load_official_sites(DEFAULT_SITES_PATH)
        self.assertGreater(len(sites), 50)
        for node_id, urls in sites.items():
            for url in urls:
                with self.subTest(node=node_id, url=url):
                    self.assertTrue(url.startswith("https://"), url)
                    self.assertEqual(classify_source_url(url), "official_site", url)


class VerifyNodeTests(unittest.TestCase):
    def _fetch(self, pages):
        def fetch(url):
            if url not in pages:
                raise OSError("connect_rejected")
            return pages[url]
        return fetch

    def test_each_outcome_records_what_was_actually_checked(self) -> None:
        node = {"id": "exec-dept-doe", "name": "Department of Energy (DOE)"}
        url = "https://www.energy.gov/about-us"
        fetch = self._fetch({url: DOE_PAGE})

        confirmed = verify_node(node, [url], fetch=fetch, now="2026-09-03T12:00:00+00:00", site_from="exec-dept-doe", is_own_page=True)
        self.assertEqual(confirmed["status"], CONFIRMED)
        self.assertEqual(confirmed["method"], METHOD_OWN_PAGE)
        self.assertEqual(confirmed["sources"][0]["url"], url)
        # The receipt is text as it appears on the page, so a human can search for it.
        self.assertIn(confirmed["sources"][0]["matchedText"], DOE_PAGE)

        # Its own page was read and did not name it: a real negative.
        own_miss = verify_node({"id": "doe-nnsa", "name": "National Nuclear Security Administration"}, [url], fetch=fetch, is_own_page=True)
        self.assertEqual(own_miss["status"], NOT_FOUND)

        # A parent's page is not obliged to list it, so its silence says nothing.
        parent_miss = verify_node({"id": "doe-nnsa", "name": "National Nuclear Security Administration"}, [url], fetch=fetch, is_own_page=False)
        self.assertEqual(parent_miss["status"], INCONCLUSIVE)

        # Confirmed from a parent's page is a different claim from its own page.
        via_parent = verify_node({"id": "doe-science", "name": "Office of Science"}, [url], fetch=fetch, is_own_page=False)
        self.assertEqual((via_parent["status"], via_parent["method"]), (CONFIRMED, METHOD_PARENT_PAGE))

        failed = verify_node(node, ["https://www.energy.gov/nope"], fetch=fetch, is_own_page=True)
        self.assertEqual(failed["status"], FETCH_FAILED)
        self.assertIn("OSError", failed["failures"][0]["reason"])

        wiki = verify_node(node, ["https://en.wikipedia.org/wiki/DOE"], fetch=fetch, is_own_page=True)
        self.assertEqual(wiki["status"], FETCH_FAILED)
        self.assertEqual(wiki["failures"][0]["reason"], "not_an_official_host")

        blank = verify_node(node, ["https://www.energy.gov/js"], fetch=self._fetch({"https://www.energy.gov/js": "<html><body><div id='root'></div></body></html>"}), is_own_page=True)
        self.assertEqual(blank["status"], FETCH_FAILED, "a 200 with no readable body was never read")
        self.assertEqual(blank["failures"][0]["reason"], "no_readable_text")

        uncheckable = verify_node({"id": "doe-labs", "name": "National Laboratories (17)"}, [url], fetch=fetch, is_own_page=True)
        self.assertEqual(uncheckable["status"], NOT_CHECKABLE)
        self.assertEqual(uncheckable["reason"], "curated_count_label")
        self.assertNotIn("sources", uncheckable)

    def test_two_official_pages_are_two_sources(self) -> None:
        body = "<h1>Department of Energy</h1><p>" + "text " * 100 + "</p>"
        pages = {"https://a.energy.gov/": body, "https://b.energy.gov/": body}
        record = verify_node({"id": "x", "name": "Department of Energy"}, list(pages), fetch=self._fetch(pages), is_own_page=True)
        self.assertEqual([s["url"] for s in record["sources"]], list(pages))
        self.assertEqual(record["pagesRead"], 2)


class NotFoundMeansNotOnThePageTests(unittest.TestCase):
    """"Its official page did not name it" is a positive claim, and the first
    live run published it about the CIA — whose About page does say "Central
    Intelligence Agency", in a sentence. What the check actually tested was
    whether the name appears as a LABEL. A page that names the unit in prose
    is evidence about this matcher, not about the unit."""

    def _page(self, body):
        return body + "<p>" + ("filler " * 90) + "</p>"

    def _fetch(self, html):
        return lambda url: html

    def test_named_in_prose_is_inconclusive_not_a_failed_check(self) -> None:
        html = self._page("<h1>About Us</h1><p>The Central Intelligence Agency collects foreign intelligence.</p>")
        record = verify_node({"id": "cia", "name": "Central Intelligence Agency (CIA)"}, ["https://www.cia.gov/about/"],
                             fetch=self._fetch(html), is_own_page=True)
        self.assertEqual(record["status"], INCONCLUSIVE)
        self.assertEqual(record["reason"], REASON_NAMED_NOT_LABELLED)
        self.assertNotIn("sources", record)

    def test_a_name_nowhere_on_the_page_is_still_a_real_negative(self) -> None:
        """epa.gov/aboutepa calls itself "US EPA" and never spells it out."""
        html = self._page("<h1>About US EPA</h1><p>US EPA protects human health and the environment.</p>")
        record = verify_node({"id": "epa", "name": "Environmental Protection Agency (EPA)"}, ["https://www.epa.gov/aboutepa"],
                             fetch=self._fetch(html), is_own_page=True)
        self.assertEqual(record["status"], NOT_FOUND)
        self.assertNotIn("reason", record)

    def test_an_ancestor_page_says_which_kind_of_inconclusive_it_is(self) -> None:
        html = self._page("<h1>Department of Energy</h1>")
        record = verify_node({"id": "x", "name": "Office of Grid Deployment"}, ["https://www.energy.gov/about-us"],
                             fetch=self._fetch(html), is_own_page=False)
        self.assertEqual((record["status"], record["reason"]), (INCONCLUSIVE, REASON_ANCESTOR_PAGE))

    def test_the_loose_test_can_only_withhold_a_claim_never_make_one(self) -> None:
        """It joins fragments, so it matches across elements on purpose. That
        is safe only because nothing positive is ever built on it."""
        self.assertTrue(name_appears_unlabelled("Office of Science", ["Office of", "Science"]))
        self.assertIsNone(find_label("Office of Science", ["Office of", "Science"]))
        # And a page that labels the unit still confirms, unaffected.
        html = self._page("<h1>Office of Science</h1>")
        record = verify_node({"id": "x", "name": "Office of Science"}, ["https://www.energy.gov/science"],
                             fetch=self._fetch(html), is_own_page=True)
        self.assertEqual(record["status"], CONFIRMED)


class ApplyEvidenceTests(unittest.TestCase):
    def _tree(self):
        return json.loads(json.dumps(BASE))

    def _confirmed(self, url="https://www.energy.gov/about-us", at="2026-09-03T12:00:00+00:00", method=METHOD_OWN_PAGE,
                   text="About the U.S. Department of Energy"):
        return {"status": CONFIRMED, "checkedAt": at, "method": method, "siteFrom": "exec-dept-doe",
                "sources": [{"url": url, "matchedText": text}]}

    def test_confirmed_evidence_becomes_a_source_a_date_and_a_named_method(self) -> None:
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {"exec-dept-doe": self._confirmed()})
        node_map, _ = index_tree(tree)
        doe = node_map["exec-dept-doe"]
        self.assertEqual(stats[CONFIRMED], 1)
        self.assertEqual(stats["own_page_confirmations"], 1)
        self.assertEqual(doe["sourceUrls"], ["https://www.energy.gov/about-us"])
        self.assertEqual(doe["lastVerified"], "2026-09-03T12:00:00+00:00")
        self.assertEqual(doe["verificationMethod"], METHOD_OWN_PAGE)
        self.assertTrue(doe["existsProven"])
        self.assertEqual(doe["name"], "Department of Energy (DOE)")
        self.assertEqual(doe["type"], "Cabinet Department")
        self.assertNotIn("lastVerified", node_map["doe-science"])

    def test_a_parent_page_confirmation_says_so(self) -> None:
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {"doe-science": self._confirmed(method=METHOD_PARENT_PAGE, text="Office of Science")})
        node_map, _ = index_tree(tree)
        self.assertEqual(node_map["doe-science"]["verificationMethod"], METHOD_PARENT_PAGE)
        self.assertEqual(stats["parent_page_confirmations"], 1)
        self.assertEqual(stats["own_page_confirmations"], 0)

    def test_only_a_miss_on_its_own_page_is_published_as_a_failed_check(self) -> None:
        for status, expect_stamp in ((NOT_FOUND, True), (INCONCLUSIVE, False), (FETCH_FAILED, False), (NOT_CHECKABLE, False)):
            with self.subTest(status=status):
                tree = self._tree()
                untouched = index_tree(self._tree())[0]["doe-nnsa"]
                stats = apply_evidence_to_tree(tree, {"doe-nnsa": {"status": status, "checkedAt": "2026-09-03T12:00:00+00:00", "siteFrom": "exec-dept-doe"}})
                node = index_tree(tree)[0]["doe-nnsa"]
                self.assertEqual(stats[status], 1)
                if expect_stamp:
                    self.assertEqual(node["lastVerified"], "2026-09-03T12:00:00+00:00")
                    self.assertEqual(node["verificationFailure"], NOT_FOUND)
                    self.assertFalse(node.get("sourceUrls"))
                else:
                    self.assertEqual(node, untouched, f"{status} must change nothing at all")

    def test_a_confirmation_is_withdrawn_when_the_evidence_is(self) -> None:
        """The published graph is re-fed as a payload on every build, so
        without an explicit withdrawal a claim outlives its evidence forever."""
        tree = self._tree()
        apply_evidence_to_tree(tree, {"exec-dept-doe": self._confirmed()})
        node_map, _ = index_tree(tree)
        self.assertEqual(node_map["exec-dept-doe"]["sourceUrls"], ["https://www.energy.gov/about-us"])

        stats = apply_evidence_to_tree(tree, {})  # the record is gone
        doe = index_tree(tree)[0]["exec-dept-doe"]
        self.assertEqual(stats["stale_claims_cleared"], 1)
        self.assertFalse(doe.get("sourceUrls"))
        self.assertNotIn("verificationMethod", doe)
        self.assertFalse(doe.get("lastVerified"))
        self.assertFalse(doe.get("existsProven"))

    def test_a_later_not_found_retracts_an_earlier_confirmation(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {"exec-dept-doe": self._confirmed()})
        apply_evidence_to_tree(tree, {"exec-dept-doe": {"status": NOT_FOUND, "checkedAt": "2026-11-01T00:00:00+00:00", "siteFrom": "exec-dept-doe"}})
        doe = index_tree(tree)[0]["exec-dept-doe"]
        self.assertFalse(doe.get("sourceUrls"), "the withdrawn URL must not survive")
        self.assertEqual(doe["verificationFailure"], NOT_FOUND)
        self.assertEqual(doe["lastVerified"], "2026-11-01T00:00:00+00:00")

    def test_a_treasury_source_survives_and_suppresses_the_failure_stamp(self) -> None:
        tree = self._tree()
        node_map, _ = index_tree(tree)
        node_map["doe-nnsa"]["sourceUrls"] = ["https://api.fiscaldata.treasury.gov/x"]
        apply_evidence_to_tree(tree, {"doe-nnsa": {"status": NOT_FOUND, "checkedAt": "2026-09-03T12:00:00+00:00"}})
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        self.assertEqual(nnsa["sourceUrls"], ["https://api.fiscaldata.treasury.gov/x"])
        self.assertNotIn("verificationFailure", nnsa)

    def test_unknown_ids_statuses_and_unofficial_urls_touch_nothing(self) -> None:
        tree = self._tree()
        before = json.dumps(tree, sort_keys=True)
        stats = apply_evidence_to_tree(tree, {
            "ghost": self._confirmed(),
            "doe-science": {"status": "guessed"},
            "doe-nnsa": self._confirmed(url="https://en.wikipedia.org/wiki/NNSA"),
        })
        self.assertEqual(stats["unknown_node"], 1)
        self.assertEqual(stats["unknown_status"], 2)
        self.assertEqual(json.dumps(tree, sort_keys=True), before)


class RobotsTests(unittest.TestCase):
    def test_a_disallow_is_obeyed_and_an_unreadable_file_is_not_a_prohibition(self) -> None:
        policy = RobotsPolicy(user_agent="bureaucracy-data-pipeline/1.0")
        with mock.patch.object(RobotsPolicy, "_parser", return_value=None):
            self.assertEqual(policy.allows("https://www.energy.gov/x")[0], True)
            self.assertEqual(policy.crawl_delay("https://www.energy.gov/x"), 0.0)

        class Denies:
            def can_fetch(self, agent, url):
                return False

            def crawl_delay(self, agent):
                return 5

        with mock.patch.object(RobotsPolicy, "_parser", return_value=Denies()):
            allowed, why = policy.allows("https://www.energy.gov/private")
            self.assertFalse(allowed)
            self.assertIn("disallows", why)
            self.assertEqual(policy.crawl_delay("https://www.energy.gov/x"), 5.0)

        disabled = RobotsPolicy(user_agent="x", enabled=False)
        with mock.patch.object(RobotsPolicy, "_parser", return_value=Denies()):
            self.assertTrue(disabled.allows("https://www.energy.gov/private")[0])

    def test_a_refused_robots_file_is_obeyed_but_not_quoted_as_a_rule(self) -> None:
        """A host that answers robots.txt with 403 is still refused, but the
        record must not claim the site published a rule nobody could read.

        RobotFileParser.read() swallows a 401/403 and sets disallow_all with
        no entries parsed. www.state.gov did exactly this on the first live
        run, and the evidence file went out saying
        "www.state.gov/robots.txt disallows /about/" -- a claim about State's
        crawl policy that no fetch supports.
        """
        policy = RobotsPolicy(user_agent="bureaucracy-data-pipeline/1.0")

        class Refused(RobotFileParser):
            """What read() leaves behind on a 403: a blanket deny, no rules."""

            def __init__(self) -> None:
                super().__init__()
                self.disallow_all = True

        with mock.patch.object(RobotsPolicy, "_parser", return_value=Refused()):
            allowed, why = policy.allows("https://www.state.gov/about/")
        self.assertFalse(allowed, "an unreadable robots.txt is still obeyed")
        self.assertIn("could not be read", why)
        self.assertNotIn("disallows /about/", why)

        # The other direction: a robots.txt that WAS read and does disallow
        # the path still says so, and still names the path.
        parsed = RobotFileParser()
        parsed.parse(["User-agent: *", "Disallow: /about/"])
        with mock.patch.object(RobotsPolicy, "_parser", return_value=parsed):
            allowed, why = policy.allows("https://www.state.gov/about/")
            self.assertFalse(allowed)
            self.assertIn("disallows /about/", why)
            self.assertNotIn("could not be read", why)
            # and a path it does not cover is still allowed
            self.assertTrue(policy.allows("https://www.state.gov/bureaus/")[0])


class RobotsRefusalReasonTests(unittest.TestCase):
    """A refusal must say which of the two things happened, and must not cite
    a rule nobody read. Python's parser sets disallow_all on a 401/403 to
    robots.txt itself — the pre-RFC-9309 convention — and the first live run
    published "www.state.gov/robots.txt disallows /about/", which is a
    statement about a file the run never saw."""

    def test_an_unreadable_robots_is_refused_without_quoting_a_rule(self) -> None:
        policy = RobotsPolicy(user_agent="bureaucracy-data-pipeline/1.0")

        unreadable = RobotFileParser()
        unreadable.disallow_all = True  # what read() sets on a 401/403

        parsed = RobotFileParser()
        parsed.parse(["User-agent: *", "Disallow: /about/"])

        with mock.patch.object(RobotsPolicy, "_parser", return_value=unreadable):
            allowed, why = policy.allows("https://www.state.gov/about/")
        self.assertFalse(allowed)
        self.assertIn("could not be read", why)
        self.assertNotIn("disallows", why)
        self.assertNotIn("RFC", why, "the standard does not require this refusal; do not cite it")

        with mock.patch.object(RobotsPolicy, "_parser", return_value=parsed):
            allowed, why = policy.allows("https://www.state.gov/about/")
        self.assertFalse(allowed)
        self.assertIn("disallows /about/", why)

        with mock.patch.object(RobotsPolicy, "_parser", return_value=parsed):
            self.assertTrue(policy.allows("https://www.state.gov/other/")[0])


class BuildAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"verify-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.evidence_path = self.tmp / "evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, evidence, *, reuse=False):
        self.evidence_path.write_text(json.dumps({"_note": "test", "nodes": evidence}), encoding="utf-8")
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base,
            graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "expanded_nodes.json",
            edges_output_path=self.tmp / "expanded_edges.json",
            validity_report_output_path=self.tmp / "node_validity_report.json",
            reuse_existing_graph_payload=reuse,
            existing_graph_payload_path=self.tmp / "graph.json",
            enforce_export_gate=True,
            evidence_path=self.evidence_path,
        )

    def _gate(self, path):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(path)])
        return code, out.getvalue()

    def _record(self, node_id, graph):
        return index_tree(graph)[0][node_id]

    def test_evidence_reaches_the_published_graph_and_the_gate_reports_it(self) -> None:
        result = self._build({
            "exec-dept-doe": {"status": CONFIRMED, "checkedAt": "2026-09-03T12:00:00+00:00", "method": METHOD_OWN_PAGE,
                              "sources": [{"url": "https://www.energy.gov/about-us", "matchedText": "About the U.S. Department of Energy"}]},
            "doe-nnsa": {"status": NOT_FOUND, "checkedAt": "2026-09-03T12:00:00+00:00", "siteFrom": "doe-nnsa"},
            "doe-science": {"status": INCONCLUSIVE, "checkedAt": "2026-09-03T12:00:00+00:00"},
        })
        self.assertEqual(result.validation["verification_evidence"][CONFIRMED], 1)
        self.assertEqual(result.validation["verification_evidence"][INCONCLUSIVE], 1)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        self.assertEqual(self._record("exec-dept-doe", graph)["sourceUrls"], ["https://www.energy.gov/about-us"])
        self.assertEqual(self._record("exec-dept-doe", graph)["sourceCount"], 1)
        self.assertEqual(self._record("doe-nnsa", graph)["verificationFailure"], NOT_FOUND)
        self.assertFalse(self._record("doe-science", graph).get("lastVerified"), "inconclusive stamps no date")
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("official source      : 1 of", out)
        self.assertIn("checked, not found   : 1", out)
        self.assertIn(METHOD_OWN_PAGE, out)

    def test_a_retraction_reaches_the_published_graph_even_when_the_last_one_is_re_fed(self) -> None:
        """Production reuses the previous graph.json as a payload. Every other
        build test switches that off, which is exactly how a permanent claim
        would go unnoticed."""
        confirmed = {"exec-dept-doe": {"status": CONFIRMED, "checkedAt": "2026-09-03T12:00:00+00:00", "method": METHOD_OWN_PAGE,
                                       "sources": [{"url": "https://www.energy.gov/about-us", "matchedText": "About the U.S. Department of Energy"}]}}
        first = self._build(confirmed, reuse=False)
        graph = json.loads(first.graph_path.read_text(encoding="utf-8"))
        self.assertEqual(self._record("exec-dept-doe", graph)["sourceUrls"], ["https://www.energy.gov/about-us"])

        second = self._build({}, reuse=True)  # evidence withdrawn, previous graph re-fed
        graph = json.loads(second.graph_path.read_text(encoding="utf-8"))
        doe = self._record("exec-dept-doe", graph)
        self.assertFalse(doe.get("sourceUrls"), "a claim must not outlive its evidence")
        self.assertNotIn("verificationMethod", doe)
        code, out = self._gate(second.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("official source      : 0 of", out)

    def test_the_gate_refuses_every_way_a_verification_claim_can_be_unbacked(self) -> None:
        result = self._build({})
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        cases = {
            "future date": lambda n: n.__setitem__("lastVerified", "2999-01-01"),
            "not a date": lambda n: n.__setitem__("lastVerified", "yesterday"),
            "method without url": lambda n: n.__setitem__("verificationMethod", METHOD_OWN_PAGE),
            "invented method": lambda n: n.update({"verificationMethod": "vibes", "sourceUrls": ["https://www.energy.gov/x"], "sourceCount": 1}),
            "failure beside a source": lambda n: n.update({"verificationFailure": NOT_FOUND, "sourceUrls": ["https://www.energy.gov/x"], "sourceCount": 1}),
            "official type without a gov url": lambda n: n.update({"sourceTypes": ["official_site"], "sourceUrls": ["https://example.com/x"], "sourceCount": 1}),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph))
                mutate(self._record("exec-dept-doe", corrupted))
                path = self.tmp / f"{uuid.uuid4().hex}.json"
                path.write_text(json.dumps(corrupted), encoding="utf-8")
                code, out = self._gate(path)
                self.assertEqual(code, 1, f"{name} should fail the gate:\n{out}")
                self.assertIn("Department of Energy", out)


class VerifierScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"verify-cli-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.sites = self.tmp / "sites.json"
        self.sites.write_text(json.dumps({"exec-dept-doe": ["https://www.energy.gov/about-us"]}), encoding="utf-8")
        self.evidence = self.tmp / "evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = verify_base_graph.main(["v", "--base-graph", str(self.base), "--sites", str(self.sites),
                                           "--evidence", str(self.evidence), "--sleep", "0", *extra])
        return code, out.getvalue()

    def test_dry_run_plans_without_fetching_or_writing(self) -> None:
        code, text = self._run("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("to check 3", text)  # DOE's own page, plus Office of Science and NNSA via it
        self.assertIn("exec-dept-doe  <-  https://www.energy.gov/about-us  (own page)", text)
        self.assertIn("doe-science  <-  https://www.energy.gov/about-us  (page of exec-dept-doe)", text)
        self.assertNotIn("doe-science-director", text)          # a Position, not selected
        self.assertIn("curated_count_label", text)               # "National Laboratories (17)"
        self.assertFalse(self.evidence.exists())
        self.assertEqual(json.loads(self.base.read_text(encoding="utf-8")), BASE)

    def test_the_inherit_depth_cap_and_the_position_filter_are_each_load_bearing(self) -> None:
        """Asserted separately, so deleting either guard fails a test."""
        _, own_only = self._run("--dry-run", "--inherit-depth", "0")
        self.assertIn("to check 1", own_only)                    # only DOE's own page
        _, with_positions = self._run("--dry-run", "--include-positions", "--inherit-depth", "2")
        self.assertIn("doe-science-director", with_positions)    # the Position reappears at depth 2

    def test_a_real_run_records_each_outcome_and_writes_nothing_else(self) -> None:
        pages = {"https://www.energy.gov/about-us": DOE_PAGE}
        with mock.patch.object(verify_base_graph, "request_text", lambda url, timeout=30: pages[url]), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=None):
            code, text = self._run()
        self.assertEqual(code, 0, text)
        store = json.loads(self.evidence.read_text(encoding="utf-8"))
        records = store["nodes"]
        self.assertEqual(records["exec-dept-doe"]["status"], CONFIRMED)
        self.assertEqual(records["exec-dept-doe"]["method"], METHOD_OWN_PAGE)
        self.assertEqual(records["doe-science"]["status"], CONFIRMED)
        self.assertEqual(records["doe-science"]["method"], METHOD_PARENT_PAGE)
        self.assertEqual(records["doe-nnsa"]["status"], INCONCLUSIVE)  # absent from a parent page proves nothing
        self.assertEqual(records["doe-labs"]["status"], NOT_CHECKABLE)
        self.assertIn("_note", store)
        self.assertEqual(json.loads(self.base.read_text(encoding="utf-8")), BASE)

    def test_one_page_is_fetched_once_however_many_nodes_share_it(self) -> None:
        calls = []

        def counting(url, timeout=30):
            calls.append(url)
            return DOE_PAGE

        with mock.patch.object(verify_base_graph, "request_text", counting), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=None):
            self._run()
        self.assertEqual(calls, ["https://www.energy.gov/about-us"])

    def test_a_run_that_reached_nothing_exits_nonzero_and_records_no_check(self) -> None:
        def blocked(url, timeout=30):
            raise OSError("Tunnel connection failed: 403 Forbidden")

        with mock.patch.object(verify_base_graph, "request_text", blocked), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=None):
            code, text = self._run()
        self.assertEqual(code, 2, text)
        records = json.loads(self.evidence.read_text(encoding="utf-8"))["nodes"]
        self.assertEqual(records["exec-dept-doe"]["status"], FETCH_FAILED)
        # And nothing that reaches the graph:
        tree = json.loads(json.dumps(BASE))
        apply_evidence_to_tree(tree, records)
        self.assertEqual(tree, json.loads(json.dumps(BASE)))

    def test_robots_disallow_is_recorded_as_a_failed_fetch_not_a_missing_name(self) -> None:
        class Denies:
            def can_fetch(self, agent, url):
                return False

            def crawl_delay(self, agent):
                return 0

        with mock.patch.object(verify_base_graph, "request_text", lambda url, timeout=30: DOE_PAGE), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=Denies()):
            code, _ = self._run()
        self.assertEqual(code, 2)
        records = json.loads(self.evidence.read_text(encoding="utf-8"))["nodes"]
        self.assertEqual(records["exec-dept-doe"]["status"], FETCH_FAILED)
        self.assertIn("robots.txt", records["exec-dept-doe"]["failures"][0]["reason"])

    def test_list_hosts_prints_the_allowlist_and_every_one_is_official(self) -> None:
        from data_pipeline.processors.normalize_nodes import classify_source_url
        from data_pipeline.verification.evidence import DEFAULT_SITES_PATH

        out = io.StringIO()
        with redirect_stdout(out):
            verify_base_graph.main(["v", "--list-hosts"])
        hosts = out.getvalue().split()
        self.assertIn("www.energy.gov", hosts)
        self.assertGreater(len(hosts), 40)
        for host in hosts:
            with self.subTest(host=host):
                self.assertEqual(classify_source_url(f"https://{host}/"), "official_site", host)


if __name__ == "__main__":
    unittest.main()


class PlacementTests(unittest.TestCase):
    """Evidence for the parent -> child EDGE, the site's central claim and the
    one thing nothing had checked. The only accepted evidence is the parent's
    own official page naming the child as a label; its silence claims nothing."""

    DOE_ORG_PAGE = "<h1>Leadership &amp; Organization</h1><ul><li><a href='/science'>Office of Science</a></li><li>Office of Environmental Management</li></ul><p>" + ("filler " * 90) + "</p>"

    def _fetch(self, pages):
        def fetch(url):
            if url not in pages:
                raise OSError("connect_rejected")
            return pages[url]
        return fetch

    def test_the_parent_page_naming_the_child_is_edge_evidence(self) -> None:
        block = verify_placement({"id": "doe-science", "name": "Office of Science"}, "exec-dept-doe",
                                 ["https://www.energy.gov/leadership-organization"],
                                 fetch=self._fetch({"https://www.energy.gov/leadership-organization": self.DOE_ORG_PAGE}),
                                 now="2026-09-06T12:00:00+00:00")
        self.assertEqual(block["status"], PLACEMENT_LISTED)
        self.assertEqual(block["parentId"], "exec-dept-doe")
        self.assertEqual(block["matchedText"], "Office of Science")
        self.assertIn(block["matchedText"], self.DOE_ORG_PAGE)

    def test_silence_on_the_parent_page_is_recorded_and_claims_nothing(self) -> None:
        block = verify_placement({"id": "doe-nnsa", "name": "National Nuclear Security Administration"}, "exec-dept-doe",
                                 ["https://www.energy.gov/leadership-organization"],
                                 fetch=self._fetch({"https://www.energy.gov/leadership-organization": self.DOE_ORG_PAGE}))
        self.assertEqual(block["status"], PLACEMENT_NOT_LISTED)
        self.assertNotIn("url", block)

    def test_an_unreadable_parent_page_concludes_nothing_at_all(self) -> None:
        self.assertIsNone(verify_placement({"id": "x", "name": "Office of Science"}, "p", ["https://www.energy.gov/nope"], fetch=self._fetch({})))
        blank = self._fetch({"https://www.energy.gov/js": "<div id='root'></div>"})
        self.assertIsNone(verify_placement({"id": "x", "name": "Office of Science"}, "p", ["https://www.energy.gov/js"], fetch=blank))
        self.assertIsNone(verify_placement({"id": "x", "name": "Energy"}, "p", ["https://www.energy.gov/"], fetch=self._fetch({"https://www.energy.gov/": self.DOE_ORG_PAGE})), "a generic name is never checked")

    def test_a_parent_page_confirmation_already_is_placement_evidence(self) -> None:
        """The 28 existing parent-page confirmations were the same fetch and
        the same fact. They count without being fetched again — but only for
        the parent whose page it actually was."""
        record = {"status": CONFIRMED, "method": METHOD_PARENT_PAGE, "siteFrom": "exec-ind-nasa", "checkedAt": "2026-09-03T12:00:00+00:00",
                  "sources": [{"url": "https://www.nasa.gov/about/", "matchedText": "Science Mission Directorate"}]}
        derived = placement_from_record(record, "exec-ind-nasa")
        self.assertEqual(derived["status"], PLACEMENT_LISTED)
        self.assertEqual(derived["url"], "https://www.nasa.gov/about/")
        self.assertEqual(derived["derivedFrom"], "parent_page_confirmation")
        self.assertIsNone(placement_from_record(record, "some-other-parent"), "a different parent is a different edge")
        own = dict(record, method=METHOD_OWN_PAGE, siteFrom="doe-science")
        self.assertIsNone(placement_from_record(own, "exec-dept-doe"), "an own-page confirmation proves existence, not the edge")

    def _tree(self):
        return json.loads(json.dumps(BASE))

    def test_apply_stamps_a_listed_placement_for_the_tree_s_actual_parent_only(self) -> None:
        tree = self._tree()
        listed = {"status": PLACEMENT_LISTED, "parentId": "exec-dept-doe", "url": "https://www.energy.gov/leadership-organization",
                  "matchedText": "Office of Science", "checkedAt": "2026-09-06T12:00:00+00:00"}
        stats = apply_evidence_to_tree(tree, {
            "doe-science": {"status": INCONCLUSIVE, "checkedAt": "2026-09-06T12:00:00+00:00", "placement": listed},
            # Evidence for an edge the tree does not have: NNSA's parent is DOE, not the Legislative Branch.
            "doe-nnsa": {"status": INCONCLUSIVE, "checkedAt": "2026-09-06T12:00:00+00:00",
                         "placement": dict(listed, parentId="legislative-branch")},
        })
        node_map, _ = index_tree(tree)
        science = node_map["doe-science"]
        self.assertTrue(science["placementVerified"])
        self.assertEqual(science["placementParentId"], "exec-dept-doe")
        self.assertEqual(science["placementUrl"], "https://www.energy.gov/leadership-organization")
        self.assertFalse(science.get("sourceUrls"), "placement is not an existence source")
        self.assertNotIn("placementVerified", node_map["doe-nnsa"])
        self.assertEqual(stats["placements_evidenced"], 1)
        self.assertEqual(stats["placements_stale_parent"], 1)

    def test_not_listed_is_recorded_as_false_and_a_withdrawal_clears_it(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {"doe-science": {"status": INCONCLUSIVE, "checkedAt": "2026-09-06",
                                                     "placement": {"status": PLACEMENT_NOT_LISTED, "parentId": "exec-dept-doe", "urls": ["https://www.energy.gov/x"], "checkedAt": "2026-09-06T12:00:00+00:00"}}})
        node = index_tree(tree)[0]["doe-science"]
        self.assertIs(node["placementVerified"], False)
        self.assertNotIn("placementUrl", node)
        apply_evidence_to_tree(tree, {})
        node = index_tree(tree)[0]["doe-science"]
        self.assertNotIn("placementVerified", node)
        self.assertNotIn("placementParentId", node)

    def test_the_gate_refuses_an_unbacked_or_misplaced_placement_claim(self) -> None:
        tmp = TEST_TMP_ROOT / f"placement-gate-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
            evidence_path = tmp / "evidence.json"
            good = {"doe-science": {"status": INCONCLUSIVE, "checkedAt": "2026-09-06T12:00:00+00:00",
                    "placement": {"status": PLACEMENT_LISTED, "parentId": "exec-dept-doe", "url": "https://www.energy.gov/leadership-organization", "matchedText": "Office of Science", "checkedAt": "2026-09-06T12:00:00+00:00"}}}
            evidence_path.write_text(json.dumps({"nodes": good}), encoding="utf-8")
            result = build_graph(
                [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
                base_graph_path=base, graph_output_path=tmp / "graph.json", nodes_output_path=tmp / "n.json",
                edges_output_path=tmp / "e.json", validity_report_output_path=tmp / "v.json",
                reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=evidence_path,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = gate_main(["gate", str(result.graph_path)])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("placement evidenced  : 1 of", out.getvalue())

            graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
            cases = {
                "wrong parent": lambda n: n.__setitem__("placementParentId", "legislative-branch"),
                "no url": lambda n: n.__setitem__("placementUrl", ""),
                "unofficial url": lambda n: n.__setitem__("placementUrl", "https://en.wikipedia.org/x"),
                "no date": lambda n: n.__setitem__("placementVerifiedAt", None),
            }
            for name, mutate in cases.items():
                with self.subTest(case=name):
                    corrupted = json.loads(json.dumps(graph))
                    mutate(index_tree(corrupted)[0]["doe-science"])
                    path = tmp / f"{uuid.uuid4().hex}.json"
                    path.write_text(json.dumps(corrupted), encoding="utf-8")
                    out = io.StringIO()
                    with redirect_stdout(out):
                        code = gate_main(["gate", str(path)])
                    self.assertEqual(code, 1, f"{name}:\n{out.getvalue()}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class EvidenceScopeTests(unittest.TestCase):
    """What the evidence module may touch on a node, and what it must leave
    alone. The first placement build stripped the FiscalData URL from 26
    measured nodes because the clearing step took the node's whole list."""

    def _tree(self):
        return json.loads(json.dumps(BASE))

    def _confirmed(self, text, at="2026-09-03T12:00:00+00:00", method=METHOD_OWN_PAGE, url="https://www.energy.gov/about-us"):
        return {"status": CONFIRMED, "checkedAt": at, "method": method, "siteFrom": "exec-dept-doe",
                "sources": [{"url": url, "matchedText": text}]}

    def test_a_label_for_a_different_unit_confirms_nothing(self) -> None:
        """Records are keyed by id and never re-fetched once confirmed; a
        renamed node must not keep a badge earned by its old name."""
        self.assertTrue(evidence_names_this_node("Office of Science", "Office of Science"))
        self.assertTrue(evidence_names_this_node("Office of Science", None), "older records carry no text and stand")
        self.assertFalse(evidence_names_this_node("Office of Science", "National Nuclear Security Administration"))
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {"doe-science": self._confirmed("National Nuclear Security Administration")})
        science = index_tree(tree)[0]["doe-science"]
        self.assertEqual(stats["existence_stale_name"], 1)
        self.assertEqual(stats[CONFIRMED], 0)
        self.assertFalse(science.get("sourceUrls"))
        self.assertNotIn("lastVerified", science)
        self.assertNotIn("verificationMethod", science)

    def test_withdrawal_takes_back_only_the_urls_and_date_it_supplied(self) -> None:
        tree = self._tree()
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        nnsa["sourceUrls"] = ["https://api.fiscaldata.treasury.gov/mts/table-5"]
        nnsa["sourceTypes"] = ["treasury_outlays"]
        apply_evidence_to_tree(tree, {"doe-nnsa": self._confirmed("National Nuclear Security Administration",
                                                                    url="https://www.energy.gov/nnsa")})
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        self.assertEqual(nnsa["sourceUrls"], ["https://api.fiscaldata.treasury.gov/mts/table-5", "https://www.energy.gov/nnsa"])
        self.assertEqual(nnsa["evidenceUrls"], ["https://www.energy.gov/nnsa"])
        self.assertEqual(nnsa["lastVerified"], "2026-09-03T12:00:00+00:00")
        self.assertEqual(nnsa["evidenceVerifiedAt"], "2026-09-03T12:00:00+00:00")

        # Evidence withdrawn, and the Treasury URL is not this module's to remove.
        apply_evidence_to_tree(tree, {})
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        self.assertEqual(nnsa["sourceUrls"], ["https://api.fiscaldata.treasury.gov/mts/table-5"])
        # FiscalData is a .gov host, so the pipeline's own classifier keeps
        # calling it an official site; that label is not this module's.
        self.assertEqual(nnsa["sourceTypes"], ["treasury_outlays", "official_site"])
        for field in EVIDENCE_OWNED_FIELDS:
            self.assertNotIn(field, nnsa)
        self.assertFalse(nnsa.get("lastVerified"), "the date belonged to the withdrawn fetch")

    def test_a_date_a_crawler_supplied_survives_a_withdrawal(self) -> None:
        tree = self._tree()
        nnsa = index_tree(tree)[0]["doe-nnsa"]
        nnsa["sourceUrls"] = ["https://api.fiscaldata.treasury.gov/mts/table-5"]
        nnsa["lastVerified"] = "2026-09-04T00:00:00+00:00"          # later than the evidence
        apply_evidence_to_tree(tree, {"doe-nnsa": self._confirmed("National Nuclear Security Administration",
                                                                    url="https://www.energy.gov/nnsa")})
        self.assertEqual(index_tree(tree)[0]["doe-nnsa"]["lastVerified"], "2026-09-04T00:00:00+00:00")
        apply_evidence_to_tree(tree, {})
        self.assertEqual(index_tree(tree)[0]["doe-nnsa"]["lastVerified"], "2026-09-04T00:00:00+00:00")

    def test_placement_checkable_is_a_fact_about_the_parent_and_is_withdrawn_with_it(self) -> None:
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {}, sites={"executive-branch": ["https://www.whitehouse.gov/"]})
        node_map, _ = index_tree(tree)
        self.assertIs(node_map["doe-science"]["placementCheckable"], False, "DOE has no page in this sites file")
        self.assertNotIn("placementCheckable", node_map["exec-dept-doe"], "its parent has a page")
        self.assertNotIn("placementCheckable", node_map["doe-science-director"], "positions are not checked")
        self.assertNotIn("placementCheckable", node_map[ROOT_ID])
        # The three branches (the root has no page) and DOE's three children.
        self.assertEqual(stats["placements_not_checkable_no_parent_page"], 6)
        self.assertNotIn("placementCheckable", index_tree(self._tree())[0]["doe-science"])
        # Without a sites file nothing can be said either way.
        bare = self._tree()
        apply_evidence_to_tree(bare, {})
        self.assertNotIn("placementCheckable", index_tree(bare)[0]["doe-science"])

        # The parent gains a page and the edge is checked: the old "could not
        # be checked" must not stand beside the result.
        listed = {"status": PLACEMENT_LISTED, "parentId": "exec-dept-doe", "url": "https://www.energy.gov/leadership-organization",
                  "matchedText": "Office of Science", "checkedAt": "2026-09-06T12:00:00+00:00"}
        apply_evidence_to_tree(tree, {"doe-science": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06T12:00:00+00:00", "placement": listed}},
                               sites={"exec-dept-doe": ["https://www.energy.gov/leadership-organization"]})
        science = index_tree(tree)[0]["doe-science"]
        self.assertIs(science["placementVerified"], True)
        self.assertNotIn("placementCheckable", science)

    def test_a_placement_only_record_is_counted_and_its_edge_applied(self) -> None:
        tree = self._tree()
        listed = {"status": PLACEMENT_LISTED, "parentId": "exec-dept-doe", "url": "https://www.energy.gov/leadership-organization",
                  "matchedText": "Office of Science", "checkedAt": "2026-09-06T12:00:00+00:00"}
        stats = apply_evidence_to_tree(tree, {"doe-science": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06T12:00:00+00:00", "placement": listed}})
        science = index_tree(tree)[0]["doe-science"]
        self.assertEqual(stats[PLACEMENT_ONLY], 1)
        self.assertEqual(stats["unknown_status"], 0)
        self.assertIs(science["placementVerified"], True)
        self.assertFalse(science.get("sourceUrls"), "the edge was checked; the unit's own existence was not")
        self.assertNotIn("lastVerified", science)


class PlacementRetractionTests(unittest.TestCase):
    """The ways a placement claim can go stale, and that each one reaches the
    published node. Every path here was a finding of the placement review."""

    def _tree(self):
        return json.loads(json.dumps(BASE))

    def _listed(self, text="Office of Science", parent="exec-dept-doe", url="https://www.energy.gov/leadership-organization"):
        return {"status": PLACEMENT_LISTED, "parentId": parent, "url": url, "matchedText": text, "checkedAt": "2026-09-06T12:00:00+00:00"}

    def test_an_explicit_not_listed_beats_a_derived_listed(self) -> None:
        """A parent-page confirmation implies placement. Re-reading that very
        page and not finding the name must retract it, not lose to it."""
        record = {"status": CONFIRMED, "method": METHOD_PARENT_PAGE, "siteFrom": "exec-dept-doe", "checkedAt": "2026-09-03T12:00:00+00:00",
                  "sources": [{"url": "https://www.energy.gov/about-us", "matchedText": "Office of Science"}],
                  "placement": {"status": PLACEMENT_NOT_LISTED, "parentId": "exec-dept-doe", "urlsRead": ["https://www.energy.gov/about-us"],
                                "checkedAt": "2026-09-07T12:00:00+00:00"}}
        self.assertIsNone(placement_from_record(record, "exec-dept-doe"))
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {"doe-science": record})
        science = index_tree(tree)[0]["doe-science"]
        self.assertIs(science["placementVerified"], False)
        self.assertEqual(science["placementVerifiedAt"], "2026-09-07T12:00:00+00:00")
        self.assertEqual(stats["placements_checked_not_listed"], 1)
        self.assertEqual(stats["placements_evidenced"], 0)
        # The existence confirmation itself still stands: the page named it once.
        self.assertEqual(science["sourceUrls"], ["https://www.energy.gov/about-us"])

    def test_a_withdrawn_placement_leaves_no_field_behind(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {"doe-science": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06", "placement": self._listed()}})
        science = index_tree(tree)[0]["doe-science"]
        for field in ("placementVerified", "placementUrl", "placementVerifiedAt", "placementParentId", "placementMatchedText", "placementMethod"):
            self.assertIn(field, science, field)
        self.assertEqual(science["placementMethod"], PLACEMENT_METHOD)
        self.assertEqual(science["placementMatchedText"], "Office of Science")
        stats = apply_evidence_to_tree(tree, {})
        science = index_tree(tree)[0]["doe-science"]
        self.assertEqual(stats["stale_claims_cleared"], 1)
        self.assertFalse(any(k.startswith("placement") for k in science), sorted(science))

    def test_a_label_for_another_unit_is_not_this_edge(self) -> None:
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {"doe-science": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06",
                                                             "placement": self._listed(text="Office of Environmental Management")}})
        self.assertEqual(stats["placements_stale_name"], 1)
        self.assertEqual(stats["placements_evidenced"], 0)
        self.assertNotIn("placementVerified", index_tree(tree)[0]["doe-science"])

    def test_not_listed_names_only_the_pages_actually_read(self) -> None:
        page = "<h1>Leadership</h1><ul><li>Office of Environmental Management</li></ul><p>" + ("filler " * 90) + "</p>"

        def fetch(url):
            if url.endswith("/gone"):
                raise OSError("404")
            return page

        block = verify_placement({"id": "doe-science", "name": "Office of Science"}, "exec-dept-doe",
                                 ["https://www.energy.gov/gone", "https://www.energy.gov/leadership", "https://example.com/x"],
                                 fetch=fetch, now="2026-09-06T12:00:00+00:00")
        self.assertEqual(block["status"], PLACEMENT_NOT_LISTED)
        self.assertEqual(block["urlsRead"], ["https://www.energy.gov/leadership"])
        self.assertEqual({f["url"] for f in block["failures"]}, {"https://www.energy.gov/gone", "https://example.com/x"})
        self.assertEqual(block["checkedAt"], "2026-09-06T12:00:00+00:00")

    def test_the_gate_refuses_each_way_a_placement_can_be_hollow(self) -> None:
        tmp = TEST_TMP_ROOT / f"placement-gate-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
            evidence_path = tmp / "evidence.json"
            evidence_path.write_text(json.dumps({"nodes": {
                "doe-science": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06T12:00:00+00:00", "placement": self._listed()},
                "doe-nnsa": {"status": PLACEMENT_ONLY, "checkedAt": "2026-09-06T12:00:00+00:00",
                             "placement": {"status": PLACEMENT_NOT_LISTED, "parentId": "exec-dept-doe",
                                           "urlsRead": ["https://www.energy.gov/leadership-organization"], "checkedAt": "2026-09-06T12:00:00+00:00"}},
            }}), encoding="utf-8")
            sites_path = tmp / "sites.json"
            sites_path.write_text(json.dumps({"exec-dept-doe": ["https://www.energy.gov/leadership-organization"]}), encoding="utf-8")
            result = build_graph(
                [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
                base_graph_path=base, graph_output_path=tmp / "graph.json", nodes_output_path=tmp / "n.json",
                edges_output_path=tmp / "e.json", validity_report_output_path=tmp / "v.json",
                reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=evidence_path, sites_path=sites_path,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = gate_main(["gate", str(result.graph_path)])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("1 checked and not listed", out.getvalue())
            # The three branches under a root with no page, and DOE under a branch with none.
            self.assertIn("4 unreachable", out.getvalue())
            graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
            self.assertIs(index_tree(graph)[0]["doe-nnsa"]["placementVerified"], False)
            self.assertIs(index_tree(graph)[0]["doe-science"]["placementVerified"], True)

            cases = {
                "future date": ("doe-science", lambda n: n.__setitem__("placementVerifiedAt", "2999-01-01T00:00:00+00:00")),
                "invented method": ("doe-science", lambda n: n.__setitem__("placementMethod", "curator_says_so")),
                "no method": ("doe-science", lambda n: n.pop("placementMethod")),
                "text names another unit": ("doe-science", lambda n: n.__setitem__("placementMatchedText", "Office of Environmental Management")),
                "unreachable beside a result": ("doe-science", lambda n: n.__setitem__("placementCheckable", False)),
                "not listed for a different parent": ("doe-nnsa", lambda n: n.__setitem__("placementParentId", "legislative-branch")),
                "not listed without a date": ("doe-nnsa", lambda n: n.pop("placementVerifiedAt")),
            }
            for name, (node_id, mutate) in cases.items():
                with self.subTest(case=name):
                    corrupted = json.loads(json.dumps(graph))
                    mutate(index_tree(corrupted)[0][node_id])
                    path = tmp / f"{uuid.uuid4().hex}.json"
                    path.write_text(json.dumps(corrupted), encoding="utf-8")
                    out = io.StringIO()
                    with redirect_stdout(out):
                        code = gate_main(["gate", str(path)])
                    self.assertEqual(code, 1, f"{name}:\n{out.getvalue()}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class PlacementScriptTests(unittest.TestCase):
    """The verifier's placement pass end to end, against the DOE page fixture
    whose nav names the Office of Science and nothing names NNSA."""

    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"placement-cli-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.sites = self.tmp / "sites.json"
        self.sites.write_text(json.dumps({"exec-dept-doe": ["https://www.energy.gov/about-us"]}), encoding="utf-8")
        self.evidence = self.tmp / "evidence.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra, pages=None):
        pages = pages if pages is not None else {"https://www.energy.gov/about-us": DOE_PAGE}
        out = io.StringIO()
        with mock.patch.object(verify_base_graph, "request_text", lambda url, timeout=30: pages[url]), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=None), \
             redirect_stdout(out):
            code = verify_base_graph.main(["v", "--base-graph", str(self.base), "--sites", str(self.sites),
                                           "--evidence", str(self.evidence), "--sleep", "0", *extra])
        return code, out.getvalue()

    def _records(self):
        return json.loads(self.evidence.read_text(encoding="utf-8"))["nodes"]

    def test_the_pass_records_listed_and_not_listed_against_the_parent(self) -> None:
        code, text = self._run()
        self.assertEqual(code, 0, text)
        self.assertIn("placements to check 2", text)          # Office of Science and NNSA under DOE; the count label is never checked
        records = self._records()
        science = records["doe-science"]["placement"]
        self.assertEqual((science["status"], science["parentId"], science["url"]),
                         (PLACEMENT_LISTED, "exec-dept-doe", "https://www.energy.gov/about-us"))
        self.assertEqual(science["matchedText"], "Office of Science")
        nnsa = records["doe-nnsa"]["placement"]
        self.assertEqual((nnsa["status"], nnsa["urlsRead"]), (PLACEMENT_NOT_LISTED, ["https://www.energy.gov/about-us"]))
        self.assertNotIn("placement", records["doe-labs"], "a count label is not checked for placement either")
        self.assertNotIn("placement", records["exec-dept-doe"], "DOE's parent has no page")
        # And the same run's existence records are unchanged by the pass.
        self.assertEqual(records["doe-science"]["status"], CONFIRMED)
        self.assertEqual(records["doe-nnsa"]["status"], INCONCLUSIVE)

    def test_an_edge_checked_without_the_unit_is_placement_only(self) -> None:
        code, text = self._run("--inherit-depth", "0")     # existence: DOE's own page only
        self.assertEqual(code, 0, text)
        records = self._records()
        self.assertEqual(records["doe-science"]["status"], PLACEMENT_ONLY)
        self.assertEqual(records["doe-science"]["placement"]["status"], PLACEMENT_LISTED)
        self.assertNotIn("sources", records["doe-science"])
        first_checked = records["doe-science"]["placement"]["checkedAt"]

        # A later existence run replaces the record and carries the edge along.
        code, text = self._run()
        self.assertEqual(code, 0, text)
        records = self._records()
        self.assertEqual(records["doe-science"]["status"], CONFIRMED)
        self.assertEqual(records["doe-science"]["method"], METHOD_PARENT_PAGE)
        self.assertEqual(records["doe-science"]["placement"]["checkedAt"], first_checked, "already listed: not fetched again")
        self.assertIn("'placement_already_listed': 1", text)

    def test_a_listed_edge_is_rechecked_when_the_parent_page_changes(self) -> None:
        self._run()
        _, text = self._run("--dry-run")
        self.assertIn("placements to check 1", text)          # NNSA again; Science is listed and skipped
        self.assertNotIn("placement: doe-science", text)
        self.sites.write_text(json.dumps({"exec-dept-doe": ["https://www.energy.gov/leadership-organization"]}), encoding="utf-8")
        _, text = self._run("--dry-run")
        self.assertIn("placements to check 2", text)
        self.assertIn("placement: doe-science  under exec-dept-doe  <-  https://www.energy.gov/leadership-organization", text)
        _, text = self._run("--dry-run", "--recheck")
        self.assertIn("placements to check 2", text)

    def test_the_limit_counts_placements_and_no_placement_skips_them(self) -> None:
        _, text = self._run("--dry-run", "--limit", "1")
        self.assertIn("to check 1  placements to check 0", text)
        _, text = self._run("--dry-run", "--limit", "4")
        self.assertIn("to check 3  placements to check 1", text)
        _, text = self._run("--dry-run", "--no-placement")
        self.assertIn("placements to check 0", text)
        self.assertFalse(self.evidence.exists())

    def test_an_unreadable_parent_page_records_no_placement_at_all(self) -> None:
        def blocked(url, timeout=30):
            raise OSError("Tunnel connection failed: 403 Forbidden")

        out = io.StringIO()
        with mock.patch.object(verify_base_graph, "request_text", blocked), \
             mock.patch.object(verify_base_graph.RobotsPolicy, "_parser", return_value=None), \
             redirect_stdout(out):
            verify_base_graph.main(["v", "--base-graph", str(self.base), "--sites", str(self.sites),
                                    "--evidence", str(self.evidence), "--sleep", "0"])
        self.assertIn("'parent_page_unreadable': 2", out.getvalue())
        for record in self._records().values():
            self.assertNotIn("placement", record)


class FrontendWordingTests(unittest.TestCase):
    """The page's placement wording is the claim the data supports and no
    more. Pinned here because the smoke check needs a browser this suite
    does not."""

    UI = Path(__file__).resolve().parent.parent / "js" / "ui.js"

    def _placement_renderer(self) -> str:
        text = self.UI.read_text(encoding="utf-8")
        start = text.index("function renderPlacementLine(")
        end = text.index("\nfunction ", start + 1)
        return text[start:end]

    def test_each_placement_state_has_its_own_sentence_and_none_says_reports_to(self) -> None:
        body = self._placement_renderer()
        for state, phrase in {
            "listed": "its parent's official page lists it",
            "listed, same read": "the same page read above lists it",
            "not listed": "does not list it as a heading or link — no claim either way",
            "position": "positions are not checked against a page",
            "unreachable": "its parent is a curated grouping with no official page of its own",
            "nothing": "no evidence recorded for where this sits in the hierarchy",
        }.items():
            with self.subTest(state=state):
                self.assertIn(phrase, body)
        self.assertIn("placementMatchedText", body, "the label found is quoted, so the claim can be audited")
        self.assertIn("placementUrl", body)
        for line in body.splitlines():
            if "reports to" in line:
                self.assertTrue(line.strip().startswith("//"), f"a rendered string says 'reports to': {line.strip()}")

    def test_the_cache_bust_is_bumped_everywhere_together(self) -> None:
        import re

        root = self.UI.parent.parent
        versions = set()
        for rel in ("index.html", "js/ui.js", "js/graph.js"):
            found = re.findall(r"\?v=([0-9a-z]+)", (root / rel).read_text(encoding="utf-8"))
            self.assertTrue(found, rel)
            versions.update(found)
        self.assertEqual(len(versions), 1, f"modules would load against each other's stale copies: {versions}")
