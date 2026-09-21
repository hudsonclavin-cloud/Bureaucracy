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

    def test_the_latest_record_wins_whatever_its_file_is_called(self) -> None:
        # A blind decline in pass1 and a live-fetched nomination in brute1:
        # alphabetically brute1 comes first, and the file order used to let
        # the older decline shadow the newer nomination.
        self.assertEqual(self.record([{"id": "bureau", "noCandidate": True, "reason": "covered_by_parent",
                                       "nominatedAt": "2026-09-09T00:00:00Z"}], run="pass1"), 0)
        self.assertEqual(self.record([{"id": "bureau", "nominations": [self.page()],
                                       "nominatedAt": "2026-09-13T23:30:00Z"}], run="brute1"), 0)
        latest = nominate.read_ledger("source")["bureau"]
        self.assertEqual(latest["run"], "brute1")
        self.assertFalse(latest.get("noCandidate"))

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

    def test_a_url_fetched_for_another_node_is_still_nominable(self) -> None:
        # stuff.gov 404ed for "bureau", not for "other": the refusal is per
        # node. A parent's page is read once and lists many children, and
        # the global rule had refused senate.gov as the page that labels the
        # Secretary of the Senate because it had already confirmed the Senate.
        code = self.record([{"id": "other", "nominations": [self.page(url="https://www.stuff.gov/", role="parent_listing")]}])
        self.assertEqual(code, 0)

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
        # Each name is a different measurement; one that is not in the
        # vocabulary is a category error waiting to be published.
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "spending",
            "identifiers": [{"system": "treasury_mts", "key": "x", "basis": "y", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_a_budget_request_is_nominable_now_the_vocabulary_carries_it(self) -> None:
        # Congressional Justifications report requests, and a request used to
        # be inexpressible here while the evidence side could record it.
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "budget_request",
            "identifiers": [{"system": "omb_public_budget", "key": "015-10",
                             "basis": "the CJ prints this bureau as its own row",
                             "confidence": "likely"}],
        }], kind="cost"), 0)

    def test_a_rate_of_pay_is_refused_for_an_organisation(self) -> None:
        # The same node-kind rule the release gate and the evidence validator
        # apply. Widening the vocabulary made this reachable more ways.
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "basic_pay",
            "identifiers": [{"system": "opm_pay_table", "key": "EX-II", "basis": "y", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_an_organisations_measure_is_refused_for_a_position(self) -> None:
        self.assertEqual(self.record([{
            "id": "post", "metric": "net_outlays",
            "identifiers": [{"system": "treasury_mts", "key": "x", "basis": "y", "confidence": "likely"}],
        }], kind="cost"), 1)

    def test_a_rate_of_pay_is_accepted_for_a_position(self) -> None:
        self.assertEqual(self.record([{
            "id": "post", "metric": "basic_pay",
            "identifiers": [{"system": "opm_pay_table", "key": "EX-II",
                             "basis": "the archive reports this post at Level II",
                             "confidence": "likely"}],
        }], kind="cost"), 0)

    def test_a_headcount_is_not_a_cost_identifier(self) -> None:
        # A valid financial-evidence basis, but not something to nominate as
        # a node's cost.
        self.assertEqual(self.record([{
            "id": "bureau", "metric": "full_time_equivalents",
            "identifiers": [{"system": "omb_public_budget", "key": "x", "basis": "y", "confidence": "likely"}],
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



class RefilingTests(HarnessTestCase):
    """A URL already queued under a node's OWN key, re-nominated under a role
    that files it elsewhere, is a refiling -- the one input
    `promote --refile-misplaced` acts on. The 2026-09-20 adversarial pass
    found 35 subcommittees carrying their committee's index page as their
    own, 26 of them published as verified on it, and the harness refused
    the repair twice: once as "already a candidate", once as "already
    fetched for this node". Both rules keep their force for own_site."""

    def setUp(self) -> None:
        super().setUp()
        self.sites.write_text(json.dumps({"bureau": ["https://www.things.gov/subcommittees"]}), encoding="utf-8")
        (self.tmp_path / "verification" / "evidence.json").write_text(json.dumps({"nodes": {"bureau": {
            "status": "confirmed", "sources": [{"url": "https://www.things.gov/subcommittees", "matchedText": "Bureau of Stuff"}]}}}), encoding="utf-8")

    def test_an_own_site_re_nomination_of_a_queued_url_is_still_refused(self) -> None:
        self.assertNotEqual(self.record([{"id": "bureau", "nominations": [self.page(url="https://www.things.gov/subcommittees", role="own_site")]}]), 0)

    def test_a_parent_listing_re_nomination_of_the_same_url_is_a_refiling_and_records(self) -> None:
        self.assertEqual(self.record([{"id": "bureau", "nominations": [
            self.page(url="https://www.things.gov/subcommittees", role="parent_listing", basis="the page's own heading names the parent and lists this unit among several")]}]), 0)

if __name__ == "__main__":
    unittest.main()


class ProbeBackedDeclineTests(unittest.TestCase):
    """A decline that says something about a page must carry the reading.

    The first pass with a working network found that `no_public_page_known`
    was doing three jobs: a unit nobody can name a page for, a unit whose host
    refuses this project's crawler, and a unit whose page was read and does
    not carry the graph's name. Those have three different fixes, and one
    string hid which applied. The two new reasons say which -- and because
    each asserts something about a specific URL rather than about the agent's
    ignorance, each is refused without the probe block that supports it.
    """

    def setUp(self) -> None:
        self.node = {"id": "exec-dept-doc-uspto", "name": "USPTO — Patent & Trademark Office",
                     "type": "Bureau", "children": []}

    def _record(self, **kwargs):
        record = {"id": self.node["id"], "noCandidate": True}
        record.update(kwargs)
        return record

    def test_a_probe_backed_decline_is_accepted(self) -> None:
        for reason, verdict in (
            ("host_refuses_crawler", "refused"),
            ("host_refuses_crawler", "fetch_failed"),
            ("page_read_does_not_name_it", "read_not_labelled"),
            ("page_read_does_not_name_it", "read_labelled_in_navigation"),
        ):
            with self.subTest(reason=reason, verdict=verdict):
                nominate.validate_source(
                    self._record(reason=reason, probe={
                        "url": "https://www.uspto.gov/about-us", "verdict": verdict,
                        "detail": "read 4,171 readable characters; the page labels "
                                  '"United States Patent and Trademark Office", not the curated name',
                    }),
                    self.node, {}, {}, set())

    def test_a_reason_that_names_a_page_is_refused_without_one(self) -> None:
        for reason in ("host_refuses_crawler", "page_read_does_not_name_it"):
            with self.subTest(reason=reason):
                with self.assertRaises(nominate.Rejected):
                    nominate.validate_source(self._record(reason=reason), self.node, {}, {}, set())

    def test_the_probe_must_agree_with_what_the_reason_claims(self) -> None:
        cases = {
            # "the host refused us" beside a probe that read the page
            "refused_but_read": ("host_refuses_crawler", "read_not_labelled"),
            # "we read it and the name is absent" beside a probe that read nothing
            "read_but_refused": ("page_read_does_not_name_it", "refused"),
        }
        for name, (reason, verdict) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(nominate.Rejected):
                    nominate.validate_source(
                        self._record(reason=reason, probe={
                            "url": "https://www.uspto.gov/", "verdict": verdict, "detail": "x"}),
                        self.node, {}, {}, set())

    def test_a_probe_needs_a_gov_url_a_known_verdict_and_a_detail(self) -> None:
        bad = {
            "a non-gov host": {"url": "https://uspto.com/", "verdict": "refused", "detail": "x"},
            "an invented verdict": {"url": "https://www.uspto.gov/", "verdict": "looked_wrong", "detail": "x"},
            "no detail": {"url": "https://www.uspto.gov/", "verdict": "refused", "detail": "  "},
            "not an object": "https://www.uspto.gov/",
        }
        for name, probe in bad.items():
            with self.subTest(case=name):
                with self.assertRaises(nominate.Rejected):
                    nominate.validate_source(
                        self._record(reason="host_refuses_crawler", probe=probe),
                        self.node, {}, {}, set())

    def test_an_ignorance_decline_still_needs_no_probe(self) -> None:
        """The distinction is the point: admitting you cannot name a page is
        not a claim about any page, so it carries no evidence and never did."""
        for reason in ("no_public_page_known", "covered_by_parent", "editorial_grouping", "not_on_a_gov_host"):
            with self.subTest(reason=reason):
                nominate.validate_source(self._record(reason=reason), self.node, {}, {}, set())


class FilingByRoleTests(unittest.TestCase):
    """Which key a nominated URL is filed under decides what gets CLAIMED.

    `official_sites.json` is keyed by node, and `evidence.candidate_urls`
    returns distance 0 for any URL under a node's own key, which `verify_node`
    turns into `name_labelled_on_own_official_page`. Until 2026-09-18 the role
    was written to the provenance file and never read again, so a
    `parent_listing` nomination -- the parent's index page, which is what the
    role means -- published the claim that it was the unit's own page.

    Twenty confirmations were live on the site under it, among them nine
    Department of Energy national laboratories each citing
    `energy.gov/national-laboratories` as ITS OWN official page.
    """

    PARENTS = {"lab": "labs", "labs": "doe", "doe": None, "orphan": None}

    def test_an_own_site_url_files_under_the_node(self) -> None:
        self.assertEqual(nominate.filing_id_for_role("lab", "own_site", self.PARENTS), ("lab", None))

    def test_a_parent_listing_url_files_under_the_parent(self) -> None:
        """So the verifier finds it one level up, is_own_page is False, and it
        publishes name_labelled_on_parent_official_page -- 'the parent's
        official page lists it', which is what the runbook has always said."""
        self.assertEqual(nominate.filing_id_for_role("lab", "parent_listing", self.PARENTS), ("labs", None))

    def test_a_parent_listing_url_for_a_node_with_no_parent_is_refused(self) -> None:
        filing, why = nominate.filing_id_for_role("orphan", "parent_listing", self.PARENTS)
        self.assertIsNone(filing)
        self.assertIn("no_parent", why)

    def test_an_official_list_url_is_never_filed(self) -> None:
        """A government directory is neither the unit's page nor its parent's,
        and both available methods would misdescribe it. Structured
        directories have their own modules here; promoting one into the page
        queue would buy a confirmation by mislabelling it."""
        filing, why = nominate.filing_id_for_role("lab", "official_list", self.PARENTS)
        self.assertIsNone(filing)
        self.assertIn("no_truthful_verifier_method", why)

    def test_an_unknown_role_is_refused_rather_than_defaulted(self) -> None:
        filing, why = nominate.filing_id_for_role("lab", "somebody's_guess", self.PARENTS)
        self.assertIsNone(filing)
        self.assertIn("unknown_role", why)


class RefileMisplacedTests(unittest.TestCase):
    """Repairing a queue written before the rule existed."""

    PARENTS = {"lab": "labs", "labs": "doe", "doe": None}
    BY_ID = {"lab": {"id": "lab"}, "labs": {"id": "labs"}, "doe": {"id": "doe"}}

    def _records(self, role, url="https://www.energy.gov/national-laboratories"):
        return {"lab": {"id": "lab", "nominations": [{"url": url, "role": role}]}}

    def test_a_parent_listing_url_is_moved_off_the_node_and_onto_the_parent(self) -> None:
        sites = {"lab": ["https://www.energy.gov/national-laboratories"]}
        moved, dropped = nominate.refile_misplaced(sites, self._records("parent_listing"), self.PARENTS, self.BY_ID)
        self.assertEqual(dropped, [])
        self.assertEqual([m[3] for m in moved], ["labs"])
        self.assertNotIn("lab", sites)
        self.assertEqual(sites["labs"], ["https://www.energy.gov/national-laboratories"])

    def test_the_provenance_record_moves_with_the_url(self) -> None:
        """A committed test asserts the queue and the provenance file agree on
        the key. A URL that moves without its record points a reader at a node
        whose queue no longer holds the URL the record describes."""
        url = "https://www.energy.gov/national-laboratories"
        sites = {"lab": [url]}
        provenance = {"lab": {"url": url, "role": "parent_listing", "basis": "x"}}
        nominate.refile_misplaced(sites, self._records("parent_listing"), self.PARENTS, self.BY_ID, provenance)
        self.assertNotIn("lab", provenance)
        self.assertEqual(provenance["labs"]["url"], url)
        self.assertEqual(provenance["labs"]["nominatedFor"], "lab")

    def test_a_dropped_url_takes_its_provenance_record_out(self) -> None:
        url = "https://www.archives.gov/presidential-libraries"
        sites = {"lab": [url]}
        provenance = {"lab": {"url": url, "role": "official_list"}}
        nominate.refile_misplaced(
            sites, self._records("official_list", url), self.PARENTS, self.BY_ID, provenance)
        self.assertEqual(provenance, {})
        self.assertEqual(sites, {})

    def test_an_official_list_url_is_removed_and_filed_nowhere(self) -> None:
        sites = {"lab": ["https://www.archives.gov/presidential-libraries"]}
        moved, dropped = nominate.refile_misplaced(
            sites, self._records("official_list", "https://www.archives.gov/presidential-libraries"),
            self.PARENTS, self.BY_ID)
        self.assertEqual(moved, [])
        self.assertEqual(len(dropped), 1)
        self.assertEqual(sites, {})

    def test_an_own_site_url_is_left_exactly_where_it_is(self) -> None:
        sites = {"lab": ["https://www.anl.gov/"]}
        moved, dropped = nominate.refile_misplaced(
            sites, self._records("own_site", "https://www.anl.gov/"), self.PARENTS, self.BY_ID)
        self.assertEqual((moved, dropped), ([], []))
        self.assertEqual(sites, {"lab": ["https://www.anl.gov/"]})

    def test_a_url_with_no_ledger_nomination_is_never_touched(self) -> None:
        """A seeded or hand-added URL is left alone, because nothing here knows
        what role it was meant to have."""
        sites = {"lab": ["https://seeded.gov/", "https://www.energy.gov/national-laboratories"]}
        nominate.refile_misplaced(sites, self._records("parent_listing"), self.PARENTS, self.BY_ID)
        self.assertEqual(sites["lab"], ["https://seeded.gov/"])

    def test_refiling_twice_changes_nothing_the_second_time(self) -> None:
        sites = {"lab": ["https://www.energy.gov/national-laboratories"]}
        records = self._records("parent_listing")
        nominate.refile_misplaced(sites, records, self.PARENTS, self.BY_ID)
        after_first = json.loads(json.dumps(sites))
        moved, dropped = nominate.refile_misplaced(sites, records, self.PARENTS, self.BY_ID)
        self.assertEqual((moved, dropped), ([], []))
        self.assertEqual(sites, after_first)
