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
    graph = export = leads = node_map = None

    @classmethod
    def load(cls):
        if cls.leads is None:
            cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
            cls.export = load_plum_export()
            cls.node_map, parent_map = index_tree(cls.graph)
            cls.leads = fpl.find_leads(cls.graph, cls.export, load_alias_table(node_map=cls.node_map, parent_map=parent_map))
        return cls


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class LeadTests(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()

    def test_every_lead_is_an_unpriced_post_whose_blank_says_the_title_is_printed_somewhere(self):
        for lead in self.s.leads:
            node = self.s.node_map[lead["nodeId"]]
            self.assertEqual(node["payNoDocument"]["kind"], fpl.BLOCK_KIND, lead["nodeId"])
            for fld in ("positionStatutoryPay", "positionPayRate", "positionCurrentPay", "positionSchedulePay"):
                self.assertNotIn(fld, node, f"{lead['nodeId']} is priced and cannot be a lead")

    def test_every_printed_row_carries_the_posts_own_title_under_its_own_agency(self):
        from data_pipeline.verification.plum_current import export_title_keys

        for lead in self.s.leads:
            key = canonical_name_key(self.s.node_map[lead["nodeId"]]["name"])
            self.assertTrue(lead["printed"], lead["nodeId"])
            for row in lead["printed"]:
                self.assertIn(key, export_title_keys(row["title"], row["organization"]), (lead["nodeId"], row))
            self.assertEqual(lead["organisations"], len({p["organization"] for p in lead["printed"]}))

    def test_a_stamped_title_printed_only_under_other_agencies_is_not_a_lead(self):
        # "Chief of Staff" is printed under dozens of agencies; a post under an agency that prints none
        # of its own is not made a lead by the others.
        leads = {l["nodeId"] for l in self.s.leads}
        unpriced_with_title_printed = [
            nid for nid, n in self.s.node_map.items()
            if isinstance(n.get("payNoDocument"), dict) and n["payNoDocument"]["kind"] == fpl.BLOCK_KIND
        ]
        self.assertGreater(len(unpriced_with_title_printed), len(leads))

    def test_the_lead_count_is_pinned_and_the_names_columns_are_never_read(self):
        self.assertEqual(len(self.s.leads), 144)
        self.assertEqual(sum(1 for l in self.s.leads if l["organisations"] == 1), 88)
        # the fields the export reader takes are the whole of what a lead can quote
        self.assertNotIn("incumbent", " ".join(READ_COLUMNS.values()).lower())
        text = DOC.read_text(encoding="utf-8")
        for forbidden in ("Last Name", "First Name", "Unique ID"):
            self.assertNotIn(forbidden, text)

    def test_the_committed_document_is_what_the_script_renders(self):
        decisions = fpl.load_decisions()
        unpriced = sum(1 for n in self.s.node_map.values() if isinstance(n.get("payNoDocument"), dict))
        self.assertEqual(DOC.read_text(encoding="utf-8"), fpl.render(self.s.leads, decisions, self.s.export, unpriced))


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()

    def test_a_decision_takes_a_lead_out_of_the_open_count_and_keeps_its_reason(self):
        first = self.s.leads[0]["nodeId"]
        decisions = {first: {"nodeId": first, "kind": "not_this_post", "basis": "a different office"}}
        open_leads, decided = fpl.partition(self.s.leads, decisions)
        self.assertEqual(len(open_leads), len(self.s.leads) - 1)
        self.assertEqual(decided[0]["decision"]["basis"], "a different office")
        text = fpl.render(self.s.leads, decisions, self.s.export, 3221)
        self.assertIn("a different office", text)
        self.assertNotIn(f"(`{first}`), under", text)

    def test_a_decision_for_a_post_that_is_not_a_lead_is_reported_stale(self):
        decisions = {"no-such-node": {"nodeId": "no-such-node", "kind": "not_this_post", "basis": "x"}}
        self.assertIn("no-such-node", fpl.render(self.s.leads, decisions, self.s.export, 3221))

    def test_the_committed_decisions_use_the_closed_vocabulary(self):
        for row in fpl.load_decisions().values():
            self.assertIn(row["kind"], fpl.DECISION_KINDS)
            self.assertTrue(str(row.get("basis") or "").strip())

    def test_the_issue_body_is_capped_and_says_nothing_is_a_claim(self):
        body = fpl.render_issue(self.s.leads, {}, self.s.export, 3221, limit=5)
        self.assertLess(len(body), 8000)
        self.assertIn("questions for you, not claims", body)
        self.assertIn("docs/PAY_LEADS.md", body)
        self.assertEqual(body.count("\n- "), 5)


class WorkflowTests(unittest.TestCase):
    def test_the_ai_workflow_is_gone_and_the_replacement_has_no_model_secret_or_push(self):
        self.assertFalse((WORKFLOWS / "go_loops.yml").exists())
        text = (WORKFLOWS / "pay_leads.yml").read_text(encoding="utf-8")
        for forbidden in ("ANTHROPIC", "claude", "secrets.", "git push", "gh pr create", "contents: write", "pull-requests"):
            self.assertNotIn(forbidden, text)
        self.assertIn("issues: write", text)
        self.assertIn("find_pay_leads.py", text)

    def test_no_workflow_in_the_repository_needs_an_api_key(self):
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("ANTHROPIC_API_KEY", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
