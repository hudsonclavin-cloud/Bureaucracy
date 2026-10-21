"""The Combined Statement probe reconciles against the chapter's own totals.

Pinned in both directions: the committed Legislative Branch chapter parses so
that every printed unit total equals its accounts' sum to the cent, and a
doctored figure makes the probe refuse rather than report.
"""

from __future__ import annotations

import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from data_pipeline.verification.congress import read_xlsx_rows  # noqa: E402
from probe_combined_statement import (  # noqa: E402
    FIXTURE_DIR,
    OUTLAYS_COLUMN,
    ReconciliationError,
    parse_chapter,
    strip_candidates,
)

ROWS = read_xlsx_rows(FIXTURE_DIR / "c01.xlsx")


class ReconciliationTests(unittest.TestCase):
    def test_committed_chapter_reconciles_to_the_cent(self):
        accounts, totals = parse_chapter(ROWS)
        self.assertEqual(len(accounts), 115)
        chapter = totals[-1]
        self.assertTrue(chapter.get("isChapterTotal"))
        self.assertEqual(chapter["netOutlays"], Decimal("7232968757.51"))
        senate = next(t for t in totals if t["unit"] == "Senate")
        self.assertEqual(senate["netOutlays"], Decimal("1308849893.25"))
        self.assertEqual(senate["accountCount"], 27)

    def test_single_year_accounts_without_a_subtotal_are_counted(self):
        accounts, _ = parse_chapter(ROWS)
        by_title = {a["title"]: a for a in accounts}
        foreign = by_title["Congressional Use of Foreign Currency, Senate"]
        self.assertEqual(foreign["subtotalRows"], 0)
        self.assertEqual(foreign["netOutlays"], Decimal("10047127.59"))

    def test_funds_held_outside_the_treasury_are_not_counted_twice(self):
        accounts, _ = parse_chapter(ROWS)
        loc = next(a for a in accounts if a["title"] == "Salaries and Expenses, Library of Congress")
        self.assertEqual(loc["netOutlays"], Decimal("602515340.44"))

    def test_a_doctored_account_figure_is_refused(self):
        doctored = copy.deepcopy(ROWS)
        for row in doctored:
            if len(row) > OUTLAYS_COLUMN and row[1] == "Subtotal" and row[OUTLAYS_COLUMN] == "24,381,415.96":
                row[OUTLAYS_COLUMN] = "24,381,416.96"
                break
        else:
            self.fail("fixture row not found")
        with self.assertRaises(ReconciliationError):
            parse_chapter(doctored)

    def test_a_dropped_account_is_refused(self):
        doctored = [row for row in copy.deepcopy(ROWS) if not (row and row[0] == "Senate Hair Care Revolving Fund, Senate")]
        # The title row gone, its data row now sits under the previous account,
        # so the totals still reconcile; dropping the data row must not.
        doctored = [row for row in doctored if not (len(row) > 4 and row[4] == "4326")]
        with self.assertRaises(ReconciliationError):
            parse_chapter(doctored)


class StripTests(unittest.TestCase):
    def test_candidates_never_include_a_name_the_title_does_not_contain(self):
        title = "Salaries and Expenses, Congressional Research Service, Library of Congress"
        for candidate in strip_candidates(title):
            self.assertIn(candidate, title)


if __name__ == "__main__":
    unittest.main()
