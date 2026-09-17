"""USAspending File A, applied beside the Treasury figure and never over it.

`docs/EXACT_NODE_COSTS.md` names USAspending File A/B as the third route to
more exact-node costs, after the crosswalk it needs and the Treasury
statement the graph already anchors on: account-level outlays and
obligations that "could take exact-node coverage from bureaus down to
offices with their own accounts", to be "published as a *separate metric*
from the MTS figure, never merged into it". This module is that route's
first pass, and both halves of that sentence are enforced here.

**What is read.** USAspending's own reference lists, fetched verbatim on
2026-09-17 into `tests/fixtures/usaspending/` (README there) with a
`.meta.json` recording the URL, the fetch time and the sha256 of the bytes
served: the toptier agency list -- the 111 DATA Act reporters with their
CGAC codes and FY-to-date `outlay_amount` -- and, per agency, the
`sub_components` list, which is the bureau grouping Treasury itself applies
to the agency's accounts in GTAS, each with a stable slug and FY-to-date
`total_outlays`. Every fixture's digest is recomputed from the bytes on disk
before a figure is read out of it, the check `pay_tables.load_executive_
schedule` established: a record's `documentSha256` is a claim, and a
hand-edited JSON under a `.gov` URL would otherwise read exactly like a
fetched one.

**What decides a match.** The crosswalk is
`data/audit/nominations/cost-cost-usaspending.jsonl`, the phase-2 ledger in
which each identifier was proposed with the fixture it was read from and a
confidence. A proposal is not a fact. What makes a figure a node's own here
is the same test `evidence.py` uses to decide whether a page names a unit
and `financial_evidence.validate_record` uses for `scopeMatch: "exact"`:
the name the API prints and the name the graph carries reduce to the same
canonical key. A proposal that rests on anything looser -- an alias
(AmeriCorps for the Corporation for National and Community Service), an
abbreviation the API spells out ("Admin" for "Administration"), a bureau
that is broader than the node (the Department of the Air Force, which holds
the Space Force) -- is left in the ledger as a proposal and reported as
`awaiting_review`, with its confidence, so a curator can accept it by
name or add an alias with a stated basis. 8 of the 47 proposed keys stay
there on the first pass; the other 39 are name-equal.

**What the figure is, and is not.** `gross_outlays`: File A's
`GrossOutlayAmountByTAS_CPE`, which the DATA Act Reporting Submission
Specification crosswalks to "GTAS SF 133 line 3020, Outlays, Gross" and
defines from OMB Circular A-11 section 20 as payments made to liquidate an
obligation. It is *gross*: before the offsetting collections the Monthly
Treasury Statement nets off, so for the same agency and period it is a
larger number than the Treasury line this graph publishes as the node's
cost, and the two must never be read as one measurement. It is also
fiscal-year-to-date as of the fetch, not a fiscal year. Nothing here writes
`resolved_total_amount`, `cost_status` or any cost field: the figure sits
in its own block, `usaspendingOutlays`, the panel prints it under its own
heading with its period and its source, and the release gate refuses the
block anywhere it could be mistaken for the cost.

**The scale, stated the only way this publisher states it.** USAspending's
JSON prints `117451319504.29` with no currency mark and no heading, and
neither its API documentation nor its glossary says "in dollars" of an
outlay anywhere this project could fetch from a `.gov` host. What the
publisher does state, in its own Data Dictionary crosswalk
(`tests/fixtures/usaspending/data_dictionary_crosswalk.xlsx`, fetched
verbatim from files.usaspending.gov), is which DATA Act element each API
field carries; and the DATA Act element is the Treasury's own dollar figure
from the SF 133. So each record's `unitsEvidence` quotes that mapping row
from the committed workbook and names the workbook's digest, and
`financial_evidence` accepts it under a rule granted to this one source
type -- `DICTIONARY_SCALED_SOURCE_TYPES`, kind `publishers_data_dictionary`
-- alongside its own plausibility ceiling, which is what actually bounds a
units error. The mapping is re-read from the workbook here and again by the
release gate, so a record cannot quote a row the dictionary does not carry.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_pipeline.verification.evidence import canonical_name_key
from data_pipeline.verification.financial_evidence import (
    DICTIONARY_SCALED_SOURCE_TYPES,
    Rejected,
    classify,
    is_organisation,
    validate_record,
)

SOURCE = "usaspending_file_ab"
BASIS = "gross_outlays"
FIELD = "usaspendingOutlays"
LEVEL_TOPTIER = "toptier"
LEVEL_BUREAU = "bureau"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "usaspending"
TOPTIER_FIXTURE = FIXTURE_ROOT / "toptier_agencies.json"
DICTIONARY_FIXTURE = FIXTURE_ROOT / "data_dictionary_crosswalk.xlsx"
DEFAULT_CROSSWALK_PATH = PROJECT_ROOT / "data" / "audit" / "nominations" / "cost-cost-usaspending.jsonl"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "usaspending_evidence.json"

#: The DATA Act element File A carries for the basis published here, and the
#: USAspending field the publisher's dictionary maps it to. Mirrored from
#: `financial_evidence.DICTIONARY_SCALED_SOURCE_TYPES` so the two cannot say
#: different things without a test noticing.
DICTIONARY_FIELD, DICTIONARY_ELEMENT = DICTIONARY_SCALED_SOURCE_TYPES[SOURCE][BASIS]


class Unreadable(Exception):
    """A fixture this module will not read a figure out of."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _meta_for(path: Path) -> dict[str, Any]:
    meta_path = path.with_name(path.name + ".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unreadable(f"{meta_path.name}: no readable meta file ({error.__class__.__name__})") from error
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256; the fetch it describes served nothing")
    actual = _sha256(path)
    if actual != recorded:
        # Refused rather than re-hashed: a fixture whose bytes are not the
        # ones the fetch recorded is not the document the URL names.
        raise Unreadable(f"{path.name}: sha256 {actual} does not match the recorded {recorded}")
    if not str(meta.get("url") or "").startswith("https://api.usaspending.gov/") and not str(
        meta.get("url") or ""
    ).startswith("https://files.usaspending.gov/"):
        raise Unreadable(f"{path.name}: recorded URL {meta.get('url')!r} is not USAspending's")
    return meta


def load_json_fixture(path: str | Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """The parsed JSON, its meta, and the verbatim text -- the text because a
    record's `quote` and `amountRaw` must be the figure as the document
    prints it, and json.loads has already turned that into a float."""
    path = Path(path)
    meta = _meta_for(path)
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise Unreadable(f"{path.name}: not JSON ({error})") from error
    return data, meta, raw


def load_dictionary(path: str | Path = DICTIONARY_FIXTURE) -> dict[str, Any]:
    """The publisher's Data Dictionary crosswalk, read with the standard
    library the way `congress.read_xlsx_rows` reads a spreadsheet: a zip of
    XML. Returns the mapping row for this module's element, quoted verbatim
    cell by cell, plus the workbook's digest."""
    path = Path(path)
    meta = _meta_for(path)
    try:
        book = zipfile.ZipFile(path)
        shared = book.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        workbook = book.read("xl/workbook.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        raise Unreadable(f"{path.name}: not a readable workbook ({error.__class__.__name__})") from error
    strings = [
        html.unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", item)))
        for item in re.findall(r"<si>(.*?)</si>", shared, re.S)
    ]
    names = re.findall(r'<sheet [^>]*name="([^"]+)"', workbook)
    rows: list[dict[str, str]] = []
    for index, _name in enumerate(names, 1):
        member = f"xl/worksheets/sheet{index}.xml"
        if member not in book.namelist():
            continue
        xml = book.read(member).decode("utf-8", "replace")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
            cells: dict[str, str] = {}
            for match in re.finditer(r'<c r="([A-Z]+)\d+"(?: [^>]*?t="(\w+)")?[^>]*>(?:<v>([^<]*)</v>)?', row):
                column, kind, value = match.groups()
                if value is None:
                    continue
                cells[column] = strings[int(value)] if kind == "s" else value
            if cells:
                rows.append(cells)
    hits = [
        cells for cells in rows
        if any(value.strip() == DICTIONARY_ELEMENT for value in cells.values())
        and any(DICTIONARY_FIELD in value for value in cells.values())
    ]
    if len(hits) != 1:
        raise Unreadable(
            f"{path.name}: expected exactly one row mapping {DICTIONARY_ELEMENT} to a field containing "
            f"{DICTIONARY_FIELD!r}, found {len(hits)}"
        )
    row = hits[0]
    line = " | ".join(f"{column}: {value.strip()}" for column, value in sorted(row.items()) if value.strip())
    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "url": meta.get("url"),
        "sha256": str(meta.get("sha256")).lower(),
        "fetchedAt": meta.get("fetched_at"),
        "element": DICTIONARY_ELEMENT,
        "field": DICTIONARY_FIELD,
        "line": line,
    }


def load_crosswalk(path: str | Path = DEFAULT_CROSSWALK_PATH) -> dict[str, dict[str, Any]]:
    """The phase-2 ledger's USAspending identifiers, latest record per node
    by nominatedAt -- the same rule `nominate.py` merges by."""
    path = Path(path)
    best: dict[str, tuple[str, dict[str, Any]]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        node_id = str(record.get("id") or "")
        stamp = str(record.get("nominatedAt") or "")
        identifiers = [i for i in record.get("identifiers") or [] if isinstance(i, dict) and i.get("system") == SOURCE]
        if not node_id or record.get("noCandidate") or not identifiers:
            if node_id and record.get("noCandidate") and (node_id not in best or best[node_id][0] <= stamp):
                best[node_id] = (stamp, {})
            continue
        if node_id not in best or best[node_id][0] <= stamp:
            best[node_id] = (stamp, {"metric": record.get("metric"), **identifiers[0]})
    return {node_id: identifier for node_id, (_, identifier) in best.items() if identifier}


def key_parts(key: str) -> tuple[str, str | None]:
    text = str(key or "").strip()
    if "/" in text:
        code, slug = text.split("/", 1)
        return code.strip(), slug.strip() or None
    return text, None


def _verbatim_number(raw: str, anchor_pattern: str, field: str) -> str | None:
    """The figure exactly as the JSON prints it, found inside the object
    `anchor_pattern` identifies, so `amountRaw` is the document's digits."""
    anchor = re.search(anchor_pattern, raw)
    if not anchor:
        return None
    window = raw[anchor.start(): anchor.start() + 4000]
    # The object's own closing brace bounds the window; a sibling object's
    # field must never be read as this one's.
    end = window.find("\n }")
    if end == -1:
        end = window.find("}")
    window = window[: end if end > 0 else len(window)]
    match = re.search(rf'"{field}":\s*(-?\d+(?:\.\d+)?|null)', window)
    if not match or match.group(1) == "null":
        return None
    return match.group(1)


def _fiscal_year_of(meta: dict[str, Any], row: dict[str, Any] | None) -> int | None:
    url = str(meta.get("url") or "")
    match = re.search(r"fiscal_year=(\d{4})", url)
    if match:
        return int(match.group(1))
    if row and str(row.get("active_fy") or "").isdigit():
        return int(row["active_fy"])
    return None


def resolve_identifier(identifier: dict[str, Any]) -> dict[str, Any]:
    """What the fixtures say about a key: the API's own name for it, the
    figure as printed, and the provenance of the file it came from."""
    code, slug = key_parts(identifier.get("key"))
    if not code:
        raise Unreadable("identifier has no toptier code")
    if slug is None:
        data, meta, raw = load_json_fixture(TOPTIER_FIXTURE)
        rows = [r for r in data.get("results") or [] if str(r.get("toptier_code")) == code]
        if len(rows) != 1:
            raise Unreadable(f"toptier {code}: {len(rows)} rows in the toptier list")
        row = rows[0]
        printed = _verbatim_number(raw, rf'"toptier_code":\s*"{re.escape(code)}"', "outlay_amount")
        return {
            "level": LEVEL_TOPTIER, "code": code, "slug": None, "apiName": row.get("agency_name"),
            "toptierName": row.get("agency_name"), "abbreviation": row.get("abbreviation"),
            "amount": row.get("outlay_amount"), "amountRaw": printed, "obligations": row.get("obligated_amount"),
            "fiscalYear": _fiscal_year_of(meta, row), "fixture": str(TOPTIER_FIXTURE.relative_to(PROJECT_ROOT)),
            "url": meta.get("url"), "sha256": str(meta.get("sha256")).lower(), "retrievedAt": meta.get("fetched_at"),
            "quote": _quote_for(raw, rf'"toptier_code":\s*"{re.escape(code)}"', ("agency_name", "outlay_amount")),
        }
    path = FIXTURE_ROOT / "sub_components" / f"{code}.json"
    data, meta, raw = load_json_fixture(path)
    rows = [r for r in data.get("results") or [] if str(r.get("id")) == slug]
    if len(rows) != 1:
        raise Unreadable(f"bureau {code}/{slug}: {len(rows)} rows in the sub_components list")
    row = rows[0]
    toptier_data, _, _ = load_json_fixture(TOPTIER_FIXTURE)
    toptier_rows = [r for r in toptier_data.get("results") or [] if str(r.get("toptier_code")) == code]
    accounts_path = FIXTURE_ROOT / "bureau_accounts" / code / f"{slug}.json"
    accounts = None
    if accounts_path.exists():
        accounts_data, _, _ = load_json_fixture(accounts_path)
        accounts = len(accounts_data.get("results") or [])
    printed = _verbatim_number(raw, rf'"id":\s*"{re.escape(slug)}"', "total_outlays")
    return {
        "level": LEVEL_BUREAU, "code": code, "slug": slug, "apiName": row.get("name"),
        "toptierName": toptier_rows[0].get("agency_name") if toptier_rows else None, "abbreviation": None,
        "amount": row.get("total_outlays"), "amountRaw": printed, "obligations": row.get("total_obligations"),
        "fiscalYear": _fiscal_year_of(meta, None), "fixture": str(path.relative_to(PROJECT_ROOT)),
        "url": meta.get("url"), "sha256": str(meta.get("sha256")).lower(), "retrievedAt": meta.get("fetched_at"),
        "accounts": accounts,
        "quote": _quote_for(raw, rf'"id":\s*"{re.escape(slug)}"', ("name", "total_outlays")),
    }


def _quote_for(raw: str, anchor_pattern: str, fields: tuple[str, ...]) -> str:
    """The object's own lines for `fields`, verbatim, joined -- the text a
    reviewer finds in the fixture with a search."""
    anchor = re.search(anchor_pattern, raw)
    if not anchor:
        return ""
    window = raw[anchor.start(): anchor.start() + 4000]
    end = window.find("\n }")
    if end == -1:
        end = window.find("}")
    window = window[: end if end > 0 else len(window)]
    parts = []
    for field in fields:
        match = re.search(rf'"{field}":\s*[^,\n]+', window)
        if match:
            parts.append(match.group(0).strip())
    return "; ".join(parts)


def _as_of_date(retrieved_at: Any) -> str:
    text = str(retrieved_at or "")
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""


def build_records(
    node_map: dict[str, dict[str, Any]],
    crosswalk: dict[str, dict[str, Any]],
    *,
    dictionary: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One validated record per node whose proposed key names it by canonical
    key equality; everything else refused with the reason on the report."""
    dictionary = dictionary or load_dictionary()
    records: dict[str, dict[str, Any]] = {}
    refused: dict[str, list[dict[str, Any]]] = {}
    applied_by_level = {LEVEL_TOPTIER: 0, LEVEL_BUREAU: 0}

    def refuse(reason: str, node_id: str, identifier: dict[str, Any], detail: str = "") -> None:
        refused.setdefault(reason, []).append(
            {"nodeId": node_id, "key": identifier.get("key"), "confidence": identifier.get("confidence"), "detail": detail}
        )

    for node_id, identifier in sorted(crosswalk.items()):
        node = node_map.get(node_id)
        if node is None:
            refuse("unknown_node", node_id, identifier)
            continue
        if not is_organisation(node):
            refuse("not_an_organisation", node_id, identifier, str(node.get("type")))
            continue
        if identifier.get("metric") != BASIS:
            refuse("metric_not_gross_outlays", node_id, identifier, str(identifier.get("metric")))
            continue
        try:
            resolved = resolve_identifier(identifier)
        except Unreadable as error:
            refuse("fixture_unreadable", node_id, identifier, str(error))
            continue
        api_name = str(resolved.get("apiName") or "")
        if canonical_name_key(api_name) != canonical_name_key(str(node.get("name") or "")):
            # A proposal, not a fact: the ledger's confidence rides along so a
            # curator can see which are plain aliases and which are guesses.
            refuse("awaiting_review_name_not_equal", node_id, identifier, f"API prints {api_name!r}")
            continue
        amount = resolved.get("amount")
        printed = resolved.get("amountRaw")
        if amount is None or printed is None:
            refuse("no_outlay_reported", node_id, identifier, api_name)
            continue
        if float(amount) == 0:
            refuse("zero_outlay_reported", node_id, identifier, api_name)
            continue
        fiscal_year = resolved.get("fiscalYear")
        if not fiscal_year:
            refuse("no_fiscal_year", node_id, identifier)
            continue
        record = {
            "nodeId": node_id,
            "financialEvidenceStatus": "verified",
            "costBasis": BASIS,
            "amount": float(amount),
            "amountRaw": printed,
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": dictionary["line"],
            "unitsEvidenceSource": {"file": dictionary["file"], "sha256": dictionary["sha256"], "url": dictionary.get("url")},
            "quote": resolved["quote"],
            "fiscalYear": int(fiscal_year),
            "periodCoverage": "fiscal_year_to_date",
            "periodAsOf": _as_of_date(resolved.get("retrievedAt")),
            "amountScope": api_name,
            "scopeMatch": "exact",
            "rollupRole": "total",
            "sourceType": SOURCE,
            "sourceUrl": resolved["url"],
            "documentSha256": resolved["sha256"],
            "retrievedAt": resolved["retrievedAt"],
            "locator": {"file": resolved["fixture"], "key": identifier.get("key")},
            "level": resolved["level"],
            "toptierCode": resolved["code"],
            "toptierName": resolved.get("toptierName"),
            "bureauId": resolved.get("slug"),
            "obligations": resolved.get("obligations"),
            "accounts": resolved.get("accounts"),
            "nominationConfidence": identifier.get("confidence"),
        }
        try:
            normalised = validate_record(record, node)
        except Rejected as error:
            refuse("validator_rejected", node_id, identifier, str(error))
            continue
        normalised["financialEvidenceStatus"] = classify(normalised)
        records[node_id] = normalised
        applied_by_level[resolved["level"]] += 1
    report = {
        "crosswalk_identifiers": len(crosswalk),
        "applied": len(records),
        "applied_by_level": applied_by_level,
        "refused": {reason: len(items) for reason, items in sorted(refused.items())},
        "refused_detail": dict(sorted(refused.items())),
        "dictionary": {k: dictionary[k] for k in ("file", "sha256", "element", "field")},
    }
    return records, report


def load_usaspending_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        store = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    nodes = store.get("nodes") if isinstance(store, dict) else None
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}


def apply_usaspending_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp the File A figure beside the cost and never into it.

    Every node's block is withdrawn first, so a record that has been
    withdrawn or refused since the last build stops being published even
    though the exporter re-feeds the previous graph.json as a payload. The
    cost fields are not read, let alone written: `resolved_total_amount` and
    `cost_status` are the Treasury cascade's, and a gross year-to-date outlay
    is neither the same measure nor the same period.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    for node in node_map.values():
        node.pop(FIELD, None)
    stats = {"applied": 0, "unknown_node": 0, "not_an_organisation": 0, "stale_name": 0, "malformed": 0,
             "by_level": {LEVEL_TOPTIER: 0, LEVEL_BUREAU: 0}}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_organisation(node):
            stats["not_an_organisation"] += 1
            continue
        amount = record.get("amount")
        if (
            record.get("sourceType") != SOURCE or record.get("costBasis") != BASIS
            or not isinstance(amount, (int, float)) or isinstance(amount, bool) or float(amount) == 0
            or not str(record.get("sourceUrl") or "").startswith("https://api.usaspending.gov/")
            or not record.get("documentSha256") or not record.get("retrievedAt") or not record.get("periodAsOf")
            or record.get("level") not in (LEVEL_TOPTIER, LEVEL_BUREAU)
        ):
            stats["malformed"] += 1
            continue
        if canonical_name_key(str(record.get("amountScope") or "")) != canonical_name_key(str(node.get("name") or "")):
            # Keyed by id and never re-derived on a rename: a figure earned by
            # a different name is not this node's.
            stats["stale_name"] += 1
            continue
        block: dict[str, Any] = {
            "source": SOURCE,
            "basis": BASIS,
            "level": record["level"],
            "key": (record.get("locator") or {}).get("key"),
            "apiName": record.get("amountScope"),
            "toptierCode": record.get("toptierCode"),
            "toptierName": record.get("toptierName"),
            "bureauId": record.get("bureauId"),
            "amount": float(amount),
            "amountRaw": record.get("amountRaw"),
            "obligations": record.get("obligations"),
            "accounts": record.get("accounts"),
            "fiscalYear": record.get("fiscalYear"),
            "periodCoverage": record.get("periodCoverage"),
            "periodAsOf": record.get("periodAsOf"),
            "url": record.get("sourceUrl"),
            "fixture": (record.get("locator") or {}).get("file"),
            "documentSha256": record.get("documentSha256"),
            "retrievedAt": record.get("retrievedAt"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "unitsEvidenceKind": record.get("unitsEvidenceKind"),
            "unitsEvidenceSource": record.get("unitsEvidenceSource"),
        }
        node[FIELD] = block
        stats["applied"] += 1
        stats["by_level"][record["level"]] += 1
    return stats


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
