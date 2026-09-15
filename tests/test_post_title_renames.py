"""Renaming a templated cabinet title to the one an official document gives.

The curated file is never hand-edited, so this rename is a script, and the
script renames nothing it cannot cite. What it must get right is narrow and
each part of it broke, or nearly broke, in development:

  - it must recognise the template by the PARENT's name, not by a guess;
  - it must never produce the replacement by string surgery. Dropping
    "Department of" is right thirteen times and wrong once, and the once is
    the Department of Justice, whose head is the Attorney General and not a
    "Secretary of Justice" at all;
  - it must refuse a title that names only the role. The first dry run would
    have renamed three deputies to a bare "Deputy Secretary", dropping the
    one word that says which department and manufacturing exactly the
    generic title the verifier's post floor exists to refuse;
  - it must be idempotent, and must leave alone every node it cannot cite.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from scripts import rename_templated_post_titles as rename

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
BASE = {
    "id": "the-constitution-of-the-united-states",
    "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            # The archive names this one's head an Attorney General.
            {"id": "exec-dept-doj", "name": "Department of Justice (DOJ)", "type": "Cabinet Department", "children": [
                {"id": "doj-sec", "name": "Secretary of Department of Justice (DOJ)", "type": "Position", "children": []},
                {"id": "doj-dep", "name": "Deputy Secretary of Department of Justice (DOJ)", "type": "Position", "children": []},
            ]},
            # The archive qualifies both, and the deputy has a specialised variant.
            {"id": "exec-dept-state", "name": "Department of State", "type": "Cabinet Department", "children": [
                {"id": "state-sec", "name": "Secretary of Department of State", "type": "Position", "children": []},
                {"id": "state-dep", "name": "Deputy Secretary of Department of State", "type": "Position", "children": []},
            ]},
            # The archive files this one's deputy as a bare "DEPUTY SECRETARY".
            {"id": "exec-dept-doc", "name": "Department of Commerce", "type": "Cabinet Department", "children": [
                {"id": "doc-dep", "name": "Deputy Secretary of Department of Commerce", "type": "Position", "children": []},
            ]},
            # Not templated: already correct, and must not be touched.
            {"id": "exec-dept-defense", "name": "Department of Defense", "type": "Cabinet Department", "children": [
                {"id": "dod-sec", "name": "Secretary of Defense", "type": "Position", "children": []},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
    ],
}
ARCHIVE_ROWS = [
    {"AgencyName": "DEPARTMENT OF JUSTICE", "PositionTitle": "ATTORNEY GENERAL"},
    {"AgencyName": "DEPARTMENT OF JUSTICE", "PositionTitle": "DEPUTY ATTORNEY GENERAL"},
    # The same department also files clerical "SECRETARY" rows; a bare role
    # word must never win, or DOJ's head would be renamed "Secretary".
    {"AgencyName": "DEPARTMENT OF JUSTICE", "PositionTitle": "SECRETARY"},
    {"AgencyName": "DEPARTMENT OF STATE", "PositionTitle": "SECRETARY OF STATE"},
    {"AgencyName": "DEPARTMENT OF STATE", "PositionTitle": "DEPUTY SECRETARY OF STATE"},
    {"AgencyName": "DEPARTMENT OF STATE", "PositionTitle": "DEPUTY SECRETARY OF STATE FOR MANAGEMENT AND RESOURCES"},
    {"AgencyName": "DEPARTMENT OF COMMERCE", "PositionTitle": "DEPUTY SECRETARY"},
    {"AgencyName": "DEPARTMENT OF DEFENSE", "PositionTitle": "SECRETARY OF DEFENSE"},
]


class QualifiedTitleTests(unittest.TestCase):
    def test_a_role_word_alone_never_qualifies(self) -> None:
        for title in ("Secretary", "SECRETARY", "Deputy Secretary", "DEPUTY SECRETARY"):
            with self.subTest(title=title):
                self.assertFalse(rename.qualified(title))

    def test_a_title_qualifies_by_naming_a_department_or_by_being_an_office(self) -> None:
        for title in (
            "SECRETARY OF STATE", "Secretary of the Treasury", "Deputy Secretary of Energy",
            "SECRETARY OF THE DEPARTMENT OF HOMELAND SECURITY",
        ):
            with self.subTest(title=title):
                self.assertTrue(rename.qualified(title))
        # Named offices need no department after them, and this is the whole
        # reason the replacement is never made by string surgery.
        for title in ("ATTORNEY GENERAL", "Deputy Attorney General"):
            with self.subTest(title=title):
                self.assertTrue(rename.qualified(title))


class TemplateAndChoiceTests(unittest.TestCase):
    def test_the_template_is_recognised_by_the_parent_s_own_name(self) -> None:
        self.assertEqual(rename.role_of("Secretary of Department of Energy (DOE)", "Department of Energy (DOE)"), "head")
        self.assertEqual(rename.role_of("Deputy Secretary of Department of State", "Department of State"), "deputy")
        # The abbreviation and the ampersand are canonicalised away on both sides.
        self.assertEqual(
            rename.role_of("Secretary of Department of Health and Human Services", "Department of Health & Human Services (HHS)"),
            "head")
        # Not the template: a correct title, and a post of another kind.
        self.assertIsNone(rename.role_of("Secretary of Defense", "Department of Defense"))
        self.assertIsNone(rename.role_of("Inspector General", "Department of Defense"))

    def test_the_general_title_wins_only_when_the_others_refine_it(self) -> None:
        chosen, why = rename.pick(["DEPUTY SECRETARY OF STATE", "DEPUTY SECRETARY OF STATE FOR MANAGEMENT AND RESOURCES"])
        self.assertEqual((chosen, why), ("DEPUTY SECRETARY OF STATE", "ok"))
        # Two titles neither of which contains the other: nothing is chosen.
        chosen, why = rename.pick(["SECRETARY OF ENERGY", "ADMINISTRATOR OF ENERGY"])
        self.assertIsNone(chosen)
        self.assertTrue(why.startswith("ambiguous"), why)
        self.assertIsNone(rename.pick([])[0])

    def test_the_archive_is_read_per_department_and_kind(self) -> None:
        found = rename.archive_titles(ARCHIVE_ROWS, "Department of Justice (DOJ)")
        self.assertEqual(found["head"], ["ATTORNEY GENERAL"])
        self.assertEqual(found["deputy"], ["DEPUTY ATTORNEY GENERAL"])
        # The bare "SECRETARY" row under the same department is dropped.
        self.assertNotIn("SECRETARY", found["head"])
        self.assertEqual(rename.archive_titles(ARCHIVE_ROWS, "Department of Commerce")["deputy"], [])

    def test_the_archive_s_shouting_becomes_a_name(self) -> None:
        self.assertEqual(rename.title_case("SECRETARY OF THE TREASURY"), "Secretary of the Treasury")
        self.assertEqual(rename.title_case("ATTORNEY GENERAL"), "Attorney General")
        self.assertEqual(rename.title_case("DEPUTY SECRETARY OF VETERANS AFFAIRS"), "Deputy Secretary of Veterans Affairs")


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"rename-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(BASE), encoding="utf-8")
        self.archive = self.tmp / "archive.csv"
        with self.archive.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["AgencyName", "PositionTitle"])
            writer.writeheader()
            writer.writerows(ARCHIVE_ROWS)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = rename.main([
                "rename", "--base-graph", str(self.base), "--archive", str(self.archive), "--no-pages", *extra,
            ])
        return code, out.getvalue()

    def _names(self):
        return {k: v["name"] for k, v in index_tree(json.loads(self.base.read_text(encoding="utf-8")))[0].items()}

    def test_a_dry_run_changes_nothing_on_disk(self) -> None:
        before = self.base.read_bytes()
        code, text = self._run("--dry-run")
        self.assertEqual(code, 0, text)
        self.assertIn("Attorney General", text)
        self.assertEqual(self.base.read_bytes(), before)

    def test_it_renames_only_what_the_archive_names_and_cites_each_one(self) -> None:
        code, text = self._run()
        self.assertEqual(code, 0, text)
        names = self._names()
        # The case string surgery gets wrong: a different office entirely.
        self.assertEqual(names["doj-sec"], "Attorney General")
        self.assertEqual(names["doj-dep"], "Deputy Attorney General")
        self.assertEqual(names["state-sec"], "Secretary of State")
        # The specialised variant never displaces the principal deputy.
        self.assertEqual(names["state-dep"], "Deputy Secretary of State")
        # No qualified title: left exactly as it was, and reported.
        self.assertEqual(names["doc-dep"], "Deputy Secretary of Department of Commerce")
        self.assertIn("left alone", text)
        # A correct title is not template-shaped and is never touched.
        self.assertEqual(names["dod-sec"], "Secretary of Defense")
        # Every rename says where the name came from.
        nodes = index_tree(json.loads(self.base.read_text(encoding="utf-8")))[0]
        for node_id in ("doj-sec", "doj-dep", "state-sec", "state-dep"):
            with self.subTest(node=node_id):
                self.assertEqual(nodes[node_id]["nameSource"], "listed_in_opm_plum_archive")
                self.assertTrue(nodes[node_id]["nameSourceDetail"].startswith("https://"))
        for node_id in ("doc-dep", "dod-sec"):
            with self.subTest(node=node_id):
                self.assertNotIn("nameSource", nodes[node_id])

    def test_it_is_idempotent_and_creates_or_removes_nothing(self) -> None:
        before_ids = set(index_tree(json.loads(self.base.read_text(encoding="utf-8")))[0])
        self._run()
        first = self.base.read_bytes()
        _, text = self._run()
        self.assertIn("renamed 0", text)
        self.assertEqual(self.base.read_bytes(), first)
        self.assertEqual(set(index_tree(json.loads(first.decode("utf-8")))[0]), before_ids)

    def test_the_published_curated_file_carries_no_templated_cabinet_title_the_archive_names(self) -> None:
        """Against the real curated file, so the committed state cannot drift
        back: whatever remains templated must be something no source names."""
        out = io.StringIO()
        with redirect_stdout(out):
            status = rename.main(["rename", "--no-pages", "--dry-run"])
        self.assertEqual(status, 0)
        self.assertIn("renamed 0", out.getvalue())


if __name__ == "__main__":
    unittest.main()
