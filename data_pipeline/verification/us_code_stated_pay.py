"""A section of the United States Code that states an office's salary in
dollars, read for the one office it names: the President.

## The claim, and why it is its own source rather than a widening

Every statutory pay claim this project publishes under `positionStatutoryPay`
comes from a document that prints a figure beside a tier or a group of roles:
uscourts.gov's compensation table (`judicial_pay.py`), senate.gov's footnote
(`congressional_pay.py`), the annual pay-adjustment order's schedules as the
note to 5 U.S.C. 5332 reproduces them (`us_code_pay_schedules.py`). 3 U.S.C.
102 is a fourth shape: the section names the office itself and states the
figure in its own operative text --

    The President shall receive in full for his services during the term for
    which he shall have been elected compensation in the aggregate amount of
    $400,000 a year, to be paid monthly, and in addition an expense
    allowance of $50,000 ...

-- so the document is both the identification and the rate. That is stronger
than a tier row, and the record says so in words (`statesTheOffice: True`);
it is still filed `scopeMatch: proxy` and graded `partial`, because which
NODE of this graph the Code's "The President" is remains a reviewed
identification (`STATED_RATE_ROWS`, keyed by node id) and not a name the
section prints equal to the node's. That is the treatment the Vice
President's Schedule 6 row already gets, and the two offices should read
alike.

**The $50,000 is not published.** The same sentence states "an expense
allowance of $50,000 ... to assist in defraying expenses", which the section
itself says reverts to the Treasury when unused and is not income. It is not
compensation and no record carries it; the gate refuses a block whose figure
is anything but the mirrored $400,000.

**The section was read from the Government Publishing Office's rendering of
the 2024 edition of the Code on www.govinfo.gov** (the OLRC's host was under
maintenance that day; docs/NETWORK_ACCESS.md section 15), through
`derived_pay.load_section`, which recomputes the digest and separates the
operative text from the notes. The quote must be in the operative text on
every run; `derived_pay.statute_publisher` names the publisher and edition on
the record. The year on the record is the year the section was read in: the
figure has stood since the 1999 amendment the section's own credits list
(Pub. L. 106-58, effective with the 2001 term), and the record does not claim
it was set in the year it was read.

Basic pay is not the node's cost, for the reason `pay_tables.py` states, and
nothing here writes `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod` -- the channel by which a five-row table carried 29
positions to `verified` on 2026-09-11.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.verification.derived_pay import (
    Unreadable,
    load_section,
    statute_publisher,
)
from data_pipeline.exporter.build_graph import canonical_name_key

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "us_code_stated_pay_evidence.json"
)

PAY_SOURCE = "us_code_stated_rate"
PAY_SOURCE_TYPE = "us_code_stated_rate"
PAY_METHOD = "rate_stated_for_the_office_by_the_us_code_section_itself"

PRESIDENT_SENTENCE = (
    "The President shall receive in full for his services during the term for which he shall have been "
    "elected compensation in the aggregate amount of $400,000 a year, to be paid monthly, and in addition "
    "an expense allowance of $50,000 to assist in defraying expenses relating to or resulting from the "
    "discharge of his official duties."
)
#: The credit the section prints for the amendment that set the figure; it is
#: in the operative text (the credits follow the section's own words) and a
#: test pins it, so "since the 1999 amendment" is read off the page.
PRESIDENT_AMENDMENT_CREDIT = "Pub. L. 106–58, title VI, §644(a), Sept. 29, 1999, 113 Stat. 478"

#: node id -> the row. Keyed by id because the identification is reviewed:
#: the section says "The President" and the graph says "The President of the
#: United States", and no name rule should be loosened to join them.
STATED_RATE_ROWS: dict[str, dict[str, Any]] = {
    "exec-president": {
        "nodeName": "The President of the United States",
        "office": "The President",
        "tier": "the president",
        "citation": "3 U.S.C. 102",
        "fixture": "president_3_usc_102_govinfo2024.html",
        "subsection": "Compensation of the President",
        "quote": PRESIDENT_SENTENCE,
        "amountRaw": "400,000",
        "amount": 400_000.0,
        "notPublished": (
            "The same sentence states an expense allowance of $50,000, which the section says reverts to "
            "the Treasury when unused and is not income; it is not compensation and is not published."
        ),
        "credit": PRESIDENT_AMENDMENT_CREDIT,
    },
}


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


def _section(fixture: str, directory: str | Path | None) -> dict[str, Any]:
    if directory is None or Path(directory) == FIXTURE_DIR:
        return load_section(fixture)
    from data_pipeline.verification.tier_reference_pay import _load_section_from

    return _load_section_from(Path(directory) / fixture)


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    *,
    read_year: int,
    read_on: str,
    directory: str | Path | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per reviewed row, each re-adjudicated: the sentence is still
    in the section's operative text, the credit is still printed, the node
    still carries the name the row was written against, and it is one post."""
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, str] = {}
    sections: dict[str, dict[str, Any]] = {}
    for node_id, row in sorted(STATED_RATE_ROWS.items()):
        sec = sections.get(row["fixture"])
        if sec is None:
            sec = _section(row["fixture"], directory)
            sections[row["fixture"]] = sec
        if row["quote"] not in sec["operative"]:
            where = "only in the publisher's notes" if row["quote"] in sec["whole"] else "nowhere on the page"
            refusals[node_id] = f"{row['citation']} no longer carries the quoted sentence ({where})"
            continue
        if row["credit"] not in sec["operative"]:
            refusals[node_id] = f"{row['citation']} no longer prints the amendment credit the row cites"
            continue
        node = node_map.get(node_id)
        if node is None:
            refusals[node_id] = "node not in the graph"
            continue
        if str(node.get("type") or "").casefold() != "position":
            refusals[node_id] = "not a position"
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]):
            refusals[node_id] = f"renamed since the row was written (row: {row['nodeName']!r}, node: {node.get('name')!r})"
            continue
        if node.get("representsPosts"):
            refusals[node_id] = "stands for several posts"
            continue
        publisher, edition = statute_publisher(sec["url"])
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(row["amount"]),
            "amountRaw": row["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": row["quote"],
            "quote": row["quote"],
            "fiscalYear": int(read_year),
            "periodCoverage": "annual_rate",
            "periodAsOf": f"{read_year}-01-01",
            "amountScope": row["office"],
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": sec["url"],
            "documentSha256": sec["sha256"],
            "retrievedAt": sec["fetched_at"],
            "locator": {"section": row["citation"], "subsection": row["subsection"]},
            "office": row["office"],
            "tier": row["tier"],
            "statute": row["citation"],
            "statuteQuote": row["quote"],
            "statesTheOffice": True,
            "identification": {"kind": "reviewed_row", "nodeName": row["nodeName"]},
            "publisher": publisher,
            "edition": edition,
            "year": str(read_year),
            "readOn": read_on,
            "rateText": f"${row['amountRaw']} a year",
            "notPublished": row["notPublished"],
            "amendmentCredit": row["credit"],
        }
    report = {
        "source": PAY_SOURCE,
        "sections": {name: {"url": s["url"], "sha256": s["sha256"], "fetched_at": s["fetched_at"]} for name, s in sorted(sections.items())},
        "reviewedRows": len(STATED_RATE_ROWS),
        "priced": len(records),
        "refused": dict(sorted(refusals.items())),
    }
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionStatutoryPay` -- the field every single-document
    statutory claim shares -- on each reviewed row's node. A node another
    source has already priced is left alone."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0, "renamed_since_the_match": 0,
             "stands_for_many_posts": 0, "already_priced_by_another_source": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        identification = record.get("identification") or {}
        if canonical_name_key(node.get("name")) != canonical_name_key(identification.get("nodeName")):
            stats["renamed_since_the_match"] += 1
            continue
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        if isinstance(node.get("positionStatutoryPay"), dict):
            stats["already_priced_by_another_source"] += 1
            continue
        node["positionStatutoryPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": f"{record.get('statute')}, as printed in the {record.get('edition')}",
            "method": PAY_METHOD,
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "year": record.get("year"),
            "effective": record.get("periodAsOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "seatTier": record.get("tier"),
            "office": record.get("office"),
            "statute": record.get("statute"),
            "statesTheOffice": True,
            "identification": dict(identification),
            "publisher": record.get("publisher"),
            "edition": record.get("edition"),
            "readOn": record.get("readOn"),
            "notPublished": record.get("notPublished"),
            "amendmentCredit": record.get("amendmentCredit"),
            "quote": record.get("quote"),
            "footnotes": [record.get("quote")] if record.get("quote") else [],
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod.
    return stats
