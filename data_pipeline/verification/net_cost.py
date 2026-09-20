"""Audited net cost, from the government's own audited financial statements.

`docs/EXACT_NODE_COSTS.md` names three steps on the route to more exact-node
costs: a reviewed identifier crosswalk, then USAspending File A/B, then "agency
AFR Statements of Net Cost". The third is the strongest of them, because an
audited figure is the only cost in this project that somebody outside the
government has checked — and it turned out not to need a single agency PDF.
Treasury publishes the consolidated Statement of Net Cost as structured JSON on
`api.fiscaldata.treasury.gov`, the same service this pipeline already crawls for
the Monthly Treasury Statement, whose `robots.txt` answers 404: nothing was
published to obey.

**It is not this graph's cost, and nothing here writes a cost field.** Three
differences, all of which ride on every record:

  - **Basis.** Net cost is accrual accounting — what a unit's programmes cost
    to run, gross cost less earned revenue. The graph's measured figure is the
    Monthly Treasury Statement's *net outlays*, which is cash out of the door.
    A department can show a large net cost in a year it disbursed less.
  - **Period.** The statement covers a fiscal year that has ENDED (FY2025,
    to 2025-09-30). The graph's anchor is the current year to date. They are
    not comparable and the panel prints both dates rather than one.
  - **Scope.** 40 reporting entities, of which 7 name no unit of government at
    all — "Total", "All other entities", "Security Assistance Accounts",
    "Interest on Treasury Securities held by the public". Those are refused
    rather than matched to the nearest thing, for the reason
    `headcounts.py` refuses an agency whose whole entry is one other unit.

Matching is canonical-key **equality** against an organisation's name, the same
test `usaspending.py` uses for a File A key and `evidence.py` uses for a page
label. 33 of the 40 rows reach exactly one node and none reaches two. There is
no alias table here and there should not be one until a name genuinely needs it:
every match is a department or major agency whose name the Treasury spells the
way the graph does.

**The scale is stated by the publisher, in the field name.** Treasury names the
columns `gross_cost_bil_amt`, `earned_revenue_bil_amt` and `net_cost_bil_amt` --
billions, said in the data rather than in prose a reader has to find. That is a
third way a publisher can state a unit, beside `financial_evidence`'s existing
"prints a currency mark" and "says so in its data dictionary", and it is
recorded on every record as `unitsEvidenceKind` so a reviewer can see which one
a figure rests on.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "treasury" / "net_cost" / "statement_net_cost_2025-09-30.json"

SOURCE = "treasury_statement_of_net_cost"
SOURCE_TYPE = "audited_financial_statement"
METRIC = "audited_net_cost"
#: Said by the publisher in the column name itself: `net_cost_bil_amt`.
UNITS_EVIDENCE = "publisher_states_the_unit_in_the_field_name"
BILLION = 1_000_000_000

#: Rows that report something other than a unit of government. Refused by name,
#: because each is a real row of the statement that must not be matched to the
#: nearest-looking node: "Total" is the consolidated figure for the whole
#: government, and aliasing it anywhere would publish $7.3 trillion as one
#: agency's cost.
NOT_A_UNIT = frozenset({
    "total",
    "all other entities",
    "security assistance accounts",
    "interest on treasury securities held by the public",
    "national railroad retirement investment trust",
})


def fixture_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_statement(path: Path | str | None = None) -> dict[str, Any]:
    """The committed API response, with its digest recomputed from the bytes.

    The same refusal `pay_tables.load_executive_schedule` makes, and for the
    same reason: a hand-entered table under a `treasury.gov` URL would read on
    the site exactly like a fetched one, and only recomputing the digest tells
    them apart.
    """
    path = Path(path or DEFAULT_FIXTURE)
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    digest = fixture_digest(path)
    recorded = None
    if meta_path.exists():
        recorded = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("sha256")
    if recorded and recorded != digest:
        raise ValueError(
            f"{path.name}: sha256 on disk {digest} does not match the fetch record {recorded}"
        )
    return {"payload": payload, "sha256": digest,
            "url": (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("url") if meta_path.exists() else None}


def current_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The reporting year's own figures: this fiscal year, not restated.

    The file carries each agency twice — the year being reported and the prior
    year restated beside it for comparison (`restmt_flag`). Publishing both
    would give one unit two different audited costs.
    """
    rows = [r for r in (payload.get("data") or []) if isinstance(r, dict)]
    if not rows:
        return []
    latest = max(str(r.get("stmt_fiscal_year") or "") for r in rows)
    return [r for r in rows
            if str(r.get("stmt_fiscal_year") or "") == latest
            and str(r.get("restmt_flag") or "").upper() == "N"]


def to_usd(value: Any) -> float | None:
    try:
        return round(float(value) * BILLION, 2)
    except (TypeError, ValueError):
        return None


def build_records(node_map: dict[str, dict[str, Any]], statement: dict[str, Any] | None = None
                  ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per organisation the statement names, by name equality."""
    statement = statement or load_statement()
    payload = statement["payload"]
    rows = current_rows(payload)

    owners: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if is_post_node(node):
            continue
        owners.setdefault(canonical_name_key(node.get("name")), []).append(node_id)

    records: dict[str, dict[str, Any]] = {}
    refused: dict[str, list[str]] = {}

    def refuse(reason: str, detail: str) -> None:
        refused.setdefault(reason, []).append(detail)

    for row in rows:
        name = str(row.get("agency_nm") or "").strip()
        key = canonical_name_key(name)
        if key in NOT_A_UNIT or not key:
            refuse("row_names_no_unit_of_government", name)
            continue
        ids = owners.get(key) or []
        if not ids:
            refuse("no_node_carries_this_name", name)
            continue
        if len(ids) > 1:
            refuse("name_reaches_more_than_one_node", f"{name} -> {', '.join(ids)}")
            continue
        net = to_usd(row.get("net_cost_bil_amt"))
        if net is None:
            refuse("no_net_cost_figure", name)
            continue
        if net == 0:
            # Zero is never published as a measurement anywhere in this project.
            refuse("zero_reported", name)
            continue
        node_id = ids[0]
        records[node_id] = {
            "source": SOURCE,
            "sourceType": SOURCE_TYPE,
            "metric": METRIC,
            "agencyName": name,
            "netCostUsd": net,
            "grossCostUsd": to_usd(row.get("gross_cost_bil_amt")),
            "earnedRevenueUsd": to_usd(row.get("earned_revenue_bil_amt")),
            "fiscalYear": str(row.get("stmt_fiscal_year") or ""),
            "statementDate": str(row.get("record_date") or ""),
            "url": statement.get("url") or "",
            "documentSha256": statement["sha256"],
            "unitsEvidenceKind": UNITS_EVIDENCE,
            "printedUnit": "billions of dollars, per the column name net_cost_bil_amt",
            "basisNote": (
                "Audited net cost for the fiscal year named, on an accrual basis: gross cost "
                "less earned revenue. It is not this unit's outlays, not the same period as "
                "the graph's anchor, and not its cost."
            ),
        }

    report = {
        "rows_considered": len(rows),
        "applied": len(records),
        "refused": {reason: len(items) for reason, items in sorted(refused.items())},
        "refused_detail": refused,
        "fiscal_year": rows[0].get("stmt_fiscal_year") if rows else None,
        "documentSha256": statement["sha256"],
    }
    return records, report


def load_net_cost_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        store = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    nodes = store.get("nodes") if isinstance(store, dict) else None
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}


def apply_net_cost_evidence(root: dict[str, Any], records: dict[str, dict[str, Any]],
                            *, index_tree=None) -> dict[str, Any]:
    """Stamp the audited figure beside the cost and never into it.

    Withdrawn first on every node, so a record refused since the last build
    stops being published even though the exporter re-feeds the previous
    graph.json as a payload. The cost fields are not read, let alone written.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree
        index_tree = _index_tree
    node_map, _ = index_tree(root)
    applied = withdrawn = renamed = 0
    for node_id, node in node_map.items():
        if node.pop("auditedNetCost", None) is not None:
            withdrawn += 1
        record = records.get(node_id)
        if not record:
            continue
        if is_post_node(node):
            continue
        # The name must still be the one the statement printed: a rename since
        # the record was derived means the record is about a different claim.
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("agencyName")):
            renamed += 1
            continue
        node["auditedNetCost"] = dict(record)
        applied += 1
    return {"applied": applied, "withdrawn_first": withdrawn, "refused_renamed": renamed}
