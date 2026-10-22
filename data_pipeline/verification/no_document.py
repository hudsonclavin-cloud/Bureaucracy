"""A recorded reason no official document can be read for a unit.

The definition of done (docs/DEFINITION_OF_DONE.md, criterion 3) is that every
current organisation carries a ``verificationMethod`` OR "a recorded reason no
official document can be read for it". The first half has nine routes and 623
organisations; the second half had exactly one published form,
``verificationUnread`` -- a page QUEUED for the node went unread, and why --
and 175 organisations fell outside both: no page was ever queued for them, so
nothing went unread, and the panel said "No source recorded. This entry comes
from the hand-compiled base graph, and no source URL has been attached to it
yet", which reads as though nobody had looked. Somebody had. Every one of the
175 has a record in the phase 1b nomination ledger (``data/audit/nominations/
source-*.jsonl``) saying what was tried and why no page could be named, or a
record in the verifier's own evidence file saying the NAME could never be
evidence.

This module publishes that, as ``verificationNoDocument``, and no more:

- ``kind`` is one of a closed vocabulary that is the ledger's own
  (``nominate.NO_CANDIDATE_REASONS`` less ``not_an_organisation``) plus the
  verifier's two name floors. Nothing here invents a reason; it quotes one.
- A **name-floor** block (``curated_count_label``, ``name_too_generic``) rests
  on the verifier's own ``uncheckable_reason`` as recomputed from the node's
  current name on every build, so a rename withdraws it. "Mission Teams (15)"
  counts things; no page will ever carry it as a label.
- A **ledger** block quotes the LATEST ledger record for the node (the rule
  ``nominate.read_ledger`` uses: by ``nominatedAt``, then file order), and only
  when that record is a decline (``noCandidate: true``) with one of the six
  reasons. A latest record that NOMINATES a page is not a reason: there is a
  page to check and the verifier decides. The two reasons the ledger itself
  requires a probe for (``host_refuses_crawler``, ``page_read_does_not_name_it``)
  carry the probe's URL and verdict, and the URL must be on a .gov/.mil host.
- A ledger judgement made about an earlier name is refused: a row of
  ``data/curation/unit_renames.json`` for the node whose ``addedOn`` is later
  than the record's ``nominatedAt`` means the agent read the page against a
  name the graph no longer uses.

It is stamped only on an organisation (never a post, a receipts line or a
Treasury accounting line), never on a replaced unit, never beside a
``verificationMethod`` and never beside ``verificationUnread``, which already
states the stronger, dated fact about a specific page. It writes no
``sourceUrls``, no ``lastVerified``, no ``verificationFailure`` and no
``verificationStatus``: nothing was learned about the unit, only about what
this project can and cannot read. The field is in ``EVIDENCE_OWNED_FIELDS``
and ``MINIMAL_GRAPH_FIELDS``; a deleted ledger record is a real withdrawal.

What it is worth is said in the panel's own words: a fact about the documents
this project holds and the hosts it may read, not a finding about the unit.
``scripts/report_evidence_coverage.py`` counts these as the criterion's
"recorded reason" and lists them by kind so the owner can see that 55 of them
are "a page was read and does not carry the graph's name", which has a route
(a rename), beside 39 that are the graph's own groupings, which has none.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_pipeline.verification.evidence import (
    is_post_node,
    uncheckable_reason_for_node,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_DIR = PROJECT_ROOT / "data" / "audit" / "nominations"
DEFAULT_RENAMES_PATH = PROJECT_ROOT / "data" / "curation" / "unit_renames.json"

FIELD = "verificationNoDocument"

#: The verifier's own floors on a NAME (evidence.uncheckable_reason): the
#: curated name could never be a label on any page.
NAME_FLOOR_KINDS = ("curated_count_label", "name_too_generic")
#: The ledger's decline reasons that are a reason no page can be read for the
#: unit. ``not_an_organisation`` is left out: a post or a line is refused by
#: type before this module looks at the ledger.
LEDGER_KINDS = (
    "editorial_grouping",          # the graph's own grouping; no page names it
    "covered_by_parent",           # no page of its own; the parent's page is the check
    "no_public_page_known",        # a real unit with no page anybody could name
    "not_on_a_gov_host",           # its site exists and is not .gov/.mil (si.edu, usps.com)
    "host_refuses_crawler",        # a .gov/.mil page exists; the host will not serve it
    "page_read_does_not_name_it",  # the page was read; the graph's name is not on it
)
#: The two the ledger requires a probe block for, since each asserts something
#: about a specific page rather than about the agent's ignorance.
PROBE_KINDS = ("host_refuses_crawler", "page_read_does_not_name_it")
KINDS = NAME_FLOOR_KINDS + LEDGER_KINDS
BASIS_NAME_FLOOR = "verifier_name_floor"
BASIS_LEDGER = "nomination_ledger"
#: The ledger note is an agent's sentence or two; the panel quotes it so a
#: reader sees what was tried. Bounded so the viewer copy stays small.
NOTE_CHARS = 320
OFFICIAL_HOST_SUFFIXES = (".gov", ".mil")


def read_source_ledger(ledger_dir: Path | str = DEFAULT_LEDGER_DIR) -> dict[str, dict[str, Any]]:
    """Every agent's source-nomination file, merged: node id -> the latest
    record, with the file it came from under ``_file``. The LATEST wins by
    ``nominatedAt`` and then by file order -- the rule ``nominate.read_ledger``
    applies, mirrored here so this module imports nothing from ``scripts/``;
    ``tests/test_no_document.py`` pins the two equal on the committed ledger."""
    records: dict[str, dict[str, Any]] = {}
    stamps: dict[str, tuple[str, int]] = {}
    directory = Path(ledger_dir)
    if not directory.is_dir():
        return records
    for order, path in enumerate(sorted(directory.glob("source-*.jsonl"))):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("id"):
                node_id = str(record["id"])
                stamp = (str(record.get("nominatedAt") or ""), order)
                if node_id not in stamps or stamp >= stamps[node_id]:
                    stamps[node_id] = stamp
                    record = dict(record)
                    record["_file"] = path.name
                    records[node_id] = record
    return records


def read_rename_dates(path: Path | str = DEFAULT_RENAMES_PATH) -> dict[str, str]:
    """Node id -> the latest ``addedOn`` of a rename row whose ``to`` is a
    name the graph now uses. A ledger judgement older than that was made
    against a name the node no longer carries."""
    out: dict[str, str] = {}
    table_path = Path(path)
    if not table_path.is_file():
        return out
    try:
        table = json.loads(table_path.read_text(encoding="utf-8"))
    except ValueError:
        return out
    for row in table.get("renames") or []:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("id") or "")
        added = str(row.get("addedOn") or "")
        if node_id and added and added > out.get(node_id, ""):
            out[node_id] = added
    return out


def is_treasury_line(node: dict[str, Any]) -> bool:
    return bool(node.get("synthetic")) or "treasury accounting line" in str(node.get("type") or "").casefold()


def is_current_organisation(node: dict[str, Any]) -> bool:
    """The population criterion 3 is measured over: an organisation node that
    is neither a post, a receipts or accounting line, nor a replaced unit."""
    if is_post_node(node) or is_treasury_line(node):
        return False
    type_text = str(node.get("type") or "").casefold()
    if any(word in type_text for word in ("caucus",)):
        return False
    return str(node.get("lifecycle") or "") != "superseded"


def _official_host(url: str) -> bool:
    from urllib.parse import urlparse

    host = urlparse(str(url or "")).netloc.lower()
    return bool(host) and host.endswith(OFFICIAL_HOST_SUFFIXES)


def ledger_refusal(record: dict[str, Any] | None, *, renamed_on: str | None = None) -> str | None:
    """Why this ledger record licenses no block, or None if it does."""
    if not record:
        return "no_ledger_record"
    if not record.get("noCandidate"):
        return "latest_record_nominates_a_page"
    reason = str(record.get("reason") or "")
    if reason not in LEDGER_KINDS:
        return "reason_is_not_a_no_document_reason"
    nominated_at = str(record.get("nominatedAt") or "")
    if len(nominated_at) < 10:
        return "record_carries_no_date"
    if renamed_on and renamed_on > nominated_at[:10]:
        return "node_renamed_after_the_record"
    if reason in PROBE_KINDS:
        probe = record.get("probe")
        if not isinstance(probe, dict) or not probe.get("url") or not probe.get("verdict"):
            return "probe_missing"
        if not _official_host(str(probe.get("url"))):
            return "probe_url_not_official"
    return None


def build_block(node: dict[str, Any], record: dict[str, Any] | None, *, renamed_on: str | None = None) -> dict[str, Any] | None:
    """The block for one organisation, or None. The name floor is tried
    first: it is recomputed from the name every build and needs no record."""
    floor = uncheckable_reason_for_node(node)
    if floor in NAME_FLOOR_KINDS:
        return {
            "kind": floor,
            "basis": BASIS_NAME_FLOOR,
            "name": str(node.get("name") or ""),
        }
    if ledger_refusal(record, renamed_on=renamed_on):
        return None
    assert record is not None
    block: dict[str, Any] = {
        "kind": str(record.get("reason")),
        "basis": BASIS_LEDGER,
        "name": str(node.get("name") or ""),
        "recordedAt": str(record.get("nominatedAt")),
        "ledger": {
            "file": str(record.get("_file") or ""),
            "run": str(record.get("run") or ""),
        },
        "note": str(record.get("note") or "")[:NOTE_CHARS],
    }
    probe = record.get("probe")
    if isinstance(probe, dict) and probe.get("url"):
        block["probe"] = {
            "url": str(probe.get("url")),
            "verdict": str(probe.get("verdict") or ""),
        }
    return block


def apply_no_document_evidence(
    root: dict[str, Any],
    *,
    ledger: dict[str, dict[str, Any]] | None = None,
    rename_dates: dict[str, str] | None = None,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp ``verificationNoDocument`` on every current organisation with no
    method and no unread record that the ledger or the name floor explains.
    Runs after every evidence pass, since it must read the final method."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    if ledger is None:
        ledger = read_source_ledger()
    if rename_dates is None:
        rename_dates = read_rename_dates()
    node_map, _ = index_tree(root)
    stats: dict[str, Any] = {
        "organisations": 0, "with_method": 0, "unread": 0, "stamped": 0,
        "kinds": {}, "refusals": {}, "no_record": 0,
    }
    for node_id, node in node_map.items():
        node.pop(FIELD, None)
        if node is root or not is_current_organisation(node):
            continue
        stats["organisations"] += 1
        if node.get("verificationMethod"):
            stats["with_method"] += 1
            continue
        if isinstance(node.get("verificationUnread"), dict):
            stats["unread"] += 1
            continue
        record = ledger.get(str(node_id))
        block = build_block(node, record, renamed_on=rename_dates.get(str(node_id)))
        if block is None:
            why = ledger_refusal(record, renamed_on=rename_dates.get(str(node_id))) or "no_block"
            stats["refusals"][why] = stats["refusals"].get(why, 0) + 1
            if record is None:
                stats["no_record"] += 1
            continue
        node[FIELD] = block
        stats["stamped"] += 1
        stats["kinds"][block["kind"]] = stats["kinds"].get(block["kind"], 0) + 1
    return stats
