"""An explained blank where no held pay document prices a post.

`docs/DEFINITION_OF_DONE.md` criterion 2 is done when every position carries
a pay claim an official document supports, or a stated reason no such figure
exists -- and the owner's own words there are that "a terminal reason needs a
document exactly as a figure does". This module is NOT a terminal reason. It
is the pay analogue of `cost_no_document.py`: for every position with no pay
claim and no employer block, it checks the post's title against the titles
printed in every TITLE-LISTING pay document this project holds and publishes
the result as `payNoDocument`:

- `kind: no_held_pay_document_prints_the_title` -- none of the documents
  prints a row, a leadership-table line, a statutory item or a footnote item
  carrying this title (canonical-key equality, the test every matcher here
  uses; the name's own "(×N)" multiplicity suffix is a parenthetical and the
  key drops it). The claim is exactly that: not "no published document states
  this post's pay", which nobody could check, but "none of THESE documents
  prints the title", with each document named, versioned, digested and
  counted.
- `kind: title_printed_in_a_held_pay_document_without_a_row_reaching_this_post`
  -- a held document DOES print the title, and no reviewed rule has turned that
  row into a figure for THIS post: OPM's current export lists "General
  Counsel" under 150 organisations, and a row reaches a post only under the
  organisation the export files it under; the archive and the Government
  Manual the same. The block names the document and the title as printed, so
  the panel can say the title is a stamp the document prints elsewhere rather
  than a title nobody has heard of.

`reason` is the unpriced report's own reason (`report_unpriced_positions.
classify`: `unreached`, `multiplicity`, `listed_no_rate`,
`beneath_replaced_unit`), so the panel can say in the same words the report
uses why nothing reached the post; the kind says what the documents print.

The six documents are the committed fixtures the pay modules read, so a title
check here is against the same bytes a figure would come from: 5 U.S.C.
§§5312-5316 (every position the Executive Schedule enumerates), OPM's current
Plum Book export (every live row's title; the incumbent columns are never
read), OPM's PLUM archive of the previous administration (every row's title),
the White House Office's staff report (every row's title; the name column is
discarded at parse time), the Government Manual's leadership tables (every
row the complete-title rule admits) and Schedule 8's enlisted footnote (the
senior enlisted advisers it names). The documents that print TIERS rather
than titles -- uscourts.gov's compensation table, senate.gov's salary table,
Schedules 5-7, the VA's Title 38 ranges, OPM's GS/SES/SL tables, the DOJ AD
chart -- are not title lists and are not checked; the block says how many
documents were checked and the panel names them, so the claim is bounded to
what was read.

The list is identical on every node and sits ONCE on the root as
`__heldPayDocuments` (3,200 posts carry the block; a copy per node would add
four megabytes to the pipeline's own state file); each block carries
`documentsRef` and `documentsChecked`, and the gate re-derives the root list
from the fixtures with its own readers and checks every block against it.

It writes no pay field, no cost field and no source: a blank explained is
still a blank. Never on an organisation, a Treasury line, a post any pay
document has priced, or a post whose employer block already says why
(`positionEmployer`, the one terminal reason this project has).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"

FIELD = "payNoDocument"
ROOT_FIELD = "__heldPayDocuments"
DOCUMENTS_REF = "heldPayDocuments"
KIND_NONE = "no_held_pay_document_prints_the_title"
KIND_NAMED = "title_printed_in_a_held_pay_document_without_a_row_reaching_this_post"
KINDS = (KIND_NONE, KIND_NAMED)
#: The unpriced report's reasons a block may carry; `not_federally_paid` is
#: the employer block's and takes no blank.
REASONS = ("unreached", "multiplicity", "listed_no_rate", "beneath_replaced_unit")

#: Every pay field; imported rather than restated so a new field cannot make
#: this module stamp a blank beside a figure.
from data_pipeline.verification.pay_documents import PAY_FIELDS  # noqa: E402

EMPLOYER_FIELD = "positionEmployer"
EXECUTIVE_SCHEDULE_SECTIONS = ("5312", "5313", "5314", "5315", "5316")


def _names(values) -> dict[str, str]:
    """Canonical key -> the first printed form, for every non-empty string."""
    out: dict[str, str] = {}
    for value in values:
        text = str(value or "").strip()
        key = canonical_name_key(text)
        if key and key not in out:
            out[key] = text
    return out


def _joined_digest(digests) -> str:
    return hashlib.sha256("\n".join(digests).encode("ascii")).hexdigest()


def executive_schedule_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import statutory_schedule

    try:
        schedule = statutory_schedule.load_schedule()
    except Exception:  # noqa: BLE001 -- a section not in hand is simply not checked
        return None
    sections = schedule.get("sections") or {}
    values: list[str] = []
    digests: list[str] = []
    for number in EXECUTIVE_SCHEDULE_SECTIONS:
        block = sections.get(number) or {}
        digests.append(str(block.get("sha256") or ""))
        values.extend(str(p.get("title") or "") for p in block.get("positions") or [])
    return {
        "id": "executive_schedule_5_usc_5312_5316",
        "document": "5 U.S.C. §§5312–5316, the Executive Schedule (every position the five sections enumerate)",
        "version": "the five sections as committed",
        "file": "exec_schedule_5312.html … exec_schedule_5316.html",
        "sha256": _joined_digest(digests),
        "names": _names(values),
    }


def plum_current_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import plum_current

    try:
        export = plum_current.load_plum_export()
    except Exception:  # noqa: BLE001
        return None
    return {
        "id": "opm_current_plum_export",
        "document": "OPM's current Plum Book export (the title of every Filled or Vacant row; incumbent columns never read)",
        "version": f"fetched {str(export.get('fetched_at') or '')[:10]}",
        "file": str(export.get("file") or ""),
        "sha256": str(export.get("sha256") or ""),
        "names": _names(r.get("title") for r in export.get("rows") or []),
    }


def plum_archive_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import positions

    try:
        archive = positions.load_plum_archive()
    except Exception:  # noqa: BLE001
        return None
    path = positions.DEFAULT_ARCHIVE_CSV
    return {
        "id": "opm_plum_archive",
        "document": "OPM's PLUM archive of the previous administration (the title of every row; incumbent columns never read)",
        "version": f"fetched {str(archive.get('fetched_at') or '')[:10]}",
        "file": str(archive.get("file") or path.name),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "names": _names(r.get("title") for r in archive.get("rows") or []),
    }


def whitehouse_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import whitehouse_pay

    try:
        loaded = whitehouse_pay.load_staff_report()
    except Exception:  # noqa: BLE001
        return None
    report = loaded.get("report") or {}
    return {
        "id": "whitehouse_staff_report",
        "document": "the White House Office's Annual Report to Congress on White House Staff (the title of every row; names discarded)",
        "version": f"as of {report.get('asOfText') or ''}".strip(),
        "file": Path(str(loaded.get("file") or "")).name,
        "sha256": str(loaded.get("sha256") or ""),
        "names": _names(r.get("title") for r in report.get("rows") or []),
    }


def govman_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import govman

    try:
        manual = govman.read_manual()
    except Exception:  # noqa: BLE001
        return None
    values: list[str] = []
    for entity in manual.get("entities") or []:
        values.extend(str(t.get("title") or "") for t in entity.get("titles") or [])
    return {
        "id": "us_government_manual_leadership_tables",
        "document": "the United States Government Manual's leadership tables (every row the complete-title rule admits; names never read)",
        "version": f"edition {manual.get('edition') or ''}",
        "file": Path(str(govman.DEFAULT_PACKAGE)).name,
        "sha256": str(manual.get("sha256") or ""),
        "names": _names(values),
    }


def schedule_8_universe() -> dict[str, Any] | None:
    from data_pipeline.verification import military_pay

    try:
        loaded = military_pay.load_schedule_8()
    except Exception:  # noqa: BLE001
        return None
    schedule = loaded.get("schedule") or {}
    footnote = schedule.get("seniorEnlistedFootnote") or {}
    return {
        "id": "schedule_8_enlisted_footnote",
        "document": "Schedule 8 of the pay-adjustment order, the enlisted footnote (the senior enlisted advisers it names)",
        "version": f"effective January 1, {schedule.get('year') or ''}",
        "file": Path(str(loaded.get("file") or "")).name,
        "sha256": str(loaded.get("sha256") or ""),
        "names": _names(t.get("title") for t in footnote.get("titles") or []),
    }


_UNIVERSE_CACHE: dict[str, list[dict[str, Any]]] = {}


def document_universes() -> list[dict[str, Any]]:
    """Every held title-listing pay document, with the titles it prints. Order
    is the order the root list gives them. Cached within a process: the
    fixtures do not change under a running build."""
    if "all" not in _UNIVERSE_CACHE:
        universes = [executive_schedule_universe(), plum_current_universe(), plum_archive_universe(),
                     whitehouse_universe(), govman_universe(), schedule_8_universe()]
        _UNIVERSE_CACHE["all"] = [u for u in universes if u and u.get("names")]
    return _UNIVERSE_CACHE["all"]


def documents_listed(universes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The root's `__heldPayDocuments` list: what was checked, without the titles."""
    return [
        {"id": u["id"], "document": u["document"], "version": u["version"], "file": u["file"],
         "sha256": u["sha256"], "titlesChecked": len(u["names"])}
        for u in universes
    ]


def is_treasury_line(node: dict[str, Any]) -> bool:
    return bool(node.get("synthetic")) or "treasury accounting line" in str(node.get("type") or "").casefold()


def reason_for(node: dict[str, Any], beneath_replaced: bool) -> str | None:
    """`report_unpriced_positions.classify`, for the reasons a blank may carry;
    None where the post is priced or the employer block speaks."""
    if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
        return None
    employer = node.get(EMPLOYER_FIELD)
    if isinstance(employer, dict) and employer.get("federallyPaid") is False:
        return None
    if beneath_replaced:
        return "beneath_replaced_unit"
    if node.get("representsPosts"):
        return "multiplicity"
    if isinstance(node.get("positionListing"), dict) or isinstance(node.get("positionCurrentListing"), dict):
        return "listed_no_rate"
    return "unreached"


def takes_block(node: dict[str, Any], beneath_replaced: bool) -> str | None:
    """The reason a blank carries, or None where none belongs: a post, not a
    Treasury line, with no pay claim and no employer block."""
    if not is_post_node(node) or is_treasury_line(node):
        return None
    return reason_for(node, beneath_replaced)


def named_in(name: str, universes: list[dict[str, Any]]) -> list[dict[str, str]]:
    key = canonical_name_key(name)
    hits = []
    for universe in universes:
        printed = universe["names"].get(key)
        if printed is not None:
            hits.append({"document": universe["id"], "printed": printed})
    return hits


def build_block(node: dict[str, Any], reason: str, universes: list[dict[str, Any]]) -> dict[str, Any]:
    hits = named_in(str(node.get("name") or ""), universes)
    return {
        "kind": KIND_NAMED if hits else KIND_NONE,
        "reason": reason,
        "name": str(node.get("name") or ""),
        "namedIn": hits,
        "documentsRef": DOCUMENTS_REF,
        "documentsChecked": len(universes),
    }


def _walk_with_replaced(root: dict[str, Any]):
    stack = [(root, False)]
    while stack:
        node, replaced = stack.pop()
        replaced = replaced or str(node.get("lifecycle") or "") == "superseded"
        yield node, replaced
        for child in node.get("children") or []:
            if isinstance(child, dict):
                stack.append((child, replaced))


def apply_pay_no_document(root: dict[str, Any], *, universes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Stamp `payNoDocument` on every post with no pay claim and no employer
    block, and the shared document list on the root. Runs after every pay
    pass, the multi-post sweep and the employer pass, since it reads all of
    them; the field is cleared everywhere first so a post that gained a figure
    loses the blank."""
    if universes is None:
        universes = document_universes()
    documents = documents_listed(universes)
    root.pop(ROOT_FIELD, None)
    stats: dict[str, Any] = {"documents": [d["id"] for d in documents], "stamped": 0, "named": 0,
                             "kinds": {}, "reasons": {}}
    for node, replaced in _walk_with_replaced(root):
        node.pop(FIELD, None)
        if node is root:
            continue
        reason = takes_block(node, replaced)
        if reason is None:
            continue
        block = build_block(node, reason, universes)
        node[FIELD] = block
        stats["stamped"] += 1
        stats["kinds"][block["kind"]] = stats["kinds"].get(block["kind"], 0) + 1
        stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1
        if block["namedIn"]:
            stats["named"] += 1
    if stats["stamped"]:
        root[ROOT_FIELD] = documents
    return stats
