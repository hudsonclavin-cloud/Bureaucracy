"""The Executive Schedule level current law assigns a post, from the U.S. Code.

Every rate of pay this project publishes for a position rests on a document
that says what somebody was paid, or what a rank pays. Until now the *level*
half of the Executive Schedule claim came from exactly one place: OPM's PLUM
archive of the **previous** administration (January 2021 - January 2025), which
reported the rank of posts as they were then filled. `pay_tables.py` joins that
archive to OPM's Salary Table No. 2026-EX and publishes 29 rates, every one of
them carrying two dates and neither of them saying what the post is at now.

There is a better source for the level half and it is the statute itself.
**5 U.S.C. 5312-5316** is the Executive Schedule: five sections, one per level,
each an enumerated list of the positions Congress placed at that level. It is
current law rather than a snapshot of an administration, it names the post by
its statutory title rather than as an incumbent's row, and it is served by
`uscode.house.gov`, which answers `robots.txt` 200.

That matters for the most recognisable posts in the government. Today the
Secretary of State, the Attorney General and the Secretary of Defense carry no
pay evidence of any kind. The statute names all three, at Level I.

The five sections are committed verbatim under `tests/fixtures/uscode/` with
the `.meta.json` each fetch wrote, and `load_schedule` **recomputes every
digest from the bytes on disk and refuses a mismatch** -- the same check
`pay_tables.load_executive_schedule` makes, and for the same reason: a
`documentSha256` is a claim that this figure came out of that document, and
re-hashing an edited fixture would launder exactly the edit the check exists
to catch.

**What the claim is, exactly.** Two documents, each stating half, and the
record prints both with their own dates:

    5 U.S.C. 5313 places "Deputy Secretary of Defense" at Level II of the
    Executive Schedule.            <- current law, no date of its own
    OPM's Salary Table No. 2026-EX prints Level II at $228,000, effective
    January 2026.                  <- a rate, with the table's own footnotes

So the record says what the post's statutory rate of basic pay is, and says
nothing about benefits, about locality, about what the current holder receives,
or about this unit's cost. `scopeMatch` is `proxy` and every record is graded
`partial`, which is deliberate and is the convention `judicial_pay.py` and
`congressional_pay.py` already set: they too price a seat a single primary
source names directly, and they too refuse `exact`, because `classify` grades
an exact scope `verified` and a rate of pay is not a measurement of the thing
`resolved_total_amount` measures everywhere else in this graph.

**Three refusals, each of which would otherwise publish something false.**

- A title the statute names that matches **more than one** node, or a node
  matched by more than one statutory title, claims neither. `General Counsel`
  is the name of 84 nodes here; the statute's "General Counsel of the
  Department of Agriculture" is one post, and a rate landing on the wrong one
  would be a correct figure attached to the wrong office.
- Equality of the canonical name key only -- never containment, never a fold.
  The statute prints "Under Secretary of the Army" and "Secretary of the
  Army"; a containment test prices the second from the first. This is the same
  failure `whitehouse_pay.title_core` documents for `Press Secretary` inside
  `ASSISTANT PRESS SECRETARY`, and the same one the existence verifier
  documents for "Office of Science" inside "Office of Science and Technology
  Policy".
- A node that stands for several posts is stripped by
  `pay_tables.withdraw_pay_from_multi_post_nodes`, which sweeps all the pay
  fields in one pass because the multi-post rule is the same rule on each.

**And one the statute forces on us.** Several sections carry a position
followed by a parenthetical count -- "(6)" against Assistant Secretaries -- and
some entries are conditional or have been repealed in place. A title whose
statutory text carries a multiplicity is parsed, reported, and never priced:
it names N posts sharing one level, and this graph's node is one of them or
none of them, which the statute does not say.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from collections.abc import Mapping
from html import unescape
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "schedule_pay_evidence.json"
)

#: Section of title 5 -> the Executive Schedule level it establishes.
SECTION_LEVELS = {
    "5312": "I",
    "5313": "II",
    "5314": "III",
    "5315": "IV",
    "5316": "V",
}
SOURCE = "us_code_executive_schedule"
SOURCE_TYPE = "opm_pay_table"  # the *rate* still comes from OPM's table; see the record's locator
METHOD = "level_assigned_by_5_usc_5312_5316"
CITATION = "5 U.S.C. §{section}"

#: The statute's own body paragraphs, as uscode.house.gov marks them up.
_BODY = re.compile(r'<p class="statutory-body[^"]*">(.*?)</p>', re.S)
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
#: "(6)" or "(2)" trailing a title: N posts sharing one level, never priced.
_MULTIPLICITY = re.compile(r"\((\d+)\)\s*$")
#: A heading rather than a position ("Level II of the Executive Schedule applies…").
_HEADING = re.compile(r"^level\s+[ivx]+\b", re.IGNORECASE)
#: Titles longer than this are sentences -- provisos, effective-date notes.
MAX_TITLE_CHARS = 140
MIN_TITLE_CHARS = 6


class Unreadable(Exception):
    """A committed section could not be trusted, so nothing is derived from it."""


def _text_of(fragment: str) -> str:
    return _SPACE.sub(" ", unescape(_TAGS.sub("", fragment))).strip()


def parse_section(html: str, *, section: str) -> dict[str, Any]:
    """The positions one section of the Executive Schedule enumerates.

    Deliberately shallow: the statute prints one position per body paragraph
    ending in a full stop, and anything that is not that shape is reported
    rather than interpreted. A parser that tried to read the provisos would be
    reading law, which is not a thing this repository does.
    """
    level = SECTION_LEVELS.get(section)
    if not level:
        raise Unreadable(f"{section} is not one of the Executive Schedule sections {sorted(SECTION_LEVELS)}")
    positions: list[dict[str, Any]] = []
    skipped: list[str] = []
    for fragment in _BODY.findall(html):
        text = _text_of(fragment)
        if not text or _HEADING.match(text):
            continue
        if not text.endswith("."):
            skipped.append(text[:120])
            continue
        title = text[:-1].strip()
        if not (MIN_TITLE_CHARS <= len(title) <= MAX_TITLE_CHARS):
            skipped.append(text[:120])
            continue
        multiplicity = _MULTIPLICITY.search(title)
        key = canonical_name_key(title)
        if not key or len(key.split()) < 2:
            skipped.append(text[:120])
            continue
        positions.append({
            "title": title,
            "key": key,
            "level": level,
            "section": section,
            "citation": CITATION.format(section=section),
            "statedPosts": int(multiplicity.group(1)) if multiplicity else 1,
        })
    return {"section": section, "level": level, "positions": positions, "skipped": skipped}


def load_section(path: str | Path) -> dict[str, Any]:
    """One committed section, with its digest recomputed and checked."""
    file_path = Path(path)
    meta_path = file_path.with_name(file_path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(
            f"{file_path.name} has no .meta.json beside it; a statute with no record of its "
            "fetch carries no URL and no date, and cannot be cited"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256; the fetch it describes served nothing")
    if digest != recorded:
        raise Unreadable(
            f"{file_path.name} does not match the digest its fetch recorded "
            f"({digest} vs {recorded}); the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(
            f"{meta_path.name} records a fetch that did not serve the page "
            f"(status {meta.get('status')!r}, error {meta.get('error')!r})"
        )
    match = re.search(r"section(\d{4})", url) or re.search(r"exec_schedule_(\d{4})", file_path.name)
    if not match:
        raise Unreadable(f"{file_path.name}: neither its URL nor its name says which section it is")
    parsed = parse_section(raw.decode("utf-8", errors="replace"), section=match.group(1))
    parsed.update({"url": url, "fetchedAt": fetched_at, "sha256": digest, "file": str(file_path)})
    return parsed


def load_schedule(directory: str | Path = FIXTURE_DIR) -> dict[str, Any]:
    """All five sections, and the index a title is looked up in.

    A key naming more than one position -- across sections or within one --
    is dropped from the index and reported. Two levels for one title is the
    statute amending itself in place, and this module does not adjudicate
    which applies.
    """
    base = Path(directory)
    sections: dict[str, dict[str, Any]] = {}
    for section in sorted(SECTION_LEVELS):
        path = base / f"exec_schedule_{section}.html"
        if not path.exists():
            raise Unreadable(f"{path} is missing; all five Executive Schedule sections are required")
        sections[section] = load_section(path)
    index: dict[str, dict[str, Any]] = {}
    ambiguous: dict[str, list[str]] = {}
    for section in sorted(sections):
        block = sections[section]
        for position in block["positions"]:
            # Each position carries its own section's provenance, so a record
            # derived from it can cite the document it was read out of rather
            # than the chapter in general.
            position.update({"url": block["url"], "sha256": block["sha256"],
                             "fetchedAt": block["fetchedAt"]})
            key = position["key"]
            if key in index and index[key]["level"] != position["level"]:
                ambiguous.setdefault(key, [index[key]["citation"]]).append(position["citation"])
                continue
            index.setdefault(key, position)
    for key in ambiguous:
        index.pop(key, None)
    return {
        "sections": sections,
        "index": index,
        "ambiguous": {k: sorted(set(v)) for k, v in sorted(ambiguous.items())},
        "positions": sum(len(s["positions"]) for s in sections.values()),
    }


#: Separators the Code uses between an office and the body it belongs to:
#: "General Counsel, Department of Education", "Deputy Administrator of the
#: Environmental Protection Agency". Ordered longest-first so " of the " is
#: tried before " of ".
SCOPE_SEPARATORS = (", ", " of the ", " of ", " for the ", " for ")
#: Types the Executive Schedule does not set pay for. Without this, "Secretary
#: of Homeland Security" reaches the Senate Appropriations subcommittee named
#: "Homeland Security" -- a real node, a unique name, and entirely the wrong
#: branch of government. The office floor below refuses that particular case
#: anyway ("Secretary" is one token), which is exactly why it must not be the
#: only thing standing in the way.
NON_EXECUTIVE_TYPE_WORDS = ("committee", "subcommittee", "caucus", "court", "circuit", "district")
METHOD_SCOPED = "level_assigned_by_5_usc_5312_5316_to_this_post_in_this_organisation"
#: An office part shorter than this is not a post, it is a role word. The
#: statute's "Secretary of X" leaves "Secretary"; the graph has hundreds of
#: nodes a bare role word would reach.
MIN_SCOPED_OFFICE_TOKENS = 2


def match_scoped_positions(
    node_map: Mapping[str, Mapping[str, Any]],
    schedule: Mapping[str, Any],
    *,
    already_matched: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The titles the Code writes as "<office>, <organisation>", scoped.

    `match_positions` above needs the node's whole name to equal the statutory
    title, which is right for "Secretary of Energy" and useless for "General
    Counsel of the Department of Agriculture" -- the graph calls that node
    `General Counsel`, under `Department of Agriculture (USDA)`. Splitting the
    statutory title and requiring the organisation half to name the node's own
    PARENT is the same scoping `headcounts.py` applies to a FedScope
    sub-agency row: a name is only evidence of placement when something else
    already placed it.

    Four guards, and the first three each close a way this would otherwise
    publish a real figure against the wrong office:

    - the organisation half must name exactly ONE node, and that node must not
      be a committee, court or other body the Executive Schedule does not
      reach;
    - the office half must be at least two tokens, so a bare role word
      ("Secretary", "Administrator") reaches nothing;
    - the office must be a DIRECT child of that organisation, and exactly one
      such child, so a title cannot pick between two identically-named posts;
    - a node already matched by whole-name equality is never scoped, and a
      node two statutory titles reach claims neither.
    """
    index = schedule["index"]
    taken = set(already_matched or ())
    direct_keys = {canonical_name_key(node.get("name"))
                   for node_id, node in node_map.items() if node_id in taken}
    organisations: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if is_post_node(node) or node.get("synthetic"):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in NON_EXECUTIVE_TYPE_WORDS):
            continue
        organisations.setdefault(canonical_name_key(node.get("name")), []).append(node_id)

    candidates: dict[str, list[dict[str, Any]]] = {}
    refusals: dict[str, list[str]] = {}
    for key, position in sorted(index.items()):
        if key in direct_keys:
            continue  # whole-name equality already priced it, or refused it
        for separator in SCOPE_SEPARATORS:
            if separator not in position["title"]:
                continue
            office, _, body = position["title"].partition(separator)
            office_key, body_key = canonical_name_key(office), canonical_name_key(body)
            if body_key not in organisations:
                break
            if len(organisations[body_key]) != 1:
                refusals.setdefault("organisation_name_reaches_several_nodes", []).append(position["title"])
                break
            if len(office_key.split()) < MIN_SCOPED_OFFICE_TOKENS:
                refusals.setdefault("office_part_is_a_bare_role_word", []).append(position["title"])
                break
            org_id = organisations[body_key][0]
            children = [
                child for child in (node_map[org_id].get("children") or [])
                if is_post_node(child) and canonical_name_key(child.get("name")) == office_key
            ]
            if len(children) > 1:
                refusals.setdefault("office_matches_several_children", []).append(position["title"])
                break
            if not children:
                refusals.setdefault("no_such_post_directly_under_that_organisation", []).append(position["title"])
                break
            child_id = str(children[0].get("id") or "")
            if child_id in taken:
                refusals.setdefault("already_matched_by_its_whole_name", []).append(position["title"])
                break
            candidates.setdefault(child_id, []).append(
                dict(position, scopedOffice=office, scopedOrganisationId=org_id,
                     scopedOrganisation=str(node_map[org_id].get("name") or ""),
                     method=METHOD_SCOPED)
            )
            break

    matched: dict[str, dict[str, Any]] = {}
    for node_id, found in sorted(candidates.items()):
        if len(found) > 1:
            refusals.setdefault("node_reached_by_several_statutory_titles", []).extend(
                sorted(p["title"] for p in found))
            continue
        matched[node_id] = found[0]
    return {"matched": matched, "refusals": {k: sorted(set(v)) for k, v in sorted(refusals.items())}}


def match_positions(node_map: Mapping[str, Mapping[str, Any]], schedule: Mapping[str, Any]) -> dict[str, Any]:
    """Which position nodes the statute names, by canonical-key equality only.

    A key that reaches more than one node claims neither: the statute names
    one post, and a rate landing on the wrong one of two identically-named
    nodes is a correct figure attached to the wrong office.
    """
    index = schedule["index"]
    by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if not is_post_node(node):
            continue
        key = canonical_name_key(node.get("name"))
        if key in index:
            by_key.setdefault(key, []).append(node_id)
    matched: dict[str, dict[str, Any]] = {}
    refusals: dict[str, list[str]] = {}
    for key, node_ids in sorted(by_key.items()):
        position = index[key]
        if len(node_ids) > 1:
            refusals.setdefault("statutory_title_matches_several_nodes", []).extend(sorted(node_ids))
            continue
        if position["statedPosts"] != 1:
            refusals.setdefault("statute_states_several_posts_at_this_title", []).append(node_ids[0])
            continue
        matched[node_ids[0]] = dict(position)
    return {"matched": matched, "refusals": {k: sorted(v) for k, v in sorted(refusals.items())}}


# --------------------------------------------------------------------------
# The third route: a reviewed identification, with the document that makes it

METHOD_REVIEWED = "level_assigned_by_5_usc_5312_5316_to_the_office_a_second_statute_identifies_this_post_as"

#: Node id -> the statutory title the Code prints for it, and the BASIS: a
#: second committed statute whose operative text says why this node is that
#: office. Neither of the two matchers above can make these: "Chair, Board of
#: Governors" is not equal to "Chairman, Board of Governors of the Federal
#: Reserve System", and the scoped matcher's organisation half ("Board of
#: Governors of the Federal Reserve System") is not the node's parent
#: ("Federal Reserve System"). The Vice Chairs are placed by a title that
#: never names them at all -- 5 U.S.C. 5313 prints "Members, Board of
#: Governors of the Federal Reserve System" -- and what makes a Vice Chairman
#: a member is 12 U.S.C. 242, which designates the two Vice Chairmen from
#: among the members and places only the Chairman separately (5312).
#:
#: The same shape as `us_code_pay_schedules.SCHEDULE_6_NODE_ROWS`: a reviewed
#: identification of which node a row names, filed `proxy` because a reviewed
#: identification is not the source naming the node. It is re-checked on
#: every run -- the title must be one the committed sections print, the basis
#: quote must be in the basis section's OPERATIVE text, and the node must
#: still carry the name the row was written against -- and the gate mirrors
#: every row by node id. "Governor (×4 members)" is deliberately absent: the
#: same "Members" title reaches it, but it stands for several posts and
#: `positionSchedulePay` is not a field the multi-post sweep keeps
#: (`pay_tables.INCUMBENCY_PAY_FIELDS`), so a row there would be stripped on
#: every build; pricing a bench from a class title is a separate decision.
REVIEWED_TITLE_ROWS: dict[str, dict[str, str]] = {
    "exec-regulatory-fed-chair-board-of-governors": {
        "nodeName": "Chair, Board of Governors",
        "statutoryTitle": "Chairman, Board of Governors of the Federal Reserve System",
        "basisCitation": "12 U.S.C. 242",
        "basisFixture": "fed_12_usc_242.html",
        "basisQuote": (
            "1 shall be designated by the President, by and with the advice and consent of the Senate, "
            "to serve as Chairman of the Board for a term of 4 years"
        ),
        "basis": (
            "the same office: 12 U.S.C. 242 designates one member of the Board to serve as Chairman of the "
            "Board, and 5 U.S.C. 5312 places that Chairman at Level I; the graph spells the title without "
            "gender and without the System's name"
        ),
    },
    "exec-regulatory-fed-vice-chair-board-of-governors": {
        "nodeName": "Vice Chair, Board of Governors",
        "statutoryTitle": "Members, Board of Governors of the Federal Reserve System",
        "basisCitation": "12 U.S.C. 242",
        "basisFixture": "fed_12_usc_242.html",
        "basisQuote": (
            "2 shall be designated by the President, by and with the advice and consent of the Senate, "
            "to serve as Vice Chairmen of the Board"
        ),
        "basis": (
            "a Vice Chairman is a member of the Board: 12 U.S.C. 242 designates the two Vice Chairmen from "
            "among the members, 5 U.S.C. 5313 places Members of the Board at Level II, and only the Chairman "
            "is placed separately (5312); 5314-5316 print no Federal Reserve entry"
        ),
    },
    "exec-regulatory-fed-vice-chair-for-supervision": {
        "nodeName": "Vice Chair for Supervision",
        "statutoryTitle": "Members, Board of Governors of the Federal Reserve System",
        "basisCitation": "12 U.S.C. 242",
        "basisFixture": "fed_12_usc_242.html",
        "basisQuote": "1 of whom shall be designated Vice Chairman for Supervision",
        "basis": (
            "the Vice Chairman for Supervision is one of the two Vice Chairmen 12 U.S.C. 242 designates from "
            "among the members, and 5 U.S.C. 5313 places Members of the Board at Level II"
        ),
    },
}


def _operative_text(raw_html: str) -> str:
    """The section's own text, cut at the publisher's notes -- the same rule
    `derived_pay.operative_text` applies, restated here so this module does
    not import that one. A quote found only beneath the law is repealed text."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_html)
    text = _SPACE.sub(" ", html_module.unescape(_TAGS.sub(" ", text))).strip()
    start = re.search(r"\u00a7\s?\d+[A-Za-z]?\.", text)
    body = text[start.start():] if start else text
    cuts = [body.find(h) for h in ("Historical and Revision Notes", "Editorial Notes", "Statutory Notes")]
    cuts = [c for c in cuts if c > 0]
    return body[: min(cuts)].strip() if cuts else ""


def load_basis_section(fixture: str, directory: str | Path = FIXTURE_DIR) -> dict[str, Any]:
    """A committed basis section with its digest recomputed from the bytes."""
    path = Path(directory) / fixture
    meta_path = path.with_name(path.name + ".meta.json")
    if not path.exists() or not meta_path.exists():
        raise Unreadable(f"{fixture} or its .meta.json is not committed")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        raise Unreadable(f"{fixture} does not match the digest its fetch recorded")
    operative = _operative_text(raw.decode("utf-8", errors="replace"))
    if not operative:
        raise Unreadable(f"{fixture} carries no operative text this reader can separate from its notes")
    return {"url": str(meta.get("url") or ""), "sha256": digest, "fetchedAt": str(meta.get("fetched_at") or ""),
            "operative": operative}


def match_reviewed_rows(
    node_map: Mapping[str, Mapping[str, Any]],
    schedule: Mapping[str, Any],
    *,
    already_matched: Mapping[str, Any] | None = None,
    directory: str | Path = FIXTURE_DIR,
) -> dict[str, Any]:
    """The rows of `REVIEWED_TITLE_ROWS`, each re-adjudicated: the node still
    carries the name the row was written against, the statutory title is one
    the committed sections print, the basis quote is in the basis section's
    operative text now, and no other route already priced the node."""
    index = schedule["index"]
    taken = set(already_matched or {})
    matched: dict[str, dict[str, Any]] = {}
    refusals: dict[str, list[str]] = {}
    basis_cache: dict[str, dict[str, Any]] = {}
    for node_id, row in sorted(REVIEWED_TITLE_ROWS.items()):
        node = node_map.get(node_id)
        if node is None:
            refusals.setdefault("reviewed_row_names_no_node", []).append(node_id)
            continue
        if not is_post_node(node):
            refusals.setdefault("reviewed_row_names_a_non_post", []).append(node_id)
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]):
            refusals.setdefault("reviewed_row_node_renamed", []).append(node_id)
            continue
        if node_id in taken:
            refusals.setdefault("reviewed_row_node_already_matched", []).append(node_id)
            continue
        position = index.get(canonical_name_key(row["statutoryTitle"]))
        if position is None or position["title"] != row["statutoryTitle"]:
            refusals.setdefault("reviewed_row_title_not_printed_by_the_code", []).append(node_id)
            continue
        try:
            basis = basis_cache.get(row["basisFixture"]) or load_basis_section(row["basisFixture"], directory)
        except Unreadable:
            refusals.setdefault("reviewed_row_basis_unreadable", []).append(node_id)
            continue
        basis_cache[row["basisFixture"]] = basis
        if row["basisQuote"] not in basis["operative"]:
            refusals.setdefault("reviewed_row_basis_quote_not_in_operative_text", []).append(node_id)
            continue
        entry = dict(position)
        entry["method"] = METHOD_REVIEWED
        entry["identification"] = {
            "nodeName": row["nodeName"],
            "basis": row["basis"],
            "basisCitation": row["basisCitation"],
            "basisQuote": row["basisQuote"],
            "basisUrl": basis["url"],
            "basisSha256": basis["sha256"],
            "basisCheckedAt": basis["fetchedAt"],
        }
        matched[node_id] = entry
    return {"matched": matched, "refusals": {k: sorted(v) for k, v in sorted(refusals.items())}}


# --------------------------------------------------------------------------
# The record, and applying it


def build_records(
    matched: Mapping[str, Mapping[str, Any]],
    table: Mapping[str, Any],
    *,
    table_url: str,
    table_sha256: str,
    retrieved_at: str,
    fiscal_year: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record per matched post: statute names the level,
    OPM's table prices it.

    Both halves ride on the record with their own provenance, because a reader
    must be able to see that this is a join and not one document's statement.
    The caller validates each record against its node through
    `financial_evidence.validate_record`, which is where a record is bound to a
    real node of the right kind.
    """
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    for node_id, position in sorted(matched.items()):
        level = (table.get("levels") or {}).get(position["level"])
        if not level:
            # Level I reaches no node in some tables, and a level the table
            # does not print cannot be priced from it.
            refusals["level_not_printed_by_the_table"] = refusals.get("level_not_printed_by_the_table", 0) + 1
            continue
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(level["amount"]),
            "amountRaw": level["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": level["rowText"],
            "quote": level["rowText"],
            "fiscalYear": fiscal_year,
            "periodCoverage": "annual_rate",
            "periodAsOf": table["effective"],
            # The table named a rank, not this unit. `proxy` is the same
            # deliberate downgrade judicial_pay and congressional_pay make:
            # `classify` grades an exact scope `verified`, and a rate of basic
            # pay is not a measurement of what this node costs.
            "amountScope": level["levelText"],
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": SOURCE_TYPE,
            "sourceUrl": table_url,
            "documentSha256": table_sha256,
            "retrievedAt": retrieved_at,
            "locator": {"table": table["table"], "row": level["levelText"], "column": "Rate"},
            # --- the two halves, each with its own provenance --------------
            "levelClaim": {
                "source": SOURCE,
                "method": position.get("method") or METHOD,
                # Present only on a scoped match, and the panel prints it: the
                # Code names "General Counsel of the Department of
                # Agriculture" and the graph calls that node "General
                # Counsel", so a reader must be able to see which office in
                # which body the figure was looked up for. 84 nodes here are
                # named "General Counsel".
                "scopedOffice": position.get("scopedOffice"),
                "scopedOrganisation": position.get("scopedOrganisation"),
                "scopedOrganisationId": position.get("scopedOrganisationId"),
                "payLevel": position["level"],
                "citation": position["citation"],
                "section": position["section"],
                "statutoryTitle": position["title"],
                "url": position["url"],
                "documentSha256": position["sha256"],
                "checkedAt": position["fetchedAt"],
                # Present only on a reviewed row: the second statute that
                # makes this node the office the title names, quoted.
                "identification": position.get("identification"),
            },
            "table": table["table"],
            "effectiveText": table["effectiveText"],
            "rateText": level["rateText"],
            "tableFootnotes": list(table.get("footnotes") or []),
        }
    report = {
        "source": SOURCE,
        "method": METHOD,
        "table": table["table"],
        "effective": table["effective"],
        "matched": len(matched),
        "priced": len(records),
        "refused": dict(sorted(refusals.items())),
        "priced_by_level": {
            level_id: sum(1 for r in records.values() if r["levelClaim"]["payLevel"] == level_id)
            for level_id in sorted(set(SECTION_LEVELS.values()))
        },
    }
    return records, report


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    """The derived records, or nothing. A missing file is not an error: the
    exporter builds without it exactly as it does without the others."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        store = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    nodes = store.get("nodes")
    return nodes if isinstance(nodes, dict) else {}


def apply_schedule_pay(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionSchedulePay` on every position the statute still names.

    A fourth pay field rather than a widening of `positionPayRate`, and
    deliberately so. That one means "OPM's archive reported this post at Level
    N while the previous administration held it"; this one means "current law
    places this post at Level N". They carry different dates, different
    strengths and different withdrawal rules, and folding them together would
    have meant loosening a gate check that already guards 29 published records
    -- to make a new claim easier to publish, which is the wrong direction.

    The rename guard is the same one every evidence module here applies: the
    node's name must still reduce to the statutory title it was matched by, so
    a rename in the curated file cannot inherit a rate looked up for a
    different office.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {
        "priced": 0,
        "priced_scoped": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "renamed_since_the_match": 0,
        "reparented_since_the_match": 0,
        "stands_for_many_posts": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_post_node(node):
            stats["not_a_position"] += 1
            continue
        if node.get("representsPosts"):
            # One rate on a node standing for several posts reads as what a
            # single holder is paid, against a panel that says the figure is
            # the group's. pay_tables.withdraw_pay_from_multi_post_nodes sweeps
            # this field too, after the counts exist; this is the earlier guard.
            stats["stands_for_many_posts"] += 1
            continue
        claim = record.get("levelClaim") or {}
        scoped_office = claim.get("scopedOffice")
        if scoped_office:
            # A scoped record rests on two things -- the node's own name and
            # the body it sits under -- so both are re-checked. A node
            # re-parented in the curated file has no claim on a level the
            # statute set for that office in a different organisation.
            if canonical_name_key(node.get("name")) != canonical_name_key(scoped_office):
                stats["renamed_since_the_match"] += 1
                continue
            if parent_map.get(node_id) != claim.get("scopedOrganisationId"):
                stats["reparented_since_the_match"] += 1
                continue
        elif isinstance(claim.get("identification"), dict):
            # A reviewed row was written against the node's name, not the
            # statutory title, and that is the name a rename must withdraw.
            if canonical_name_key(node.get("name")) != canonical_name_key(claim["identification"].get("nodeName")):
                stats["renamed_since_the_match"] += 1
                continue
        elif canonical_name_key(node.get("name")) != canonical_name_key(claim.get("statutoryTitle")):
            stats["renamed_since_the_match"] += 1
            continue
        node["positionSchedulePay"] = {
            "source": SOURCE,
            "method": claim.get("method") or METHOD,
            "identification": dict(claim["identification"]) if isinstance(claim.get("identification"), dict) else None,
            "payLevel": claim.get("payLevel"),
            "citation": claim.get("citation"),
            "statutoryTitle": claim.get("statutoryTitle"),
            "scopedOffice": claim.get("scopedOffice"),
            "scopedOrganisation": claim.get("scopedOrganisation"),
            "scopedOrganisationId": claim.get("scopedOrganisationId"),
            "statuteUrl": claim.get("url"),
            "statuteCheckedAt": claim.get("checkedAt"),
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "table": record.get("table"),
            "effectiveText": record.get("effectiveText"),
            "effective": record.get("periodAsOf"),
            "fiscalYear": record.get("fiscalYear"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "quote": record.get("quote"),
            "footnotes": list(record.get("tableFootnotes") or []),
            "url": record.get("sourceUrl"),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        if scoped_office:
            stats["priced_scoped"] += 1
        # As in pay_tables: no `sourceUrls`, no `sourceTypes`, no
        # `lastVerified`, no `verificationMethod`. The Code saying a post sits
        # at Level II is not evidence that this graph's node for it exists as
        # drawn, and every one of those fields is read elsewhere as a claim
        # that something does. Publishing one here would repeat, exactly, the
        # 2026-09-11 failure in which a five-row table took 29 positions to
        # `verified`.
    return stats
