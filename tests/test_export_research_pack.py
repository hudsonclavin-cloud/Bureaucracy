"""The research pack is a faithful view of the published graph.

`scripts/export_research_pack.py` writes the node lists a deep-research run
is given. These tests hold its two largest lists to the project's own
counts, so an attached file cannot quietly disagree with the site.
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_research_pack  # noqa: E402
from report_unpriced_positions import collect  # noqa: E402


class ResearchPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.counts = export_research_pack.build(cls.out)
        cls.graph = json.loads(export_research_pack.GRAPH.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def rows(self, name):
        with (self.out / name).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_unpriced_posts_match_the_unpriced_inventory(self):
        groups, _, _, _ = collect(self.graph)
        expected = {row["id"] for rows in groups.values() for row in rows}
        got = [row["id"] for row in self.rows("unpriced_posts.csv")]
        self.assertEqual(len(got), len(set(got)))
        self.assertEqual(set(got), expected)

    def test_estimated_units_are_exactly_the_live_allocated_organisations(self):
        got = {row["id"] for row in self.rows("estimated_units.csv")}
        expected = set()
        for node, ancestors, replaced in export_research_pack.walk(self.graph):
            if (ancestors and not replaced and node.get("cost_status") == "allocated"
                    and not export_research_pack.is_post(node)
                    and not export_research_pack.is_line(node)):
                expected.add(node["id"])
        self.assertEqual(got, expected)

    def test_no_post_is_listed_as_an_organisation(self):
        for row in self.rows("organisations.csv"):
            self.assertNotIn("position", row["type"].casefold(), row["id"])

    def test_every_file_the_readme_names_was_written(self):
        readme = (self.out / "README.md").read_text(encoding="utf-8")
        for name in self.counts:
            self.assertIn(name, readme)
            self.assertTrue((self.out / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
