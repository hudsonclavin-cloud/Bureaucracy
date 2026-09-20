"""The crawl rules this project follows, pinned to the standard it cites.

`politeness.py` quotes RFC 9309 to justify what it does with a robots.txt
that was never read. For most of this repository's life those quotes were
marked "[Likely, from memory]" because rfc-editor.org was refused by the
environment's proxy — a citation nobody could check, in a module whose whole
job is not making unfounded claims.

The allowlist reached the host on 2026-09-15 and the standard is now
committed verbatim at `tests/fixtures/standards/rfc9309.txt`. These tests
keep the code and the document honest with each other: the digest is
recomputed from the bytes on disk, and every rule the module acts on has to
be findable in the text, so a paraphrase that drifts from the standard fails
here rather than shipping as a justification.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.robotparser import RobotFileParser

from data_pipeline.verification import politeness

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "standards"
RFC = FIXTURES / "rfc9309.txt"
META = FIXTURES / "rfc9309.txt.meta.json"


def normalised(text: str) -> str:
    """The RFC is hard-wrapped at 72 columns, so a sentence-length quote
    crosses newlines. Whitespace is collapsed; nothing else is."""
    return re.sub(r"\s+", " ", text).strip()


class TheCommittedStandardTests(unittest.TestCase):
    def setUp(self) -> None:
        if not RFC.exists():  # pragma: no cover - the fixture is tracked
            self.skipTest("RFC 9309 fixture not present")
        self.raw = RFC.read_bytes()
        self.text = normalised(self.raw.decode("utf-8"))
        self.meta = json.loads(META.read_text(encoding="utf-8"))

    def test_the_digest_is_recomputed_from_the_bytes_on_disk(self) -> None:
        """The check that makes `sha256` a claim rather than a copied string.
        A hand-typed RFC would otherwise read exactly like a fetched one."""
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), self.meta["sha256"])
        self.assertEqual(len(self.raw), self.meta["bytes"])
        self.assertEqual(self.meta["status"], 200)
        self.assertTrue(str(self.meta["url"]).startswith("https://www.rfc-editor.org/"))

    def test_it_is_the_document_it_claims_to_be(self) -> None:
        # The RFC names itself in its own header block, not as "RFC 9309".
        self.assertIn("Request for Comments: 9309", self.text)
        self.assertIn("Robots Exclusion Protocol", self.text)
        self.assertIn("Category: Standards Track", self.text)

    def test_the_two_rules_the_module_acts_on_are_really_in_it(self) -> None:
        """Quoted, not paraphrased. Each maps to one branch of `allows()`."""
        unavailable = (
            "If a server status code indicates that the robots.txt file is "
            "unavailable to the crawler, then the crawler MAY access any resources "
            "on the server."
        )
        unreachable = (
            "If the robots.txt file is unreachable due to server or network errors, "
            "this means the robots.txt file is undefined and the crawler MUST assume "
            "complete disallow."
        )
        self.assertIn(unavailable, self.text, "2.3.1.3 is not in the committed RFC as quoted")
        self.assertIn(unreachable, self.text, "2.3.1.4 is not in the committed RFC as quoted")
        # The ranges the module keys off, also from the document itself.
        self.assertIn("such status codes are in the 400-499 range", self.text)
        self.assertIn("server errors are identified by status codes in the 500-599 range", self.text)

    def test_the_module_quotes_the_standard_it_ships_beside(self) -> None:
        """The docstring's block quote must match the document, since it is
        what a reader of the code is being asked to take on trust."""
        doc = normalised(politeness.__doc__ or "")
        for fragment in (
            "the crawler MAY access any resources on the server",
            "MUST assume complete disallow",
        ):
            self.assertIn(fragment, doc)
            self.assertIn(fragment, self.text, "the module quotes words the RFC does not use")


class WhatTheModuleDoesWithEachRuleTests(unittest.TestCase):
    """The mapping from the standard to the four outcomes, stated once.

    `tests/test_verification.py` exercises these against a mocked network;
    this asserts the classification constants themselves carry the meaning
    the docstring claims, so renaming one without thinking fails a test.
    """

    def test_each_outcome_is_distinct_and_named_for_what_happened(self) -> None:
        kinds = [politeness.RULES, politeness.NO_FILE, politeness.REFUSED,
                 politeness.UNREACHABLE, politeness.UNFETCHABLE]
        self.assertEqual(len(set(kinds)), 5, "two outcomes share a name")

    def test_the_deliberate_deviation_is_the_only_one(self) -> None:
        """401/403 is where this project is stricter than RFC 9309, on
        purpose. Everything else follows the standard: other 4xx allows,
        5xx refuses, and a network error refuses."""
        self.assertEqual(politeness.REFUSED, "refused")
        doc = normalised(politeness.__doc__ or "")
        self.assertIn("deliberately stricter than the rule we cite", doc)
        self.assertNotIn("[Likely, from memory", doc,
                         "the citation is verifiable now; drop the hedge")


class TheStandard4xxHostListTests(unittest.TestCase):
    """The one per-host deviation from the deviation, pinned both ways.

    `politeness.py` is deliberately stricter than RFC 9309 on a robots.txt
    answered 401/403: the standard calls the file "Unavailable" and permits
    access, and this project refuses anyway. `STANDARD_4XX_HOSTS` names the
    hosts where that stricter choice is withdrawn and the standard's own rule
    applies. It is a list, not a switch, so these tests assert what it does
    NOT reach as hard as what it does -- a listing that quietly became a
    global relaxation would pass a one-directional test.
    """

    def file(self, kind: str, status: int | None = None, detail: str = "") -> object:
        return politeness.RobotsFile(kind, status, detail=detail)

    def verdict(self, url: str, found: object) -> tuple[bool, str]:
        policy = politeness.RobotsPolicy(user_agent="test-agent/1.0")
        policy._file = lambda _url, _found=found: _found  # type: ignore[assignment]
        return policy.allows(url)

    def test_the_list_carries_a_reason_for_every_host(self) -> None:
        """An entry is a decision, so it has to say why it was made and
        when. A bare hostname records nothing a reviewer could weigh."""
        self.assertTrue(politeness.STANDARD_4XX_HOSTS, "the list is empty")
        for host, reason in politeness.STANDARD_4XX_HOSTS.items():
            self.assertEqual(host, host.lower().strip(), host)
            self.assertNotIn("/", host, f"{host} is a host, not a URL")
            self.assertGreater(len(reason), 80, f"{host}: the reason is a stub")
            self.assertRegex(reason, r"\b20\d\d-\d\d-\d\d\b",
                             f"{host}: the reason names no date")

    def test_a_listed_host_is_recognised_however_the_netloc_is_written(self) -> None:
        for netloc in ("escs.opm.gov", "ESCS.OPM.GOV", "escs.opm.gov:443",
                       "user@escs.opm.gov", " escs.opm.gov "):
            self.assertEqual(politeness.standard_4xx_host(netloc), "escs.opm.gov", netloc)

    def test_a_host_that_merely_ends_with_a_listed_one_is_not_listed(self) -> None:
        """Substring matching is how an allowlist becomes a wildcard."""
        for netloc in ("opm.gov", "www.opm.gov", "escs.opm.gov.example.com",
                       "notescs.opm.gov", "", "escs.opm.govv"):
            self.assertIsNone(politeness.standard_4xx_host(netloc), netloc)

    def test_a_listed_host_answering_403_is_allowed_by_the_standard(self) -> None:
        allowed, why = self.verdict("https://escs.opm.gov/escs-net/api/pbpub/download-data",
                                    self.file(politeness.REFUSED, 403))
        self.assertTrue(allowed)
        self.assertIn("could not be read (403)", why)
        self.assertIn("RFC 9309 2.3.1.3", why)

    def test_the_verdict_never_reads_as_though_a_rule_had_been_seen(self) -> None:
        """The whole point of the module: no record may claim robots.txt was
        fetched and permitted the path, because it was not fetched."""
        _, why = self.verdict("https://escs.opm.gov/escs-net/api/pbpub/download-data",
                              self.file(politeness.REFUSED, 403))
        self.assertIn("no rule was seen", why)
        self.assertNotIn("allows", why)
        self.assertNotIn("allowed by robots.txt", why)

    def test_an_unlisted_host_answering_403_is_still_refused(self) -> None:
        for status in (401, 403):
            allowed, why = self.verdict("https://www.state.gov/about/",
                                        self.file(politeness.REFUSED, status))
            self.assertFalse(allowed, status)
            self.assertIn("refused by policy", why)
            self.assertIn("no rule was seen", why)

    def test_a_listed_host_is_still_refused_on_a_5xx(self) -> None:
        """2.3.1.4, where the standard itself requires complete disallow.
        The listing withdraws this project's extra strictness, never the
        standard's own rule."""
        for status in (500, 502, 503):
            allowed, why = self.verdict("https://escs.opm.gov/escs-net/api/pbpub/download-data",
                                        self.file(politeness.UNREACHABLE, status))
            self.assertFalse(allowed, status)
            self.assertIn("while the site is failing", why)

    def test_a_listed_host_is_still_refused_on_a_network_failure(self) -> None:
        allowed, why = self.verdict("https://escs.opm.gov/escs-net/api/pbpub/download-data",
                                    self.file(politeness.UNFETCHABLE, None, detail="URLError"))
        self.assertFalse(allowed)
        self.assertIn("complete disallow", why)

    def test_a_listed_host_that_does_publish_rules_obeys_them(self) -> None:
        """The listing is about an unreadable file. A host on it that later
        publishes a robots.txt disallowing the path is obeyed."""
        parser = RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /escs-net/"])
        found = politeness.RobotsFile(politeness.RULES, 200, parser=parser)
        allowed, why = self.verdict(
            "https://escs.opm.gov/escs-net/api/pbpub/download-data", found)
        self.assertFalse(allowed)
        self.assertIn("disallows", why)

    def test_the_fixture_fetcher_rests_on_the_same_list(self) -> None:
        """`scripts/fetch_fixture.py` used to carry its own copy of the
        401/403 rule. A per-host exception written in one place and not the
        other is how a fetch gets refused here and allowed there."""
        source = (Path(__file__).resolve().parent.parent
                  / "scripts" / "fetch_fixture.py").read_text(encoding="utf-8")
        self.assertIn("from data_pipeline.verification.politeness import standard_4xx_host",
                      source)
        self.assertNotIn("STANDARD_4XX_HOSTS: dict", source,
                         "the fetcher has grown its own copy of the list")

    def test_the_docstring_records_the_change_rather_than_making_it_quietly(self) -> None:
        doc = normalised(politeness.__doc__ or "")
        self.assertIn("2026-09-20", doc)
        self.assertIn("per-host list, not a switch", doc)
        self.assertIn("deliberately stricter than the rule we cite", doc,
                      "the general refusal must still be documented as the default")


if __name__ == "__main__":
    unittest.main()
