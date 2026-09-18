"""The candidate-page probe is the instrument a nomination is argued from.

Every prior nomination pass ran without network and proposed URLs from
memory. 304 organisations still have no candidate page, and the declines
include units that plainly do have one: USPTO was declined `covered_by_parent`
while uspto.gov exists and reads fine. The runbook has always said an agent
with network should read the page rather than guess at it; this script is how.

Two properties matter and they pull against each other. It must give the same
answer `verify_base_graph.py` will give, or it is not worth running -- so it
calls the verifier's own `find_label_region_rule`, honours the same
readable-text floor and the same robots policy. And it must decide NOTHING and
write nothing, or a probe becomes a published claim that never passed a gate.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from data_pipeline.verification.evidence import parse_page
from data_pipeline.verification.politeness import NO_FILE, REFUSED, RobotsFile
from scripts import probe_candidate_pages as probe

ORG_ID = "exec-dept-doc-nist"
BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-dept-doc", "name": "Department of Commerce", "type": "Cabinet Department", "children": [
                {"id": ORG_ID, "name": "National Institute of Standards and Technology", "type": "Bureau",
                 "children": [
                     {"id": "nist-dir", "name": "Director of NIST", "type": "Position", "children": []},
                     {"id": "nist-ig", "name": "Inspector General", "type": "Position", "children": []},
                 ]},
                # The curated name no page will ever carry -- the case that
                # made `page_read_does_not_name_it` necessary.
                {"id": "exec-dept-doc-uspto", "name": "USPTO — Patent & Trademark Office", "type": "Bureau",
                 "children": []},
            ]},
        ]},
    ],
}
# Long enough to clear the verifier's readable-text floor, so "not labelled"
# is a verdict the verifier would also reach rather than an artefact of a
# page that is a banner around no body.
PAGE = (
    "<html><body><nav><a href='/ig'>Inspector General</a></nav>"
    "<main><h1>National Institute of Standards and Technology</h1>"
    "<p>The bureau measures things and publishes standards, and this sentence exists so the page "
    "carries enough readable text outside its chrome to count as a page a person could have read, "
    "which is the floor the verifier applies before it will record a negative about any unit.</p>"
    "<p>More prose, for the same reason, because a short page records nothing either way, and a "
    "probe that called such a page a negative would be predicting a verdict the verifier never "
    "reaches on it at all.</p>"
    "</main></body></html>"
)


def run(argv, page_html=PAGE, robots=None):
    """Drive main() with the network replaced, and return (code, stdout)."""
    buffer = io.StringIO()
    with mock.patch.object(probe, "load_base_graph", return_value=json.loads(json.dumps(BASE))), \
         mock.patch.object(probe, "load_official_sites", return_value={"exec-dept-doc": ["https://www.commerce.gov/"]}), \
         mock.patch.object(probe, "request_text", return_value=page_html), \
         mock.patch.object(probe.RobotsPolicy, "_fetch", return_value=robots or RobotsFile(NO_FILE, 404)), \
         mock.patch.object(probe.time, "sleep", lambda _s: None), \
         redirect_stdout(buffer):
        code = probe.main(["probe_candidate_pages.py", *argv])
    return code, buffer.getvalue()


class VerdictTests(unittest.TestCase):
    def test_the_probe_gives_the_verifiers_own_answer(self) -> None:
        code, out = run(["--url", "https://www.nist.gov/", "--ids", ORG_ID, "--json"])
        self.assertEqual(code, 0)
        result = json.loads(out)["pages"][0]["results"][0]
        self.assertEqual(result["verdict"], probe.LABELLED)
        self.assertEqual(result["matchedText"], "National Institute of Standards and Technology")
        self.assertEqual(result["region"], "content")

    def test_a_curated_name_the_page_never_says_is_not_labelled(self) -> None:
        """The USPTO case: the URL is right, the name is the problem. A probe
        that reported this as a bad URL would send the next pass hunting for
        another page that also cannot exist."""
        code, out = run(["--url", "https://www.uspto.gov/", "--ids", "exec-dept-doc-uspto", "--json"])
        self.assertEqual(code, 0)
        result = json.loads(out)["pages"][0]["results"][0]
        self.assertEqual(result["verdict"], probe.NOT_LABELLED)
        self.assertTrue(json.loads(out)["pages"][0]["readable"])

    def test_a_site_navigation_hit_is_reported_apart_from_a_content_one(self) -> None:
        """A mega-menu listing holds for every page on the host: real evidence
        for an organisation, furniture for a post. The probe prints the region
        and refuses to collapse the two, because the verifier does not."""
        code, out = run(["--url", "https://www.nist.gov/", "--ids", ORG_ID, "--with-children", "--json"])
        self.assertEqual(code, 0)
        rows = {r["name"]: r for r in json.loads(out)["pages"][0]["results"]}
        self.assertEqual(rows["Inspector General"]["verdict"], probe.LABELLED_IN_NAV)
        self.assertEqual(rows["Inspector General"]["region"], "navigation")
        self.assertIn("never confirmed from site-wide chrome", rows["Inspector General"]["detail"])
        # A one-word post title is refused before any comparison, by type.
        self.assertEqual(rows["Director of NIST"]["verdict"], probe.LABELLED
                         if "Director of NIST" in PAGE else probe.NOT_LABELLED)

    def test_a_refused_host_reports_the_refusal_and_reads_nothing(self) -> None:
        code, out = run(["--url", "https://www.nro.gov/", "--ids", ORG_ID, "--json"],
                        robots=RobotsFile(REFUSED, 403, attempts=3))
        self.assertEqual(code, 0)
        page = json.loads(out)["pages"][0]
        self.assertIn("refused by policy", page["error"])
        self.assertNotIn("results", page)

    def test_an_unreadable_page_is_flagged_rather_than_called_a_negative(self) -> None:
        """Below the floor the verifier records nothing either way, so a probe
        that said "not labelled" would be predicting a verdict it never
        reaches. www.hud.gov/about served a banner and a footer around no body
        and was recorded as "checked and not listed" fifteen times."""
        code, out = run(["--url", "https://www.hud.gov/about", "--ids", ORG_ID, "--json"],
                        page_html="<html><body><main><p>Short.</p></main></body></html>")
        self.assertEqual(code, 0)
        page = json.loads(out)["pages"][0]
        self.assertFalse(page["readable"])


class ItWritesNothingTests(unittest.TestCase):
    def test_no_file_is_opened_for_writing(self) -> None:
        real_open = open
        opened: list[tuple] = []

        def watched(path, mode="r", *rest, **kwargs):
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                opened.append((str(path), mode))
            return real_open(path, mode, *rest, **kwargs)

        with mock.patch("builtins.open", watched):
            code, _ = run(["--url", "https://www.nist.gov/", "--ids", ORG_ID, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(opened, [], f"the probe opened files for writing: {opened}")

    def test_the_uncovered_listing_fetches_nothing(self) -> None:
        with mock.patch.object(probe, "request_text", side_effect=AssertionError("fetched during --uncovered")):
            code, out = run(["--uncovered"])
        self.assertEqual(code, 0)
        self.assertIn("organisations with no candidate page", out)

    def test_it_never_prints_a_verifier_status_word(self) -> None:
        """Its verdicts are deliberately not `confirmed`/`not_found`: a reader
        must not be able to mistake a probe for a record in evidence.json."""
        _, out = run(["--url", "https://www.nist.gov/", "--ids", ORG_ID, "--with-children"])
        for word in ("confirmed", "not_found", "inconclusive", "fetch_failed", "not_checkable"):
            self.assertNotIn(word, out, f"the probe printed the verifier's own status word {word!r}")
        self.assertIn("This is a reading, not a record.", out)


class PageTextTests(unittest.TestCase):
    def test_probe_page_is_pure_given_a_parsed_page(self) -> None:
        page = parse_page(PAGE)
        nodes = [{"id": ORG_ID, "name": "National Institute of Standards and Technology", "type": "Bureau"}]
        first = probe.probe_page(page, nodes)
        second = probe.probe_page(page, nodes)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["verdict"], probe.LABELLED)


if __name__ == "__main__":
    unittest.main()
