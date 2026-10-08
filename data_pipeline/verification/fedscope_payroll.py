"""What an organisation's civilian staff are paid, from OPM's FedScope table.

The FedScope employment summary that `headcounts.py` reads for a headcount
prints, on the same row, a second figure: `AVGSAL`, which the data
dictionary defines as "The average employee annualized adjusted basic pay."
So a row says how many civilians a sub-agency had in an active pay status at
the snapshot and what they were paid on average, annualized.

OPM prints no total. A unit's payroll here is this repository's arithmetic:
the sum, over the sub-agency rows the headcount record already rests on, of
each row's printed count times its printed average. Each printed average is
a whole dollar, so the sum is exact only to within half a dollar per
employee, and the block says so. The unit's average is that total divided by
the count. Nothing here is a cost: basic pay is not outlays, excludes
benefits, and covers a different population from the Treasury's lines.

The matching is not redone: a block is published only on a node that
`apply_headcount_evidence` has just stamped with an `employeesOfficialSource`
for the same period, so every refusal that module makes (an agency that is
one other unit, an unscoped sub-agency row, a renamed node, a post) binds
here unchanged. Never on a post. Withdrawn every build with the headcount it
depends on (`EVIDENCE_OWNED_FIELDS`).
"""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path
from typing import Any

from data_pipeline.verification.headcounts import (
    DEFAULT_FEDSCOPE_ZIP,
    FEDSCOPE_MEMBER_PREFIX,
    FEDSCOPE_SOURCE,
    load_fedscope_meta,
    period_label,
)

PAYROLL_FIELD = "payrollOfficial"
PAYROLL_SOURCE = "opm_fedscope_employment_avgsal"
# The data dictionary's own definition of the column (the March 2025
# dictionary, every table's AVGSAL row). Pinned against the PDF by a test.
AVGSAL_DEFINITION = "The average employee annualized adjusted basic pay."
DEFINITION_SOURCE = "OPM, (Preliminary) March 2025 Employment Dataset data dictionary, column AVGSAL (Average Employee Salary)"
ARITHMETIC_NOTE = (
    "OPM prints no total: the figure is the sum over the listed sub-agency rows of each row's printed "
    "count times its printed average, which OPM rounds to the dollar, so it is exact only to within half "
    "a dollar per employee. Basic pay excludes benefits and is not the unit's cost."
)


def load_avgsal_rows(zip_path: str | Path = DEFAULT_FEDSCOPE_ZIP) -> dict[tuple[str, str], tuple[int, int]]:
    """(period, sub-agency code) -> (EMPCOUNT, AVGSAL), as printed."""
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if Path(n).name.startswith(FEDSCOPE_MEMBER_PREFIX)]
        if len(names) != 1:
            raise ValueError(f"expected one '{FEDSCOPE_MEMBER_PREFIX}*' member in {zip_path}")
        text = archive.read(names[0]).decode("utf-8-sig")
    rows: dict[tuple[str, str], tuple[int, int]] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        key = (period_label(row.get("DATECODE")), str(row.get("AGYSUB") or "").strip())
        if key in rows:
            raise ValueError(f"duplicate sub-agency row {key}")
        rows[key] = (int(str(row["EMPCOUNT"]).strip()), int(str(row["AVGSAL"]).strip()))
    return rows


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def payroll_block(source: dict[str, Any], employees: int, rows, *, sha256: str) -> dict[str, Any] | None:
    """The block for one stamped headcount, or None when a row is missing."""
    period = str(source.get("period") or "")
    if source.get("level") == "agency":
        codes = [c.get("subagencyCode") for c in source.get("components") or []]
    else:
        codes = [source.get("subagencyCode")]
    if not codes or not period:
        return None
    components = []
    for code in codes:
        printed = rows.get((period, str(code or "")))
        if printed is None or printed[0] <= 0:
            return None
        components.append([code, printed[0], printed[1]])
    count = sum(c[1] for c in components)
    if count != employees:
        return None  # the headcount and the rows it rests on must be the same rows
    total = sum(c[1] * c[2] for c in components)
    if total <= 0:
        return None
    block: dict[str, Any] = {
        "source": PAYROLL_SOURCE,
        "period": period,
        "totalAnnualPay": total,
        "employees": count,
        "average": round(total / count),
        "rows": components,  # [sub-agency code, printed count, printed average]
        "definition": AVGSAL_DEFINITION,
        "definitionSource": DEFINITION_SOURCE,
        "coverage": source.get("coverage"),
        "note": ARITHMETIC_NOTE,
        "url": source.get("url"),
        "sha256": sha256,
    }
    if len(components) > 1:
        averages = [c[2] for c in components]
        block["rowAverageRange"] = [min(averages), max(averages)]
    return block


def apply_payroll_evidence(root: dict[str, Any], *, zip_path: str | Path = DEFAULT_FEDSCOPE_ZIP, index_tree=None) -> dict[str, Any]:
    """Stamp `payrollOfficial` beside every headcount stamped this build."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"published": 0, "no_matching_rows": 0, "post_refused": 0, "measured_equal_refused": 0, "total_annual_pay": 0}
    for node in node_map.values():
        node.pop(PAYROLL_FIELD, None)
    rows = load_avgsal_rows(zip_path)
    meta = load_fedscope_meta(zip_path)
    sha = file_sha256(zip_path)
    if meta.get("sha256") and meta["sha256"] != sha:
        raise ValueError(f"{zip_path}: digest {sha} is not the fetch record's {meta['sha256']}")
    for node in node_map.values():
        source = node.get("employeesOfficialSource")
        employees = node.get("employeesOfficial")
        if not isinstance(source, dict) or source.get("source") != FEDSCOPE_SOURCE or not isinstance(employees, int):
            continue
        if "position" in str(node.get("type") or "").casefold():
            stats["post_refused"] += 1
            continue
        if source.get("outsideStatedCoverage"):
            continue
        block = payroll_block(source, employees, rows, sha256=sha)
        if block is None:
            stats["no_matching_rows"] += 1
            continue
        if node.get("cost_status") in ("official", "root_total") and node.get("resolved_total_amount") == block["totalAnnualPay"]:
            stats["measured_equal_refused"] += 1
            continue
        node[PAYROLL_FIELD] = block
        stats["published"] += 1
        stats["total_annual_pay"] += block["totalAnnualPay"]
    return stats
