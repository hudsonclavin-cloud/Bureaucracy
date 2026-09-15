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


if __name__ == "__main__":
    unittest.main()
