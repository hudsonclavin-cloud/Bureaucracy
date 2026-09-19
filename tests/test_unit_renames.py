"""The organisation rename table, and the checks that stand between it and the
curated file.

`scripts/rename_units_to_official_wording.py` is the only writer of the
organisation renames CURATION.md §9 records, and the curated file is never
hand-edited. What makes the table something other than a hand-edit wearing a
script's clothes is that **the table proposes and the page decides**: every row
is re-fetched and re-tested with the verifier's own label test on every run.
That part needs the network, so it is not tested here. Everything decidable
without a fetch is, in both directions -- a good row passes each check and a
corrupted one is refused by name.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from rename_units_to_official_wording import (  # noqa: E402
    DEFAULT_TABLE,
    GENERIC_NAMES,
    MIN_NAME_TOKENS,
    check_static,
    load_table,
)


class TableShapeTests(unittest.TestCase):
    """The committed table says what it must, about nodes that exist."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_table(DEFAULT_TABLE)
        cls.node_map, _ = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))

    def test_the_table_is_not_empty(self) -> None:
        self.assertGreaterEqual(len(self.rows), 60, "CURATION.md §9 records 69 renames")

    def test_every_row_names_a_real_node_and_states_a_basis(self) -> None:
        for row in self.rows:
            with self.subTest(node=row.get("id")):
                node = self.node_map.get(str(row.get("id")))
                self.assertIsNotNone(node, f"{row.get('id')} is not in the curated file")
                self.assertTrue(str(row.get("basis") or "").strip(),
                                "a row with no basis is an assertion, not an identification")
                self.assertTrue(str(row.get("url") or "").startswith("https://"),
                                "a row must cite the page that decides it")

    def test_every_row_has_been_applied_so_the_node_carries_the_proposed_name(self) -> None:
        """The table and the curated file agree, which is what makes the script
        idempotent: a second run finds every row already applied."""
        for row in self.rows:
            with self.subTest(node=row.get("id")):
                node = self.node_map[str(row["id"])]
                self.assertEqual(node.get("name"), row["to"])
                self.assertEqual(node.get("nameSourceDetail"), row["url"],
                                 "the node should cite the page its name came from")

    def test_no_applied_rename_is_a_no_op(self) -> None:
        """A proposed name reducing to the curated one changes no verifier
        outcome. The one allowed exception is a curated name the verifier
        refuses before any fetch -- "National Laboratories (17)" is a count
        label, so dropping the count changes the outcome with the key equal."""
        from data_pipeline.verification.evidence import uncheckable_reason
        for row in self.rows:
            if canonical_name_key(row["to"]) != canonical_name_key(row["from"]):
                continue
            with self.subTest(node=row["id"]):
                self.assertIsNotNone(
                    uncheckable_reason(row["from"]),
                    f"{row['id']}: the keys are equal and the old name was checkable, so the rename buys nothing")

    #: The one sibling collision in the curated file, and it predates this work
    #: by every commit: the Council of Economic Advisers carries two nodes both
    #: named "Member, CEA". It is curation (the council has three members and
    #: the graph names two of them identically), recorded here so this test can
    #: assert the invariant the rename script actually guarantees without
    #: asserting a clean file it has never been.
    KNOWN_SIBLING_COLLISIONS = {("exec-eop-cea", "member cea")}

    def test_no_rename_collides_with_a_sibling(self) -> None:
        """Two entries of one listing must stay tellable apart. Across parents a
        duplicate is allowed on purpose -- see the module docstring."""
        renamed = {str(row["id"]) for row in self.rows}
        for parent in self.node_map.values():
            keys: dict[str, str] = {}
            for child in parent.get("children") or []:
                key = canonical_name_key(child.get("name"))
                other = keys.get(key)
                if other is not None and (str(parent.get("id")), key) not in self.KNOWN_SIBLING_COLLISIONS:
                    self.assertFalse(
                        {other, str(child.get("id"))} & renamed,
                        f"a rename made {child.get('id')} and {other} siblings reducing to {key!r}")
                keys.setdefault(key, str(child.get("id")))

    def test_the_only_known_sibling_collision_is_still_the_only_one(self) -> None:
        """If a second appears, the line above stops being a note and starts
        being a hole, so it is pinned rather than merely commented."""
        found = set()
        for parent in self.node_map.values():
            keys: dict[str, str] = {}
            for child in parent.get("children") or []:
                key = canonical_name_key(child.get("name"))
                if key in keys:
                    found.add((str(parent.get("id")), key))
                keys.setdefault(key, str(child.get("id")))
        self.assertEqual(found, self.KNOWN_SIBLING_COLLISIONS)


class StaticCheckTests(unittest.TestCase):
    """Each refusal, tripped on purpose. A gate only tested with good input is
    not known to refuse anything."""

    def setUp(self) -> None:
        self.node = {"id": "n1", "name": "Old Name of the Agency", "type": "Agency"}
        self.row = {"id": "n1", "from": "Old Name of the Agency", "to": "New Name of the Agency",
                    "url": "https://example.gov/", "basis": "same unit"}
        self.siblings: dict[str, str] = {}

    def verdict(self):
        return check_static(self.row, self.node, self.siblings)

    def test_a_good_row_passes_every_static_check(self) -> None:
        self.assertIsNone(self.verdict())

    def test_a_missing_node_is_refused(self) -> None:
        self.assertEqual(check_static(self.row, None, self.siblings)[0], "no_such_node")

    def test_a_node_already_carrying_the_proposed_name_is_a_no_op(self) -> None:
        self.node["name"] = self.row["to"]
        self.assertEqual(self.verdict()[0], "already_applied")

    def test_a_node_renamed_since_the_row_was_written_is_never_overwritten(self) -> None:
        """The check that stops a stale reading undoing a later, better name."""
        self.node["name"] = "Something Else Entirely"
        self.assertEqual(self.verdict()[0], "curated_name_has_changed")

    def test_a_post_is_refused(self) -> None:
        self.node["type"] = "Position"
        self.assertEqual(self.verdict()[0], "node_is_a_post")

    def test_a_rename_that_changes_no_key_is_refused(self) -> None:
        self.row["to"] = "Old Name of the Agency"          # differs only by case below
        self.row["to"] = "old name of THE agency"
        self.assertEqual(self.verdict()[0], "rename_is_a_no_op")

    def test_an_ampersand_spelling_is_a_no_op_because_the_key_folds_it(self) -> None:
        self.node["name"] = "Health & Human Services Board"
        self.row["from"] = "Health & Human Services Board"
        self.row["to"] = "Health and Human Services Board"
        self.assertEqual(self.verdict()[0], "rename_is_a_no_op")

    def test_a_one_token_name_is_refused(self) -> None:
        self.row["to"] = "Energy"
        reason, detail = self.verdict()
        self.assertEqual(reason, "proposed_name_too_short")
        self.assertIn(str(MIN_NAME_TOKENS), detail)

    def test_a_generic_name_is_refused(self) -> None:
        """`Inspector General` names 72 nodes here and sits in every .gov
        footer, which is the furniture match the navigation rule exists for."""
        self.row["to"] = "Office of the Inspector General"
        self.assertIn("Office of the Inspector General".casefold(), GENERIC_NAMES)
        self.assertEqual(self.verdict()[0], "proposed_name_is_generic")

    def test_a_sibling_collision_is_refused(self) -> None:
        self.siblings[canonical_name_key("New Name of the Agency")] = "n2"
        reason, detail = self.verdict()
        self.assertEqual(reason, "proposed_name_collides_with_a_sibling")
        self.assertIn("n2", detail)

    def test_a_collision_with_the_node_itself_is_not_a_collision(self) -> None:
        self.siblings[canonical_name_key("New Name of the Agency")] = "n1"
        self.assertIsNone(self.verdict())

    def test_an_incomplete_row_is_refused(self) -> None:
        self.row["to"] = ""
        self.assertEqual(self.verdict()[0], "row_is_incomplete")


class ParentheticalAcronymTests(unittest.TestCase):
    """Why the renames keep the acronym the agents proposed dropping.

    `canonical_name_key` drops parentheticals, so `... (NIST)` matches a page
    labelling the name alone -- the node keeps information the bare form would
    lose, at no cost to whether it confirms. The same fact is why a bracketed
    qualifier is never evidence of anything, which is why EPA's own qualifier
    is used rather than the graph's.
    """

    def test_an_acronym_in_brackets_does_not_change_the_key(self) -> None:
        for full, bracketed in (
            ("National Institute of Standards and Technology",
             "National Institute of Standards and Technology (NIST)"),
            ("Southern District of New York", "Southern District of New York (S.D.N.Y.)"),
        ):
            with self.subTest(name=full):
                self.assertEqual(canonical_name_key(full), canonical_name_key(bracketed))

    def test_a_bracketed_qualifier_is_not_checked_at_all(self) -> None:
        """So it must be the page's word, not the graph's: these two differ in
        the bracket and are the same key, which is exactly why EPA Region 7's
        curated "Plains" could have ridden along unverified beside EPA's own
        "Midwest"."""
        self.assertEqual(canonical_name_key("EPA Region 7 (Midwest)"),
                         canonical_name_key("EPA Region 7 (Plains)"))


if __name__ == "__main__":
    unittest.main()
