"""The Combined Statement's scale, reconciled against the committed fixtures.

Pinned in both directions: the Legislative Branch chapter's total equals the
September 2025 Monthly Treasury Statement's line to the cent and a record built
from the real fixtures files under the granted rule; a doctored statement, a
statement whose bytes no longer match their fetch record, and a statement of
the wrong date are each refused.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.combined_statement import (
    CHAPTER_DIR,
    FIXTURE_ROOT,
    ReconciliationError,
    load_chapter,
    reconcile_chapter_scale,
    statement_fixture,
)


def _copy_statement(fiscal_year: int, into: Path) -> Path:
    source = statement_fixture(fiscal_year)
    target = into / source.name
    shutil.copy(source, target)
    shutil.copy(source.with_name(source.name + ".meta.json"), target.with_name(target.name + ".meta.json"))
    return target


def _rewrite(path: Path, transform, *, keep_digest: bool = False) -> None:
    import hashlib
    payload = json.loads(path.read_text(encoding="utf-8"))
    transform(payload)
    data = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
    path.write_bytes(data)
    if not keep_digest:
        meta_path = path.with_name(path.name + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(data).hexdigest()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")


class CommittedFixturesReconcileTests(unittest.TestCase):
    def test_the_legislative_branch_total_equals_the_september_statement_to_the_cent(self):
        block = reconcile_chapter_scale("c01", 2025)
        self.assertEqual(block["chapterTotal"]["label"], "Total, Legislative Branch")
        self.assertEqual(block["chapterTotal"]["amountRaw"], "7,232,968,757.51")
        self.assertEqual(block["statementLine"]["label"], "Total--Legislative Branch")
        self.assertEqual(block["statementLine"]["amountRaw"], "7232968757.51")
        self.assertEqual(block["statementLine"]["recordDate"], "2025-09-30")
        self.assertEqual(block["statementLine"]["field"], "current_fytd_net_outly_amt")

    def test_a_record_from_the_real_fixtures_files_under_the_granted_rule(self):
        chapter = load_chapter("c01")
        account = next(a for a in chapter["accounts"] if a["title"] == "Capitol Grounds, Architect of the Capitol")
        self.assertEqual(account["netOutlays"], Decimal("17858652.41"))
        block = reconcile_chapter_scale("c01", 2025)
        node_map, _ = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
        node = node_map["leg-support-aoc-capitol-grounds"]
        raw = f"{account['netOutlays']:,.2f}"
        evidence = (
            f"{block['chapterTotal']['label']} {block['chapterTotal']['amountRaw']} = "
            f"{block['statementLine']['label']} {block['statementLine']['amountRaw']}; "
            f"{account['title']} {raw}"
        )
        record = {
            "nodeId": node["id"], "amount": float(account["netOutlays"]), "amountRaw": raw,
            "units": "usd", "normalizedMultiplier": 1, "unitsEvidence": evidence,
            "scaleReconciliation": block, "costBasis": "net_outlays", "fiscalYear": 2025,
            "periodCoverage": "full_fiscal_year", "amountScope": account["title"], "scopeMatch": "proxy",
            "rollupRole": "line", "sourceType": "treasury_combined_statement",
            "sourceUrl": chapter["url"], "documentSha256": chapter["sha256"],
            "retrievedAt": "2026-10-21T16:30:58Z",
            "locator": {"chapter": "c01", "account": account["title"], "column": "Outlays (Net)"},
            "quote": f"{account['title']} ... Subtotal ... {raw}",
            "financialEvidenceStatus": "partial",
        }
        out = fe.validate_record(record, node)
        self.assertEqual(out["unitsEvidenceKind"], "chapter_total_equals_the_monthly_treasury_statements_line_to_the_cent")


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.statement = _copy_statement(2025, self.tmp)

    def test_a_statement_a_cent_off_is_refused(self):
        def nudge(payload):
            for row in payload["rows"]:
                if row["classification_desc"] == "Total--Legislative Branch":
                    row["current_fytd_net_outly_amt"] = "7232968757.52"
        _rewrite(self.statement, nudge)
        with self.assertRaises(ReconciliationError):
            reconcile_chapter_scale("c01", 2025, statement_root=self.tmp)

    def test_a_statement_whose_bytes_are_not_its_fetch_record_is_refused(self):
        _rewrite(self.statement, lambda payload: None, keep_digest=True)
        meta_path = self.statement.with_name(self.statement.name + ".meta.json")
        meta = json.loads(meta_path.read_text())
        meta["sha256"] = "0" * 64
        meta_path.write_text(json.dumps(meta))
        with self.assertRaises(ReconciliationError):
            reconcile_chapter_scale("c01", 2025, statement_root=self.tmp)

    def test_a_statement_not_dated_the_last_day_of_the_year_is_refused(self):
        _rewrite(self.statement, lambda payload: payload.update(record_date="2025-08-31"))
        with self.assertRaises(ReconciliationError):
            reconcile_chapter_scale("c01", 2025, statement_root=self.tmp)

    def test_a_year_with_no_committed_statement_is_refused(self):
        with self.assertRaises(ReconciliationError):
            reconcile_chapter_scale("c01", 2024)

    def test_a_chapter_whose_bytes_are_not_its_fetch_record_is_refused(self):
        chapters = self.tmp / "cs"
        chapters.mkdir()
        for name in ("c01.xlsx", "c01.xlsx.meta.json"):
            shutil.copy(CHAPTER_DIR / name, chapters / name)
        meta = json.loads((chapters / "c01.xlsx.meta.json").read_text())
        meta["sha256"] = "0" * 64
        (chapters / "c01.xlsx.meta.json").write_text(json.dumps(meta))
        with self.assertRaises(ReconciliationError):
            reconcile_chapter_scale("c01", 2025, chapter_dir=chapters, statement_root=FIXTURE_ROOT)


if __name__ == "__main__":
    unittest.main()
