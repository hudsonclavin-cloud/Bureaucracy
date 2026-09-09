"""The nomination harness, pinned in both directions.

A nomination is deliberately weaker than a finding: an agent may propose a URL
it cannot read, because the verifier adjudicates. What the harness must still
refuse is a nomination that could never be adjudicated at all — a host the
verifier will not fetch, a URL already tried, a confidence the agent has no
way to earn — and a shard scheme that hands two agents the same node.
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from scripts import nominate

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"

GRAPH = {
    "id": "root", "name": "Root", "type": "Foundation",
    "children": [
        {"id": "dept", "name": "Department of Things", "type": "Department", "children": [
            {"id": "bureau", "name": "Bureau of Stuff", "type": "Bureau", "children": []},
            {"id": "other", "name": "Office of Other", "type": "Office", "children": []},
            {"id": "post", "name": "Director", "type": "Position", "children": []},
            {"id": "receipts", "name": "Receipts", "type": "Treasury accounting line",
             "synthetic": "treasury_receipts", "children": []},
        ]},
    ],
}
SITES = {"_note": "candidates", "dept": ["https://www.things.gov/"]}
EVIDENCE = {"nodes": {"bureau": {"failures": [{"url": "https://www.stuff.gov/", "reason": "HTTP Error 404"}]}}}


class HarnessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"nom-{uuid.uuid4().hex}"
        (self.tmp_path / "verification").mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp_path, True)
        graph_path = self.tmp_path / "graph.json"
        graph_path.write_text(json.dumps(GRAPH), encoding="utf-8")
        evidence_dir = self.tmp_path / "verification"
        (evidence_dir / "evidence.json").write_text(json.dumps(EVIDENCE), encoding="utf-8")
        (evidence_dir / "directory_evidence.json").write_text(json.dumps({"nodes": {}}), encoding="utf-8")
        self.sites = evidence_dir / "official_sites.json"
        self.sites.write_text(json.dumps(SITES), encoding="utf-8")
        self.provenance = evidence_dir / "official_sites_provenance.json"
        self.provenance.write_text(json.dumps({}), encoding="utf-8")
        self.ledger_dir = self.tmp_path / "nominations"
        for attr, value in {
            "GRAPH": graph_path, "EVIDENCE_DIR": evidence_dir, "SITES": self.sites,
            "PROVENANCE": self.provenance, "LEDGER_DIR": self.ledger_dir,
        }.items():
            patcher = mock.patch.object(nominate, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def record(self, records, kind="source", run="agent-1"):
        path = self.tmp_path / f"batch-{uuid.uuid4().hex}.json"
        path.write_text(json.dumps({"records": records}), encoding="utf-8")
        return nominate.cmd_record(mock.Mock(file=str(path), run=run, kind=kind))

    @staticmethod
    def page(url="https://www.stuffbureau.gov/", role="own_site", confidence="likely", basis="its own domain"):
        return {"url": url, "role": role, "confidence": confidence, "basis": basis}


class AcceptsHonestNominationsTests(HarnessTestCase):
    def test_a_plausible_page_records(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page()]}]), 0)
        self.assertEqual(list(nominate.read_ledger("source")), ["bureau"])

    def test_a_speculative_nomination_is_allowed(self) -> None:
        # The point of the phase: an agent that cannot fetch may still propose.
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page(confidence="speculative")]}]), 0)

    def test_an_honest_gap_records(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "noCandidate": True, "reason": "no_public_page_known",
            "note": "cannot name a host",
        }]), 0)

    def test_several_roles_for_one_node(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "nominations": [
            self.page(),
            self.page(url="https://www.things.gov/offices", role="parent_listing", basis="the parent's index"),
        ]}]), 0)

    def test_each_run_writes_its_own_file(self) -> None:
        # This is what lets N agents work at once without clobbering.
        self.record([{"id": "bureau", "nominations": [self.page()]}], run="agent-1")
        self.record([{"id": "other", "nominations": [self.page(url="https://www.other.gov/")]}], run="agent-2")
        self.assertEqual(len(nominate.ledger_paths("source")), 2)
        self.assertEqual(sorted(nominate.read_ledger("source")), ["bureau", "other"])


class RefusesUnadjudicableNominationsTests(HarnessTestCase):
    """Not "wrong" — unadjudicable. The verifier could never settle these."""

    def test_a_non_government_host_is_refused(self) -> None:
        code = self.record([{"id": "bureau", "nominations": [self.page(url="https://en.wikipedia.org/wiki/X")]}])
        self.assertEqual(code, 1)

    def test_http_is_refused(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page(url="http://www.stuff.gov/")]}]), 1)

    def test_a_dataset_host_is_refused(self) -> None:
        # A record about a unit is never the unit's own page.
        for host in ("fiscaldata.treasury.gov", "api.usaspending.gov"):
            with self.subTest(host=host):
                code = self.record([{"id": "bureau", "nominations": [self.page(url=f"https://{host}/x")]}])
                self.assertEqual(code, 1)

    def test_certainty_is_refused(self) -> None:
        # An agent that cannot read the page cannot be certain it is the page.
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page(confidence="certain")]}]), 1)

    def test_a_url_already_fetched_and_failed_is_refused(self) -> None:
        # https://www.stuff.gov/ 404ed for this node; re-nominating it burns
        # the scarcest thing here.
        code = self.record([{"id": "bureau", "nominations": [self.page(url="https://www.stuff.gov/")]}])
        self.assertEqual(code, 1)

    def test_a_url_already_queued_is_refused(self) -> None:
        self.assertEqual(self.record([{"id": "dept", "nominations": [self.page(url="https://www.things.gov/")]}]), 1)

    def test_a_nomination_without_a_basis_is_refused(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page(basis="  ")]}]), 1)

    def test_a_position_is_refused(self) -> None:
        self.assertEqual(self.record([{"id": "post", "nominations": [self.page()]}]), 1)

    def test_an_unknown_no_candidate_reason_is_refused(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "noCandidate": True, "reason": "too hard"}]), 1)

    def test_no_candidate_beside_nominations_is_refused(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "noCandidate": True, "reason": "covered_by_parent",
            "nominations": [self.page()],
        }]), 1)

    def test_one_bad_record_rejects_the_batch(self) -> None:
        code = self.record([
            {"id": "bureau", "nominations": [self.page()]},
            {"id": "other", "nominations": [self.page(url="http://nope.gov/")]},
        ])
        self.assertEqual(code, 1)
        self.assertEqual(nominate.ledger_paths("source"), [])


class ShardingTests(HarnessTestCase):
    def _shard(self, spec):
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            nominate.cmd_next(mock.Mock(kind="source", count=100, shard=spec,
                                        include_covered=False, run="r"))
        return [n["id"] for n in json.loads(out.getvalue())["nodes"]]

    def test_shards_are_disjoint_and_complete(self) -> None:
        whole = set(self._shard(None))
        halves = [self._shard("1/2"), self._shard("2/2")]
        self.assertEqual(set(halves[0]) | set(halves[1]), whole)
        self.assertEqual(set(halves[0]) & set(halves[1]), set())

    def test_positions_and_synthetic_lines_are_never_handed_out(self) -> None:
        # 4,382 positions would otherwise produce 4,382 identical refusals.
        ids = self._shard(None)
        self.assertNotIn("post", ids)
        self.assertNotIn("receipts", ids)

    def test_a_node_that_already_has_a_page_is_skipped(self) -> None:
        self.assertNotIn("dept", self._shard(None))

    def test_an_out_of_range_shard_is_an_error(self) -> None:
        with self.assertRaises(SystemExit):
            self._shard("3/2")


class PromoteTests(HarnessTestCase):
    def test_promote_queues_the_url_and_records_who_proposed_it(self) -> None:
        self.record([{"id": "bureau", "nominations": [self.page()]}], run="agent-7")
        nominate.cmd_promote(mock.Mock(kind="source", dry_run=False, only_role=None, limit=10))
        sites = json.loads(self.sites.read_text(encoding="utf-8"))
        self.assertIn("https://www.stuffbureau.gov/", sites["bureau"])
        provenance = json.loads(self.provenance.read_text(encoding="utf-8"))
        self.assertEqual(provenance["bureau"]["source"], "agent_nomination")
        self.assertEqual(provenance["bureau"]["run"], "agent-7")
        self.assertIn("not evidence", provenance["bureau"]["note"].lower())

    def test_a_dry_run_writes_nothing(self) -> None:
        self.record([{"id": "bureau", "nominations": [self.page()]}])
        nominate.cmd_promote(mock.Mock(kind="source", dry_run=True, only_role=None, limit=10))
        self.assertEqual(json.loads(self.sites.read_text(encoding="utf-8")), SITES)

    def test_a_gap_is_never_promoted(self) -> None:
        self.record([{"id": "bureau", "noCandidate": True, "reason": "editorial_grouping"}])
        nominate.cmd_promote(mock.Mock(kind="source", dry_run=False, only_role=None, limit=10))
        self.assertNotIn("bureau", json.loads(self.sites.read_text(encoding="utf-8")))


class CostNominationTests(HarnessTestCase):
    def test_a_scoped_identifier_records(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "net_outlays",
            "identifiers": [{"system": "treasury_mts", "key": "Total--Bureau of Stuff",
                             "basis": "printed under the department the graph gives it",
                             "confidence": "likely"}],
        }], kind="cost"), 0)

    def test_an_unknown_metric_is_refused(self) -> None:
        # The five numbers are different measurements; a sixth is a category
        # error waiting to be published.
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "spending",
            "identifiers": [{"system": "treasury_mts", "key": "x", "basis": "y", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_an_unknown_system_is_refused(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "net_outlays",
            "identifiers": [{"system": "a_website", "key": "x", "basis": "y", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_an_identifier_without_a_basis_is_refused(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "net_outlays",
            "identifiers": [{"system": "treasury_mts", "key": "x", "basis": "", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_certainty_is_refused_here_too(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "net_outlays",
            "identifiers": [{"system": "treasury_mts", "key": "x", "basis": "y", "confidence": "certain"}],
        }], kind="cost"), 1)

    def test_a_reasoned_gap_records(self) -> None:
        self.assertEqual(self.record([{
            "id": "bureau", "noCandidate": True,
            "reason": "The only line that reaches it also covers a sibling, so it is the parent's key.",
        }], kind="cost"), 0)

    def test_a_position_may_carry_a_pay_nomination(self) -> None:
        # Unlike a page, a position can have a cost-side identifier: its rate
        # of basic pay, which is not the unit's cost and is labelled as such.
        self.assertEqual(self.record([{
            "id": "post", "metric": "basic_pay",
            "identifiers": [{"system": "opm_pay_table", "key": "EX-II",
                             "basis": "the archive reports this post at Executive Schedule level II",
                             "confidence": "likely"}],
        }], kind="cost"), 0)

    def test_cost_and_source_ledgers_are_separate(self) -> None:
        self.record([{"id": "bureau", "nominations": [self.page()]}], kind="source", run="a")
        self.record([{"id": "bureau", "noCandidate": True, "reason": "x"}], kind="cost", run="a")
        self.assertEqual(len(nominate.read_ledger("source")), 1)
        self.assertEqual(len(nominate.read_ledger("cost")), 1)


class RunbookTests(unittest.TestCase):
    """Neither runbook may teach something the harness refuses."""

    ROOT = Path(__file__).resolve().parents[1] / "docs"

    def test_the_source_runbook_documents_every_vocabulary(self) -> None:
        text = (self.ROOT / "SOURCE_NOMINATION_RUNBOOK.md").read_text(encoding="utf-8")
        for value in nominate.SOURCE_ROLES + nominate.NO_CANDIDATE_REASONS:
            self.assertIn(value, text, f"{value!r} is not documented")
        self.assertIn("scripts/nominate.py", text)
        self.assertIn("--shard", text)

    def test_the_cost_runbook_documents_every_vocabulary(self) -> None:
        text = (self.ROOT / "COST_NOMINATION_RUNBOOK.md").read_text(encoding="utf-8")
        for value in nominate.COST_METRICS + nominate.COST_SYSTEMS:
            self.assertIn(value, text, f"{value!r} is not documented")

    def test_both_runbooks_refuse_certainty(self) -> None:
        for name in ("SOURCE_NOMINATION_RUNBOOK.md", "COST_NOMINATION_RUNBOOK.md"):
            text = (self.ROOT / name).read_text(encoding="utf-8")
            self.assertIn("certain", text, f"{name} does not mention the refused confidence level")

    def test_the_cost_runbook_reads_phase_one(self) -> None:
        # The dependency the owner asked for: phase 2 is built on phase 1.
        text = (self.ROOT / "COST_NOMINATION_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("node_audit.jsonl", text)
        self.assertIn("NODE_AUDIT_RUNBOOK.md", text)

    def test_the_audit_runbook_hands_off_to_both(self) -> None:
        text = (self.ROOT / "NODE_AUDIT_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("SOURCE_NOMINATION_RUNBOOK.md", text)
        self.assertIn("COST_NOMINATION_RUNBOOK.md", text)


if __name__ == "__main__":
    unittest.main()
