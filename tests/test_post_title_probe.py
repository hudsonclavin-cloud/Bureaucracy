"""The post-title probe is the tool a curated rename is argued from.

It exists because the first position pass found that 839 position nodes are
named with their parent organisation's name embedded verbatim, so the most
recognisable posts in the government could never match a page — energy.gov
says "Secretary of Energy" where the graph says "Secretary of Department of
Energy (DOE)", and justice.gov says "The Attorney General" where the graph
asserts a "Secretary of Department of Justice (DOJ)" that does not exist.

Two properties matter, and they pull against each other. It must surface the
page's own wording for a title the graph is missing, or a curator has nothing
to act on. And it must write NOTHING and conclude nothing, or a proposal
becomes a published claim without ever passing the gate.
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

from scripts import probe_post_titles

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
DEPT_ID = "exec-dept-doj"
URL = "https://www.justice.gov/about"
BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States",
    "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": DEPT_ID, "name": "Department of Justice (DOJ)", "type": "Cabinet Department", "children": [
                # The template-generated title: an office that does not exist.
                {"id": "doj-sec", "name": "Secretary of Department of Justice (DOJ)", "type": "Position", "children": []},
                # One the page really does label, so "labelled" is exercised too.
                {"id": "doj-sg", "name": "Solicitor General", "type": "Position", "children": []},
                # Refused before any comparison: a bare job title.
                {"id": "doj-para", "name": "Paralegal", "type": "Position", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
PAGE = (
    "<html><body><nav><a href='/ag'>The Attorney General</a></nav>"
    "<main><h2>Solicitor General</h2>"
    "<p>The Department of Justice enforces the law and defends the interests of the United States. "
    "This paragraph is long enough that the page clears the readable-text floor, which is what "
    "separates a page a person could have read from a JavaScript shell returning nothing at all.</p>"
    "<p>Sentences like this one are prose and must never be offered as an office title.</p>"
    "</main></body></html>"
)


class OfficeShapeTests(unittest.TestCase):
    def test_only_office_shaped_labels_are_offered_as_candidates(self) -> None:
        for key in (
            "attorney general", "deputy attorney general", "secretary of energy",
            "under secretary for science", "inspector general", "chief of staff",
        ):
            with self.subTest(key=key):
                self.assertTrue(probe_post_titles.looks_like_an_office(key))
        for key in (
            "",                                              # nothing
            "secretary",                                     # one token: the floor a post never clears
            "about",                                         # page furniture
            "the department of justice enforces the law and defends the interests",  # a sentence
            "news and press releases",                       # a nav item that is not an office
        ):
            with self.subTest(key=key):
                self.assertFalse(probe_post_titles.looks_like_an_office(key))


class ProbeOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"probe-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.sites = self.tmp / "sites.json"
        self.sites.write_text(json.dumps({DEPT_ID: [URL]}), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(TEST_TMP_ROOT / self.tmp.name, ignore_errors=True)

    def _run(self, *extra):
        argv = ["probe", "--base-graph", str(self.base), "--sites", str(self.sites), "--sleep", "0", *extra]
        out = io.StringIO()
        with mock.patch.object(probe_post_titles, "request_text", lambda url, timeout=30: PAGE), \
             mock.patch.object(probe_post_titles.RobotsPolicy, "_parser", return_value=None), \
             redirect_stdout(out):
            code = probe_post_titles.main(argv)
        return code, out.getvalue()

    def test_it_names_the_title_the_page_carries_that_the_graph_lacks(self) -> None:
        code, text = self._run()
        self.assertEqual(code, 0, text)
        # The curated title is reported missing...
        self.assertIn("not labelled        'Secretary of Department of Justice (DOJ)'", text)
        # ...and the page's own word for the office is offered beside it, with
        # the region, so a curator can see it came out of the site's chrome.
        self.assertIn("The Attorney General", text)
        self.assertIn("[navigation]", text)
        # A title the page really does label is reported as such, not as a gap.
        self.assertIn("labelled            'Solicitor General'", text)
        # A bare job title is refused before any comparison is attempted.
        self.assertIn("not checkable       'Paralegal'", text)
        self.assertIn("post_title_is_a_bare_job_title", text)
        # Prose is never offered as a title.
        self.assertNotIn("enforces the law", text)

    def test_it_concludes_nothing_and_says_so(self) -> None:
        _, text = self._run()
        self.assertIn("proposes and never concludes", text)
        self.assertIn("Nothing was written", text)

    def test_it_writes_no_file_at_all(self) -> None:
        """The whole safety claim. A probe that quietly wrote evidence would
        put a proposal on the site without it ever passing the gate."""
        before = {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}
        self._run()
        after = {p: p.read_bytes() for p in self.tmp.rglob("*") if p.is_file()}
        self.assertEqual(after, before, "the probe changed a file")
        repo = Path(probe_post_titles.__file__).resolve().parents[1]
        for tracked in ("data/verification/evidence.json", "data/federal_gov_complete_1.json"):
            path = repo / tracked
            if path.exists():
                self.assertNotIn(
                    "probe_post_titles", path.read_text(encoding="utf-8")[:4000],
                    f"{tracked} names the probe as a writer",
                )

    def test_a_dry_run_fetches_nothing(self) -> None:
        def explode(url, timeout=30):
            raise AssertionError("a dry run fetched a page")

        out = io.StringIO()
        with mock.patch.object(probe_post_titles, "request_text", explode), redirect_stdout(out):
            code = probe_post_titles.main(
                ["probe", "--base-graph", str(self.base), "--sites", str(self.sites), "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn(DEPT_ID, out.getvalue())
        self.assertIn("3 posts", out.getvalue())


if __name__ == "__main__":
    unittest.main()
