"""The posts renamed to a title a committed official document prints
(`scripts/rename_posts_to_printed_titles.py`, `data/curation/post_renames.json`,
since 2026-10-07).

Pinned in both directions: every row applies to the names it was written
against and is idempotent on the curated file; a doctored fixture, a stale
name, a moved node, a changed qualifier, a wrong singular, a class over-counted
and every static refusal each leave the node alone.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph
from scripts import rename_posts_to_printed_titles as writer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEA = "exec-dept-defense-sf-senior-enlisted-advisor"
USTR = (
    "exec-eop-ustr-deputy-ustr-wto-multilateral-affairs",
    "exec-eop-ustr-deputy-ustr-americas",
    "exec-eop-ustr-deputy-ustr-asia",
)
NOTE = "tests/fixtures/uscode/pay_schedules_5_usc_5332.html"
SCHEDULE = "tests/fixtures/uscode/exec_schedule_5314.html"
COMPOSING = "tests/fixtures/uscode/ustr_19_usc_2171_govinfo2024.html"


def _rows():
    return writer.load_table(writer.DEFAULT_TABLE)


def _unrenamed_tree(rows=None):
    """The real curated file with every row's node set back to the name the
    row was written against -- the state the writer acted on."""
    tree = copy.deepcopy(load_base_graph(DEFAULT_BASE_GRAPH))
    node_map, _ = index_tree(tree)
    for row in rows or _rows():
        node = node_map[row["id"]]
        node["name"] = row["from"]
        for key in ("nameSource", "nameSourceDetail", "nameMatchedText"):
            node.pop(key, None)
    return tree


def _by_id(results):
    return {r["id"]: r for r in results}


class _TempFixtures:
    """A project root holding copies of the three fixtures, so a test can
    doctor one without touching the committed bytes."""

    def __enter__(self):
        self.dir = Path(tempfile.mkdtemp())
        for rel in (NOTE, SCHEDULE, COMPOSING):
            for suffix in ("", ".meta.json"):
                source = PROJECT_ROOT / (rel + suffix)
                target = self.dir / (rel + suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def doctor(self, rel, old, new, *, fix_digest=True):
        path = self.dir / rel
        raw = path.read_text(encoding="utf-8")
        assert old in raw, old
        path.write_text(raw.replace(old, new), encoding="utf-8")
        if fix_digest:
            meta_path = self.dir / (rel + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            meta_path.write_text(json.dumps(meta), encoding="utf-8")


class TableTests(unittest.TestCase):
    def test_the_table_names_the_four_rows_the_owner_decided(self):
        rows = _by_id(_rows())
        self.assertEqual({SEA, *USTR}, set(rows))
        self.assertEqual("Chief Master Sergeant of the Space Force", rows[SEA]["to"])
        for node_id in USTR:
            row = rows[node_id]
            self.assertEqual("Deputy United States Trade Representatives (3)", row["printed"])
            self.assertEqual("Deputy United States Trade Representative", row["singular"])
            # Only the abbreviation is spelled out; the qualifier is the graph's own.
            self.assertEqual(row["from"].split(" — ", 1)[1], row["to"].split(" — ", 1)[1])

    def test_the_curated_file_carries_every_rename_and_a_rerun_is_a_no_op(self):
        tree = copy.deepcopy(load_base_graph(DEFAULT_BASE_GRAPH))
        node_map, _ = index_tree(tree)
        for row in _rows():
            self.assertEqual(row["to"], node_map[row["id"]]["name"])
        results = writer.adjudicate(tree, _rows(), apply=True)
        self.assertEqual({"already_applied"}, {r["reason"] for r in results})
        self.assertEqual(load_base_graph(DEFAULT_BASE_GRAPH), tree)


class ApplyTests(unittest.TestCase):
    def test_every_row_applies_to_the_name_it_was_written_against(self):
        tree = _unrenamed_tree()
        results = _by_id(writer.adjudicate(tree, _rows(), apply=True))
        node_map, _ = index_tree(tree)
        for row in _rows():
            with self.subTest(row["id"]):
                self.assertTrue(results[row["id"]]["applied"], results[row["id"]])
                node = node_map[row["id"]]
                self.assertEqual(row["to"], node["name"])
                self.assertEqual(writer.NAME_SOURCES[row["licence"]], node["nameSource"])
                self.assertEqual(row["printed"], node["nameMatchedText"])
                self.assertTrue(node["nameSourceDetail"].startswith("https://uscode.house.gov/"))
                # It only renames: type, children and description are untouched.
                self.assertEqual("Position", node["type"])
                self.assertEqual([], node.get("children") or [])

    def test_a_dry_run_decides_and_writes_nothing(self):
        tree = _unrenamed_tree()
        before = copy.deepcopy(tree)
        results = writer.adjudicate(tree, _rows(), apply=False)
        self.assertTrue(all(r["applied"] for r in results))
        self.assertEqual(before, tree)

    def test_it_never_reparents_retypes_or_removes(self):
        tree = _unrenamed_tree()
        before_map, before_parents = index_tree(copy.deepcopy(tree))
        writer.adjudicate(tree, _rows(), apply=True)
        after_map, after_parents = index_tree(tree)
        self.assertEqual(set(before_map), set(after_map))
        self.assertEqual(before_parents, after_parents)
        self.assertEqual({k: v.get("type") for k, v in before_map.items()},
                         {k: v.get("type") for k, v in after_map.items()})


class RefusalTests(unittest.TestCase):
    def _one(self, row_id, mutate_row=None, mutate_tree=None, project_root=writer.PROJECT_ROOT, rows=None):
        rows = copy.deepcopy(rows or _rows())
        tree = _unrenamed_tree(rows)
        if mutate_tree:
            mutate_tree(index_tree(tree)[0], tree)
        if mutate_row:
            mutate_row(next(r for r in rows if r["id"] == row_id))
        before = copy.deepcopy(tree)
        result = _by_id(writer.adjudicate(tree, rows, apply=True, project_root=project_root))[row_id]
        self.assertFalse(result["applied"], result)
        self.assertEqual(index_tree(before)[0][row_id]["name"], index_tree(tree)[0][row_id]["name"])
        return result["reason"]

    def test_a_stale_current_name_refuses_the_row(self):
        def rename(node_map, _tree):
            node_map[SEA]["name"] = "Senior Enlisted Leader"
        self.assertEqual("curated_name_has_changed", self._one(SEA, mutate_tree=rename))

    def test_a_moved_node_refuses_the_row(self):
        def move(node_map, _tree):
            node = node_map[USTR[1]]
            node_map["exec-eop-ustr"]["children"].remove(node)
            node_map["exec-dept-defense-sf"]["children"].append(node)
        self.assertEqual("node_has_moved", self._one(USTR[1], mutate_tree=move))

    def test_a_node_that_is_not_a_post_refuses_the_row(self):
        def retype(node_map, _tree):
            node_map[SEA]["type"] = "Office"
        self.assertEqual("node_is_not_a_post", self._one(SEA, mutate_tree=retype))

    def test_a_sibling_collision_refuses_the_row(self):
        def twin(node_map, _tree):
            node_map["exec-dept-defense-sf"]["children"].append(
                {"id": "twin", "name": "Chief Master Sergeant of the Space Force", "type": "Position", "children": []})
        self.assertEqual("proposed_name_collides_with_a_sibling", self._one(SEA, mutate_tree=twin))

    def test_static_refusals(self):
        self.assertEqual("rename_is_a_no_op",
                         self._one(SEA, mutate_row=lambda r: r.update(to="Senior Enlisted Advisor (USSF)", printed="Senior Enlisted Advisor (USSF)")))
        self.assertEqual("proposed_name_too_short", self._one(SEA, mutate_row=lambda r: r.update(to="Sergeant")))
        self.assertEqual("proposed_name_is_generic", self._one(SEA, mutate_row=lambda r: r.update(to="Chief of Staff")))
        self.assertEqual("row_states_no_basis", self._one(SEA, mutate_row=lambda r: r.update(basis="")))
        self.assertEqual("unknown_licence", self._one(SEA, mutate_row=lambda r: r.update(licence="a_hunch")))
        self.assertEqual("row_is_incomplete", self._one(SEA, mutate_row=lambda r: r.pop("printed")))

    def test_the_footnote_must_print_the_title_and_the_name_must_be_it(self):
        self.assertEqual("document_does_not_print_the_title",
                         self._one(SEA, mutate_row=lambda r: r.update(printed="Chief Master Sergeant of the Orbital Force",
                                                                     to="Chief Master Sergeant of the Orbital Force")))
        self.assertEqual("proposed_name_is_not_the_printed_title",
                         self._one(SEA, mutate_row=lambda r: r.update(to="Chief Master Sergeant, Space Force")))

    def test_a_doctored_footnote_refuses_the_row(self):
        with _TempFixtures() as fx:
            fx.doctor(NOTE, "Chief Master Sergeant of the Space Force", "Chief Master Sergeant of the Orbital Force")
            self.assertEqual("document_does_not_print_the_title", self._one(SEA, project_root=fx.dir))
        with _TempFixtures() as fx:
            # The same edit with the digest left alone: the bytes are not the
            # bytes that were served, and nothing is read from them.
            fx.doctor(NOTE, "Chief Master Sergeant of the Space Force", "Chief Master Sergeant of the Orbital Force",
                      fix_digest=False)
            self.assertEqual("document_unreadable", self._one(SEA, project_root=fx.dir))

    def test_a_doctored_schedule_or_composing_section_refuses_the_row(self):
        with _TempFixtures() as fx:
            fx.doctor(SCHEDULE, "Deputy United States Trade Representatives (3)", "Deputy Trade Envoys (3)")
            self.assertEqual("document_does_not_print_the_title", self._one(USTR[0], project_root=fx.dir))
        with _TempFixtures() as fx:
            fx.doctor(COMPOSING, "There shall be in the Office three Deputy United States Trade Representatives",
                      "There shall be in the Office two Deputy United States Trade Representatives")
            self.assertEqual("composing_quote_not_in_operative_text", self._one(USTR[0], project_root=fx.dir))
        with _TempFixtures() as fx:
            fx.doctor(SCHEDULE, "Deputy United States Trade Representatives (3)", "Deputy Trade Envoys (3)",
                      fix_digest=False)
            self.assertEqual("document_unreadable", self._one(USTR[0], project_root=fx.dir))

    def test_the_counted_class_rules(self):
        # The singular must be the class title's plural less one trailing "s".
        self.assertEqual("singular_is_not_the_class_titles_singular",
                         self._one(USTR[2], mutate_row=lambda r: r.update(singular="Deputy Trade Representative")))
        # The class title must state a count.
        self.assertEqual("printed_title_states_no_count",
                         self._one(USTR[2], mutate_row=lambda r: r.update(printed="Deputy United States Trade Representatives")))
        # The proposed name must begin with the singular, whole.
        self.assertEqual("proposed_name_does_not_begin_with_the_singular",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy U.S. Trade Representative — Asia")))
        # The rename may change only the office half: the qualifier is the node's own.
        self.assertEqual("qualifier_is_not_the_nodes_own",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy United States Trade Representative — Asia & Pacific")))
        self.assertEqual("qualifier_is_not_the_nodes_own",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy United States Trade Representative for Asia")))
        # A counted-class rename needs the section that composes the class.
        self.assertEqual("row_names_no_composing_section",
                         self._one(USTR[2], mutate_row=lambda r: r.pop("composedBy")))

    def test_more_rows_than_the_class_counts_refuses_them_all(self):
        rows = _rows()
        extra = dict(next(r for r in rows if r["id"] == USTR[0]), id="exec-eop-ustr-chief-of-staff",
                     **{"from": "Chief of Staff", "to": "Deputy United States Trade Representative — Staff"})
        rows = rows + [extra]
        tree = _unrenamed_tree(rows[:-1])
        results = _by_id(writer.adjudicate(tree, rows, apply=False))
        for node_id in USTR + ("exec-eop-ustr-chief-of-staff",):
            self.assertEqual("more_rows_than_the_class_counts", results[node_id]["reason"])
        self.assertTrue(results[SEA]["applied"])


class NoPersonTests(unittest.TestCase):
    def test_the_writer_reads_no_persons_name(self):
        source = (PROJECT_ROOT / "scripts" / "rename_posts_to_printed_titles.py").read_text(encoding="utf-8")
        for marker in ("First Name", "Last Name", "NameColumnValue", "plum", "whitehouse"):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
