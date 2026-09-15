"""A post confirmed by its own organisation's page, and the four things that
narrow the claim to what was actually read.

4,604 of this graph's 5,392 curated nodes are positions and until 2026-09-15
not one of them carried evidence of any kind: the verifier's `--include-
positions` flag existed but had never been run, and the nomination harness
refused a position outright. The page that can speak for a post is its
organisation's, which the verifier already fetches for the organisation
itself, so the marginal cost of checking a post is one string comparison.

What makes it honest rather than merely cheap is what it refuses, and each
refusal is pinned here in both directions:

  - a bare job title ("Hydrologist", "Warden", "Director") is never checked.
    Scoping to one organisation's page supplies the context a qualified
    title needs, but no scoping rescues a single common noun.
  - a title found only in the site-wide navigation, header or footer never
    confirms. The chrome standard is host-blind inside `.gov`, and job
    titles are standard site furniture in a way organisation names are not.
  - the claim is `name_labelled_on_its_organisations_official_page`, not the
    organisation methods, because the page belongs to the post's employer.
  - no placement claim is ever published for a post: the organisation's page
    naming it is ONE observation, and publishing it as both existence and
    edge evidence would present one reading as two corroborating findings.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    build_graph,
    canonical_name_key,
    index_tree,
    is_post_node,
)
from data_pipeline.verification.evidence import (
    CONFIRMED,
    INCONCLUSIVE,
    METHOD_OWN_PAGE,
    METHOD_PARENT_PAGE,
    METHOD_POST_ON_ORG_PAGE,
    NOT_CHECKABLE,
    PLACEMENT_LISTED,
    REASON_POST_ONLY_IN_NAVIGATION,
    REASON_POST_TITLE_TOO_GENERIC,
    apply_evidence_to_tree,
    label_matches,
    placement_from_record,
    uncheckable_reason,
    uncheckable_reason_for_node,
    verify_node,
    verify_placement,
)
from scripts import validate_published_graph as gate
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
DEPT_ID = "exec-dept-defense"
SEC_ID = "exec-dept-defense-secretary"
IG_ID = "exec-dept-defense-ig"
BARE_ID = "exec-dept-defense-hydrologist"
URL = "https://www.defense.gov/"

BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": DEPT_ID, "name": "Department of Defense", "type": "Cabinet Department", "children": [
                {"id": SEC_ID, "name": "Secretary of Defense", "type": "Position", "children": []},
                # The stamped administrative title: "Inspector General" is the
                # name of 72 nodes in the real graph. Only the page it was
                # found on and the words on it separate one from another.
                {"id": IG_ID, "name": "Inspector General", "type": "Position", "children": []},
                {"id": BARE_ID, "name": "Hydrologist", "type": "Position", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}

# Long enough that the page counts as one a person could have read, which is
# the condition for concluding anything negative from it.
PROSE = (
    "<p>The Department provides the military forces needed to deter war and ensure the nation's "
    "security. This paragraph runs long enough that the page clears the readable-text floor, which "
    "is what separates a page somebody could have read from a JavaScript shell or a bot challenge "
    "returning two hundred OK with nothing in it. A few more clauses make certain of that.</p>"
)
# Secretary in the body; Inspector General only in the footer, which is
# exactly the shape this design refuses for a post.
PAGE = (
    "<html><body><nav><a href='/ig'>Inspector General</a></nav>"
    "<main><h1>Secretary of Defense</h1>" + PROSE + "</main>"
    "<footer><a href='/ig'>Inspector General</a></footer></body></html>"
)
# The same title, in the body this time.
PAGE_IG_IN_BODY = "<html><body><main><h2>Inspector General</h2>" + PROSE + "</main></body></html>"
ORG_IN_NAV_ONLY = "<html><body><nav><a>Department of Defense</a></nav><main>" + PROSE + "</main></body></html>"


def fetch_for(pages):
    def fetch(url):
        if url not in pages:
            raise OSError("connect_rejected")
        return pages[url]
    return fetch


SEC = {"id": SEC_ID, "name": "Secretary of Defense", "type": "Position"}
IG = {"id": IG_ID, "name": "Inspector General", "type": "Position"}
BARE = {"id": BARE_ID, "name": "Hydrologist", "type": "Position"}
DEPT = {"id": DEPT_ID, "name": "Department of Defense", "type": "Cabinet Department"}


class PostTitleFloorTests(unittest.TestCase):
    def test_a_bare_job_title_is_refused_for_a_post_and_allowed_for_an_organisation(self) -> None:
        """The floor is raised by what the node IS, not by how it reads."""
        for name in ("Hydrologist", "Warden", "Director", "Specialist", "Judge", "Archivist"):
            with self.subTest(name=name):
                self.assertEqual(uncheckable_reason(name, is_post=True), REASON_POST_TITLE_TOO_GENERIC)
                # The same word as an organisation's name clears the older,
                # lower floor: this rule adds to that one, it does not replace it.
                self.assertIsNone(uncheckable_reason(name))
        # Two tokens is the floor, and the parenthetical never counts toward it:
        # "Director (×3)" reduces to "director" and is refused like the rest.
        for name in ("Director (×3)", "U.S. Attorney (×94, appointed by President)", "Specialist (×multiple)"):
            with self.subTest(name=name):
                self.assertIsNotNone(uncheckable_reason(name, is_post=True))
        for name in ("Secretary of Defense", "Inspector General", "Deputy Director", "Chief of Staff"):
            with self.subTest(name=name):
                self.assertIsNone(uncheckable_reason(name, is_post=True))

    def test_the_node_typed_wrapper_grants_and_withdraws_the_floor_with_the_type(self) -> None:
        self.assertEqual(uncheckable_reason_for_node(BARE), REASON_POST_TITLE_TOO_GENERIC)
        # Re-typed as an office, the same name clears: the stricter rule is
        # granted by the node's kind, the same way the committee fold is.
        self.assertIsNone(uncheckable_reason_for_node({**BARE, "type": "Office"}))
        self.assertIsNone(uncheckable_reason_for_node(SEC))
        self.assertIsNone(uncheckable_reason_for_node(DEPT))

    def test_the_gate_s_label_test_is_the_matcher_s_label_test(self) -> None:
        """The gate keeps a stdlib copy of `label_matches`, and a copy that
        drifts EITHER way is a fault: too loose lets a label for a different
        office through, too strict rejects a confirmation the matcher made
        correctly. The first version here was too strict and refused the
        Senate's own heading for its own officer.
        """
        cases = [
            ("Sergeant at Arms", "U.S. Senate: About the Sergeant at Arms"),
            ("Sergeant at Arms", "Sergeant at Arms"),
            ("Chief Administrative Officer", "CAO | Chief Administrative Officer |"),
            ("Office of Science", "About the Office of Science"),
            ("Office of Science", "Office of Science — Advancing discovery"),
            # Must be refused: a different office, a superset, a substring.
            ("Secretary of Defense", "Deputy Secretary of Defense"),
            ("Office of Science", "Office of Science and Technology Policy"),
            ("Press Secretary", "Assistant Press Secretary"),
            ("Inspector General", "Deputy Inspector General"),
            ("Sergeant at Arms", "Readiness"),
            ("Sergeant at Arms", ""),
        ]
        for name, matched in cases:
            with self.subTest(name=name, matched=matched):
                self.assertEqual(
                    gate.label_names({"name": name}, matched),
                    label_matches(canonical_name_key(name), matched),
                    f"the gate and the matcher disagree about {matched!r} naming {name!r}",
                )

    def test_the_gate_s_post_mirror_is_the_exporter_s_function(self) -> None:
        """The gate is stdlib-only and cannot import the pipeline, so it keeps
        its own copy; a copy that drifts would gate the wrong nodes."""
        for type_text in (
            "Position", "position", "Senior Position", "Role", "Office Holder",
            "Office", "Cabinet Department", "Committee", "Agency", "", None,
        ):
            with self.subTest(type=type_text):
                self.assertEqual(gate.is_post({"type": type_text}), is_post_node({"type": type_text}))


class PostPageMatchTests(unittest.TestCase):
    def _run(self, node, html=PAGE):
        return verify_node(
            node, [URL], fetch=fetch_for({URL: html}),
            now="2026-09-13T00:00:00+00:00", site_from=DEPT_ID, is_own_page=False,
        )

    def test_a_post_named_in_the_page_body_is_confirmed_under_its_own_method(self) -> None:
        record = self._run(SEC)
        self.assertEqual(record["status"], CONFIRMED)
        self.assertEqual(record["method"], METHOD_POST_ON_ORG_PAGE)
        self.assertNotIn(record["method"], (METHOD_OWN_PAGE, METHOD_PARENT_PAGE))
        self.assertTrue(record["isPost"])
        source = record["sources"][0]
        self.assertEqual((source["matchedText"], source["matchedIn"]), ("Secretary of Defense", "content"))

    def test_a_title_only_in_the_site_chrome_confirms_nothing_and_says_why(self) -> None:
        record = self._run(IG)
        self.assertNotEqual(record["status"], CONFIRMED)
        self.assertNotIn("sources", record)
        self.assertEqual([f["reason"] for f in record["failures"]], [REASON_POST_ONLY_IN_NAVIGATION])
        # Nothing was concluded, so it is inconclusive rather than not_found:
        # an organisation's page is not obliged to name every post it carries.
        self.assertEqual(record["status"], INCONCLUSIVE)
        # The same title in the body confirms, so the refusal is about WHERE
        # the label sat and nothing else.
        in_body = self._run(IG, PAGE_IG_IN_BODY)
        self.assertEqual((in_body["status"], in_body["method"]), (CONFIRMED, METHOD_POST_ON_ORG_PAGE))
        self.assertEqual(in_body["sources"][0]["matchedIn"], "content")

    def test_an_organisation_is_still_confirmed_from_the_site_chrome(self) -> None:
        """The asymmetry is the whole point, so a regression on the older
        path would silently halve the organisations this project can verify:
        the first live run's DOI, DOL, Treasury, NSF and NASA listings were
        all mega-menu matches."""
        record = verify_node(
            DEPT, [URL], fetch=fetch_for({URL: ORG_IN_NAV_ONLY}),
            now="2026-09-13T00:00:00+00:00", site_from=DEPT_ID, is_own_page=True,
        )
        self.assertEqual((record["status"], record["method"]), (CONFIRMED, METHOD_OWN_PAGE))
        self.assertEqual(record["sources"][0]["matchedIn"], "navigation")

    def test_a_bare_title_is_never_fetched_against(self) -> None:
        record = self._run(BARE)
        self.assertEqual((record["status"], record["reason"]), (NOT_CHECKABLE, REASON_POST_TITLE_TOO_GENERIC))
        self.assertNotIn("sources", record)


class PostsGetNoPlacementClaimTests(unittest.TestCase):
    """Three independent guards, because one observation must not publish as
    two findings and because the "N of M organisation placements" line counts
    a denominator that excludes positions."""

    def test_the_verifier_writes_no_placement_block_for_a_post(self) -> None:
        fetch = fetch_for({URL: PAGE})
        self.assertIsNone(verify_placement(SEC, DEPT_ID, [URL], fetch=fetch, now="2026-09-13T00:00:00+00:00"))
        # The identical page and name, typed as an office: a block IS written,
        # so the refusal is the type and not the page.
        block = verify_placement({**SEC, "type": "Office"}, DEPT_ID, [URL], fetch=fetch, now="2026-09-13T00:00:00+00:00")
        self.assertEqual(block["status"], PLACEMENT_LISTED)

    def test_a_post_confirmation_is_never_promoted_into_placement_evidence(self) -> None:
        post = {"status": CONFIRMED, "method": METHOD_POST_ON_ORG_PAGE, "siteFrom": DEPT_ID,
                "sources": [{"url": URL, "matchedText": "Secretary of Defense", "matchedIn": "content"}]}
        self.assertIsNone(placement_from_record(post, DEPT_ID))
        # The organisation method on the same record IS promoted — that is the
        # behaviour the distinct method name exists to stay clear of.
        self.assertIsNotNone(placement_from_record({**post, "method": METHOD_PARENT_PAGE}, DEPT_ID))

    def test_the_exporter_refuses_a_placement_block_that_reaches_a_post_anyway(self) -> None:
        tree = json.loads(json.dumps(BASE))
        record = verify_node(SEC, [URL], fetch=fetch_for({URL: PAGE}), now="2026-09-13T00:00:00+00:00",
                             site_from=DEPT_ID, is_own_page=False)
        # Hand-made, of the shape an older evidence file could carry.
        record["placement"] = {"status": PLACEMENT_LISTED, "parentId": DEPT_ID, "url": URL,
                               "matchedText": "Secretary of Defense", "checkedAt": "2026-09-13T00:00:00+00:00"}
        stats = apply_evidence_to_tree(tree, {SEC_ID: record})
        node = index_tree(tree)[0][SEC_ID]
        self.assertEqual(stats["placements_refused_post"], 1)
        for field in ("placementVerified", "placementMethod", "placementUrl", "placementMatchedText"):
            self.assertNotIn(field, node)
        # ...and the existence claim it earned is untouched by that refusal.
        self.assertEqual(node["verificationMethod"], METHOD_POST_ON_ORG_PAGE)


class ApplyAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"post-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _records(self):
        fetch = fetch_for({URL: PAGE})
        now = "2026-09-13T00:00:00+00:00"
        return {
            SEC_ID: verify_node(SEC, [URL], fetch=fetch, now=now, site_from=DEPT_ID, is_own_page=False),
            DEPT_ID: verify_node(DEPT, [URL], fetch=fetch, now=now, site_from=DEPT_ID, is_own_page=True),
        }

    def test_the_exporter_publishes_the_label_and_withdraws_the_whole_shape(self) -> None:
        tree = json.loads(json.dumps(BASE))
        apply_evidence_to_tree(tree, self._records())
        node = index_tree(tree)[0][SEC_ID]
        self.assertEqual(node["verificationMethod"], METHOD_POST_ON_ORG_PAGE)
        self.assertEqual(node["verificationMatchedText"], "Secretary of Defense")
        self.assertEqual(node["verificationMatchedIn"], "content")
        self.assertIn(URL, node["sourceUrls"])
        # One official URL is 0.4 + 0.3: a post confirmed on one page reads
        # "partial", not "verified". The pay-table incident of 2026-09-11
        # published 29 positions as verified off a table naming no post, and
        # the arithmetic that did it is this same arithmetic.
        self.assertEqual(node["verificationStatus"], "partial")
        # A rename withdraws it: the label recorded no longer names the node.
        renamed = json.loads(json.dumps(BASE))
        index_tree(renamed)[0][SEC_ID]["name"] = "Deputy Secretary of Defense"
        stats = apply_evidence_to_tree(renamed, self._records())
        self.assertEqual(stats["existence_stale_name"], 1)
        self.assertNotIn("verificationMethod", index_tree(renamed)[0][SEC_ID])
        # ...and the next build with no evidence withdraws everything.
        apply_evidence_to_tree(tree, {})
        node = index_tree(tree)[0][SEC_ID]
        for field in ("verificationMethod", "verificationMatchedText", "verificationMatchedIn"):
            self.assertNotIn(field, node)
        # `lastVerified` is nulled rather than dropped — the site's "no source
        # recorded" state keys on its falsiness, not on the key's absence.
        self.assertFalse(node.get("lastVerified"))
        self.assertEqual(node["sourceUrls"], [])

    def test_the_gate_accepts_an_earned_post_claim_and_refuses_every_way_of_faking_one(self) -> None:
        base = self.tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
        ev = self.tmp / "evidence.json"; ev.write_text(json.dumps({"nodes": self._records()}), encoding="utf-8")
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=ev, sites_path=None,
        )
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("posts on their org's page: 1 of 3 positions", out.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        self.assertEqual(index_tree(graph)[0][SEC_ID]["verificationMethod"], METHOD_POST_ON_ORG_PAGE)

        for name, mutate in {
            # The method's justification is that the page belongs to the
            # post's organisation rather than to the post. On an organisation
            # it would be a parent-page claim wearing a stronger name.
            "the post method on a node typed as an office":
                lambda n: n[SEC_ID].__setitem__("type", "Office"),
            # 72 nodes are called "Inspector General". Without the text there
            # is nothing tying this confirmation to this node.
            "the post method without the page's label":
                lambda n: n[SEC_ID].pop("verificationMatchedText"),
            "a label that does not name it":
                lambda n: n[SEC_ID].__setitem__("verificationMatchedText", "Deputy Secretary"),
            # The refusal this whole design turns on, arriving as data.
            "a post confirmed from the site-wide navigation":
                lambda n: n[SEC_ID].__setitem__("verificationMatchedIn", "navigation"),
            "a post confirmed from nowhere in particular":
                lambda n: n[SEC_ID].pop("verificationMatchedIn"),
            "an invented method":
                lambda n: n[SEC_ID].__setitem__("verificationMethod", "somebody_told_me"),
            "the post method with no source URL behind it":
                lambda n: n[SEC_ID].__setitem__("sourceUrls", []),
            # One fetch, two claims.
            "a post whose placement rests on the same page read":
                lambda n: (n[SEC_ID].__setitem__("placementVerified", True),
                           n[SEC_ID].__setitem__("placementUrl", URL),
                           n[SEC_ID].__setitem__("placementMethod", METHOD_PARENT_PAGE),
                           n[SEC_ID].__setitem__("placementVerifiedAt", "2026-09-13T00:00:00+00:00")),
            # And the organisation's own claim keeps its guard: quoting a
            # label with no rule is still refused on anything but a post.
            "an organisation quoting a label with no rule":
                lambda n: n[DEPT_ID].__setitem__("verificationMatchedText", "Department of Defense"),
        }.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph)); mutate(index_tree(corrupted)[0])
                path = self.tmp / f"{uuid.uuid4().hex}.json"; path.write_text(json.dumps(corrupted), encoding="utf-8")
                out = io.StringIO()
                with redirect_stdout(out):
                    code = gate_main(["gate", str(path)])
                self.assertEqual(code, 1, f"{name} was accepted:\n{out.getvalue()}")

    def test_a_placement_from_a_separate_document_is_still_allowed_on_a_post(self) -> None:
        """The refusal is "the same page read twice", not "positions may never
        be placed": OPM's PLUM archive files 126 of this graph's positions
        under an organisation, which is a second document and a real claim."""
        base = self.tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
        ev = self.tmp / "evidence.json"; ev.write_text(json.dumps({"nodes": self._records()}), encoding="utf-8")
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True, evidence_path=ev, sites_path=None,
        )
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        nodes = index_tree(graph)[0]
        nodes[SEC_ID].update({
            "placementVerified": True,
            "placementUrl": "https://www.opm.gov/plum",
            "placementMethod": "listed_under_organization_in_opm_plum_archive",
            "placementVerifiedAt": "2026-09-13T00:00:00+00:00",
            "placementParentId": DEPT_ID,
        })
        path = self.tmp / "with-plum.json"; path.write_text(json.dumps(graph), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(path)])
        self.assertEqual(code, 0, out.getvalue())


if __name__ == "__main__":
    unittest.main()
