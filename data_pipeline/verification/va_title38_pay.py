"""The VA's own Title 38 pay ranges, and the one table of the four whose
titles mean something without a clinical specialty beside them.

## What the document is

`www.va.gov/OHRM/Pay/2026/PDOP/PayTables.pdf` is the Veterans Health
Administration's schedule of annual pay RANGES under 38 U.S.C. 7431,
effective January 11, 2026. It carries four tables, each a set of tiers with a
printed minimum and maximum and a coverage column naming the assignments in
that tier.

A range is not a rate. The document states the bounds within which a VHA
appointment may be set and says nothing about what any post is actually paid,
so every claim here is published as a band and the panel heads it as one --
the treatment `gs_pay.py` already gives the GS, SES and SL/ST tables.

## Why this reads ONE table of the four, and what that costs

**Table 3 — Chief of Staff and Network Chief Medical Officers** prints three
tiers whose coverage is a bare job title: `Network Chief Medical Officer`,
`Chief of Staff`, `Deputy Chief Medical Officer, Deputy Chief of Staff`. No
other fact is needed to know which tier a title sits in, so the join is the
document's own.

The other three are refused, each for its own reason:

- **Tables 1 and 2 (Clinical Specialty)** print the same leadership titles --
  `Supervisor, Program Manager, Section Chief` at Tier 2 and `Service Chief,
  Service Line Manager, ...` at Tier 3 -- at DIFFERENT ranges, because the two
  tables cover different lists of clinical specialties. Table 1's Tier 3 is
  $165,000-$350,000 and Table 2's is $225,000-$400,000. This graph carries
  `Chief — Medicine Service`, `Chief — Surgery Service` and eighteen more per
  medical centre, and deciding which table each falls under would mean reading
  "Surgery" against Table 2's "Surgery — Cardio-Thoracic, General, Orthopedic,
  Plastic, Hand, Neurosurgery, Thoracic, Transplant, Vascular" and calling it
  a match. That is the assembly this repository refuses everywhere else, and
  the tell is that the same family includes `Chief — Finance`, `Chief — Human
  Resources` and `Chief — Facilities Management`, which are not clinical
  specialties at all and appear in neither table. Publishing a band for the
  clinical ones and nothing for the administrative ones would be this module
  deciding which VA service chiefs are doctors.
**Table 4 (Executive Assignments)** is read too, and its Tier 1 coverage is a
semicolon-separated list that ends `...; Chief Officers (VHA CO); Network
Directors; Medical Center Directors`. A record may claim a Tier 4 band only
when the phrase it names is one whole item of that printed list -- not a
substring of it -- so the module reads the coverage words rather than
trusting a tier number, and a schedule that stopped printing a title stops
pricing it.

Tiers 2 and 3 of that table name VHA Central Office assignments only
(`Executive Directors (VHA CO)`, `Chief Consultants (VHA CO)`,
`Deputy Chief Officers (VHA CO)`), and this graph carries no node of any of
those names.

## A correction this module's own test forced, recorded because it nearly went the other way

A first pass at this file asserted, in its docstring and in the derive
script's note, that the document prints no "Medical Center Director" and no
"Network Director" anywhere -- and refused 36 nodes on that basis. It was
wrong. The check behind it was an ad-hoc grep whose text reconstruction
dropped runs, so the phrase never appeared in the string being searched;
`_text_runs` reads the same bytes correctly and the phrase is plainly there.
`tests/test_va_title38_pay.py` asserts the presence of each priced title and
the ABSENCE of "Associate Director" directly against the committed bytes, so
neither claim rests on anybody's memory of a search.

What survives that correction: "Associate Director" really is absent, so
`VAMC Associate Director (Administrative)` and `Associate Director for
Patient Care Services (CNO)` are refused; and the word "VISN" is absent, so
identifying a Veterans Integrated Service Network with the schedule's
"Network" is a reviewed judgement rather than the document's own word.

## Which nodes it reaches, and the scope rule on each

Four families, 72 nodes, each a single post:

- **`VAMC Chief of Staff (Medical)`**, under the curated `VA Medical Centers`
  grouping -> Table 3's `Chief of Staff`, Tier 2.
- **`VAMC Director`**, same parent -> Table 4's `Medical Center Directors`,
  Tier 1.
- **`Chief Medical Officer, VISN N — <name>`**, under that VISN -> Table 3's
  `Network Chief Medical Officer`, Tier 1.
- **`Network Director, VISN N — <name>`**, under that VISN -> Table 4's
  `Network Directors`, Tier 1.

A name written `<office>, <organisation>` is split at its first comma and the
organisation half must name the node's OWN parent -- the scoping
`statutory_schedule.match_scoped_positions` uses -- and that parent must be
typed `VISN`.

Both are reviewed identifications rather than the document naming the node, so
both are `scopeMatch: proxy` and graded `partial`, for the reason
`us_code_pay_schedules.py` gives. Refused deliberately: `Chief of Staff, VHA`
and the Department's own `Chief of Staff`, because Table 3's bare "Chief of
Staff" is the medical-centre role in VHA usage and neither of those is one.

Basic pay is not the node's cost, and nothing here writes `sourceUrls`,
`sourceTypes`, `lastVerified` or `verificationMethod`.
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "va"
DEFAULT_PAY_PDF = FIXTURE_DIR / "title38_pay_tables_2026.pdf"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "va_title38_pay_evidence.json"
)

PAY_SOURCE = "va_title38_pay_ranges"
PAY_SOURCE_TYPE = "va_title38_pay_ranges"
PAY_METHOD = "title_named_in_the_va_s_title_38_pay_range_table"
TABLE_LABEL = "PAY TABLE 3- CHIEF OF STAFF AND NETWORK CHIEF MEDICAL OFFICERS"
TABLE_4_LABEL = "PAY TABLE 4 \u0096 EXECUTIVE ASSIGNMENTS"
EFFECTIVE_TEXT = "Effective January 11, 2026"
EFFECTIVE_DATE = "2026-01-11"
AUTHORITY = "Title 38, U.S.C. §7431, Physician, Dentist, Podiatrist and Optometrist Annual Pay Ranges"

#: The two curated families this module prices, and the coverage title each
#: answers to in Table 3. A reviewed identification, not the document naming
#: the node -- so `proxy`, always.
NODE_NAME_TO_COVERAGE = {
    "VAMC Chief of Staff (Medical)": ("3", "Chief of Staff"),
    "VAMC Director": ("4", "Medical Center Directors"),
}
#: A post written `<office>, <organisation>` is priced only when the
#: organisation half names its own parent AND that parent is of this type.
SCOPED_OFFICE_TO_COVERAGE = {
    "Chief Medical Officer": ("3", "Network Chief Medical Officer", "VISN"),
    "Network Director": ("4", "Network Directors", "VISN"),
}
#: The parent a whole-name match must sit under, so a node of the same name
#: somewhere else in the tree is never priced.
NODE_NAME_PARENT = {
    "VAMC Chief of Staff (Medical)": "VA Medical Centers",
    "VAMC Director": "VA Medical Centers",
}

_MONEY_PAIR = re.compile(r"\$([0-9][0-9,]*)\s+\$([0-9][0-9,]*)\s+(.*)")


class Unreadable(Exception):
    """The PDF is not the schedule this parser knows how to read."""


def _text_runs(pdf_bytes: bytes) -> list[str]:
    """Every text run the content streams draw, in document order.

    The same standard-library route `whitehouse_pay.extract_text_runs` and
    `omb_budget.guide_text` take -- an inflate of each stream, then the
    ordinary `[(...)...] TJ` and `(...) Tj` operators. No third-party PDF
    library enters the repository.
    """
    if not pdf_bytes.startswith(b"%PDF"):
        raise Unreadable("not a PDF")
    if b"/Encrypt" in pdf_bytes:
        raise Unreadable("the PDF is encrypted; ciphertext is not read")
    runs: list[str] = []
    for raw_stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        try:
            data = zlib.decompress(raw_stream)
        except zlib.error:
            continue
        if b"TJ" not in data and b"Tj" not in data:
            continue
        for match in re.finditer(rb"\[(.*?)\]\s*TJ|\((?:\\.|[^\\()])*\)\s*Tj", data, re.S):
            block = match.group(0)
            pieces = re.findall(rb"\((?:\\.|[^\\()])*\)", block)
            text = b"".join(piece[1:-1] for piece in pieces)
            decoded = text.decode("latin-1").replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
            if decoded.strip():
                runs.append(decoded)
    return runs


def _tier_rows(window: list[str], label: str) -> list[dict[str, Any]]:
    """Every `$min $max <coverage>` row in one table's run window."""
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(window):
        money = _MONEY_PAIR.match(line)
        if not money:
            continue
        minimum = float(money.group(1).replace(",", ""))
        maximum = float(money.group(2).replace(",", ""))
        coverage = money.group(3).strip()
        cursor = index + 1
        while cursor < len(window) and not _MONEY_PAIR.match(window[cursor]) and not window[cursor].startswith(
            ("MINIMUM", "TIER", "PAY TABLE", "COVERAGE", "DEPARTMENT", "Veterans", "Title 38", "Optometrist", "Effective")
        ):
            coverage = f"{coverage} {window[cursor]}".strip()
            cursor += 1
        if minimum <= 0 or maximum <= 0:
            raise Unreadable(f"{label}: {line!r} is not a pair of positive figures")
        if maximum < minimum:
            raise Unreadable(f"{label}: {line!r} prints a maximum below its minimum")
        if not coverage:
            raise Unreadable(f"{label}: {line!r} prints a range with no coverage text")
        rows.append(
            {
                "minimum": minimum,
                "maximum": maximum,
                "minimumRaw": money.group(1),
                "maximumRaw": money.group(2),
                "coverage": coverage,
                # The coverage is one title on Table 3 and a semicolon list on
                # Table 4. Split into whole items so a record can only ever
                # claim something the schedule prints as its own entry, never
                # a substring of a longer phrase.
                "coverageItems": [item.strip() for item in coverage.split(";") if item.strip()],
                "printed": f"${money.group(1)} ${money.group(2)} {coverage}",
            }
        )
    for tier, row in enumerate(rows, start=1):
        row["tier"] = tier
    return rows


def parse_pay_tables(pdf_bytes: bytes) -> dict[str, Any]:
    """Tables 3 and 4 as the document prints them, keyed by table number.

    Tables 1 and 2 are deliberately not returned; the module's docstring says
    why. The parser checks the document's own headings and effective line, so
    a reshaped schedule yields nothing rather than a tier number with no words
    behind it.
    """
    runs = _text_runs(pdf_bytes)
    if not runs:
        raise Unreadable("no text runs; this is not the text-bearing schedule")
    flat = [" ".join(run.split()) for run in runs]
    joined = " ".join(flat)

    if AUTHORITY.split(",")[0] not in joined:
        raise Unreadable("the document does not carry its own Title 38 authority line")
    if EFFECTIVE_TEXT not in joined:
        raise Unreadable(f"the document does not print {EFFECTIVE_TEXT!r}")

    starts = [i for i, line in enumerate(flat) if line.startswith("PAY TABLE ")]
    if len(starts) < 4:
        raise Unreadable(f"{len(starts)} PAY TABLE headings; this parser reads a document with four")

    tables: dict[str, dict[str, Any]] = {}
    for position, start in enumerate(starts):
        heading = flat[start]
        number = heading.split()[2].rstrip("-\u0096").strip() if len(heading.split()) > 2 else ""
        if number not in ("3", "4"):
            continue
        if number == "3":
            # Table 3's heading wraps onto the next run.
            if not flat[start + 1].startswith("NETWORK CHIEF MEDICAL"):
                raise Unreadable(f"PAY TABLE 3's heading continues {flat[start + 1]!r}, not the network-officer line")
            heading = f"{heading} {flat[start + 1]}".strip()
            expected = TABLE_LABEL
        else:
            expected = TABLE_4_LABEL
        if heading != expected:
            raise Unreadable(f"PAY TABLE {number} is headed {heading!r}, not {expected!r}")
        end = starts[position + 1] if position + 1 < len(starts) else len(flat)
        rows = _tier_rows(flat[start:end], heading)
        if len(rows) != 3:
            raise Unreadable(f"{heading} yielded {len(rows)} tier rows; this parser reads tables of exactly three")
        tables[number] = {"number": number, "table": heading, "rows": rows}

    for required in ("3", "4"):
        if required not in tables:
            raise Unreadable(f"the document does not carry PAY TABLE {required}")
    return {
        "source": PAY_SOURCE,
        "tables": tables,
        "authority": AUTHORITY,
        "effectiveText": EFFECTIVE_TEXT,
        "effective": EFFECTIVE_DATE,
    }


def load_pay_tables(pdf_path: str | Path = DEFAULT_PAY_PDF) -> dict[str, Any]:
    """The committed PDF, with its provenance and the digest recomputed from
    the bytes -- the refusal `pay_tables` makes."""
    path = Path(pdf_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256")
    if digest != recorded:
        raise Unreadable(
            f"{path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the document")
    parsed = parse_pay_tables(raw)
    return {"table": parsed, "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(path)}


def load_pay_evidence(path: str | Path = DEFAULT_PAY_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def _quote_for(parsed: Mapping[str, Any], table: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    """The table's own heading, authority, effective line and the tier row."""
    return " \u00b7 ".join(
        [
            parsed["authority"],
            table["table"],
            parsed["effectiveText"],
            "TIER {}: {}".format(row["tier"], row["printed"]),
        ]
    )


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_of: Mapping[str, str],
    parsed: Mapping[str, Any],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A band record for every node whose title one of the read tables prints.

    `parent_of` maps node id -> parent id, because both scope rules are about
    the parent the published tree actually gives the node, never a `parentId`
    field stamped on an export.
    """
    tables = parsed["tables"]
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    matched_by_rule: dict[str, int] = {}

    def refuse(reason: str) -> None:
        refusals[reason] = refusals.get(reason, 0) + 1

    def find_row(table_number: str, coverage_title: str):
        table = tables.get(table_number)
        if table is None:
            return None, None
        for row in table["rows"]:
            # A whole printed item of the coverage list, never a substring:
            # "Medical Center Directors" is one entry of Table 4 Tier 1's
            # seven, and a containment test would also match a longer phrase
            # that merely mentioned it.
            if coverage_title in row["coverageItems"]:
                return table, row
        return table, None

    for node_id, node in sorted(node_map.items()):
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        parent = node_map.get(parent_of.get(node_id, ""))
        rule = ""

        if name in NODE_NAME_TO_COVERAGE:
            table_number, coverage_title = NODE_NAME_TO_COVERAGE[name]
            wanted_parent = NODE_NAME_PARENT[name]
            if parent is None or str(parent.get("name") or "") != wanted_parent:
                refuse("name_matches_but_parent_is_not_the_scoped_one")
                continue
            rule = "whole_name_under_its_scoped_parent"
        elif ", " in name:
            office, _, organisation = name.partition(", ")
            scoped = SCOPED_OFFICE_TO_COVERAGE.get(office.strip())
            if scoped is None:
                continue
            table_number, coverage_title, parent_type = scoped
            if parent is None or str(parent.get("name") or "").strip() != organisation.strip():
                refuse("scoped_office_whose_organisation_half_is_not_its_parent")
                continue
            if str(parent.get("type") or "").strip() != parent_type:
                refuse("scoped_office_whose_parent_is_not_the_expected_kind")
                continue
            rule = "office_scoped_to_its_own_parent"
        else:
            continue

        table, row = find_row(table_number, coverage_title)
        if row is None:
            refuse("table_no_longer_prints_this_coverage_title")
            continue
        if str(node.get("type") or "").casefold() != "position":
            refuse("not_a_position")
            continue
        if node.get("representsPosts"):
            refuse("stands_for_several_posts")
            continue

        quote = _quote_for(parsed, table, row)
        matched_by_rule[rule] = matched_by_rule.get(rule, 0) + 1
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            # The record's own figure is the band's MINIMUM; the maximum rides
            # beside it. `financial_evidence` validates one amount per record,
            # and a band's lower bound is the figure a reader can check
            # against the printed row.
            "amount": float(row["minimum"]),
            "amountRaw": row["minimumRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": int(parsed["effective"][:4]),
            "periodCoverage": "annual_rate",
            "periodAsOf": parsed["effective"],
            "amountScope": coverage_title,
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {"page": table["table"], "section": "TIER {}".format(row["tier"])},
            "rangeMinimum": float(row["minimum"]),
            "rangeMaximum": float(row["maximum"]),
            "rangeMinimumRaw": row["minimumRaw"],
            "rangeMaximumRaw": row["maximumRaw"],
            "tier": int(row["tier"]),
            "tableLabel": table["table"],
            "coverageTitle": coverage_title,
            "matchRule": rule,
            "rangeText": "${} \u2013 ${}".format(row["minimumRaw"], row["maximumRaw"]),
        }

    report = {
        "source": PAY_SOURCE,
        "effective": parsed["effective"],
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "tables": {
            number: [
                {"tier": r["tier"], "minimum": r["minimum"], "maximum": r["maximum"], "coverage": r["coverageItems"]}
                for r in table["rows"]
            ]
            for number, table in sorted(tables.items())
        },
        "priced": len(records),
        "matchedByRule": dict(sorted(matched_by_rule.items())),
        "refused": dict(sorted(refusals.items())),
        "tablesNotRead": {
            "PAY TABLE 1 / 2 (Clinical Specialty)": (
                "the same leadership titles at two different ranges, selected by clinical specialty; this graph's "
                "'Chief \u2014 X Service' family includes Finance, Human Resources and Facilities Management, which "
                "are in neither table"
            ),
        },
        "titlesNotPrinted": [
            "Associate Director (so VAMC Associate Director (Administrative) and Associate Director for Patient "
            "Care Services (CNO) are refused)",
        ],
    }
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionTierPay` -- a BAND, never a rate.

    Its own field rather than `positionGradePay` for the reason
    `statutory_schedule.py` gives for not widening `positionPayRate`: that one
    is published only while a PLUM listing still reports the pay plan it was
    looked up from, and this one rests on a title printed in a schedule with
    no listing underneath it at all. Two withdrawal rules cannot share a field.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0, "stands_for_many_posts": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        node["positionTierPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "the VA's own Title 38 annual pay ranges",
            "method": PAY_METHOD,
            "kind": "title_38_tier",
            "minimum": record.get("rangeMinimum"),
            "maximum": record.get("rangeMaximum"),
            "rangeText": record.get("rangeText"),
            "tier": record.get("tier"),
            "coverageTitle": record.get("coverageTitle"),
            "matchRule": record.get("matchRule"),
            "table": record.get("tableLabel"),
            "authority": AUTHORITY,
            "effective": record.get("periodAsOf"),
            "effectiveText": EFFECTIVE_TEXT,
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "note": (
                "a range the schedule sets for this tier, not a rate: the VA states the bounds within which an "
                "appointment may be set and does not publish what any holder is paid"
            ),
            "quote": record.get("quote"),
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod — see `judicial_pay.apply_pay_evidence`.
    return stats
