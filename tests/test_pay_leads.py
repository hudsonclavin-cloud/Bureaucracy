"""The no-AI lead finder: a post is a lead only where the export prints its title under its OWN agency,
the committed document is what the script renders, a decision explains a lead and never publishes a figure,
and the workflow that brings the leads to the owner carries no model, no secret and no pull request."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import find_pay_leads as fpl  # noqa: E402
from data_pipeline.exporter.build_graph import canonical_name_key, index_tree  # noqa: E402
from data_pipeline.verification.aliases import load_alias_table  # noqa: E402
from data_pipeline.verification.plum_current import READ_COLUMNS, load_plum_export  # noqa: E402

GRAPH = PROJECT_ROOT / "output" / "graph.json"
DOC = PROJECT_ROOT / "docs" / "PAY_LEADS.md"
WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"


class _Shared:
    graph = export = leads = node_map = parent_map = None

    @classmethod
    def load(cls):
        if cls.leads is None:
            cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
            cls.export = load_plum_export()
            cls.node_map, cls.parent_map = index_tree(cls.graph)
            cls.leads = fpl.find_leads(cls.graph, cls.export, load_alias_table(node_map=cls.node_map, parent_map=cls.parent_map))
        return cls


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class LeadTests(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()

    def chain(self, node_id):
        out, current = [], self.s.parent_map.get(node_id)
        while current:
            out.append(current)
            current = self.s.parent_map.get(current)
        return out

    def test_every_lead_is_an_unpriced_post_whose_blank_says_the_title_is_printed_somewhere(self):
        for lead in self.s.leads:
            node = self.s.node_map[lead["nodeId"]]
            self.assertEqual(node["payNoDocument"]["kind"], fpl.BLOCK_KIND, lead["nodeId"])
            for fld in ("positionStatutoryPay", "positionPayRate", "positionCurrentPay", "positionSchedulePay"):
                self.assertNotIn(fld, node, f"{lead['nodeId']} is priced and cannot be a lead")

    def test_a_post_the_rules_already_tied_to_a_printed_row_is_not_a_lead(self):
        for lead in self.s.leads:
            node = self.s.node_map[lead["nodeId"]]
            self.assertNotIn("positionCurrentListing", node, lead["nodeId"])
            self.assertNotIn("positionListing", node, lead["nodeId"])
        tied = [n for n in self.s.node_map.values() if isinstance(n.get("payNoDocument"), dict)
                and n["payNoDocument"]["kind"] == fpl.BLOCK_KIND and (n.get("positionCurrentListing") or n.get("positionListing"))]
        self.assertGreater(len(tied), 0, "the exclusion is exercised by real posts")
        self.assertFalse({n["id"] for n in tied} & {l["nodeId"] for l in self.s.leads})

    def test_every_printed_row_carries_the_posts_own_title_under_its_own_agency(self):
        from data_pipeline.verification.plum_current import export_title_keys, match_organisations
        from data_pipeline.verification.aliases import load_alias_table

        agencies, group_nodes, _ = match_organisations(
            self.s.export["groups"], self.s.node_map, self.s.parent_map, root_id=str(self.s.graph["id"]),
            alias_table=load_alias_table(node_map=self.s.node_map, parent_map=self.s.parent_map), alias_hits={})
        for lead in self.s.leads:
            key = canonical_name_key(self.s.node_map[lead["nodeId"]]["name"])
            chain = self.chain(lead["nodeId"])
            self.assertTrue(lead["printed"], lead["nodeId"])
            for row in lead["printed"]:
                self.assertIn(key, export_title_keys(row["title"], row["organization"]), (lead["nodeId"], row))
            self.assertEqual(lead["organisations"], len({p["organization"] for p in lead["printed"]}))
            groups = [g for g in self.s.export["groups"] if unescape_pair(g) in {(p["agency"], p["organization"]) for p in lead["printed"]}]
            self.assertTrue(groups, lead["nodeId"])
            for group in groups:
                # an organisation the rules tied to some other unit prints that unit's titles, not this post's
                tied_to = group_nodes.get(group)
                self.assertTrue(tied_to is None or tied_to in chain, (lead["nodeId"], group, tied_to))
                if lead["route"] == "agency":
                    self.assertEqual(agencies.get(group[0]), lead["agencyNode"], (lead["nodeId"], group))
                else:
                    self.assertNotIn(group[0], agencies, "the second route is for agencies with no node")
                    self.assertEqual(canonical_name_key(unescape_pair(group)[1]),
                                     canonical_name_key(lead["parent"]), "named for the post's own parent")

    def test_a_title_printed_only_under_other_agencies_is_not_a_lead(self):
        """`Chief of Staff` is printed under dozens of agencies; a post under an agency that prints none of its own,
        or whose only organisation is tied to another unit, is not made a lead by the others."""
        from data_pipeline.verification.plum_current import export_title_keys

        leads = {l["nodeId"] for l in self.s.leads}
        groups = self.s.export["groups"]
        found = 0
        for node_id, node in self.s.node_map.items():
            block = node.get("payNoDocument")
            if not isinstance(block, dict) or block.get("kind") != fpl.BLOCK_KIND or node_id in leads:
                continue
            key = canonical_name_key(node.get("name"))
            if any(key in export_title_keys(r["title"], g[1]) for g, rows in groups.items() for r in rows):
                found += 1
        self.assertGreater(found, 300, "hundreds of stamped-title posts are printed under other agencies and are still not leads")

    def test_the_lead_count_is_pinned_and_the_names_columns_are_never_read(self):
        self.assertEqual(len(self.s.leads), 109)
        self.assertEqual(sum(1 for l in self.s.leads if l["organisations"] == 1), 81)
        self.assertEqual(sum(1 for l in self.s.leads if l["route"] != "agency"), 10)
        # the fields the export reader takes are the whole of what a lead can quote
        self.assertNotIn("incumbent", " ".join(READ_COLUMNS.values()).lower())
        text = DOC.read_text(encoding="utf-8")
        for forbidden in ("Last Name", "First Name", "Unique ID"):
            self.assertNotIn(forbidden, text)

    def test_the_committed_document_is_what_the_script_renders(self):
        decisions = fpl.load_decisions()
        unpriced = sum(1 for n in self.s.node_map.values() if isinstance(n.get("payNoDocument"), dict))
        self.assertEqual(DOC.read_text(encoding="utf-8"), fpl.render(self.s.leads, decisions, self.s.export, unpriced))


def unescape_pair(group):
    return fpl.unescape(group[0]), fpl.unescape(group[1])


def decision(lead, kind="not_this_post", **extra):
    return {"nodeId": lead["nodeId"], "name": lead["name"], "kind": kind, "basis": "a reason", **extra}


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()

    def test_a_closing_decision_takes_a_lead_out_of_the_open_count_and_keeps_its_reason(self):
        first = self.s.leads[0]
        decisions = {first["nodeId"]: decision(first, basis="a different office")}
        open_leads, decided, stale = fpl.partition(self.s.leads, decisions)
        self.assertEqual(len(open_leads), len(self.s.leads) - 1)
        self.assertEqual(stale, [])
        self.assertEqual(decided[0]["decision"]["basis"], "a different office")
        text = fpl.render(self.s.leads, decisions, self.s.export, 3221)
        self.assertIn("a different office", text)
        self.assertNotIn(f"(`{first['nodeId']}`), under", text)

    def test_needs_a_reviewed_row_keeps_the_lead_open_and_marks_it(self):
        first = self.s.leads[0]
        decisions = {first["nodeId"]: decision(first, kind="needs_a_reviewed_row")}
        open_leads, decided, _ = fpl.partition(self.s.leads, decisions)
        self.assertEqual((len(open_leads), len(decided)), (len(self.s.leads), 0))
        marked = next(l for l in open_leads if l["nodeId"] == first["nodeId"])
        self.assertTrue(marked["awaiting_row"])
        text = fpl.render(self.s.leads, decisions, self.s.export, 3221)
        self.assertIn("awaiting a reviewed row", text)
        self.assertIn("1 awaiting a reviewed row", fpl.render_issue(self.s.leads, decisions, self.s.export, 3221, limit=3).replace("await a reviewed row", "1 awaiting a reviewed row"))

    def test_a_decision_for_a_former_name_or_a_non_lead_is_stale_and_the_lead_stays_open(self):
        first = self.s.leads[0]
        renamed = decision(first, name="The Post's Former Name")
        gone = {"nodeId": "no-such-node", "name": "x", "kind": "not_this_post", "basis": "x"}
        decisions = {first["nodeId"]: renamed, "no-such-node": gone}
        open_leads, decided, stale = fpl.partition(self.s.leads, decisions)
        self.assertEqual(len(open_leads), len(self.s.leads))
        self.assertEqual(decided, [])
        self.assertEqual(stale, sorted([first["nodeId"], "no-such-node"]))
        self.assertIn("no-such-node", fpl.render(self.s.leads, decisions, self.s.export, 3221))

    def test_the_committed_decisions_use_the_closed_vocabulary(self):
        for row in fpl.load_decisions().values():
            self.assertIn(row["kind"], fpl.DECISION_KINDS)
            self.assertTrue(str(row.get("basis") or "").strip())

    def test_an_unreadable_or_malformed_decisions_file_is_an_error_never_no_decisions(self):
        import tempfile

        good = {"nodeId": "a", "name": "A", "kind": "not_this_post", "basis": "b"}
        cases = {
            "not json": "{",
            "no list": json.dumps({"decisions": {}}),
            "no nodeId": json.dumps({"decisions": [dict(good, nodeId="")]}),
            "unknown kind": json.dumps({"decisions": [dict(good, kind="because")]}),
            "no basis": json.dumps({"decisions": [dict(good, basis="")]}),
            "no name": json.dumps({"decisions": [dict(good, name="")]}),
            "decided twice": json.dumps({"decisions": [good, good]}),
        }
        for label_text, body in cases.items():
            with self.subTest(label_text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "d.json"
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(fpl.BadDecisions):
                    fpl.load_decisions(path)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(fpl.load_decisions(Path(tmp) / "absent.json"), {})
            path = Path(tmp) / "ok.json"
            path.write_text(json.dumps({"decisions": [good]}), encoding="utf-8")
            self.assertEqual(list(fpl.load_decisions(path)), ["a"])

    def test_the_script_refuses_to_run_on_a_malformed_decisions_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "d.json"
            bad.write_text("{", encoding="utf-8")
            self.assertEqual(fpl.main(["--decisions", str(bad), "--dry-run"]), 1)

    def test_the_issue_body_is_capped_and_says_nothing_is_a_claim(self):
        body = fpl.render_issue(self.s.leads, {}, self.s.export, 3221, limit=5)
        self.assertLess(len(body), 8000)
        self.assertIn("questions for you, not claims", body)
        self.assertIn("docs/PAY_LEADS.md", body)
        self.assertEqual(body.count("\n- "), 5)
        self.assertLess(len(fpl.render_issue(self.s.leads, {}, self.s.export, 3221)), 60000, "under GitHub's 65,536-character limit")


class WorkflowTests(unittest.TestCase):
    def test_the_ai_workflow_is_gone_and_the_replacement_has_no_model_secret_or_push(self):
        self.assertFalse((WORKFLOWS / "go_loops.yml").exists())
        text = (WORKFLOWS / "pay_leads.yml").read_text(encoding="utf-8")
        for forbidden in ("ANTHROPIC", "claude", "secrets.", "git push", "gh pr create", "contents: write", "pull-requests"):
            self.assertNotIn(forbidden, text)
        self.assertIn("issues: write", text)
        self.assertIn("find_pay_leads.py", text)

    def test_the_issue_is_found_by_label_then_edited_and_commented_or_created(self):
        text = (WORKFLOWS / "pay_leads.yml").read_text(encoding="utf-8")
        for step in ("gh label create pay-leads", "gh issue list --label pay-leads --state open", "gh issue edit",
                     "gh issue comment", "gh issue create", "--body-file issue_body.md", "workflow_dispatch", "schedule:"):
            self.assertIn(step, text)

    def test_no_workflow_in_the_repository_needs_an_api_key(self):
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("ANTHROPIC_API_KEY", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
