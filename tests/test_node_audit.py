"""The audit harness is a gate, so it is tested like one: in both directions.

Its whole value is that it refuses a finding whose evidence does not check
out. A version of it that accepted everything would still look like it was
working — that is exactly how this repository's earlier validators "ran
happily and were wrong" — so the refusals are what these tests pin.
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from scripts import node_audit

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

GRAPH = {
    "id": "root",
    "name": "Root",
    "type": "Foundation",
    "children": [
        {"id": "dept", "name": "Department of Things", "type": "Department", "desc": "Does things.",
         "cost_status": "official", "resolved_total_amount": 100.0,
         "children": [
             {"id": "bureau", "name": "Bureau of Stuff", "type": "Bureau", "children": []},
             {"id": "twin", "name": "Bureau of Stuff", "type": "Bureau", "children": []},
         ]},
    ],
}

CHECKS_OK = {
    "existence": "no_evidence_in_repo",
    "placement": "no_evidence_in_repo",
    "name_currency": "no_evidence_in_repo",
    "node_type": "fits",
    "description": "no_description",
    "cost": "estimate_only",
    "duplication": "distinct",
}


class HarnessTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"audit-{uuid.uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp_path, True)
        graph_path = self.tmp_path / "graph.json"
        graph_path.write_text(json.dumps(GRAPH), encoding="utf-8")
        self.ledger = self.tmp_path / "node_audit.jsonl"
        self.evidence_dir = self.tmp_path / "verification"
        self.evidence_dir.mkdir()
        for name in ("evidence", "directory_evidence", "headcount_evidence", "position_evidence"):
            (self.evidence_dir / f"{name}.json").write_text(json.dumps({"nodes": {}}), encoding="utf-8")
        patches = {
            "GRAPH": graph_path,
            "LEDGER": self.ledger,
            "EVIDENCE_DIR": self.evidence_dir,
        }
        for attr, value in patches.items():
            patcher = mock.patch.object(node_audit, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def record(self, records, force=False):
        path = self.tmp_path / f"batch-{uuid.uuid4().hex}.json"
        path.write_text(json.dumps({"records": records}), encoding="utf-8")
        args = mock.Mock(file=str(path), force=force)
        return node_audit.cmd_record(args)

    def clean(self, node_id="bureau", **overrides):
        record = {"id": node_id, "checks": dict(CHECKS_OK), "findings": []}
        record.update(overrides)
        return record


class AcceptsHonestWorkTests(HarnessTestCase):
    def test_a_clean_node_records(self) -> None:
        self.assertEqual(self.record([self.clean()]), 0)
        self.assertEqual(list(node_audit.read_ledger()), ["bureau"])

    def test_a_finding_citing_a_real_quote_records(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "certain",
            "claim": "The project documents its standing rule.",
            "evidence": [{"source": "CLAUDE.md", "locator": "Project goal",
                          "quote": "never let the data or the UI claim more than the evidence supports"}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(code, 0)

    def test_a_quote_spanning_a_wrapped_line_still_matches(self) -> None:
        """These files are hard-wrapped, so an honest sentence-length quote
        crosses a line break. Comparing raw would fail every one of them and
        teach an agent to quote three words at a time or to fight the tool —
        neither of which makes the citation truer. The words must still all be
        present in order, so normalising space lets nothing invented through."""
        wrapped = "never let the data or the UI claim more than the evidence supports"
        raw = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn(wrapped, raw, "CLAUDE.md no longer wraps this sentence; pick another")
        code = self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "certain",
            "claim": "The project documents its standing rule.",
            "evidence": [{"source": "CLAUDE.md", "locator": "Project goal", "quote": wrapped}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(code, 0)

    def test_normalising_space_does_not_admit_an_invented_sentence(self) -> None:
        # The tolerance is for line breaks, not for content: reordered or
        # extra words must still fail.
        code = self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "certain",
            "claim": "Invented.",
            "evidence": [{"source": "CLAUDE.md", "locator": "",
                          "quote": "never let the data or the UI claim less than the evidence supports"}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(code, 1)

    def test_a_speculative_finding_may_carry_no_evidence(self) -> None:
        # The one confidence level that can stand alone: it is how an agent
        # raises a question honestly instead of dressing it as a fact.
        code = self.record([self.clean(findings=[{
            "kind": "wrong_type", "severity": "note", "confidence": "speculative",
            "claim": "This may be a grouping rather than a bureau.",
            "evidence": [], "proposedAction": "Curator: check.",
        }])])
        self.assertEqual(code, 0)

    def test_a_gov_url_is_citable_without_being_re_read(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "stale_name", "severity": "correction", "confidence": "likely",
            "claim": "Renamed per the agency's own page.",
            "evidence": [{"source": "https://www.opm.gov/some/page", "locator": "heading",
                          "quote": "anything at all"}],
            "proposedAction": "Curator: rename.",
        }])])
        self.assertEqual(code, 0)

    def test_the_ledger_is_append_only_across_batches(self) -> None:
        self.record([self.clean("bureau")])
        self.record([self.clean("twin")])
        self.assertEqual(sorted(node_audit.read_ledger()), ["bureau", "twin"])


class RefusesFabricationTests(HarnessTestCase):
    """Each of these is a way an agent invents support for a claim."""

    def test_a_quote_that_is_not_in_the_file_is_refused(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "stale_name", "severity": "correction", "confidence": "certain",
            "claim": "It was renamed.",
            "evidence": [{"source": "CLAUDE.md", "locator": "somewhere",
                          "quote": "the Bureau of Stuff was renamed in 2024"}],
            "proposedAction": "Rename.",
        }])])
        self.assertEqual(code, 1)
        self.assertFalse(self.ledger.exists(), "a rejected batch wrote to the ledger")

    def test_a_confident_finding_with_no_evidence_is_refused(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "not_a_real_unit", "severity": "blocking", "confidence": "certain",
            "claim": "This unit does not exist.", "evidence": [], "proposedAction": "Delete.",
        }])])
        self.assertEqual(code, 1)

    def test_a_file_outside_the_citable_roots_is_refused(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "likely",
            "claim": "Per a file nobody publishes.",
            "evidence": [{"source": "/etc/hostname", "locator": "", "quote": ""}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(code, 1)

    def test_a_non_government_url_is_refused(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "stale_name", "severity": "correction", "confidence": "likely",
            "claim": "Per an encyclopedia.",
            "evidence": [{"source": "https://en.wikipedia.org/wiki/Thing", "locator": "", "quote": ""}],
            "proposedAction": "Rename.",
        }])])
        self.assertEqual(code, 1)

    def test_a_missing_file_is_refused(self) -> None:
        code = self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "likely",
            "claim": "Per a file that is not there.",
            "evidence": [{"source": "docs/NO_SUCH_FILE.md", "locator": "", "quote": "x"}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(code, 1)


class RefusesMalformedWorkTests(HarnessTestCase):
    def test_an_unknown_check_value_is_refused(self) -> None:
        record = self.clean()
        record["checks"]["existence"] = "probably fine"
        self.assertEqual(self.record([record]), 1)

    def test_a_missing_check_is_refused(self) -> None:
        record = self.clean()
        del record["checks"]["duplication"]
        self.assertEqual(self.record([record]), 1)

    def test_an_unknown_finding_kind_is_refused(self) -> None:
        self.assertEqual(self.record([self.clean(findings=[{
            "kind": "vibes", "severity": "note", "confidence": "speculative",
            "claim": "Something.", "evidence": [], "proposedAction": "",
        }])]), 1)

    def test_a_finding_with_no_claim_is_refused(self) -> None:
        self.assertEqual(self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "speculative",
            "claim": "   ", "evidence": [], "proposedAction": "",
        }])]), 1)

    def test_a_node_that_is_not_in_the_graph_is_refused(self) -> None:
        self.assertEqual(self.record([self.clean("no-such-node")]), 1)

    def test_re_auditing_needs_force(self) -> None:
        self.assertEqual(self.record([self.clean()]), 0)
        self.assertEqual(self.record([self.clean()]), 1)
        self.assertEqual(self.record([self.clean()], force=True), 0)

    def test_one_bad_record_rejects_the_whole_batch(self) -> None:
        # Letting the good half through teaches an agent that some of its
        # invented citations survive, which is worse than losing the batch.
        good = self.clean("bureau")
        bad = self.clean("twin", findings=[{
            "kind": "other", "severity": "note", "confidence": "certain",
            "claim": "Invented.", "evidence": [], "proposedAction": "",
        }])
        self.assertEqual(self.record([good, bad]), 1)
        self.assertFalse(self.ledger.exists())


class DossierTests(HarnessTestCase):
    def test_next_skips_what_is_already_recorded(self) -> None:
        _, order, parents, by_id = node_audit.load_graph()
        self.assertEqual(order, ["root", "dept", "bureau", "twin"])
        self.record([self.clean("root"), self.clean("dept")])
        done = set(node_audit.read_ledger())
        self.assertEqual([i for i in order if i not in done], ["bureau", "twin"])

    def test_the_dossier_surfaces_a_same_name_sibling(self) -> None:
        # The duplicate hint the audit leans on: two "Bureau of Stuff" nodes.
        _, order, parents, by_id = node_audit.load_graph()
        name_index: dict[str, list[str]] = {}
        for node_id in order:
            name_index.setdefault(str(by_id[node_id].get("name") or "").casefold(), []).append(node_id)
        entry = node_audit.dossier("bureau", order, parents, by_id, node_audit.load_evidence(), name_index)
        self.assertEqual(entry["otherNodesWithThisName"], ["twin"])
        self.assertEqual([a["id"] for a in entry["ancestors"]], ["dept", "root"])

    def test_the_dossier_omits_claims_the_node_does_not_make(self) -> None:
        # published_claims is what the site actually says; a null would read
        # as a claim of absence rather than an absence of claim.
        _, order, parents, by_id = node_audit.load_graph()
        entry = node_audit.dossier("bureau", order, parents, by_id, node_audit.load_evidence(), {})
        self.assertNotIn("employeesOfficial", entry["published_claims"])


class VerifyTests(HarnessTestCase):
    def test_verify_passes_on_citations_that_still_match(self) -> None:
        self.record([self.clean(findings=[{
            "kind": "other", "severity": "note", "confidence": "certain",
            "claim": "The rule is written down.",
            "evidence": [{"source": "CLAUDE.md", "locator": "Project goal",
                          "quote": "never let the data or the UI claim more than the evidence supports"}],
            "proposedAction": "None.",
        }])])
        self.assertEqual(node_audit.cmd_verify(mock.Mock()), 0)

    def test_verify_fails_when_a_cited_file_no_longer_says_it(self) -> None:
        # Written straight to the ledger: record() would have refused it, and
        # the point is that a citation can go stale after it was accepted.
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({
            "id": "bureau", "checks": dict(CHECKS_OK), "findings": [{
                "kind": "other", "severity": "note", "confidence": "certain",
                "claim": "Something that was true once.",
                "evidence": [{"source": "CLAUDE.md", "locator": "", "quote": "a sentence nobody wrote"}],
                "proposedAction": "",
            }],
        }) + "\n", encoding="utf-8")
        self.assertEqual(node_audit.cmd_verify(mock.Mock()), 1)


class RunbookTests(unittest.TestCase):
    """The runbook must not teach anything the harness refuses."""

    RUNBOOK = PROJECT_ROOT / "docs" / "NODE_AUDIT_RUNBOOK.md"

    def test_the_runbook_exists_and_names_the_harness(self) -> None:
        text = self.RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("scripts/node_audit.py", text)

    def test_every_check_vocabulary_is_documented(self) -> None:
        text = self.RUNBOOK.read_text(encoding="utf-8")
        for name, values in node_audit.CHECKS.items():
            self.assertIn(f"`{name}`", text, f"check {name} is not documented")
            for value in values:
                self.assertIn(value, text, f"{name} value {value!r} is not documented")

    def test_every_finding_kind_and_level_is_documented(self) -> None:
        text = self.RUNBOOK.read_text(encoding="utf-8")
        for kind in node_audit.FINDING_KINDS:
            self.assertIn(kind, text, f"finding kind {kind!r} is not documented")
        for level in node_audit.SEVERITIES + node_audit.CONFIDENCES:
            self.assertIn(level, text)

    def test_the_runbook_forbids_editing_the_curated_file(self) -> None:
        text = self.RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("data/federal_gov_complete_1.json", text)
        self.assertIn("append", text.lower())


if __name__ == "__main__":
    unittest.main()
