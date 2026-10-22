"""An explained blank where no held money document prints a figure for a unit.

`docs/DEFINITION_OF_DONE.md` criterion 1 is done when no organisation is left
with only an apportioned estimate: each shows a figure a document states, or
"says in words why none exists" -- an explained blank, which "must name the
documents checked". This module is that state. For every organisation whose
cost is an apportioned share and which carries no sourced figure of another
kind beside it, it checks the unit's name against the unit names printed in
every money document this project holds, and publishes the result as
`costNoDocument`:

- `kind: no_held_document_names_it` -- none of the documents prints a row,
  account, bureau, agency, entity or organisation carrying this unit's name
  (canonical-key equality, the test every matcher here uses). The claim is
  exactly that: not "no published document states this unit's money", which
  nobody could check, but "none of THESE documents does", with each document
  named, dated and counted.
- `kind: named_in_a_held_document_without_a_licensed_figure` -- a held
  document DOES print the name, and no reviewed rule has turned that row into
  a figure for the unit: OMB's database prints an ACCOUNT named "Board of
  Veterans Appeals" under the Department of Veterans Affairs' "Departmental
  Administration" bureau; the Combined Statement prints an account the
  reviewed table does not carry. The block names the document and the printed
  row so the next review has somewhere to start, and the panel says the row is
  not yet this unit's figure.

The documents are the committed fixtures the money modules read, so a name
check here is against the same bytes a figure would come from: the Monthly
Treasury Statement the graph was built from (every Table 5 line), the
Combined Statement chapter in hand (unit totals and account titles), OMB's
Public Budget Database (agency, bureau and account names, both measures),
USAspending's toptier agency list and the committed sub-component lists,
Treasury's Statement of Net Cost (entities), the House's Statement of
Disbursements (organisations, the fiscal-year prefix set aside) and the Report
of the Secretary of the Senate (committee headings). Each is listed on the
block with a version (a record date, a fiscal year, a package name, a digest)
and the number of distinct names checked, and the gate re-derives the whole
check from the same fixtures with its own readers.

It writes no cost field, no figure and no source: a blank explained is still a
blank. Never on a post, a committee or subcommittee (a subcommittee reads
"funded through its committee" on the panel, the owner's decision of
2026-10-07), a Treasury line, a replaced unit, a measured node or a node that
already shows a sourced figure of another kind. The `documents` list is the
same on every node and the viewer copy stores it once (`SHARED_DOCUMENT_BLOCKS`).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"

FIELD = "costNoDocument"
KIND_NONE = "no_held_document_names_it"
KIND_NAMED = "named_in_a_held_document_without_a_licensed_figure"
KINDS = (KIND_NONE, KIND_NAMED)

#: The sourced figures a node may carry beside its estimate (the panel heads
#: the node with one of them). Mirrors report_cost_coverage.SOURCED_FIGURES_BESIDE.
SOURCED_FIGURES_BESIDE = ("usaspendingOutlays", "combinedStatementOutlays", "ombBudget", "auditedNetCost",
                          "committeeDisbursements")
COMMITTEE_TYPE_WORDS = ("committee", "subcommittee", "caucus")
ESTIMATE_STATUSES = ("allocated", "scaled_official")

#: The House statement files an organisation under "FISCAL YEAR 2026 CLERK OF
#: THE HOUSE" or "2026 COMMITTEE ON AGRICULTURE"; the year is the file's, not
#: the unit's name. Mirrors committee_disbursements.HOUSE_ORG.
HOUSE_ORG = re.compile(r"^(?:FISCAL YEAR )?(\d{4}) (.+?)\s*$")

MTS_FIXTURE_PATTERN = "mts_table5_{record_date}.json"
COMBINED_STATEMENT_CHAPTERS = ("c01",)
HOUSE_CSV = FIXTURES / "disbursements" / "house" / "2026q2_sod_summary_grid.csv"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _names(values) -> dict[str, str]:
    """Canonical key -> the first printed form, for every non-empty string."""
    out: dict[str, str] = {}
    for value in values:
        text = str(value or "").strip()
        key = canonical_name_key(text)
        if key and key not in out:
            out[key] = text
    return out


def mts_universe(record_date: str | None) -> dict[str, Any] | None:
    """Every line of the Table 5 statement the graph was built from."""
    if not record_date:
        return None
    path = FIXTURES / MTS_FIXTURE_PATTERN.format(record_date=str(record_date)[:10])
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    return {
        "id": "monthly_treasury_statement",
        "document": "Monthly Treasury Statement, Table 5 (every line, headers included)",
        "version": f"statement of {payload.get('record_date') or record_date}",
        "file": path.name,
        "sha256": _sha256(path),
        "names": _names(r.get("classification_desc") for r in rows if isinstance(r, dict)),
    }


def combined_statement_universe(stem: str) -> dict[str, Any] | None:
    from data_pipeline.verification import combined_statement

    try:
        chapter = combined_statement.load_chapter(stem)
    except Exception:  # noqa: BLE001 -- a chapter not in hand is simply not checked
        return None
    # Account titles and the unit each account is printed under: the set the
    # gate's own chapter reader yields, so the two universes stay equal.
    values: list[str] = []
    for account in chapter.get("accounts") or []:
        if not account.get("figureCells"):
            # An account the chapter prints with no figure prints no figure
            # for anybody; the gate's reader keeps only accounts with cells.
            continue
        values.append(str(account.get("title") or ""))
        values.append(str(account.get("unit") or ""))
    return {
        "id": f"treasury_combined_statement_{stem}",
        "document": "Treasury Combined Statement of Receipts, Outlays, and Balances, "
                    f"chapter {stem} (unit totals and account titles)",
        "version": f"FY{combined_statement.FISCAL_YEAR}" if hasattr(combined_statement, "FISCAL_YEAR") else "FY2025",
        "file": f"{stem}.xlsx",
        "sha256": str(chapter.get("sha256") or ""),
        "names": _names(values),
    }


def omb_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import omb_budget

    try:
        database = omb_budget.load_database()
    except Exception:  # noqa: BLE001
        return None
    values: list[str] = []
    for table in database.get("tables", {}).values():
        if not table:
            continue
        header = table[0]
        columns = [header.index(c) for c in ("Agency Name", "Bureau Name", "Account Name") if c in header]
        for row in table[1:]:
            for index in columns:
                if index < len(row):
                    values.append(str(row[index] or ""))
    return {
        "id": "omb_public_budget_database",
        "document": "OMB Public Budget Database (agency, bureau and account names, budget authority and outlays)",
        "version": f"package {database.get('package')}, last actual year FY{database.get('lastActualYear')}",
        "file": str(Path(str(database.get("url") or "")).name or "BUDGET-DB.zip"),
        "sha256": str(database.get("sha256") or ""),
        "names": _names(values),
    }


def usaspending_universe() -> dict[str, Any] | None:
    toptier = FIXTURES / "usaspending" / "toptier_agencies.json"
    if not toptier.is_file():
        return None
    values: list[str] = []
    payload = json.loads(toptier.read_text(encoding="utf-8"))
    for row in payload.get("results") or []:
        values.append(str(row.get("agency_name") or ""))
        values.append(str(row.get("abbreviation") or ""))
    digests = [_sha256(toptier)]
    files = 1
    for path in sorted((FIXTURES / "usaspending" / "sub_components").glob("*.json")):
        if path.name.endswith(".meta.json"):
            continue
        files += 1
        digests.append(_sha256(path))
        for row in (json.loads(path.read_text(encoding="utf-8")).get("results") or []):
            values.append(str(row.get("name") or ""))
    return {
        "id": "usaspending_agency_lists",
        "document": "USAspending toptier agency list and the committed bureau (sub-component) lists",
        "version": f"{files} files",
        "file": "usaspending/",
        "sha256": hashlib.sha256("\n".join(digests).encode("ascii")).hexdigest(),
        "names": _names(values),
    }


def net_cost_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import net_cost

    try:
        statement = net_cost.load_statement()
    except Exception:  # noqa: BLE001
        return None
    payload = statement.get("payload") if isinstance(statement.get("payload"), dict) else {}
    rows = payload.get("data") or []
    values = [str(r.get("agency_nm") or "") for r in rows if isinstance(r, dict)]
    years = sorted({str(r.get("stmt_fiscal_year") or "") for r in rows if isinstance(r, dict) and r.get("stmt_fiscal_year")})
    return {
        "id": "treasury_statement_of_net_cost",
        "document": "Treasury Statement of Net Cost (reporting entities)",
        "version": f"FY{years[-1]}" if years else "FY2025",
        "file": "statement_net_cost_2025-09-30.json",
        "sha256": str(statement.get("sha256") or ""),
        "names": _names(values),
    }


def house_universe() -> dict[str, Any] | None:
    if not HOUSE_CSV.is_file():
        return None
    values: list[str] = []
    for row in csv.reader(io.StringIO(HOUSE_CSV.read_text(encoding="utf-8-sig"))):
        if not row:
            continue
        label = str(row[0] or "").strip()
        match = HOUSE_ORG.match(label)
        if match:
            values.append(match.group(2))
    return {
        "id": "house_statement_of_disbursements",
        "document": "House Statement of Disbursements, summary (organisations, the fiscal-year prefix set aside)",
        "version": "April 1 - June 30, 2026",
        "file": HOUSE_CSV.name,
        "sha256": _sha256(HOUSE_CSV),
        "names": _names(values),
    }


def senate_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import committee_disbursements

    try:
        report = committee_disbursements.load_senate_report()
    except Exception:  # noqa: BLE001
        return None
    values = [str(s.get("label") or "") for s in report.get("sections") or [] if isinstance(s, dict)]
    pdf = report.get("pdf") if isinstance(report.get("pdf"), dict) else {}
    return {
        "id": "senate_secretary_report",
        "document": "Report of the Secretary of the Senate, Part II (committee headings)",
        "version": str((report.get("period") or {}).get("printed") or "October 1, 2025 - March 31, 2026"),
        "file": str(Path(str(pdf.get("file") or "")).name or "GPO-CDOC-119sdoc6-2.pdf"),
        "sha256": str(pdf.get("sha256") or ""),
        "names": _names(values),
    }


_UNIVERSE_CACHE: dict[str, list[dict[str, Any]]] = {}


def document_universes(record_date: str | None) -> list[dict[str, Any]]:
    """Every held money document, with the unit names it prints. Order is the
    order the block lists them in. Cached per statement date within a process:
    OMB's package alone takes tens of seconds to read, and the fixtures do not
    change under a running build."""
    key = str(record_date or "")[:10]
    if key not in _UNIVERSE_CACHE:
        universes = [mts_universe(record_date)]
        universes.extend(combined_statement_universe(stem) for stem in COMBINED_STATEMENT_CHAPTERS)
        universes.extend([omb_universe(), usaspending_universe(), net_cost_universe(), house_universe(), senate_universe()])
        _UNIVERSE_CACHE[key] = [u for u in universes if u and u.get("names")]
    return _UNIVERSE_CACHE[key]


def documents_listed(universes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The shared `documents` list: what was checked, without the names."""
    return [
        {"id": u["id"], "document": u["document"], "version": u["version"], "file": u["file"],
         "sha256": u["sha256"], "namesChecked": len(u["names"])}
        for u in universes
    ]


def is_treasury_line(node: dict[str, Any]) -> bool:
    return bool(node.get("synthetic")) or "treasury accounting line" in str(node.get("type") or "").casefold()


def takes_block(node: dict[str, Any]) -> bool:
    """An organisation whose cost is an apportioned share and which shows no
    sourced figure of another kind."""
    if is_post_node(node) or is_treasury_line(node):
        return False
    type_text = str(node.get("type") or "").casefold()
    if any(word in type_text for word in COMMITTEE_TYPE_WORDS):
        return False
    if str(node.get("lifecycle") or "") == "superseded":
        return False
    if str(node.get("cost_status") or "") not in ESTIMATE_STATUSES:
        return False
    return not any(isinstance(node.get(field), dict) for field in SOURCED_FIGURES_BESIDE)


def named_in(name: str, universes: list[dict[str, Any]]) -> list[dict[str, str]]:
    key = canonical_name_key(name)
    hits = []
    for universe in universes:
        printed = universe["names"].get(key)
        if printed is not None:
            hits.append({"document": universe["id"], "printed": printed})
    return hits


def build_block(node: dict[str, Any], universes: list[dict[str, Any]], documents: list[dict[str, Any]]) -> dict[str, Any]:
    hits = named_in(str(node.get("name") or ""), universes)
    return {
        "kind": KIND_NAMED if hits else KIND_NONE,
        "name": str(node.get("name") or ""),
        "namedIn": hits,
        "documents": documents,
    }


def apply_cost_no_document(root: dict[str, Any], *, universes: list[dict[str, Any]] | None = None, index_tree=None) -> dict[str, Any]:
    """Stamp `costNoDocument` on every organisation left with only an estimate.
    Runs after the cost cascade and every sourced-figure pass, since it reads
    both; the field is cleared everywhere first so a node that gained a figure
    loses the blank."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    if universes is None:
        summary = root.get("__budgetSummary") if isinstance(root.get("__budgetSummary"), dict) else {}
        universes = document_universes(str(summary.get("record_date") or "") or None)
    documents = documents_listed(universes)
    node_map, _ = index_tree(root)
    stats: dict[str, Any] = {"documents": [d["id"] for d in documents], "stamped": 0, "named": 0, "kinds": {}}
    for node in node_map.values():
        node.pop(FIELD, None)
        if node is root or not takes_block(node):
            continue
        block = build_block(node, universes, documents)
        node[FIELD] = block
        stats["stamped"] += 1
        stats["kinds"][block["kind"]] = stats["kinds"].get(block["kind"], 0) + 1
        if block["namedIn"]:
            stats["named"] += 1
    return stats
