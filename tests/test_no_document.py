"""A recorded reason no official document can be read for a unit.

`verificationNoDocument` publishes why no page was ever queued for an
organisation: the verifier's own floor on the NAME, recomputed every build,
or the phase 1b nomination ledger's latest decline, quoted. Both directions
are pinned here: the module stamps exactly what the ledger and the floor say
and nothing where the latest record nominates a page; the gate mirrors the
floor, the ledger reader and the vocabulary (stdlib-only), re-reads the
committed ledger, and refuses every corruption in turn.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import nominate  # noqa: E402
import validate_published_graph as gate  # noqa: E402
from data_pipeline.exporter.build_graph import index_tree, load_base_graph, DEFAULT_BASE_GRAPH  # noqa: E402
from data_pipeline.verification import no_document  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    EVIDENCE_OWNED_FIELDS,
    GENERIC_SINGLE_TOKENS,
    uncheckable_reason,
)

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"
TMP = PROJECT_ROOT / "tests" / ".tmp"


def org(node_id, name, children=None, **fields):
    return {"id": node_id, "name": name, "type": "Division", "children": children or [], **fields}


def tree(*children):
    return {"id": "the-constitution-of-the-united-states", "name": "Root", "type": "Foundation",
            "children": [{"id": "branch", "name": "A Branch", "type": "Branch", "children": list(children)}]}


def ledger_record(node_id, reason, *, note="tried and found nothing", probe=None, nominated_at="2026-09-20T23:44:26Z", run="sweep"):
    record = {"id": node_id, "noCandidate": True, "reason": reason, "note": note, "kind": "source",
              "run": run, "nominatedAt": nominated_at}
    if probe:
        record["probe"] = probe
    return record


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirrors_the_vocabulary(self):
        self.assertEqual(gate.NO_DOCUMENT_FIELD, no_document.FIELD)
        self.assertEqual(gate.NO_DOCUMENT_NAME_FLOOR_KINDS, no_document.NAME_FLOOR_KINDS)
        self.assertEqual(gate.NO_DOCUMENT_LEDGER_KINDS, no_document.LEDGER_KINDS)
        self.assertEqual(gate.NO_DOCUMENT_PROBE_KINDS, no_document.PROBE_KINDS)
        self.assertEqual(gate.NO_DOCUMENT_NOTE_CHARS, no_document.NOTE_CHARS)
        self.assertEqual(gate.NO_DOCUMENT_GENERIC_SINGLE_TOKENS, GENERIC_SINGLE_TOKENS)

    def test_the_ledger_kinds_are_the_ledgers_own_reasons_less_the_type_refusal(self):
        self.assertEqual(set(no_document.LEDGER_KINDS), set(nominate.NO_CANDIDATE_REASONS) - {"not_an_organisation"})
        self.assertEqual(set(no_document.PROBE_KINDS), set(nominate.REASONS_REQUIRING_A_PROBE))

    def test_the_gate_s_name_floor_equals_the_verifier_s_on_every_curated_organisation(self):
        base = load_base_graph(DEFAULT_BASE_GRAPH)
        nodes, _ = index_tree(base)
        checked = 0
        for node in nodes.values():
            if not no_document.is_current_organisation(node):
                continue
            checked += 1
            expected = uncheckable_reason(str(node.get("name") or ""))
            self.assertEqual(gate.no_document_name_floor(node.get("name")), expected, node.get("name"))
        self.assertGreater(checked, 800)
        for name in ("Mission Teams (15)", "All 94 District Courts — Standard Structure", "Defense",
                     "Districts (multiple)", "VISN 1 — New England", "K-9 Unit", "Office of Science"):
            self.assertEqual(gate.no_document_name_floor(name), uncheckable_reason(name), name)

    def test_both_ledger_readers_agree_with_nominate_on_the_committed_ledger(self):
        theirs = nominate.read_ledger("source")
        ours = no_document.read_source_ledger()
        gates = gate.no_document_read_ledger(gate.NO_DOCUMENT_LEDGER_DIR)
        self.assertEqual(set(theirs), set(ours))
        self.assertEqual(set(theirs), set(gates))
        for node_id, record in theirs.items():
            mine = dict(ours[node_id]); mine.pop("_file")
            his = dict(gates[node_id]); his.pop("_file")
            self.assertEqual(mine, record, node_id)
            self.assertEqual(his, record, node_id)
        self.assertGreater(len(theirs), 500)

    def test_the_field_is_owned_and_in_the_viewer_copy(self):
        from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS

        self.assertIn(no_document.FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(no_document.FIELD, MINIMAL_GRAPH_FIELDS)


class ApplyTests(unittest.TestCase):
    def _apply(self, root, ledger, renames=None):
        return no_document.apply_no_document_evidence(root, ledger=ledger, rename_dates=renames or {}, index_tree=index_tree)

    def test_the_name_floor_is_stamped_from_the_name_and_needs_no_record(self):
        root = tree(org("teams", "Mission Teams (15)"), org("d", "Defense", type="Subcommittee"), org("ok", "Office of Science"))
        stats = self._apply(root, {})
        nodes, _ = index_tree(root)
        self.assertEqual(nodes["teams"][no_document.FIELD], {"kind": "curated_count_label", "basis": "verifier_name_floor", "name": "Mission Teams (15)"})
        self.assertEqual(nodes["d"][no_document.FIELD]["kind"], "name_too_generic")
        self.assertNotIn(no_document.FIELD, nodes["ok"])
        self.assertEqual(stats["stamped"], 2)
        # the branch grouping and "Office of Science": neither trips the floor and neither has a record
        self.assertEqual(stats["refusals"], {"no_ledger_record": 2})

    def test_a_ledger_decline_is_quoted_field_for_field(self):
        probe = {"url": "https://www.gao.gov/about", "verdict": "refused", "detail": "403"}
        ledger = {
            "g": dict(ledger_record("g", "host_refuses_crawler", probe=probe, note="x" * 400), _file="source-probe-04.jsonl"),
            "j": dict(ledger_record("j", "editorial_grouping"), _file="source-sweep.jsonl"),
        }
        root = tree(org("g", "Economic & Financial Markets"), org("j", "Joint Congressional Bodies"))
        stats = self._apply(root, ledger)
        nodes, _ = index_tree(root)
        g = nodes["g"][no_document.FIELD]
        self.assertEqual(g["kind"], "host_refuses_crawler")
        self.assertEqual(g["basis"], "nomination_ledger")
        self.assertEqual(g["probe"], {"url": "https://www.gao.gov/about", "verdict": "refused"})
        self.assertEqual(g["note"], "x" * no_document.NOTE_CHARS)
        self.assertEqual(g["ledger"], {"file": "source-probe-04.jsonl", "run": "sweep"})
        self.assertEqual(g["recordedAt"], "2026-09-20T23:44:26Z")
        self.assertNotIn("probe", nodes["j"][no_document.FIELD])
        self.assertEqual(stats["kinds"], {"host_refuses_crawler": 1, "editorial_grouping": 1})

    def test_each_refusal_in_turn(self):
        probe = {"url": "https://www.gao.gov/about", "verdict": "refused"}
        cases = {
            "latest record nominates a page": ({"id": "n", "nominations": [{"url": "https://x.gov/"}], "nominatedAt": "2026-09-20T00:00:00Z"}, "latest_record_nominates_a_page", None),
            "a reason outside the vocabulary": (ledger_record("n", "not_an_organisation"), "reason_is_not_a_no_document_reason", None),
            "no date": (dict(ledger_record("n", "editorial_grouping"), nominatedAt=""), "record_carries_no_date", None),
            "renamed after the record": (ledger_record("n", "editorial_grouping"), "node_renamed_after_the_record", "2026-10-01"),
            "probe missing": (ledger_record("n", "host_refuses_crawler"), "probe_missing", None),
            "probe off every official host": (ledger_record("n", "page_read_does_not_name_it", probe={"url": "https://example.com/", "verdict": "read_not_labelled"}), "probe_url_not_official", None),
        }
        for name, (record, expected, renamed) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(no_document.ledger_refusal(record, renamed_on=renamed), expected)
                root = tree(org("n", "A Real Unit"))
                stats = self._apply(root, {"n": dict(record, _file="f.jsonl")}, {"n": renamed} if renamed else {})
                self.assertEqual(stats["stamped"], 0)
        self.assertIsNone(no_document.ledger_refusal(dict(ledger_record("n", "host_refuses_crawler", probe=probe))))

    def test_never_on_a_post_a_line_a_replaced_unit_or_beside_a_method_or_an_unread_record(self):
        ledger = {k: dict(ledger_record(k, "editorial_grouping"), _file="f") for k in ("p", "l", "s", "m", "u", "ok")}
        root = tree(
            org("p", "A Post (×4)", type="Position"),
            org("l", "Some Receipts (12)", type="Treasury accounting line"),
            org("s", "Old Unit (3)", lifecycle="superseded"),
            org("m", "Listed Unit", verificationMethod="listed_in_us_government_manual"),
            org("u", "Walled Unit", verificationUnread={"kind": "host_refuses_crawler"}),
            org("ok", "Plain Unit"),
        )
        stats = self._apply(root, ledger)
        nodes, _ = index_tree(root)
        for node_id in ("p", "l", "s", "m", "u"):
            self.assertNotIn(no_document.FIELD, nodes[node_id], node_id)
        self.assertIn(no_document.FIELD, nodes["ok"])
        self.assertEqual(stats["organisations"], 4)  # the post and the line are not organisations
        self.assertEqual(stats["with_method"], 1)
        self.assertEqual(stats["unread"], 1)

    def test_the_field_is_cleared_before_it_is_recomputed(self):
        root = tree(org("ok", "Plain Unit", **{no_document.FIELD: {"kind": "editorial_grouping", "basis": "nomination_ledger", "name": "Plain Unit"}}))
        self._apply(root, {})
        nodes, _ = index_tree(root)
        self.assertNotIn(no_document.FIELD, nodes["ok"], "a deleted ledger record is a real withdrawal")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TMP / f"nodoc-{uuid.uuid4().hex}"
        (self.tmp / "ledger").mkdir(parents=True)
        self.ledger_dir = self.tmp / "ledger"
        self.renames = self.tmp / "renames.json"
        self.renames.write_text(json.dumps({"renames": []}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_ledger(self, *records, name="source-sweep.jsonl"):
        (self.ledger_dir / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    def _nodes(self):
        probe = {"url": "https://www.gao.gov/about", "verdict": "refused", "detail": "403"}
        self._write_ledger(ledger_record("g", "host_refuses_crawler", probe=probe), ledger_record("j", "editorial_grouping"))
        root = tree(org("g", "Economic & Financial Markets"), org("j", "Joint Congressional Bodies"), org("teams", "Mission Teams (15)"), org("ok", "Office of Science"))
        no_document.apply_no_document_evidence(root, ledger=no_document.read_source_ledger(self.ledger_dir), rename_dates={}, index_tree=index_tree)
        nodes, _ = index_tree(root)
        return nodes

    def _check(self, nodes):
        return gate.no_document_violations(list(nodes.values()), gate.label, ledger_dir=self.ledger_dir, renames_path=self.renames)

    def test_what_the_module_stamps_passes(self):
        nodes = self._nodes()
        self.assertEqual(self._check(nodes), [])

    def test_a_name_that_trips_the_floor_without_a_block_is_refused(self):
        nodes = self._nodes()
        del nodes["teams"][no_document.FIELD]
        self.assertTrue(any("trips the verifier's name floor" in v for v in self._check(nodes)))
        # a method or an unread record excuses it: the block is not owed there
        nodes["teams"]["verificationMethod"] = "listed_in_us_government_manual"
        self.assertEqual(self._check(nodes), [])

    def test_each_corruption_is_refused(self):
        cases = {
            "not an object": lambda n: n["g"].__setitem__(no_document.FIELD, "yes"),
            "on a post": lambda n: n["g"].__setitem__("type", "Position"),
            "on an accounting line": lambda n: n["j"].__setitem__("type", "Treasury accounting line"),
            "on a replaced unit": lambda n: n["j"].__setitem__("lifecycle", "superseded"),
            "beside a method": lambda n: n["j"].__setitem__("verificationMethod", "listed_in_us_government_manual"),
            "beside an unread record": lambda n: n["j"].__setitem__("verificationUnread", {"kind": "page_not_found"}),
            "invented kind": lambda n: n["j"][no_document.FIELD].__setitem__("kind", "vibes"),
            "another node's name": lambda n: n["j"][no_document.FIELD].__setitem__("name", "Something Else"),
            "name floor on a name that does not trip it": lambda n: n["teams"].update({"name": "Mission Teams", no_document.FIELD: {"kind": "curated_count_label", "basis": "verifier_name_floor", "name": "Mission Teams"}}),
            "name floor with the ledger basis": lambda n: n["teams"][no_document.FIELD].__setitem__("basis", "nomination_ledger"),
            "name floor with an extra key": lambda n: n["teams"][no_document.FIELD].__setitem__("note", "made up"),
            "ledger basis spelled wrong": lambda n: n["j"][no_document.FIELD].__setitem__("basis", "verifier_name_floor"),
            "a node the ledger has no record for": lambda n: n["ok"].__setitem__(no_document.FIELD, dict(n["j"][no_document.FIELD], name="Office of Science")),
            "the other record's reason": lambda n: n["j"][no_document.FIELD].__setitem__("kind", "no_public_page_known"),
            "a different date": lambda n: n["j"][no_document.FIELD].__setitem__("recordedAt", "2026-09-19T00:00:00Z"),
            "a future date": lambda n: n["j"][no_document.FIELD].__setitem__("recordedAt", "2999-01-01T00:00:00Z"),
            "another file": lambda n: n["j"][no_document.FIELD]["ledger"].__setitem__("file", "source-other.jsonl"),
            "another run": lambda n: n["j"][no_document.FIELD]["ledger"].__setitem__("run", "other"),
            "a note the record does not carry": lambda n: n["j"][no_document.FIELD].__setitem__("note", "the agent said something else"),
            "a probe kind with no probe": lambda n: n["g"][no_document.FIELD].pop("probe"),
            "a probe that is not the record's": lambda n: n["g"][no_document.FIELD]["probe"].__setitem__("url", "https://www.gao.gov/other"),
            "a probe on a non-official host": lambda n: n["g"][no_document.FIELD]["probe"].__setitem__("url", "https://example.com/"),
            "an extra key": lambda n: n["g"][no_document.FIELD].__setitem__("sentence", "a paraphrase"),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                nodes = self._nodes()
                corrupt(nodes)
                self.assertNotEqual(self._check(nodes), [], name)

    def test_a_record_that_nominates_a_page_or_a_later_rename_is_refused(self):
        nodes = self._nodes()
        self._write_ledger({"id": "j", "nominations": [{"url": "https://www.senate.gov/"}], "nominatedAt": "2026-09-21T00:00:00Z"},
                           name="source-later.jsonl")
        self.assertTrue(any("NOMINATES a page" in v or "latest record says" in v or "nominatedAt" in v for v in self._check(nodes)))
        (self.ledger_dir / "source-later.jsonl").unlink()
        nodes = self._nodes()
        self.renames.write_text(json.dumps({"renames": [{"id": "j", "from": "Old", "to": "Joint Congressional Bodies", "addedOn": "2026-10-01"}]}), encoding="utf-8")
        self.assertTrue(any("renamed on 2026-10-01" in v for v in self._check(nodes)))

    @unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
    def test_the_published_graph_passes_and_prints_the_criterion(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        nodes = [n for n, _ in gate.walk(graph)]
        self.assertEqual(gate.no_document_violations(nodes, gate.label), [])
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate.main(["gate", str(PUBLISHED)])
        self.assertEqual(code, 0)
        self.assertIn("no document          :", out.getvalue())
        self.assertIn("evidence gap         :", out.getvalue())


if __name__ == "__main__":
    unittest.main()
