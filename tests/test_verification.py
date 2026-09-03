"""Existence verification: fetched evidence only, and it reads as what it is.

The base graph has no source on any node. The only honest way one gets a
source is a fetch of an official page on a date with the name on it, and the
only honest way a failed check shows up is as a failed check.
"""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree, load_base_graph
from data_pipeline.verification.evidence import (
    CONFIRMED,
    FETCH_FAILED,
    NOT_FOUND,
    apply_evidence_to_tree,
    candidate_urls,
    find_name,
    load_official_sites,
    verify_node,
)
from scripts import verify_base_graph
from scripts.validate_published_graph import main as gate_main


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
                    ],
                },
            ],
        },
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "employees": "30,000", "children": []},
    ],
}
DOE_PAGE = "<html><head><title>x</title></head><nav>Office of Science</nav><body><h1>About the U.S. Department of Energy</h1><p>Our programs include the Office of Science &amp; more.</p><script>var Office='National Nuclear Security Administration'</script></body></html>"


class MatchingTests(unittest.TestCase):
    def test_the_whole_name_has_to_be_on_the_page(self) -> None:
        text = "The Department of Energy (DOE) runs the Office of Science."
        self.assertTrue(find_name("Department of Energy (DOE)", text))
        self.assertTrue(find_name("Office of Science", text))
        self.assertTrue(find_name("U.S. Department of Energy", "the United States Department of Energy is"))
        self.assertTrue(find_name("Health & Human Services", "Health and Human Services"))
        self.assertIsNone(find_name("Office of Science and Technology Policy", text))
        self.assertIsNone(find_name("DOE", "DOE"))  # a key this short would match an acronym anywhere; not evidence
        self.assertIsNone(find_name("Office", "Officer of the day"))  # word-bounded

    def test_candidate_pages_come_from_the_node_or_a_measured_number_of_ancestors(self) -> None:
        _, parent_map = index_tree(json.loads(json.dumps(BASE)))
        sites = {"exec-dept-doe": ["https://www.energy.gov/about-us"]}
        self.assertEqual(candidate_urls("exec-dept-doe", parent_map, sites), (["https://www.energy.gov/about-us"], "exec-dept-doe", 0))
        self.assertEqual(candidate_urls("doe-science", parent_map, sites), (["https://www.energy.gov/about-us"], "exec-dept-doe", 1))
        self.assertEqual(candidate_urls("doe-science-director", parent_map, sites)[2], 2)
        self.assertEqual(candidate_urls("legislative-branch", parent_map, sites), ([], None, 2))

    def test_candidate_file_keeps_only_urls_and_ignores_its_note(self) -> None:
        path = TEST_TMP_ROOT / f"sites-{uuid.uuid4().hex}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_note": "x", "a": "https://a.gov/", "b": ["https://b.gov/", 5, "nope"], "c": "not a url"}), encoding="utf-8")
        try:
            self.assertEqual(load_official_sites(path), {"a": ["https://a.gov/"], "b": ["https://b.gov/"]})
        finally:
            path.unlink()


class VerifyNodeTests(unittest.TestCase):
    def _fetch(self, pages):
        def fetch(url):
            if url not in pages:
                raise OSError("connect_rejected")
            return pages[url]
        return fetch

    def test_each_outcome_records_what_was_actually_checked(self) -> None:
        node = {"id": "exec-dept-doe", "name": "Department of Energy (DOE)"}
        fetch = self._fetch({"https://www.energy.gov/about-us": DOE_PAGE})
        confirmed = verify_node(node, ["https://www.energy.gov/about-us"], fetch=fetch, now="2026-09-03T12:00:00+00:00", site_from="exec-dept-doe")
        self.assertEqual(confirmed["status"], CONFIRMED)
        self.assertEqual(confirmed["sources"][0]["url"], "https://www.energy.gov/about-us")
        self.assertIn("department of energy", confirmed["sources"][0]["matchedText"])
        self.assertEqual(confirmed["checkedAt"], "2026-09-03T12:00:00+00:00")

        # nav/script text is not page content: the NNSA name only appears in a <script>.
        not_found = verify_node({"id": "doe-nnsa", "name": "National Nuclear Security Administration"}, ["https://www.energy.gov/about-us"], fetch=fetch)
        self.assertEqual(not_found["status"], NOT_FOUND)
        self.assertEqual(not_found["failures"][0]["reason"], "name_not_on_page")

        failed = verify_node(node, ["https://www.energy.gov/nope"], fetch=fetch)
        self.assertEqual(failed["status"], FETCH_FAILED)
        self.assertIn("OSError", failed["failures"][0]["reason"])

        # A non-official host is never fetched, let alone counted.
        wiki = verify_node(node, ["https://en.wikipedia.org/wiki/DOE"], fetch=fetch)
        self.assertEqual(wiki["status"], FETCH_FAILED)
        self.assertEqual(wiki["failures"][0]["reason"], "not_an_official_host")

    def test_two_official_pages_are_two_sources(self) -> None:
        pages = {"https://a.energy.gov/": "Department of Energy", "https://b.energy.gov/": "the Department of Energy is"}
        record = verify_node({"id": "x", "name": "Department of Energy"}, list(pages), fetch=self._fetch(pages))
        self.assertEqual([s["url"] for s in record["sources"]], list(pages))


class ApplyEvidenceTests(unittest.TestCase):
    def _tree(self):
        return json.loads(json.dumps(BASE))

    def test_confirmed_evidence_becomes_a_source_and_a_date_and_nothing_else(self) -> None:
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {
            "exec-dept-doe": {"status": CONFIRMED, "checkedAt": "2026-09-03T12:00:00+00:00", "sources": [{"url": "https://www.energy.gov/about-us", "matchedText": "x"}]},
        })
        node_map, _ = index_tree(tree)
        doe = node_map["exec-dept-doe"]
        self.assertEqual(stats["confirmed"], 1)
        self.assertEqual(doe["sourceUrls"], ["https://www.energy.gov/about-us"])
        self.assertEqual(doe["lastVerified"], "2026-09-03T12:00:00+00:00")
        self.assertTrue(doe["existsProven"])
        self.assertEqual(doe["name"], "Department of Energy (DOE)")  # curated name untouched
        self.assertEqual(doe["type"], "Cabinet Department")
        self.assertNotIn("lastVerified", node_map["doe-science"])  # nothing spills onto neighbours

    def test_a_failed_check_is_a_date_without_a_url(self) -> None:
        tree = self._tree()
        apply_evidence_to_tree(tree, {"doe-nnsa": {"status": NOT_FOUND, "checkedAt": "2026-09-03T12:00:00+00:00"}})
        node_map, _ = index_tree(tree)
        nnsa = node_map["doe-nnsa"]
        self.assertEqual(nnsa["lastVerified"], "2026-09-03T12:00:00+00:00")
        self.assertFalse(nnsa.get("sourceUrls"))
        self.assertEqual(nnsa["verificationFailure"], NOT_FOUND)
        self.assertFalse(nnsa.get("existsProven"))

    def test_a_fetch_that_never_happened_is_not_a_failed_check(self) -> None:
        """The most dangerous confusion in this module. A blocked network
        would otherwise stamp "checked, not found" on every node in the
        graph on the strength of our own connectivity."""
        tree = self._tree()
        stats = apply_evidence_to_tree(tree, {
            "exec-dept-doe": {"status": FETCH_FAILED, "checkedAt": "2026-09-03T12:00:00+00:00", "failures": [{"url": "https://www.energy.gov/about-us", "reason": "URLError: blocked"}]},
        })
        node_map, _ = index_tree(tree)
        doe = node_map["exec-dept-doe"]
        self.assertEqual(stats["fetch_failed"], 1)
        self.assertNotIn("lastVerified", doe)
        self.assertNotIn("verificationFailure", doe)
        self.assertFalse(doe.get("sourceUrls"))
        # Untouched entirely: not even rescored, so it is byte-identical to a
        # node no evidence mentions.
        self.assertEqual(doe, index_tree(self._tree())[0]["exec-dept-doe"])

    def test_a_failed_check_never_removes_a_source_another_route_recorded(self) -> None:
        tree = self._tree()
        node_map, _ = index_tree(tree)
        node_map["doe-nnsa"]["sourceUrls"] = ["https://api.fiscaldata.treasury.gov/x"]
        apply_evidence_to_tree(tree, {"doe-nnsa": {"status": NOT_FOUND, "checkedAt": "2026-09-03T12:00:00+00:00"}})
        self.assertEqual(node_map["doe-nnsa"]["sourceUrls"], ["https://api.fiscaldata.treasury.gov/x"])
        self.assertNotIn("verificationFailure", node_map["doe-nnsa"])

    def test_unknown_ids_and_unknown_statuses_touch_nothing(self) -> None:
        tree = self._tree()
        before = json.dumps(tree, sort_keys=True)
        stats = apply_evidence_to_tree(tree, {"ghost": {"status": CONFIRMED, "checkedAt": "2026-01-01"}, "exec-dept-doe": {"status": "guessed"}})
        self.assertEqual(stats["unknown_node"], 1)
        self.assertEqual(json.dumps(tree, sort_keys=True), before)


class BuildAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"verify-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, evidence):
        evidence_path = self.tmp / "evidence.json"
        evidence_path.write_text(json.dumps({"_note": "test", "nodes": evidence}), encoding="utf-8")
        return build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=self.base,
            graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "expanded_nodes.json",
            edges_output_path=self.tmp / "expanded_edges.json",
            validity_report_output_path=self.tmp / "node_validity_report.json",
            reuse_existing_graph_payload=False,
            enforce_export_gate=True,
            evidence_path=evidence_path,
        )

    def _gate(self, path):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(path)])
        return code, out.getvalue()

    def test_evidence_reaches_the_published_graph_and_the_gate_reports_it(self) -> None:
        result = self._build({
            "exec-dept-doe": {"status": CONFIRMED, "checkedAt": "2026-09-03T12:00:00+00:00", "sources": [{"url": "https://www.energy.gov/about-us", "matchedText": "x"}]},
            "doe-nnsa": {"status": NOT_FOUND, "checkedAt": "2026-09-03T12:00:00+00:00"},
        })
        self.assertEqual(result.validation["verification_evidence"]["confirmed"], 1)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node_map, _ = index_tree(graph)
        self.assertEqual(node_map["exec-dept-doe"]["sourceUrls"], ["https://www.energy.gov/about-us"])
        self.assertEqual(node_map["exec-dept-doe"]["sourceCount"], 1)
        self.assertTrue(node_map["exec-dept-doe"]["existsProven"])
        self.assertEqual(node_map["doe-nnsa"]["lastVerified"], "2026-09-03T12:00:00+00:00")
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("official source      : 1 of", out)
        self.assertIn("checked, not found   : 1", out)

    def test_the_gate_refuses_a_future_date_or_a_method_without_a_url(self) -> None:
        result = self._build({})
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        node_map, _ = index_tree(graph)
        cases = {
            "future date": lambda: node_map["exec-dept-doe"].__setitem__("lastVerified", "2999-01-01"),
            "not a date": lambda: node_map["exec-dept-doe"].__setitem__("lastVerified", "yesterday"),
            "method without url": lambda: node_map["exec-dept-doe"].__setitem__("verificationMethod", "name_on_official_page"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph))
                cm, _ = index_tree(corrupted)
                node_map = cm
                mutate()
                path = self.tmp / f"{uuid.uuid4().hex}.json"
                path.write_text(json.dumps(corrupted), encoding="utf-8")
                code, out = self._gate(path)
                self.assertEqual(code, 1, out)
                self.assertIn("Department of Energy", out)


class VerifierScriptTests(unittest.TestCase):
    def test_dry_run_plans_without_fetching_or_writing(self) -> None:
        tmp = TEST_TMP_ROOT / f"verify-cli-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp / "base.json"; base.write_text(json.dumps(BASE), encoding="utf-8")
            sites = tmp / "sites.json"; sites.write_text(json.dumps({"exec-dept-doe": ["https://www.energy.gov/about-us"]}), encoding="utf-8")
            evidence = tmp / "evidence.json"
            out = io.StringIO()
            with redirect_stdout(out):
                code = verify_base_graph.main(["v", "--base-graph", str(base), "--sites", str(sites), "--evidence", str(evidence), "--dry-run"])
            self.assertEqual(code, 0)
            text = out.getvalue()
            # DOE itself and its two direct units; the Director (a Position) and
            # the branches (no page within one level) are not in the plan.
            self.assertIn("to check 3", text)
            self.assertIn("exec-dept-doe  <-  https://www.energy.gov/about-us", text)
            self.assertIn("doe-science  <-", text)
            self.assertNotIn("doe-science-director", text)
            self.assertFalse(evidence.exists())
            self.assertEqual(json.loads(base.read_text(encoding="utf-8")), BASE)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_list_hosts_is_the_allowlist(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            verify_base_graph.main(["v", "--list-hosts"])
        hosts = out.getvalue().split()
        self.assertIn("www.energy.gov", hosts)
        self.assertTrue(all(h.endswith((".gov", ".mil", ".edu", ".com")) for h in hosts), hosts)


if __name__ == "__main__":
    unittest.main()
