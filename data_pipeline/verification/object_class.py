"""Where an agency's money goes: USAspending's object-class breakdown, FY2025.

The owner's ask was not a figure per person but "a good total cost of
everyone combined ... we just want to see where the money goes, generally".
The DATA Act's File B reports every account's obligations and outlays by
OBJECT CLASS -- what the money was spent ON: personnel compensation, benefits,
contracts and services, grants, equipment -- and USAspending publishes it per
agency. This module reads it for the agencies `usaspending.py` already
matches to a node, and nothing wider.

**Which agencies.** Every row of USAspending's committed toptier list whose
name reduces (canonical key equality) to exactly one organisation node, the
row's key being carried by no other toptier row, plus the toptier rows a
reviewed `usaspending.USASPENDING_NAME_ALIASES` entry names (AmeriCorps
through CNCS, the CSB). Widened on 2026-10-08 by the owner's decision from
the phase-2 crosswalk's 22 toptier keys, which remain a subset, so the
departments are reached. The object-class endpoints are toptier-only, so a
bureau never is -- an agency's breakdown stamped on one of its bureaus
would publish a bigger unit's spending as the bureau's.
`usaspending.BROADER_API_ENTITY` is honoured for the same reason.

**What is read, three documents per agency, each committed verbatim** under
`tests/fixtures/usaspending/object_class/` with its `.meta.json`, digest
recomputed before a figure is read:

- `minor/<code>.json` -- `/api/v2/agency/<code>/object_class/?fiscal_year=2025`:
  every object class as the API names it, with `obligated_amount` and
  `gross_outlay_amount`. It prints no class codes.
- `major/<code>.json` -- `/api/v2/financial_spending/major_object_class/`:
  the publisher's own grouping ("Personnel compensation and benefits",
  "Contractual services and supplies", "Acquisition of assets", "Grants and
  fixed charges", "Other", "Unknown Object Type") with its code and
  obligations. This is the grouping the panel draws, and it is OMB's, not
  this repository's: no class is regrouped here.
- `personnel/<code>.json` -- the same service's minor classes beneath major
  class 10, WITH codes, which is what lets staff pay be named by code.

**Staff pay** is the obligations of object classes 11.x (personnel
compensation) and 12.x (personnel benefits), listed by code and name on the
block. Class 13.0, "Benefits for former personnel", sits in the same major
group and is excluded and said to be: it pays people the agency no longer
employs. The result is a sum this repository performs over rows the API
prints, and the block says so.

**Refused, with the reason on the report:** a fixture whose digest has
changed; a paged response with a further page; two endpoints disagreeing on
the total (the minor classes must sum to the major groups to the dollar, and
major group 10 to its own minor rows) -- the Appalachian Regional Commission
fails this, its minor classes summing to $190m against $9.2m of major
groups; and a staff pay or total of zero, which is never published.

**What it is not.** FY2025 obligations by object class -- a completed year,
commitments rather than cash, gross of offsetting collections -- and not the
Treasury's net outlays the graph publishes as a cost. Nothing here writes a
cost field, `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod`.

**Scale.** The JSON prints bare numbers. The publisher's Data Dictionary
(`tests/fixtures/usaspending/data_dictionary_crosswalk.xlsx`) carries rows
for the two File B elements these figures are --
`ObligationsIncurredByProgramObjectClass_CPE` and
`GrossOutlayAmountByProgramObjectClass_CPE`, "Account Breakdown" -- and
both rows are re-read here from the committed workbook and quoted by element
on every record. Those rows map the elements to the ACCOUNT DOWNLOAD's
columns, not to this endpoint's field names, so the reading of
`obligated_amount` as that element rests on the endpoint being File B's
object-class breakdown; the block's own `units.note` says so in words, and
it is weaker than the rule `usaspending.py` uses, where the dictionary names
the API field itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_pipeline.verification import usaspending as _us
from data_pipeline.verification.evidence import canonical_name_key
from data_pipeline.verification.financial_evidence import is_organisation

FIELD = "spendingByKind"
SOURCE = "usaspending_file_b_object_class"
FISCAL_YEAR = 2025
PROJECT_ROOT = _us.PROJECT_ROOT
FIXTURE_ROOT = _us.FIXTURE_ROOT / "object_class"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "object_class_evidence.json"

#: Object-class code prefixes that are pay and benefits of people the agency
#: employs now. 13.0 "Benefits for former personnel" is deliberately absent.
STAFF_CLASS_PREFIXES = ("11.", "12.")
STAFF_NOTE = (
    "Pay and benefits of everyone the agency employs, FY2025, obligations: object classes 11 "
    "(personnel compensation) and 12 (personnel benefits) as listed; 13.0, benefits for former "
    "personnel, is not included. A sum this repository performed over the rows USAspending prints."
)
NOTE = (
    "Obligations by object class for fiscal year 2025, a completed year, as USAspending reports "
    "DATA Act File B. Obligations are commitments, not cash, and gross of offsetting collections: "
    "this is not the Treasury's net outlays the graph shows as a cost."
)
UNITS_NOTE = (
    "The publisher's Data Dictionary carries both File B elements as dollar figures of the account "
    "breakdown; it maps them to the account download's columns, not to this endpoint's field names."
)
DICTIONARY_ELEMENTS = (
    ("ObligationsIncurredByProgramObjectClass_CPE", "obligations_incurred"),
    ("GrossOutlayAmountByProgramObjectClass_CPE", "gross_outlay_amount"),
)


class Refused(Exception):
    pass


def _load(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        data, meta, _raw = _us.load_json_fixture(path)
    except _us.Unreadable as error:
        raise Refused(f"fixture_unreadable: {error}") from error
    except OSError as error:
        raise Refused(f"fixture_missing: {path.name}") from error
    return data, meta


def _has_next(data: dict[str, Any]) -> bool:
    meta = data.get("page_metadata") or {}
    return bool(meta.get("hasNext") or meta.get("has_next_page"))


def _money(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise Refused(f"not_a_figure: {value!r}")
    return round(float(value), 2)


def load_dictionary_rows() -> list[dict[str, str]]:
    """Both File B elements, re-read from the committed workbook."""
    rows = []
    for element, field in DICTIONARY_ELEMENTS:
        saved = (_us.DICTIONARY_ELEMENT, _us.DICTIONARY_FIELD)
        try:
            _us.DICTIONARY_ELEMENT, _us.DICTIONARY_FIELD = element, field
            row = _us.load_dictionary()
        finally:
            _us.DICTIONARY_ELEMENT, _us.DICTIONARY_FIELD = saved
        rows.append({"element": element, "column": field, "file": row["file"], "sha256": row["sha256"]})
    return rows


def matched_agencies(node_map: dict[str, dict[str, Any]], crosswalk: dict[str, dict[str, Any]] | None = None):
    """node id -> (toptier code, the API's name, alias or None).

    One reach rule (since 2026-10-08, the owner's decision): a row of the
    committed toptier list reaches an organisation node when the two names
    reduce to the same canonical key, or when the node carries one of
    `usaspending.USASPENDING_NAME_ALIASES` naming that row -- and only when
    the match is unique both ways: the row's key names exactly one
    organisation here, and no other toptier row reduces to the same key. A
    bureau is never reached: these endpoints are toptier-only. The phase-2
    crosswalk's 22 toptier keys are a subset of what this reaches; the
    argument is accepted for the callers that still pass it and not read.
    """
    out: dict[str, tuple[str, str, dict[str, str] | None]] = {}
    refused: dict[str, str] = {}
    data, _meta = _load(_us.TOPTIER_FIXTURE)
    rows = [r for r in data.get("results") or [] if isinstance(r, dict)]
    orgs: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if is_organisation(node) and not node.get("synthetic"):
            orgs.setdefault(canonical_name_key(str(node.get("name") or "")), []).append(node_id)
    row_keys: dict[str, int] = {}
    for row in rows:
        key = canonical_name_key(str(row.get("agency_name") or ""))
        row_keys[key] = row_keys.get(key, 0) + 1
    by_name = {str(r.get("agency_name") or ""): r for r in rows}
    for row in rows:
        api_name = str(row.get("agency_name") or "")
        code = str(row.get("toptier_code") or "")
        key = canonical_name_key(api_name)
        nodes = orgs.get(key) or []
        if not key or not code or not nodes:
            continue
        if len(nodes) > 1:
            for node_id in nodes:
                refused[node_id] = f"toptier {code} name reaches {len(nodes)} organisations"
            continue
        if row_keys[key] != 1:
            refused[nodes[0]] = f"{row_keys[key]} toptier rows reduce to this name"
            continue
        if nodes[0] in _us.BROADER_API_ENTITY:
            refused[nodes[0]] = "api_entity_is_broader"
            continue
        out[nodes[0]] = (code, api_name, None)
    for node_id, alias in sorted(_us.USASPENDING_NAME_ALIASES.items()):
        node = node_map.get(node_id)
        row = by_name.get(alias.get("apiName") or "")
        if node is None or row is None or node_id in out:
            continue
        if not is_organisation(node) or node.get("synthetic"):
            refused[node_id] = "not_an_organisation_in_this_graph"
            continue
        if canonical_name_key(alias["graphName"]) != canonical_name_key(node.get("name") or ""):
            refused[node_id] = "alias_names_a_different_node_name"
            continue
        if row_keys[canonical_name_key(alias["apiName"])] != 1:
            refused[node_id] = "alias_row_not_unique"
            continue
        claimed = [n for n, v in out.items() if v[0] == str(row.get("toptier_code"))]
        if claimed:
            refused[node_id] = f"toptier row already reached by {claimed[0]}"
            continue
        out[node_id] = (str(row.get("toptier_code")), alias["apiName"], alias)
    return out, refused


def build_record(node_id: str, code: str, api_name: str, alias, dictionary: list[dict[str, str]]) -> dict[str, Any]:
    paths = {kind: FIXTURE_ROOT / kind / f"{code}.json" for kind in ("minor", "major", "personnel")}
    loaded = {kind: _load(path) for kind, path in paths.items()}
    for kind, (data, meta) in loaded.items():
        if _has_next(data):
            raise Refused(f"paged_response_incomplete: {kind}")
        if f"fiscal_year={FISCAL_YEAR}" not in str(meta.get("url") or ""):
            raise Refused(f"not_fiscal_year_{FISCAL_YEAR}: {kind}")
    minor = loaded["minor"][0].get("results") or []
    major = loaded["major"][0].get("results") or []
    personnel = loaded["personnel"][0].get("results") or []
    classes = [[str(r.get("name")), _money(r.get("obligated_amount")), _money(r.get("gross_outlay_amount"))]
               for r in minor]
    groups = sorted(
        ({"code": str(r.get("major_object_class_code")), "name": str(r.get("major_object_class_name")),
          "obligations": _money(r.get("obligated_amount"))} for r in major),
        key=lambda g: -g["obligations"],
    )
    total = round(sum(g["obligations"] for g in groups), 2)
    if total <= 0:
        raise Refused("total_obligations_not_positive")
    minor_total = round(sum(c[1] for c in classes), 2)
    if abs(minor_total - total) > 1.0:
        raise Refused(f"endpoints_disagree: minor classes sum to {minor_total}, major groups to {total}")
    group10 = [g for g in groups if g["code"] == "10"]
    personnel_total = round(sum(_money(r.get("obligated_amount")) for r in personnel), 2)
    if not group10 or abs(group10[0]["obligations"] - personnel_total) > 1.0:
        raise Refused("personnel_group_disagrees_with_its_rows")
    staff_rows = [[str(r.get("object_class_code")), str(r.get("object_class_name")), _money(r.get("obligated_amount"))]
                  for r in personnel if str(r.get("object_class_code") or "").startswith(STAFF_CLASS_PREFIXES)]
    staff_rows.sort(key=lambda r: r[0])
    staff = round(sum(r[2] for r in staff_rows), 2)
    if staff <= 0:
        raise Refused("staff_pay_not_positive")
    gross_total = round(sum(c[2] for c in classes), 2)
    docs = {kind: {"url": meta.get("url"), "file": str(paths[kind].relative_to(PROJECT_ROOT)),
                   "sha256": str(meta.get("sha256")).lower(), "fetchedAt": meta.get("fetched_at")}
            for kind, (_data, meta) in loaded.items()}
    return {
        "nodeId": node_id,
        "source": SOURCE,
        "fiscalYear": FISCAL_YEAR,
        "periodCoverage": "full_fiscal_year",
        "basis": "obligations",
        "toptierCode": code,
        "apiName": api_name,
        "nameAlias": ({"graphName": alias["graphName"], "apiName": alias["apiName"]} if alias else None),
        "groups": groups,
        "totalObligations": total,
        "totalGrossOutlays": gross_total,
        "classes": classes,
        "staffPay": {"amount": staff, "share": round(staff / total, 4), "classes": staff_rows, "note": STAFF_NOTE},
        "documents": docs,
        "units": {"elements": [d["element"] for d in dictionary], "dictionarySha256": dictionary[0]["sha256"],
                  "dictionaryFile": dictionary[0]["file"], "note": UNITS_NOTE},
        "note": NOTE,
    }


def build_records(node_map, crosswalk):
    dictionary = load_dictionary_rows()
    matched, refused = matched_agencies(node_map, crosswalk)
    records: dict[str, dict[str, Any]] = {}
    for node_id, (code, api_name, alias) in sorted(matched.items()):
        try:
            records[node_id] = build_record(node_id, code, api_name, alias, dictionary)
        except Refused as error:
            refused[node_id] = str(error)
    report = {
        "matched": len(matched), "applied": len(records), "refused": dict(sorted(refused.items())),
        "staffPayTotal": round(sum(r["staffPay"]["amount"] for r in records.values()), 2),
    }
    return records, report


def load_evidence(path) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        store = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in (store.get("nodes") or {}).items() if isinstance(v, dict)}


def apply_evidence(root: dict[str, Any], records: dict[str, dict[str, Any]], *, index_tree=None) -> dict[str, Any]:
    """Stamp the breakdown beside the cost, never in it; every block withdrawn first."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    for node in node_map.values():
        node.pop(FIELD, None)
    stats = {"applied": 0, "unknown_node": 0, "not_an_organisation": 0, "stale_name": 0, "malformed": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_organisation(node) or node.get("synthetic"):
            stats["not_an_organisation"] += 1
            continue
        staff = record.get("staffPay") or {}
        if (record.get("source") != SOURCE or record.get("fiscalYear") != FISCAL_YEAR
                or not isinstance(staff.get("amount"), (int, float)) or not staff.get("amount")
                or not record.get("totalObligations")):
            stats["malformed"] += 1
            continue
        alias = record.get("nameAlias") or {}
        expected = alias.get("apiName") or str(node.get("name") or "")
        graph_name = alias.get("graphName") or str(node.get("name") or "")
        if (canonical_name_key(str(record.get("apiName") or "")) != canonical_name_key(expected)
                or canonical_name_key(str(node.get("name") or "")) != canonical_name_key(graph_name)):
            stats["stale_name"] += 1
            continue
        node[FIELD] = {k: v for k, v in record.items() if k != "nodeId"}
        stats["applied"] += 1
    return stats


