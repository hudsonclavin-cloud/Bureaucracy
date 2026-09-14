"""The committee fold: a committee or subcommittee is confirmed by its name
with the graph's "Committee on" / "Subcommittee on" prefix set aside, and by
nothing weaker — only for those two types, only with two or more tokens left,
recorded with the rule and the label as the page prints it, refused by the
gate anywhere it is not earned."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph, index_tree
from data_pipeline.verification.evidence import (
    CONFIRMED,
    MATCH_RULE_COMMITTEE,
    METHOD_OWN_PAGE,
    METHOD_PARENT_PAGE,
    NOT_FOUND,
    PLACEMENT_LISTED,
    apply_evidence_to_tree,
    canonical_name_key,
    committee_core_key,
    evidence_names_this_node,
    find_label,
    find_label_region_rule,
    page_fragments,
    verify_node,
    verify_placement,
)
from scripts import validate_published_graph as gate
from scripts.validate_published_graph import main as gate_main

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"
COMMITTEE_ID = "leg-house-cmte-armed-services"
SUB_ID = "leg-house-cmte-armed-services-sub-seapower-projection-forces"
OFFICE_ID = "doe-science"
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-house", "name": "House of Representatives", "type": "Chamber", "children": [
                {"id": COMMITTEE_ID, "name": "House Committee on Armed Services", "type": "Committee", "children": [
                    {"id": SUB_ID, "name": "Subcommittee on Seapower & Projection Forces", "type": "Subcommittee", "children": []},
                    {"id": "leg-house-cmte-armed-services-sub-readiness", "name": "Subcommittee on Readiness", "type": "Subcommittee", "children": []},
                ]},
            ]},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                {"id": OFFICE_ID, "name": "Office of Science", "type": "Office", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
PROSE = (
    "<p>The committee oversees the Department of Defense and the armed forces, holding hearings and "
    "marking up the annual National Defense Authorization Act. This paragraph is long enough that the "
    "page counts as one a person could actually have read, which is the condition for concluding that "
    "a name was looked for and was not there. It goes on for a few more clauses to be sure of it.</p>"
)
COMMITTEE_PAGE = "<html><body><h1>Committee on Armed Services</h1><h2>Subcommittees</h2><ul><li><a href='/s'>Seapower and Projection Forces</a></li><li><a href='/r'>Readiness</a></li></ul>" + PROSE + "</body></html>"
SUB_PAGE = "<html><body><h1>Seapower and Projection Forces</h1>" + PROSE + "</body></html>"
FULL_PAGE = "<html><body><h1>Subcommittee on Seapower and Projection Forces</h1>" + PROSE + "</body></html>"
URL_CMTE = "https://armedservices.house.gov/"
URL_SUB = "https://armedservices.house.gov/subcommittees/seapower"


def fetch_for(pages):
    def fetch(url):
        if url not in pages:
            raise OSError("connect_rejected")
        return pages[url]
    return fetch


class CoreKeyTests(unittest.TestCase):
    def test_the_type_words_fold_on_both_sides_and_a_bare_word_never_does(self) -> None:
        for name, core in (
            ("House Committee on Armed Services", "armed services"),
            ("Committee on Armed Services", "armed services"),
            ("Armed Services Committee", "armed services"),
            ("Subcommittee on Seapower & Projection Forces", "seapower and projection forces"),
            ("The Subcommittee on the Constitution and Limited Government", "constitution and limited government"),
            ("Western Hemisphere Subcommittee", "western hemisphere"),
            ("Subcommittee on The Western Hemisphere", "western hemisphere"),
            ("House Committee on House Administration", "house administration"),
            ("United States Committee on House Administration", "house administration"),
            ("Senate Committee on Select Committee on Ethics", ""),   # "ethics": one token
            ("Subcommittee on Readiness", ""),
            ("Subcommittee on Africa", ""),
            ("Office of Science", "office of science"),               # not committee scaffolding: untouched
        ):
            with self.subTest(name=name):
                self.assertEqual(committee_core_key(canonical_name_key(name)), core)

    def test_the_gate_s_mirror_is_the_module_s_function(self) -> None:
        names = [
            "House Committee on Armed Services", "Subcommittee on Seapower & Projection Forces", "Readiness",
            "Senate Committee on Special Committee on Aging", "Joint Committee on Taxation", "Ways & Means",
            "Committee on Education & the Workforce | Republicans", "Office of Science", "",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(gate.committee_core_key(gate.canonical_key(name)), committee_core_key(canonical_name_key(name)))


class LabelFoldTests(unittest.TestCase):
    def test_a_committee_is_confirmed_by_its_name_without_the_type_words_and_an_office_is_not(self) -> None:
        frags = page_fragments(COMMITTEE_PAGE)
        # Plain equality first, and it still refuses the prefix-less label.
        self.assertIsNone(find_label("House Committee on Armed Services", frags))
        self.assertIsNone(find_label("Subcommittee on Seapower & Projection Forces", frags))
        # Folded: the label, its region, and the rule it took.
        self.assertEqual(find_label_region_rule("House Committee on Armed Services", frags, fold_committee=True),
                         ("Committee on Armed Services", "content", MATCH_RULE_COMMITTEE))
        self.assertEqual(find_label_region_rule("Subcommittee on Seapower & Projection Forces", frags, fold_committee=True),
                         ("Seapower and Projection Forces", "content", MATCH_RULE_COMMITTEE))
        # A page that carries the name in full is never recorded as folded.
        self.assertEqual(find_label_region_rule("Subcommittee on Seapower & Projection Forces", page_fragments(FULL_PAGE), fold_committee=True),
                         ("Subcommittee on Seapower and Projection Forces", "content", None))
        # One token left is not a name: "Readiness" is on the page and confirms nothing.
        self.assertIsNone(find_label_region_rule("Subcommittee on Readiness", frags, fold_committee=True))
        # The fold never reaches a unit that is not a committee, whatever the page says.
        self.assertIsNone(find_label_region_rule("Office of Science", page_fragments("<h1>Science</h1>"), fold_committee=True))
        self.assertIsNone(find_label_region_rule("Office of Science", page_fragments("<h1>Science</h1>"), fold_committee=False))

    def test_verify_node_and_verify_placement_fold_by_the_node_s_type_only(self) -> None:
        fetch = fetch_for({URL_CMTE: COMMITTEE_PAGE, URL_SUB: SUB_PAGE})
        sub = {"id": SUB_ID, "name": "Subcommittee on Seapower & Projection Forces", "type": "Subcommittee"}
        own = verify_node(sub, [URL_SUB], fetch=fetch, now="2026-09-13T00:00:00+00:00", site_from=SUB_ID, is_own_page=True)
        self.assertEqual((own["status"], own["method"]), (CONFIRMED, METHOD_OWN_PAGE))
        self.assertEqual(own["sources"][0]["matchedText"], "Seapower and Projection Forces")
        self.assertEqual(own["sources"][0]["matchRule"], MATCH_RULE_COMMITTEE)
        # Same page, same name, typed as an office: not found — and a real negative, since it is its own page.
        office = verify_node({**sub, "type": "Office"}, [URL_SUB], fetch=fetch, is_own_page=True)
        self.assertEqual(office["status"], NOT_FOUND)
        # A plain match carries no rule.
        full = verify_node(sub, [URL_SUB], fetch=fetch_for({URL_SUB: FULL_PAGE}), is_own_page=True)
        self.assertNotIn("matchRule", full["sources"][0])
        # Placement on the committee's page, folded and said so.
        block = verify_placement(sub, COMMITTEE_ID, [URL_CMTE], fetch=fetch, now="2026-09-13T00:00:00+00:00")
        self.assertEqual(block["status"], PLACEMENT_LISTED)
        self.assertEqual((block["matchedText"], block["matchRule"]), ("Seapower and Projection Forces", MATCH_RULE_COMMITTEE))
        readiness = {"id": "r", "name": "Subcommittee on Readiness", "type": "Subcommittee"}
        self.assertEqual(verify_placement(readiness, COMMITTEE_ID, [URL_CMTE], fetch=fetch)["status"], "not_listed")

    def test_the_rename_guard_grants_the_fold_by_type_and_withdraws_it_with_the_type(self) -> None:
        sub = {"name": "Subcommittee on Seapower & Projection Forces", "type": "Subcommittee"}
        self.assertTrue(evidence_names_this_node(sub["name"], "Seapower and Projection Forces", sub))
        self.assertFalse(evidence_names_this_node(sub["name"], "Seapower and Projection Forces", {**sub, "type": "Office"}))
        self.assertFalse(evidence_names_this_node(sub["name"], "Seapower and Projection Forces"))
        self.assertFalse(evidence_names_this_node("Subcommittee on Readiness", "Readiness", {"type": "Subcommittee"}))
        self.assertTrue(evidence_names_this_node(sub["name"], "Subcommittee on Seapower and Projection Forces"))


class ApplyAndGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"fold-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _records(self):
        fetch = fetch_for({URL_CMTE: COMMITTEE_PAGE, URL_SUB: SUB_PAGE})
        now = "2026-09-13T00:00:00+00:00"
        sub = {"id": SUB_ID, "name": "Subcommittee on Seapower & Projection Forces", "type": "Subcommittee"}
        sub_record = verify_node(sub, [URL_SUB], fetch=fetch, now=now, site_from=SUB_ID, is_own_page=True)
        sub_record["placement"] = verify_placement(sub, COMMITTEE_ID, [URL_CMTE], fetch=fetch, now=now)
        cmte = {"id": COMMITTEE_ID, "name": "House Committee on Armed Services", "type": "Committee"}
        cmte_record = verify_node(cmte, [URL_CMTE], fetch=fetch, now=now, site_from=COMMITTEE_ID, is_own_page=True)
        return {SUB_ID: sub_record, COMMITTEE_ID: cmte_record}

    def test_the_exporter_publishes_the_rule_and_the_page_s_label_and_withdraws_them_whole(self) -> None:
        tree = json.loads(json.dumps(BASE))
        stats = apply_evidence_to_tree(tree, self._records())
        nodes = index_tree(tree)[0]
        sub, cmte = nodes[SUB_ID], nodes[COMMITTEE_ID]
        self.assertEqual((stats["existence_folded"], stats["placements_folded"]), (2, 1))
        self.assertEqual(sub["verificationMethod"], METHOD_OWN_PAGE)
        self.assertEqual(sub["verificationMatchRule"], MATCH_RULE_COMMITTEE)
        self.assertEqual(sub["verificationMatchedText"], "Seapower and Projection Forces")
        self.assertEqual((sub["placementVerified"], sub["placementMatchRule"], sub["placementMatchedText"]),
                         (True, MATCH_RULE_COMMITTEE, "Seapower and Projection Forces"))
        self.assertEqual((cmte["verificationMatchRule"], cmte["verificationMatchedText"]), (MATCH_RULE_COMMITTEE, "Committee on Armed Services"))
        # Re-typed as an office in the curated file: everything earned as a committee goes.
        retyped = json.loads(json.dumps(BASE))
        index_tree(retyped)[0][SUB_ID]["type"] = "Office"
        stats = apply_evidence_to_tree(retyped, self._records())
        office = index_tree(retyped)[0][SUB_ID]
        self.assertEqual(stats["existence_stale_name"], 1)
        self.assertEqual(stats["placements_stale_name"], 1)
        for field in ("verificationMethod", "verificationMatchRule", "verificationMatchedText", "placementVerified", "placementMatchRule"):
            self.assertNotIn(field, office)
        # And the next build with no evidence withdraws the whole shape.
        apply_evidence_to_tree(tree, {})
        sub = index_tree(tree)[0][SUB_ID]
        for field in ("verificationMethod", "verificationMatchRule", "verificationMatchedText", "placementMatchRule", "placementVerified"):
            self.assertNotIn(field, sub)

    def test_the_gate_accepts_an_earned_fold_and_refuses_every_way_of_faking_one(self) -> None:
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
        self.assertIn("committee labels     : 2 confirmed and 1 placed", out.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        self.assertEqual(index_tree(graph)[0][SUB_ID]["verificationMatchRule"], MATCH_RULE_COMMITTEE)
        for name, mutate in {
            "the rule on a node typed as an office": lambda n: n[SUB_ID].__setitem__("type", "Office"),
            "an invented rule": lambda n: n[SUB_ID].__setitem__("verificationMatchRule", "vibes"),
            "the rule without the page's label": lambda n: n[SUB_ID].pop("verificationMatchedText"),
            "a label that does not name it": lambda n: n[SUB_ID].__setitem__("verificationMatchedText", "Readiness"),
            "a label without the rule": lambda n: n[SUB_ID].pop("verificationMatchRule"),
            "the rule under a directory method": lambda n: n[SUB_ID].__setitem__("verificationMethod", "listed_in_federal_register_agency_directory"),
            "a folded placement label on an office": lambda n: (n[SUB_ID].__setitem__("type", "Office"), n[SUB_ID].pop("verificationMatchRule"), n[SUB_ID].pop("verificationMatchedText")),
            "a folded placement label without the placement rule": lambda n: n[SUB_ID].pop("placementMatchRule"),
            "an invented placement rule": lambda n: n[SUB_ID].__setitem__("placementMatchRule", "vibes"),
        }.items():
            with self.subTest(case=name):
                corrupted = json.loads(json.dumps(graph)); mutate(index_tree(corrupted)[0])
                path = self.tmp / f"{uuid.uuid4().hex}.json"; path.write_text(json.dumps(corrupted), encoding="utf-8")
                out = io.StringIO()
                with redirect_stdout(out):
                    code = gate_main(["gate", str(path)])
                self.assertEqual(code, 1, f"{name}:\n{out.getvalue()}")


if __name__ == "__main__":
    unittest.main()
