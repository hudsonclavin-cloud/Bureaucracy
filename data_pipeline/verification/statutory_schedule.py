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

from data_pipeline.exporter.build_graph import STATED_MULTIPLICITY, canonical_name_key, is_post_node

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
#: The Code's footnote-reference element, exactly as the five committed
#: sections print it: an optional &nbsp; or space, then
#: <sup><a href="#5315_1_target" name="5315_1">1</a></sup>. Only one that
#: CLOSES the paragraph is stripped (since 2026-10-06). The Office of the Law
#: Revision Counsel prints two positions with the mark standing where the
#: full stop should be -- "Commissioner of Food and Drugs, Department of
#: Health and Human Services" (§5315) and "Under Secretary of Education"
#: (§5314), its own footnotes on both reading "So in original. Probably should
#: be followed by a period." -- and a third with the mark AFTER the full stop
#: ("...Acquisition, Technology, and Logistics.", §5314). Read as text the
#: digit survived ("...Human Services 1", "...Logistics.1"), the full-stop
#: rule skipped all three, and three real titles were invisible to the index.
#: A mark anywhere else in a paragraph is kept as printed: §5315's "The 2
#: Commissioner of Labor Statistics, Department of Labor" is indexed under
#: exactly those words, and the Bureau's reviewed row keys on them.
_TRAILING_FOOTNOTE_REF = re.compile(
    r'(?:&nbsp;|\s)*<sup>\s*<a href="#\d{4}_\d+_target" name="\d{4}_\d+">\d+</a>\s*</sup>\s*$'
)
#: Titles longer than this are sentences -- provisos, effective-date notes.
MAX_TITLE_CHARS = 140
MIN_TITLE_CHARS = 6


class Unreadable(Exception):
    """A committed section could not be trusted, so nothing is derived from it."""


def _text_of(fragment: str) -> str:
    return _SPACE.sub(" ", unescape(_TAGS.sub("", fragment))).strip()


def _strip_trailing_footnote_reference(fragment: str) -> tuple[str, bool]:
    """A body paragraph with a CLOSING footnote-reference element removed, and
    whether one was there. A mark anywhere else in the paragraph is left as
    printed; a bare digit or a <sup> that is not the Code's own element is
    never touched."""
    stripped = _TRAILING_FOOTNOTE_REF.sub("", fragment, count=1)
    return stripped, stripped != fragment


def parse_section(html: str, *, section: str) -> dict[str, Any]:
    """The positions one section of the Executive Schedule enumerates.

    Deliberately shallow: the statute prints one position per body paragraph
    ending in a full stop -- or, for three items, in a footnote-reference mark
    standing where the full stop should be, which the Code's own footnote says
    ("So in original. Probably should be followed by a period."; see
    `_TRAILING_FOOTNOTE_REF`) -- and anything that is not that shape is
    reported rather than interpreted. A parser that tried to read the provisos
    would be reading law, which is not a thing this repository does.
    """
    level = SECTION_LEVELS.get(section)
    if not level:
        raise Unreadable(f"{section} is not one of the Executive Schedule sections {sorted(SECTION_LEVELS)}")
    positions: list[dict[str, Any]] = []
    skipped: list[str] = []
    for fragment in _BODY.findall(html):
        body, closed_by_footnote_mark = _strip_trailing_footnote_reference(fragment)
        text = _text_of(body)
        if not text or _HEADING.match(text):
            continue
        if text.endswith("."):
            title = text[:-1].strip()
        elif closed_by_footnote_mark:
            # 2026-10-06: the Code's own footnote says a period should follow,
            # so the closing mark terminates the item as the full stop would.
            title = text
        else:
            skipped.append(text[:120])
            continue
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
#: every row by node id.
#:
#: A row marked `classTitle: True` prices a BENCH from the Code's class title
#: (since 2026-09-27, on the owner's decision): "Members, Federal
#: Communications Commission" is the office every one of the four
#: commissioners holds, and 5 U.S.C. 5315 sets that office's level, so the
#: figure is each holder's by the statute's own words rather than one
#: appointment's -- the reading `derived_pay.BENCH_NODES` already applies to
#: "Each judge shall receive salary at the same rate". Such a row is refused
#: unless the statutory title IS a class title (`is_class_title`: the Code's
#: "Members, ..." form) and the node's own name states a multiplicity; a row
#: without the mark is refused on a node that states one. The record carries
#: `classTitle: True`, which is the one thing that lets
#: `pay_tables.withdraw_pay_from_multi_post_nodes` keep a `positionSchedulePay`
#: block on a multi-post node -- with a `holders` block -- where every other
#: schedule record (a singular title the Code names once) is stripped as an
#: incumbency-shaped claim. The gate mirrors the mark by node id.
REVIEWED_TITLE_ROWS: dict[str, dict[str, Any]] = {
    # The twelfth research batch (2026-10-05): two Executive Office posts the
    # Code prints under a title this graph does not use, then four Justice and
    # Homeland Security posts from the same batch (CURATION.md §19.20), and
    # nine from its regulatory and financial agencies cluster.
    #
    # Its Defense cluster (2026-10-06): the Department's Chief Financial
    # Officer. "Chief Financial Officer" is the stamped title this graph
    # carries under 81 nodes, so the row is keyed to the Department of
    # Defense's node and no other; the Code prints no "Chief Financial
    # Officer, Department of Defense" in its operative text -- §5315's
    # Amendments note records that item inserted by Pub. L. 101-576 (1990)
    # and struck by Pub. L. 103-160 (1993) -- because the Department's CFO is
    # the Under Secretary of Defense (Comptroller), whom §5314 places at
    # Level III and whom 10 U.S.C. 135(b) names as the CFO in so many words.
    # The Department's Chief Information Officer is NOT a row here: §5315
    # prints that title with a 164-character proviso ("unless the official
    # designated as the Chief Information Officer ... is an official listed
    # under section 5312, 5313, or 5314"), the parser refuses a title over
    # `MAX_TITLE_CHARS` as a sentence rather than a title, and reading the
    # proviso would be reading law. Recorded in CURATION.md §19.20.
    "exec-dept-defense-chief-financial-officer": {
        "nodeName": "Chief Financial Officer",
        "statutoryTitle": "Under Secretary of Defense (Comptroller)",
        "basisCitation": "10 U.S.C. 135",
        "basisFixture": "dod_10_usc_135_govinfo2024.html",
        "basisQuote": "The Under Secretary of Defense (Comptroller) is the agency Chief Financial Officer of the Department of Defense for the purposes of chapter 9 of title 31.",
        "basis": "the same office: 10 U.S.C. 135(b) makes the Under Secretary of Defense (Comptroller) the agency Chief Financial Officer of the Department of Defense for the purposes of chapter 9 of title 31, and 5 U.S.C. 5314 places the Under Secretary of Defense (Comptroller) at Level III; the Schedule's own history agrees -- 5 U.S.C. 5315's Amendments note records a 'Chief Financial Officer, Department of Defense' item inserted at Level IV by Pub. L. 101-576 (1990) and struck by Pub. L. 103-160 (1993), the Act whose entry in 5314's note inserted 'Comptroller of the Department of Defense' at Level III, renamed 'Under Secretary of Defense (Comptroller)' by Pub. L. 103-337 -- so the Department's CFO is the Under Secretary and not a Level IV officer of its own; 'Chief Financial Officer' is a stamped title this graph carries under 81 nodes, and this row is keyed to the Department of Defense's node alone",
    },
    "exec-ind-misc-national-labor-relations-board-nlrb-independent-director-administrator-chair-national-labor-relations-board": {
        "nodeName": "Director / Administrator / Chair, National Labor Relations Board",
        "statutoryTitle": "Chairman, National Labor Relations Board",
        "basisCitation": "29 U.S.C. 153",
        "basisFixture": "nlrb_29_usc_153_govinfo2024.html",
        "basisQuote": "The President shall designate one member to serve as Chairman of the Board.",
        "basis": "the office under the template is the Chairman: 29 U.S.C. 153(a) has the President designate one member of the Board to serve as Chairman, and 5 U.S.C. 5314 places the Chairman of the National Labor Relations Board at Level III; the Board's own statute creates no Director or Administrator",
    },
    "exec-regulatory-fdic-chair-fdic": {
        "nodeName": "Chair, FDIC",
        "statutoryTitle": "Chairman, Board of Directors, Federal Deposit Insurance Corporation",
        "basisCitation": "12 U.S.C. 1812",
        "basisFixture": "fdic_12_usc_1812_govinfo2024.html",
        "basisQuote": "1 of the appointed members shall be designated by the President, by and with the advice and consent of the Senate, to serve as Chairperson of the Board of Directors for a term of 5 years.",
        "basis": "the same office: 12 U.S.C. 1812(b)(1) has one appointed member designated to serve as Chairperson of the Board of Directors, and 5 U.S.C. 5314 places the Chairman of the Board of Directors of the Federal Deposit Insurance Corporation at Level III; the graph spells the title without gender and names the Corporation by its acronym",
    },
    "exec-regulatory-fdic-vice-chair": {
        "nodeName": "Vice Chair",
        "statutoryTitle": "Member, Board of Directors of the Federal Deposit Insurance Corporation",
        "basisCitation": "12 U.S.C. 1812",
        "basisFixture": "fdic_12_usc_1812_govinfo2024.html",
        "basisQuote": "1 of the appointed members shall be designated by the President, by and with the advice and consent of the Senate, to serve as Vice Chairperson of the Board of Directors.",
        "basis": "the Vice Chairperson is an appointed member of the Board: 12 U.S.C. 1812(b)(2) designates one appointed member to serve as Vice Chairperson, 5 U.S.C. 5315 places a Member of the Board of Directors of the Federal Deposit Insurance Corporation at Level IV, and only the Chairman is placed separately (5314)",
    },
    "exec-ind-misc-merit-systems-protection-board-mspb-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "statutoryTitle": "Members, Merit Systems Protection Board",
        "basisCitation": "5 U.S.C. 1203",
        "basisFixture": "mspb_5_usc_1203.html",
        "basisQuote": "The President shall from time to time designate one of the members of the Board as Vice Chairman of the Board.",
        "basis": "the office under the template is the Vice Chairman, a member of the Board: 5 U.S.C. 1203(b) has the President designate one of the members as Vice Chairman, and 5 U.S.C. 5315 places the Members of the Merit Systems Protection Board at Level IV; the Board's statute creates no Deputy Director",
    },
    "exec-ind-misc-national-transportation-safety-board-ntsb-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "statutoryTitle": "Members, National Transportation Safety Board",
        "basisCitation": "49 U.S.C. 1111",
        "basisFixture": "ntsb_49_usc_1111.html",
        "basisQuote": "The President also shall designate a Vice Chairman of the Board.",
        "basis": "the office under the template is the Vice Chairman, a member of the Board: 49 U.S.C. 1111(d) has the President designate a Vice Chairman, and 5 U.S.C. 5315 places the Members of the National Transportation Safety Board at Level IV; the Board's statute creates no Deputy Director",
    },
    "exec-ind-misc-peace-corps-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "statutoryTitle": "Deputy Director of the Peace Corps",
        "basisCitation": "22 U.S.C. 2503",
        "basisFixture": "peacecorps_22_usc_2503.html",
        "basisQuote": "The President may appoint, by and with the advice and consent of the Senate, a Director of the Peace Corps and a Deputy Director of the Peace Corps.",
        "basis": "the office under the template is the Deputy Director: 22 U.S.C. 2503(a) has the President appoint a Director of the Peace Corps and a Deputy Director of the Peace Corps, and 5 U.S.C. 5315 places the Deputy Director of the Peace Corps at Level IV; the Peace Corps has no Vice Chair",
    },
    "exec-ind-misc-u-s-postal-rate-commission-postal-regulatory-commission-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "statutoryTitle": "Members, Postal Regulatory Commission (4)",
        "basisCitation": "39 U.S.C. 502",
        "basisFixture": "prc_39_usc_502.html",
        "basisQuote": "The Commissioners shall by majority vote designate a Vice Chairman of the Commission.",
        "basis": "the office under the template is the Vice Chairman, one of the Commissioners: 39 U.S.C. 502(e) has the Commissioners designate a Vice Chairman from among themselves, and 5 U.S.C. 5315 places the Members of the Postal Regulatory Commission (4) at Level IV, only the Chairman being placed separately (5314); CURATION.md §19.14 declined this post on the ground that the statute designates no Vice Chairman, which the committed section shows to be wrong",
    },
    "exec-ind-misc-federal-labor-relations-authority-flra-general-counsel": {
        "nodeName": "General Counsel",
        "statutoryTitle": "Members, Federal Labor Relations Authority (2) and its General Counsel",
        "basisCitation": "5 U.S.C. 7104",
        "basisFixture": "flra_5_usc_7104.html",
        "basisQuote": "The General Counsel of the Authority shall be appointed by the President, by and with the advice and consent of the Senate, for a term of 5 years.",
        "basis": "the same office: 5 U.S.C. 7104(f)(1) has the President appoint the General Counsel of the Authority, and 5 U.S.C. 5316 places the General Counsel at Level V in one printed item with the Authority's two Members; OPM's current export lists the post at EX V, which agrees",
    },
    "exec-ind-misc-u-s-international-development-finance-corp-dfc-director-administrator-chair-u-s-international-development-finance-corp": {
        "nodeName": "Director / Administrator / Chair, U.S. International Development Finance Corp",
        "statutoryTitle": "Chief Executive Officer, United States International Development Finance Corporation",
        "basisCitation": "22 U.S.C. 9613",
        "basisFixture": "dfc_22_usc_9613_govinfo2024.html",
        "basisQuote": "There shall be in the Corporation a Chief Executive Officer, who shall be appointed by the President, by and with the advice and consent of the Senate, and who shall serve at the pleasure of the President.",
        "basis": "the office under the template is the Chief Executive Officer: 22 U.S.C. 9613(d)(1) puts a Chief Executive Officer in the Corporation, appointed by the President, and 5 U.S.C. 5313 places the Chief Executive Officer of the United States International Development Finance Corporation at Level II; the Corporation's statute creates no Director or Administrator",
    },
    "exec-dept-dhs-cisa-executive-assistant-director-cybersecurity": {
        "nodeName": "Executive Assistant Director — Cybersecurity",
        "statutoryTitle": "Assistant Director for Cybersecurity, Cybersecurity and Infrastructure Security Agency",
        "basisCitation": "6 U.S.C. 653",
        "basisFixture": "cisa_6_usc_653_govinfo2024.html",
        "basisQuote": (
            "Any reference to the Assistant Secretary for Cybersecurity and Communications or Assistant Director "
            "for Cybersecurity in any law, regulation, map, document, record, or other paper of the United States "
            "shall be deemed to be a reference to the Executive Assistant Director for Cybersecurity."
        ),
        "basis": (
            "the same office by the statute's own deeming rule: 6 U.S.C. 653(a)(3) deems any reference to the "
            "Assistant Director for Cybersecurity in any law to be a reference to the Executive Assistant Director "
            "for Cybersecurity, and 5 U.S.C. 5315 -- a law -- places the Assistant Director for Cybersecurity of "
            "the Cybersecurity and Infrastructure Security Agency at Level IV; the same shape as the 6 U.S.C. "
            "652(a) rule TREASURY_ROW_ALIASES already relies on for CISA's Treasury line"
        ),
    },
    "exec-dept-dhs-cisa-executive-assistant-director-infrastructure-security": {
        "nodeName": "Executive Assistant Director — Infrastructure Security",
        "statutoryTitle": "Assistant Director for Infrastructure Security, Cybersecurity and Infrastructure Security Agency",
        "basisCitation": "6 U.S.C. 654",
        "basisFixture": "cisa_6_usc_654_govinfo2024.html",
        "basisQuote": (
            "Any reference to the Assistant Secretary for Infrastructure Protection or Assistant Director for "
            "Infrastructure Security in any law, regulation, map, document, record, or other paper of the United "
            "States shall be deemed to be a reference to the Executive Assistant Director for Infrastructure Security."
        ),
        "basis": (
            "the same office by the statute's own deeming rule: 6 U.S.C. 654(a)(3) deems any reference to the "
            "Assistant Director for Infrastructure Security in any law to be a reference to the Executive Assistant "
            "Director for Infrastructure Security, and 5 U.S.C. 5315 places the Assistant Director for "
            "Infrastructure Security of the Cybersecurity and Infrastructure Security Agency at Level IV"
        ),
    },
    "exec-dept-doj-bop-director-bop": {
        "nodeName": "Director, BOP",
        "statutoryTitle": "Director, Bureau of Prisons, Department of Justice",
        "basisCitation": "18 U.S.C. 4041",
        "basisFixture": "bop_18_usc_4041_govinfo2024.html",
        "basisQuote": "The Bureau of Prisons shall be in charge of a director appointed by and serving directly under the Attorney General.",
        "basis": (
            "the same office: 18 U.S.C. 4041 puts the Bureau of Prisons in charge of a director appointed by and "
            "serving under the Attorney General, and 5 U.S.C. 5315 places the Director of the Bureau of Prisons, "
            "Department of Justice, at Level IV; the graph names the post with the Bureau's acronym, which the "
            "scoped route refuses because the office half is the bare word Director"
        ),
    },
    "exec-dept-dhs-fema-deputy-administrator": {
        "nodeName": "Deputy Administrator",
        "statutoryTitle": "Deputy Administrators, Federal Emergency Management Agency",
        "basisCitation": "6 U.S.C. 321c",
        "basisFixture": "fema_6_usc_321c_govinfo2024.html",
        "basisQuote": (
            "The President may appoint, by and with the advice and consent of the Senate, not more than 4 Deputy "
            "Administrators to assist the Administrator in carrying out this subchapter."
        ),
        "basis": (
            "a Deputy Administrator is one of the Deputy Administrators: 6 U.S.C. 321c(a) lets the President "
            "appoint not more than four Deputy Administrators of the Federal Emergency Management Agency, and "
            "5 U.S.C. 5314 places the Deputy Administrators of the Agency at Level III as a class, the way it places "
            "the Members of the Federal Reserve Board whose Vice Chairs this table already prices one node at a time; "
            "this node is the Agency's one Deputy Administrator so named, and the current PLUM export lists two PAS "
            "rows at EX III under the title"
        ),
    },
    "exec-eop-ondcp-deputy-director": {
        "nodeName": "Deputy Director",
        "statutoryTitle": "Deputy Director of National Drug Control Policy",
        "basisCitation": "21 U.S.C. 1703",
        "basisFixture": "ondcp_21_usc_1703.html",
        "basisQuote": (
            "There shall be a Deputy Director who shall report directly to the Director, and who shall be "
            "appointed by the President, and shall serve at the pleasure of the President."
        ),
        "basis": (
            "the same office: 21 U.S.C. 1703(a)(1)(B) creates one Deputy Director of the Office of National "
            "Drug Control Policy, reporting to the Director the same section puts at the head of the Office, "
            "and 5 U.S.C. 5313 places the Deputy Director of National Drug Control Policy at Level II; the "
            "graph names the post by its bare title under the Office"
        ),
    },
    "exec-eop-ostp-director-presidential-science-advisor": {
        "nodeName": "Director (Presidential Science Advisor)",
        "statutoryTitle": "Director of the Office of Science and Technology",
        "basisCitation": "42 U.S.C. 6612",
        "basisFixture": "ostp_42_usc_6612_govinfo2024.html",
        "basisQuote": (
            "There shall be at the head of the Office a Director who shall be appointed by the President, by "
            "and with the advice and consent of the Senate, and who shall be compensated at the rate provided "
            "for level II of the Executive Schedule in section 5313 of title 5."
        ),
        "basis": (
            "the same office: 42 U.S.C. 6612(a) puts a Director at the head of the Office of Science and "
            "Technology Policy and itself pays that Director at level II of the Executive Schedule, the level "
            "5 U.S.C. 5313 prints for 'Director of the Office of Science and Technology' -- the office's "
            "name as styled before Pub. L. 94-282 (1976) created the present Office; the graph names the post "
            "by its title with the informal label in brackets"
        ),
    },
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
    "exec-regulatory-fcc-chair-fcc": {
        "nodeName": "Chair, FCC",
        "statutoryTitle": "Chairman, Federal Communications Commission",
        "basisCitation": "47 U.S.C. 154",
        "basisFixture": "fcc_47_usc_154.html",
        "basisQuote": (
            "The Chairman of the Commission, during the period of his service as Chairman, shall receive an annual salary at the annual rate payable from time to time for level III of the Executive Schedule."
        ),
        "basis": (
            "the same office: 47 U.S.C. 154 itself pays the Chairman of the Commission at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for 'Chairman, Federal Communications Commission'; the graph spells the title without gender and names the Commission by its acronym"
        ),
    },
    "exec-regulatory-ftc-chair-ftc": {
        "nodeName": "Chair, FTC",
        "statutoryTitle": "Chairman, Federal Trade Commission",
        "basisCitation": "15 U.S.C. 41",
        "basisFixture": "ftc_15_usc_41.html",
        "basisQuote": (
            "The President shall choose a chairman from the Commission's membership."
        ),
        "basis": (
            "the same office: 15 U.S.C. 41 has the President choose a chairman from the Commission's membership, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym"
        ),
    },
    "exec-dept-treasury-irs-commissioner-irs": {
        "nodeName": "Commissioner, IRS",
        "statutoryTitle": "Commissioner of Internal Revenue",
        "basisCitation": "26 U.S.C. 7803",
        "basisFixture": "irs_26_usc_7803.html",
        "basisQuote": (
            "There shall be in the Department of the Treasury a Commissioner of Internal Revenue who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 26 U.S.C. 7803 creates the Commissioner of Internal Revenue in the Department of the Treasury, and 5 U.S.C. 5314 places that Commissioner at Level III; the graph files the post under the Internal Revenue Service and names it by the Service's acronym"
        ),
    },
    # The twelfth batch's judiciary cluster (2026-10-06): the IRS's Chief
    # Counsel. "Chief Counsel" is a stamped title this graph carries under nine
    # bureaus, so the row is keyed to the Internal Revenue Service's node alone;
    # the Tax Court subtree's "Chief Counsel — IRS (opposing)" is the same
    # office drawn a second time where it litigates and is NOT priced.
    "exec-dept-treasury-irs-chief-counsel": {
        "nodeName": "Chief Counsel",
        "statutoryTitle": "Chief Counsel for the Internal Revenue Service, Department of the Treasury",
        "basisCitation": "26 U.S.C. 7803",
        "basisFixture": "irs_26_usc_7803.html",
        "basisQuote": (
            "There shall be in the Department of the Treasury a Chief Counsel for the Internal Revenue Service who shall be appointed by the President, by and with the consent of the Senate."
        ),
        "basis": (
            "the same office: 26 U.S.C. 7803(b)(1) creates the Chief Counsel for the Internal Revenue Service in the Department of the Treasury, and 5 U.S.C. 5316 places the Chief Counsel for the Internal Revenue Service, Department of the Treasury at Level V; the graph files the post under the Internal Revenue Service under the bare title 'Chief Counsel', a stamped title nine bureaus carry here, so the row is keyed to the Service's node alone"
        ),
    },
    "exec-dept-dot-faa-administrator-faa": {
        "nodeName": "Administrator, FAA",
        "statutoryTitle": "Administrator, Federal Aviation Administration",
        "basisCitation": "49 U.S.C. 106",
        "basisFixture": "faa_49_usc_106.html",
        "basisQuote": (
            "The head of the Administration is the Administrator, who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 49 U.S.C. 106 makes the Administrator the head of the Federal Aviation Administration, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dhs-secretary-of-department-of-homeland-security-dhs": {
        "nodeName": "Secretary of the Department of Homeland Security",
        "statutoryTitle": "Secretary of Homeland Security",
        "basisCitation": "6 U.S.C. 112",
        "basisFixture": "dhs_6_usc_112.html",
        "basisQuote": (
            "There is a Secretary of Homeland Security, appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 6 U.S.C. 112 creates the Secretary of Homeland Security, and 5 U.S.C. 5312 places that Secretary at Level I; the graph keeps OPM's archive spelling 'Secretary of the Department of Homeland Security' (CURATION.md §8), which whole-name equality cannot reach"
        ),
    },
    "exec-dept-dhs-deputy-secretary-of-department-of-homeland-security-dhs": {
        "nodeName": "Deputy Secretary of the Department of Homeland Security",
        "statutoryTitle": "Deputy Secretary of Homeland Security",
        "basisCitation": "6 U.S.C. 113",
        "basisFixture": "dhs_6_usc_113.html",
        "basisQuote": (
            "A Deputy Secretary of Homeland Security, who shall be the Secretary's first assistant for purposes of subchapter III of chapter 33 of title 5 ."
        ),
        "basis": (
            "the same office: 6 U.S.C. 113 provides for a Deputy Secretary of Homeland Security as the Secretary's first assistant, and 5 U.S.C. 5313 places that Deputy Secretary at Level II; the graph keeps OPM's archive spelling 'Deputy Secretary of the Department of Homeland Security' (CURATION.md §8), which whole-name equality cannot reach"
        ),
    },
    "exec-regulatory-fcc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Federal Communications Commission",
        "basisCitation": "47 U.S.C. 154",
        "basisFixture": "fcc_47_usc_154.html",
        "basisQuote": (
            "shall be composed of five commissioners appointed by the President, by and with the advice and consent of the Senate, one of whom the President shall designate as chairman"
        ),
        "basis": (
            "a bench priced from its class title: 47 U.S.C. 154 composes the Commission of five commissioners, one of whom is designated chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Communications Commission' at Level IV; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-regulatory-ftc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Federal Trade Commission",
        "basisCitation": "15 U.S.C. 41",
        "basisFixture": "ftc_15_usc_41.html",
        "basisQuote": (
            "which shall be composed of five Commissioners, who shall be appointed by the President, by and with the advice and consent of the Senate"
        ),
        "basis": (
            "a bench priced from its class title: 15 U.S.C. 41 composes the Commission of five Commissioners and has the President choose a chairman from among them, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Trade Commission' at Level IV; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-regulatory-fed-governor-4-members": {
        "nodeName": "Governor (×4 members)",
        "statutoryTitle": "Members, Board of Governors of the Federal Reserve System",
        "basisCitation": "12 U.S.C. 241",
        "basisFixture": "fed_12_usc_241.html",
        "basisQuote": (
            "shall be composed of seven members, to be appointed by the President, by and with the advice and consent of the Senate"
        ),
        "basis": (
            "a bench priced from its class title: 12 U.S.C. 241 composes the Board of seven members, of whom 12 U.S.C. 242 designates a Chairman and two Vice Chairmen, so a Governor is one of the four members holding no designated office, and 5 U.S.C. 5313 places 'Members, Board of Governors of the Federal Reserve System' at Level II; the level is the office's and holds for each alike (the '$15,000 per annum' 12 U.S.C. 241 itself prints is the 1935 figure the Executive Schedule superseded, and nothing here publishes it)"
        ),
        "classTitle": True,
    },
    "exec-regulatory-cftc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Commodity Futures Trading Commission",
        "basisCitation": "7 U.S.C. 2",
        "basisFixture": "cftc_7_usc_2.html",
        "basisQuote": (
            "The Commission shall be composed of five Commissioners who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "a bench priced from its class title: 7 U.S.C. 2 composes the Commission of five Commissioners and has the President appoint one of them as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Commodity Futures Trading Commission' at Level IV; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-regulatory-ferc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Federal Energy Regulatory Commission",
        "basisCitation": "42 U.S.C. 7171",
        "basisFixture": "ferc_42_usc_7171.html",
        "basisQuote": (
            "The Commission shall be composed of five members appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "a bench priced from its class title: 42 U.S.C. 7171 composes the Commission of five members and has the President designate one as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Energy Regulatory Commission' at Level IV; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-regulatory-cftc-chair-cftc": {
        "nodeName": "Chair, CFTC",
        "statutoryTitle": "Chairman, Commodity Futures Trading Commission",
        "basisCitation": "7 U.S.C. 2",
        "basisFixture": "cftc_7_usc_2.html",
        "basisQuote": (
            "The President shall appoint, by and with the advice and consent of the Senate, a member of the Commission as Chairman, who shall serve as Chairman at the pleasure of the President."
        ),
        "basis": (
            "the same office: 7 U.S.C. 2 has the President appoint a member of the Commission as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym"
        ),
    },
    "exec-regulatory-ferc-chair-ferc": {
        "nodeName": "Chair, FERC",
        "statutoryTitle": "Chairman, Federal Energy Regulatory Commission",
        "basisCitation": "42 U.S.C. 7171",
        "basisFixture": "ferc_42_usc_7171.html",
        "basisQuote": (
            "One of the members shall be designated by the President as Chairman."
        ),
        "basis": (
            "the same office: 42 U.S.C. 7171 has the President designate one member of the Commission as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym"
        ),
    },
    "exec-ind-opm-director-opm": {
        "nodeName": "Director, OPM",
        "statutoryTitle": "Director of the Office of Personnel Management",
        "basisCitation": "5 U.S.C. 1102",
        "basisFixture": "opm_5_usc_1102.html",
        "basisQuote": (
            "There is at the head of the Office of Personnel Management a Director of the Office of Personnel Management appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 5 U.S.C. 1102 puts a Director of the Office of Personnel Management at the head of the Office, and 5 U.S.C. 5313 places that Director at Level II; the graph names the Office by its acronym"
        ),
    },
    "exec-ind-ssa-commissioner-ssa": {
        "nodeName": "Commissioner, SSA",
        "statutoryTitle": "Commissioner of Social Security, Social Security Administration",
        "basisCitation": "42 U.S.C. 902",
        "basisFixture": "ssa_42_usc_902.html",
        "basisQuote": (
            "There shall be in the Administration a Commissioner of Social Security"
        ),
        "basis": (
            "the same office: 42 U.S.C. 902 creates in the Social Security Administration a Commissioner of Social Security, and 5 U.S.C. 5312 places that Commissioner at Level I; the graph names the Administration by its acronym"
        ),
    },
    "exec-ind-ssa-deputy-commissioner-ssa": {
        "nodeName": "Deputy Commissioner, SSA",
        "statutoryTitle": "Deputy Commissioner of Social Security, Social Security Administration",
        "basisCitation": "42 U.S.C. 902",
        "basisFixture": "ssa_42_usc_902.html",
        "basisQuote": (
            "The Deputy Commissioner shall be compensated at the rate provided for level II of the Executive Schedule."
        ),
        "basis": (
            "the same office: 42 U.S.C. 902 creates in the Social Security Administration a Deputy Commissioner of Social Security and itself compensates that office at level II of the Executive Schedule, the level 5 U.S.C. 5313 prints for it; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dhs-fema-administrator-fema": {
        "nodeName": "Administrator, FEMA",
        "statutoryTitle": "Administrator of the Federal Emergency Management Agency",
        "basisCitation": "6 U.S.C. 313",
        "basisFixture": "fema_6_usc_313.html",
        "basisQuote": (
            "There is in the Department the Federal Emergency Management Agency, headed by an Administrator."
        ),
        "basis": (
            "the same office: 6 U.S.C. 313 places the Federal Emergency Management Agency in the Department of Homeland Security headed by an Administrator, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Agency by its acronym"
        ),
    },
    "exec-dept-doi-blm-director-blm": {
        "nodeName": "Director, BLM",
        "statutoryTitle": "Director, Bureau of Land Management, Department of the Interior",
        "basisCitation": "43 U.S.C. 1731",
        "basisFixture": "blm_43_usc_1731.html",
        "basisQuote": (
            "The Bureau of Land Management established by Reorganization Plan Numbered 3, of 1946 shall have as its head a Director."
        ),
        "basis": (
            "the same office: 43 U.S.C. 1731 gives the Bureau of Land Management a Director as its head, and 5 U.S.C. 5316 places that Director at Level V; the graph names the Bureau by its acronym"
        ),
    },
    "exec-ind-cia-director-of-the-cia-dcia": {
        "nodeName": "Director of the CIA (DCIA)",
        "statutoryTitle": "Director of the Central Intelligence Agency",
        "basisCitation": "50 U.S.C. 3036",
        "basisFixture": "cia_50_usc_3036.html",
        "basisQuote": (
            "There is a Director of the Central Intelligence Agency who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 50 U.S.C. 3036 creates the Director of the Central Intelligence Agency as head of the Agency, and 5 U.S.C. 5313 places that Director at Level II; the graph names the Agency by its acronym"
        ),
    },
    "exec-ind-cia-deputy-director-of-the-cia-ddcia": {
        "nodeName": "Deputy Director of the CIA (DDCIA)",
        "statutoryTitle": "Deputy Director of the Central Intelligence Agency",
        "basisCitation": "50 U.S.C. 3037",
        "basisFixture": "cia_50_usc_3037.html",
        "basisQuote": (
            "There is a Deputy Director of the Central Intelligence Agency who shall be appointed by the President"
        ),
        "basis": (
            "the same office: 50 U.S.C. 3037 creates the Deputy Director of the Central Intelligence Agency, and 5 U.S.C. 5314 places that Deputy Director at Level III; the graph names the Agency by its acronym"
        ),
    },
    "exec-dept-hhs-cms-administrator-cms": {
        "nodeName": "Administrator, CMS",
        "statutoryTitle": "Administrator of the Centers for Medicare & Medicaid Services",
        "basisCitation": "42 U.S.C. 1317",
        "basisFixture": "cms_42_usc_1317.html",
        "basisQuote": (
            "The Administrator of the Centers for Medicare & Medicaid Services shall be appointed by the President by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 42 U.S.C. 1317 provides for the appointment of the Administrator of the Centers for Medicare & Medicaid Services, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Centers by their acronym"
        ),
    },
    "exec-dept-doc-nist-director-nist": {
        "nodeName": "Director, NIST",
        "statutoryTitle": "Under Secretary of Commerce for Standards and Technology, who also serves as Director of the National Institute of Standards and Technology",
        "basisCitation": "15 U.S.C. 273a",
        "basisFixture": "nist_15_usc_273a.html",
        "basisQuote": (
            "The Under Secretary shall serve as the Director of the Institute and shall perform such duties as required of the Director by the Secretary under this chapter or by law."
        ),
        "basis": (
            "the same office: 15 U.S.C. 273a creates in the Department of Commerce an Under Secretary of Commerce for Standards and Technology who shall serve as the Director of the Institute, and itself compensates that office at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for the joint title; the graph names the post by the Director half of that title and the Institute by its acronym"
        ),
    },
    "exec-regulatory-nrc-chair-nrc": {
        "nodeName": "Chair, NRC",
        "statutoryTitle": "Chairman, Nuclear Regulatory Commission",
        "basisCitation": "42 U.S.C. 5841",
        "basisFixture": "nrc_42_usc_5841.html",
        "basisQuote": (
            "The President shall designate one member of the Commission as Chairman thereof to serve as such during the pleasure of the President."
        ),
        "basis": (
            "the same office: 42 U.S.C. 5841 establishes the Nuclear Regulatory Commission of five members and has the President designate one of them as Chairman, and 5 U.S.C. 5313 places that Chairman at Level II; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym"
        ),
    },
    "exec-regulatory-nrc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Nuclear Regulatory Commission",
        "basisCitation": "42 U.S.C. 5841",
        "basisFixture": "nrc_42_usc_5841.html",
        "basisQuote": (
            "There is established an independent regulatory commission to be known as the Nuclear Regulatory Commission which shall be composed of five members, each of whom shall be a citizen of the United States."
        ),
        "basis": (
            "a bench priced from its class title: 42 U.S.C. 5841 composes the Nuclear Regulatory Commission of five members, one of whom the President designates as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5314 places 'Members, Nuclear Regulatory Commission' at Level III; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-ind-sba-administrator-sba": {
        "nodeName": "Administrator, SBA",
        "statutoryTitle": "Administrator of the Small Business Administration",
        "basisCitation": "15 U.S.C. 633",
        "basisFixture": "sba_15_usc_633.html",
        "basisQuote": (
            "The management of the Administration shall be vested in an Administrator who shall be appointed from civilian life by the President, by and with the advice and consent of the Senate,"
        ),
        "basis": (
            "the same office: 15 U.S.C. 633 vests the management of the Small Business Administration in an Administrator appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym"
        ),
    },
    "exec-ind-nsf-director-nsf": {
        "nodeName": "Director, NSF",
        "statutoryTitle": "Director of the National Science Foundation",
        "basisCitation": "42 U.S.C. 1864",
        "basisFixture": "nsf_42_usc_1864.html",
        "basisQuote": (
            "The Director shall receive basic pay at the rate provided for level II of the Executive Schedule under section 5313 of title 5"
        ),
        "basis": (
            "the same office: 42 U.S.C. 1864 provides for the Director of the Foundation, appointed by the President with the Senate's consent, and itself sets that Director's basic pay at level II of the Executive Schedule, the level 5 U.S.C. 5313 prints for it; the graph names the Foundation by its acronym"
        ),
    },
    "exec-ind-nsf-deputy-director-nsf": {
        "nodeName": "Deputy Director, NSF",
        "statutoryTitle": "Deputy Director, National Science Foundation",
        "basisCitation": "42 U.S.C. 1864a",
        "basisFixture": "nsf_42_usc_1864a.html",
        "basisQuote": (
            "The Deputy Director shall receive basic pay at the rate provided for level III of the Executive Schedule under section 5314 of title 5"
        ),
        "basis": (
            "the same office: 42 U.S.C. 1864a provides for a Deputy Director of the Foundation, appointed by the President with the Senate's consent, and itself sets that Deputy Director's basic pay at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for it; the graph names the Foundation by its acronym"
        ),
    },
    "exec-eop-ondcp-director-drug-czar": {
        "nodeName": "Director (Drug Czar)",
        "statutoryTitle": "Director of National Drug Control Policy",
        "basisCitation": "21 U.S.C. 1703",
        "basisFixture": "ondcp_21_usc_1703.html",
        "basisQuote": (
            "There shall be at the head of the Office a Director who shall hold the same rank and status as the head of an executive department listed in section 101 of title 5"
        ),
        "basis": (
            "the same office: 21 U.S.C. 1703 puts a Director at the head of the Office of National Drug Control Policy, the Office 21 U.S.C. 1702 establishes in the Executive Office of the President and the node above this one, and 5 U.S.C. 5312 places the Director of National Drug Control Policy at Level I; the graph names the post by its informal label in brackets"
        ),
    },
    "exec-dept-dol-bls-commissioner-bls": {
        "nodeName": "Commissioner, BLS",
        "statutoryTitle": "The 2 Commissioner of Labor Statistics, Department of Labor",
        "basisCitation": "29 U.S.C. 3",
        "basisFixture": "bls_29_usc_3.html",
        "basisQuote": (
            "The Bureau of Labor Statistics shall be under the charge of a Commissioner of Labor Statistics, who shall be appointed by the President, by and with the advice and consent of the Senate;"
        ),
        "basis": (
            "the same office: 29 U.S.C. 3 puts the Bureau of Labor Statistics under the charge of a Commissioner of Labor Statistics appointed by the President with the Senate's consent, and 5 U.S.C. 5315 places that Commissioner at Level IV, printing the title with a leading 'The' and the footnote mark '2' (the Code's own note: the word 'The' probably should not appear), which the index keeps as printed; the graph names the Bureau by its acronym"
        ),
    },
    "exec-dept-doc-census-director-census-bureau": {
        "nodeName": "Director, Census Bureau",
        "statutoryTitle": "Director, Bureau of the Census, Department of Commerce",
        "basisCitation": "13 U.S.C. 21",
        "basisFixture": "census_13_usc_21.html",
        "basisQuote": (
            "The Bureau shall be headed by a Director of the Census, appointed by the President, by and with the advice and consent of the Senate, without regard to political affiliation."
        ),
        "basis": (
            "the same office: 13 U.S.C. 21 puts a Director of the Census at the head of the Bureau, appointed by the President with the Senate's consent, and 5 U.S.C. 5315 places the Director of the Bureau of the Census at Level IV; the graph writes 'Census Bureau' where the Code writes 'Bureau of the Census'"
        ),
    },
    "exec-eop-cea-chair-cea": {
        "nodeName": "Chair, CEA",
        "statutoryTitle": "Chairman, Council of Economic Advisers",
        "basisCitation": "15 U.S.C. 1023",
        "basisFixture": "cea_15_usc_1023.html",
        "basisQuote": (
            "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President."
        ),
        "basis": (
            "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, one of whom is the chairman appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Chairman at Level II; the graph writes 'Chair' where the Code writes 'Chairman' and names the Council by its acronym"
        ),
    },
    "exec-eop-cea-member-cea": {
        "nodeName": "Member, CEA",
        "statutoryTitle": "Members, Council of Economic Advisers",
        "basisCitation": "15 U.S.C. 1023",
        "basisFixture": "cea_15_usc_1023.html",
        "basisQuote": (
            "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President."
        ),
        "basis": (
            "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, two of them appointed by the President beside the chairman, and 5 U.S.C. 5315 places 'Members, Council of Economic Advisers' at Level IV, the office each of the two holds; this graph draws the two as one node each, and the Code names the office once for both"
        ),
    },
    "exec-eop-cea-member-cea-1": {
        "nodeName": "Member, CEA",
        "statutoryTitle": "Members, Council of Economic Advisers",
        "basisCitation": "15 U.S.C. 1023",
        "basisFixture": "cea_15_usc_1023.html",
        "basisQuote": (
            "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President."
        ),
        "basis": (
            "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, two of them appointed by the President beside the chairman, and 5 U.S.C. 5315 places 'Members, Council of Economic Advisers' at Level IV, the office each of the two holds; this graph draws the two as one node each, and the Code names the office once for both"
        ),
    },
    "exec-regulatory-cpsc-chair-cpsc": {
        "nodeName": "Chair, CPSC",
        "statutoryTitle": "Chairman, Consumer Product Safety Commission",
        "basisCitation": "15 U.S.C. 2053",
        "basisFixture": "cpsc_15_usc_2053.html",
        "basisQuote": (
            "The Chairman shall be appointed by the President, by and with the advice and consent of the Senate, from among the members of the Commission."
        ),
        "basis": (
            "the same office: 15 U.S.C. 2053 establishes the Consumer Product Safety Commission of five Commissioners and has the President appoint the Chairman from among them, and 5 U.S.C. 5314 places that Chairman at Level III; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym"
        ),
    },
    "exec-dept-dot-fhwa-administrator-fhwa": {
        "nodeName": "Administrator, FHWA",
        "statutoryTitle": "Administrator, Federal Highway Administration",
        "basisCitation": "49 U.S.C. 104",
        "basisFixture": "fhwa_49_usc_104.html",
        "basisQuote": (
            "The head of the Administration is the Administrator who is appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 49 U.S.C. 104 makes the Administrator the head of the Federal Highway Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym"
        ),
    },
    # --- 2026-10-06, the twelfth batch's remaining-departments cluster: four
    # --- Transportation posts the Schedule prints and no route reached. The
    # --- NHTSA rows' section was read from govinfo's 2024 edition; the FHWA
    # --- Deputy's from the section already committed for its Administrator.
    "exec-dept-dot-nhtsa-administrator-nhtsa": {
        "nodeName": "Administrator, NHTSA",
        "statutoryTitle": "Administrator of the National Highway Traffic Safety Administration",
        "basisCitation": "49 U.S.C. 105",
        "basisFixture": "nhtsa_49_usc_105_govinfo2024.html",
        "basisQuote": (
            "The head of the Administration is the Administrator who is appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 49 U.S.C. 105(b) makes the Administrator the head of the National Highway Traffic Safety Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dot-nhtsa-deputy-administrator": {
        "nodeName": "Deputy Administrator",
        "statutoryTitle": "Deputy Administrator of the National Highway Traffic Safety Administration",
        "basisCitation": "49 U.S.C. 105",
        "basisFixture": "nhtsa_49_usc_105_govinfo2024.html",
        "basisQuote": (
            "The Administration has a Deputy Administrator who is appointed by the Secretary of Transportation, with the approval of the President."
        ),
        "basis": (
            "the same office: 49 U.S.C. 105(b) gives the National Highway Traffic Safety Administration one Deputy Administrator, appointed by the Secretary with the President's approval, and 5 U.S.C. 5316 places that Deputy Administrator at Level V; the graph names the post bare under the Administration's own node, and a row is keyed by id"
        ),
    },
    "exec-dept-dot-fmcsa-deputy-administrator": {
        "nodeName": "Deputy Administrator",
        "statutoryTitle": "Deputy Administrator of the Federal Motor Carrier Safety Administration",
        "basisCitation": "49 U.S.C. 113",
        "basisFixture": "fmcsa_49_usc_113_govinfo2024.html",
        "basisQuote": (
            "The Administration shall have a Deputy Administrator appointed by the Secretary, with the approval of the President."
        ),
        "basis": (
            "the same office: 49 U.S.C. 113(d) gives the Federal Motor Carrier Safety Administration one Deputy Administrator, appointed by the Secretary with the President's approval, and 5 U.S.C. 5316 places that Deputy Administrator at Level V; the graph names the post bare under the Administration's own node, and a row is keyed by id"
        ),
    },
    "exec-dept-dot-fhwa-deputy-administrator": {
        "nodeName": "Deputy Administrator",
        "statutoryTitle": "Deputy Federal Highway Administrator",
        "basisCitation": "49 U.S.C. 104",
        "basisFixture": "fhwa_49_usc_104.html",
        "basisQuote": (
            "The Administration has a Deputy Federal Highway Administrator who is appointed by the Secretary, with the approval of the President."
        ),
        "basis": (
            "the same office: 49 U.S.C. 104(b)(2) gives the Federal Highway Administration one Deputy Federal Highway Administrator, appointed by the Secretary with the President's approval, and 5 U.S.C. 5315 places that officer at Level IV; the graph names the post bare 'Deputy Administrator' under the Administration's own node, and a row is keyed by id"
        ),
    },
    # --- 2026-10-06, the twelfth batch's health cluster: the Commissioner of
    # --- Food and Drugs. §5315 prints the title with a footnote mark standing
    # --- where its full stop should be ("So in original. Probably should be
    # --- followed by a period."), which kept it out of the index until the
    # --- parser learned to read a closing mark the same day. The basis
    # --- section was read from govinfo's 2024 edition (the OLRC host was under
    # --- maintenance). The current PLUM export lists the title at EX-IV under
    # --- the Administration, but no listing reaches the node, which the graph
    # --- names "Commissioner, FDA"; the row is the node's only pay claim.
    "exec-dept-hhs-fda-commissioner-fda": {
        "nodeName": "Commissioner, FDA",
        "statutoryTitle": "Commissioner of Food and Drugs, Department of Health and Human Services",
        "basisCitation": "21 U.S.C. 393",
        "basisFixture": "fda_21_usc_393_govinfo2024.html",
        "basisQuote": (
            'There shall be in the Administration a Commissioner of Food and Drugs (hereinafter in this section referred to as the "Commissioner") who shall be appointed by the President by and with the advice and consent of the Senate.'
        ),
        "basis": (
            "the same office: 21 U.S.C. 393(d)(1) creates in the Food and Drug Administration a Commissioner of Food and Drugs appointed by the President with the Senate's advice and consent, and 5 U.S.C. 5315 places the Commissioner of Food and Drugs, Department of Health and Human Services at Level IV, printing the title with a footnote mark standing where its full stop should be (the Code's own note: 'So in original. Probably should be followed by a period.'); the graph names the post with the Administration's acronym"
        ),
    },
    "exec-dept-doc-uspto-director-under-secretary-for-ip": {
        "nodeName": "Director / Under Secretary for IP",
        "statutoryTitle": "Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office",
        "basisCitation": "35 U.S.C. 3",
        "basisFixture": "uspto_35_usc_3.html",
        "basisQuote": (
            "The powers and duties of the United States Patent and Trademark Office shall be vested in an Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office (in this title referred to as the \"Director\"), who shall be a citizen of the United States and who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 35 U.S.C. 3 vests the Office's powers and duties in one officer holding the joint title Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office, and 5 U.S.C. 5314 places that joint title at Level III; the graph writes the two halves as 'Director / Under Secretary for IP'"
        ),
    },
    "exec-dept-doi-bor-commissioner-bor": {
        "nodeName": "Commissioner, BOR",
        "statutoryTitle": "Commissioner of Reclamation, Department of the Interior",
        "basisCitation": "43 U.S.C. 373a",
        "basisFixture": "bor_43_usc_373a.html",
        "basisQuote": (
            "shall be administered by a Commissioner of Reclamation who shall be appointed by the President by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 43 U.S.C. 373a puts the reclamation of arid lands under a Commissioner of Reclamation in the Department of the Interior, appointed by the President with the Senate's consent, and 5 U.S.C. 5316 places that Commissioner at Level V; the graph names the Bureau of Reclamation by its acronym"
        ),
    },
    "leg-support-loc-copyright-register-of-copyrights-director": {
        "nodeName": "Register of Copyrights & Director",
        "statutoryTitle": "Register of Copyrights",
        "basisCitation": "17 U.S.C. 701",
        "basisFixture": "copyright_17_usc_701.html",
        "basisQuote": (
            "All administrative functions and duties under this title, except as otherwise specified, are the responsibility of the Register of Copyrights as director of the Copyright Office of the Library of Congress."
        ),
        "basis": (
            "the same office: 17 U.S.C. 701 makes the Register of Copyrights the director of the Copyright Office of the Library of Congress, and 5 U.S.C. 5314 places the Register of Copyrights at Level III; the graph's '& Director' is the Office's own styling of that one post"
        ),
    },
    "exec-ind-nasa-administrator-nasa": {
        "nodeName": "Administrator, NASA",
        "statutoryTitle": "Administrator of the National Aeronautics and Space Administration",
        "basisCitation": "51 U.S.C. 20111",
        "basisFixture": "nasa_51_usc_20111.html",
        "basisQuote": (
            "The Administration shall be headed by an Administrator, who shall be appointed from civilian life by the President by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 51 U.S.C. 20111 puts an Administrator at the head of the National Aeronautics and Space Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dot-fta-administrator-fta": {
        "nodeName": "Administrator, FTA",
        "statutoryTitle": "Federal Transit Administrator",
        "basisCitation": "49 U.S.C. 107",
        "basisFixture": "fta_49_usc_107.html",
        "basisQuote": (
            "The head of the Administration is the Administrator who is appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 49 U.S.C. 107 makes the Administrator the head of the Federal Transit Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places the Federal Transit Administrator at Level II; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dot-fra-administrator-fra": {
        "nodeName": "Administrator, FRA",
        "statutoryTitle": "Administrator, Federal Railroad Administration",
        "basisCitation": "49 U.S.C. 103",
        "basisFixture": "fra_49_usc_103.html",
        "basisQuote": (
            "The head of the Administration shall be the Administrator who shall be appointed by the President, by and with the advice and consent of the Senate,"
        ),
        "basis": (
            "the same office: 49 U.S.C. 103 makes the Administrator the head of the Federal Railroad Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dot-marad-administrator-marad": {
        "nodeName": "Administrator, MARAD",
        "statutoryTitle": "Administrator, Maritime Administration",
        "basisCitation": "49 U.S.C. 109",
        "basisFixture": "marad_49_usc_109.html",
        "basisQuote": (
            "The head of the Maritime Administration is the Maritime Administrator, who is appointed by the President by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 49 U.S.C. 109 makes the Maritime Administrator the head of the Maritime Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym"
        ),
    },
    "exec-dept-dol-msha-assistant-secretary-of-labor-for-mine-safety": {
        "nodeName": "Assistant Secretary of Labor for Mine Safety",
        "statutoryTitle": "Assistant Secretary of Labor for Mine Safety and Health",
        "basisCitation": "29 U.S.C. 557a",
        "basisFixture": "msha_29_usc_557a.html",
        "basisQuote": (
            "There is established in the Department of Labor a Mine Safety and Health Administration to be headed by an Assistant Secretary of Labor for Mine Safety and Health appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 29 U.S.C. 557a puts the Mine Safety and Health Administration under an Assistant Secretary of Labor for Mine Safety and Health, and 5 U.S.C. 5315 places that Assistant Secretary at Level IV; the graph's name drops the words 'and Health'"
        ),
    },
    "exec-dept-treasury-ofr-director-ofr": {
        "nodeName": "Director, OFR",
        "statutoryTitle": "Director of the Office of Financial Research",
        "basisCitation": "12 U.S.C. 5342",
        "basisFixture": "ofr_12_usc_5342.html",
        "basisQuote": (
            "The Office shall be headed by a Director, who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 12 U.S.C. 5342 puts a Director at the head of the Office of Financial Research in the Department of the Treasury and itself compensates that Director at Level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for it; the graph names the Office by its acronym"
        ),
    },
    "exec-regulatory-fmc-chair-fmc": {
        "nodeName": "Chair, FMC",
        "statutoryTitle": "Chairman, Federal Maritime Commission",
        "basisCitation": "46 U.S.C. 46101",
        "basisFixture": "fmc_46_usc_46101.html",
        "basisQuote": (
            "The President shall designate one of the Commissioners as Chairman."
        ),
        "basis": (
            "the same office: 46 U.S.C. 46101 composes the Federal Maritime Commission of five Commissioners and has the President designate one of them as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym"
        ),
    },
    "exec-regulatory-fmc-commissioner-4": {
        "nodeName": "Commissioner (×4)",
        "statutoryTitle": "Members, Federal Maritime Commission",
        "basisCitation": "46 U.S.C. 46101",
        "basisFixture": "fmc_46_usc_46101.html",
        "basisQuote": (
            "The Commission is composed of 5 Commissioners, appointed by the President by and with the advice and consent of the Senate."
        ),
        "basis": (
            "a bench priced from its class title: 46 U.S.C. 46101 composes the Federal Maritime Commission of five Commissioners, one of whom the President designates as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Maritime Commission' at Level IV; the level is the office's and holds for each of the four alike"
        ),
        "classTitle": True,
    },
    "exec-ind-misc-merit-systems-protection-board-mspb-director-administrator-chair-merit-systems-protection-board": {
        "nodeName": "Director / Administrator / Chair, Merit Systems Protection Board",
        "statutoryTitle": "Chairman of the Merit Systems Protection Board",
        "basisCitation": "5 U.S.C. 1203",
        "basisFixture": "mspb_5_usc_1203.html",
        "basisQuote": (
            "The President shall from time to time appoint, by and with the advice and consent of the Senate, one of the members of the Merit Systems Protection Board as the Chairman of the Board."
        ),
        "basis": (
            "the same office: 5 U.S.C. 1203 has the President appoint one member of the Merit Systems Protection Board as its Chairman, the Board's chief executive and administrative officer, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for"
        ),
    },
    "exec-ind-misc-national-credit-union-administration-ncua-director-administrator-chair-national-credit-union-administration": {
        "nodeName": "Director / Administrator / Chair, National Credit Union Administration",
        "statutoryTitle": "Chairman, National Credit Union Administration Board",
        "basisCitation": "12 U.S.C. 1752a",
        "basisFixture": "ncua_12_usc_1752a.html",
        "basisQuote": (
            "In appointing the members of the Board, the President shall designate the Chairman."
        ),
        "basis": (
            "the same office: 12 U.S.C. 1752a puts the National Credit Union Administration under the management of a three-member Board whose Chairman the President designates, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Board's Chairman is the head the template stands for"
        ),
    },
    "exec-ind-misc-peace-corps-director-administrator-chair-peace-corps": {
        "nodeName": "Director / Administrator / Chair, Peace Corps",
        "statutoryTitle": "Director of the Peace Corps",
        "basisCitation": "22 U.S.C. 2503",
        "basisFixture": "peacecorps_22_usc_2503.html",
        "basisQuote": (
            "The President may appoint, by and with the advice and consent of the Senate, a Director of the Peace Corps and a Deputy Director of the Peace Corps."
        ),
        "basis": (
            "the same office: 22 U.S.C. 2503 provides for a Director of the Peace Corps appointed by the President with the Senate's consent, through whom the President exercises the chapter's functions, and 5 U.S.C. 5314 places that Director at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for"
        ),
    },
    "exec-ind-misc-selective-service-system-director-administrator-chair-selective-service-system": {
        "nodeName": "Director / Administrator / Chair, Selective Service System",
        "statutoryTitle": "Director of Selective Service",
        "basisCitation": "50 U.S.C. 3809",
        "basisFixture": "sss_50_usc_3809.html",
        "basisQuote": (
            "There is established in the executive branch of the Government an agency to be known as the Selective Service System, and a Director of Selective Service who shall be the head thereof."
        ),
        "basis": (
            "the same office: 50 U.S.C. 3809 establishes the Selective Service System with a Director of Selective Service as its head, and 5 U.S.C. 5315 places that Director at Level IV; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for"
        ),
    },
    "exec-ind-misc-federal-labor-relations-authority-flra-director-administrator-chair-federal-labor-relations-authority": {
        "nodeName": "Director / Administrator / Chair, Federal Labor Relations Authority",
        "statutoryTitle": "Chairman, Federal Labor Relations Authority",
        "basisCitation": "5 U.S.C. 7104",
        "basisFixture": "flra_5_usc_7104.html",
        "basisQuote": (
            "The President shall designate one member to serve as Chairman of the Authority."
        ),
        "basis": (
            "the same office: 5 U.S.C. 7104 composes the Federal Labor Relations Authority of three members and has the President designate one as Chairman, the Authority's chief executive and administrative officer, and 5 U.S.C. 5315 places that Chairman at Level IV; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for"
        ),
    },
    "exec-ind-misc-national-endowment-for-the-humanities-neh-director-administrator-chair-national-endowment-for-the-humanities": {
        "nodeName": "Director / Administrator / Chair, National Endowment for the Humanities",
        "statutoryTitle": "Chairman of the National Endowment for the Humanities",
        "basisCitation": "20 U.S.C. 956",
        "basisFixture": "neh_20_usc_956.html",
        "basisQuote": (
            "The Endowment shall be headed by a chairperson, who shall be appointed by the President, by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 20 U.S.C. 956 puts a chairperson at the head of the National Endowment for the Humanities, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places the Chairman of the Endowment at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the chairperson is the head the template stands for"
        ),
    },
    "exec-ind-misc-national-transportation-safety-board-ntsb-director-administrator-chair-national-transportation-safety-board": {
        "nodeName": "Director / Administrator / Chair, National Transportation Safety Board",
        "statutoryTitle": "Chairman, National Transportation Safety Board",
        "basisCitation": "49 U.S.C. 1111",
        "basisFixture": "ntsb_49_usc_1111.html",
        "basisQuote": (
            "The President shall designate, by and with the advice and consent of the Senate, a Chairman of the Board."
        ),
        "basis": (
            "the same office: 49 U.S.C. 1111 composes the National Transportation Safety Board of five members and has the President designate a Chairman with the Senate's consent, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for"
        ),
    },
    "exec-ind-misc-office-of-special-counsel-osc-director-administrator-chair-office-of-special-counsel": {
        "nodeName": "Director / Administrator / Chair, Office of Special Counsel",
        "statutoryTitle": "Special Counsel of the Office of Special Counsel",
        "basisCitation": "5 U.S.C. 1211",
        "basisFixture": "osc_5_usc_1211.html",
        "basisQuote": (
            "There is established the Office of Special Counsel, which shall be headed by the Special Counsel."
        ),
        "basis": (
            "the same office: 5 U.S.C. 1211 establishes the Office of Special Counsel headed by the Special Counsel, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places the Special Counsel at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Special Counsel is the head the template stands for"
        ),
    },
    "exec-ind-misc-pension-benefit-guaranty-corporation-pbgc-director-administrator-chair-pension-benefit-guaranty-corporation": {
        "nodeName": "Director / Administrator / Chair, Pension Benefit Guaranty Corporation",
        "statutoryTitle": "Director, Pension Benefit Guaranty Corporation",
        "basisCitation": "29 U.S.C. 1302",
        "basisFixture": "pbgc_29_usc_1302.html",
        "basisQuote": (
            "the corporation shall be administered by a Director, who shall be appointed by the President, by and with the advice and consent of the Senate,"
        ),
        "basis": (
            "the same office: 29 U.S.C. 1302 has the Pension Benefit Guaranty Corporation administered by a Director appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Director at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for"
        ),
    },
    "exec-ind-misc-u-s-postal-rate-commission-postal-regulatory-commission-director-administrator-chair-u-s-postal-rate-commission-postal-regulatory-commission": {
        "nodeName": "Director / Administrator / Chair, U.S. Postal Rate Commission / Postal Regulatory Commission",
        "statutoryTitle": "Chairman, Postal Regulatory Commission",
        "basisCitation": "39 U.S.C. 502",
        "basisFixture": "prc_39_usc_502.html",
        "basisQuote": (
            "One of the Commissioners shall be designated as Chairman by, and shall serve in the position of Chairman at the pleasure of, the President."
        ),
        "basis": (
            "the same office: 39 U.S.C. 502 composes the Postal Regulatory Commission of five Commissioners, one of whom the President designates as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name with the Commission's former name beside its current one, and the Chairman is the head the template stands for"
        ),
    },
    "exec-ind-misc-export-import-bank-of-the-u-s-director-administrator-chair-export-import-bank-of-the-u-s": {
        "nodeName": "Director / Administrator / Chair, Export-Import Bank of the U.S.",
        "statutoryTitle": "President of the Export-Import Bank of Washington",
        "basisCitation": "12 U.S.C. 635a",
        "basisFixture": "exim_12_usc_635a.html",
        "basisQuote": (
            "There shall be a President of the Export-Import Bank of the United States, who shall be appointed by the President of the United States by and with the advice and consent of the Senate, and who shall serve as chief executive officer"
        ),
        "basis": (
            "the same office: 12 U.S.C. 635a creates a President of the Export-Import Bank of the United States as the Bank's chief executive officer, and 5 U.S.C. 5314 places the 'President of the Export-Import Bank of Washington' at Level III — the Schedule keeps the Bank's name before Pub. L. 90-267 renamed it in 1968, a rename the Code records in the notes to 12 U.S.C. 635 and this row relies on; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Bank's President is the head the template stands for"
        ),
    },
    "exec-ind-misc-export-import-bank-of-the-u-s-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "statutoryTitle": "First Vice President of the Export-Import Bank of Washington",
        "basisCitation": "12 U.S.C. 635a",
        "basisFixture": "exim_12_usc_635a.html",
        "basisQuote": (
            "There shall be a Board of Directors of the Bank consisting of the President of the Export-Import Bank of the United States, who shall serve as Chairman, the First Vice President who shall serve as Vice Chairman, and three additional persons appointed by the President of the United States by and with the advice and consent of the Senate."
        ),
        "basis": (
            "the same office: 12 U.S.C. 635a(b) creates a First Vice President of the Export-Import Bank of the United States and 635a(c)(1) seats that officer on the Board as its Vice Chairman, and 5 U.S.C. 5315 places the 'First Vice President of the Export-Import Bank of Washington' at Level IV — the Schedule keeps the Bank's pre-1968 name, the rename the President's row already relies on; the graph names the post with its stamped 'Deputy Director / Vice Chair' template under the Bank, and the First Vice President is the Vice Chairman the template stands for"
        ),
    },
    "exec-dept-doc-uspto-deputy-director": {
        "nodeName": "Deputy Director",
        "statutoryTitle": "Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office",
        "basisCitation": "35 U.S.C. 3",
        "basisFixture": "uspto_35_usc_3.html",
        "basisQuote": (
            "The Secretary of Commerce, upon nomination by the Director, shall appoint a Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office"
        ),
        "basis": (
            "the same office: 35 U.S.C. 3(b)(1) creates one officer holding the joint title Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office, and 5 U.S.C. 5315 places that joint title at Level IV; the graph writes the bare 'Deputy Director' under the Office, and the row is keyed to that node by id"
        ),
    },
    'exec-ind-misc-equal-employment-opportunity-commission-eeoc-director-administrator-chair-equal-employment-opportunity-commission': {
        "nodeName": 'Director / Administrator / Chair, Equal Employment Opportunity Commission',
        "statutoryTitle": 'Chairman, Equal Employment Opportunity Commission',
        "basisCitation": '42 U.S.C. 2000e-4',
        "basisFixture": 'eeoc_42_usc_2000e-4.html',
        "basisQuote": (
            'The President shall designate one member to serve as Chairman of the Commission, and one member to serve as Vice Chairman.'
        ),
        "basis": (
            "the same office: 42 U.S.C. 2000e-4(a) has the President designate one member of the Commission as its Chairman, and 5 U.S.C. 5314 places 'Chairman, Equal Employment Opportunity Commission' at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that Chairman, the only one of the three offices the Act creates"
        ),
    },
    'exec-ind-misc-equal-employment-opportunity-commission-eeoc-deputy-director-vice-chair': {
        "nodeName": 'Deputy Director / Vice Chair',
        "statutoryTitle": 'Members, Equal Employment Opportunity Commission (4)',
        "basisCitation": '42 U.S.C. 2000e-4',
        "basisFixture": 'eeoc_42_usc_2000e-4.html',
        "basisQuote": (
            'The President shall designate one member to serve as Chairman of the Commission, and one member to serve as Vice Chairman.'
        ),
        "basis": (
            "a Vice Chairman is a member of the Commission: 42 U.S.C. 2000e-4(a) has the President designate one member as Vice Chairman, 5 U.S.C. 5315 places the four members other than the Chairman at Level IV as 'Members, Equal Employment Opportunity Commission (4)', and only the Chairman is placed separately (5314); the graph's stamped 'Deputy Director / Vice Chair' template stands for that Vice Chairman, the one such office the Act creates"
        ),
    },
    'exec-ind-misc-national-mediation-board-nmb-director-administrator-chair-national-mediation-board': {
        "nodeName": 'Director / Administrator / Chair, National Mediation Board',
        "statutoryTitle": 'Chairman, National Mediation Board',
        "basisCitation": '45 U.S.C. 154',
        "basisFixture": 'nmb_45_usc_154.html',
        "basisQuote": (
            'The Mediation Board shall annually designate a member to act as chairman.'
        ),
        "basis": (
            "the same office: 45 U.S.C. 154 Second has the Board annually designate a member to act as chairman, and 5 U.S.C. 5314 places 'Chairman, National Mediation Board' at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that chairman, the only one of the three offices the Act creates"
        ),
    },
    'exec-ind-misc-national-endowment-for-the-arts-nea-director-administrator-chair-national-endowment-for-the-arts': {
        "nodeName": 'Director / Administrator / Chair, National Endowment for the Arts',
        "statutoryTitle": 'Chairman of the National Endowment for the Arts the incumbent of which also serves as Chairman of the National Council on the Arts',
        "basisCitation": '20 U.S.C. 954',
        "basisFixture": 'nea_20_usc_954.html',
        "basisQuote": (
            'The Endowment shall be headed by a chairperson, to be known as the Chairperson of the National Endowment for the Arts, who shall be appointed by the President, by and with the advice and consent of the Senate.'
        ),
        "basis": (
            "the same office: 20 U.S.C. 954(b)(1) has the Endowment headed by the Chairperson of the National Endowment for the Arts, and 5 U.S.C. 5314 places that Chairman at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that Chairperson, the only one of the three offices the Act creates, spelt with gender by the Schedule and without by the Act"
        ),
    },
    'exec-dept-hud-ginnie-president-ginnie-mae': {
        "nodeName": 'President, Ginnie Mae',
        "statutoryTitle": 'President, Government National Mortgage Association, Department of Housing and Urban Development',
        "basisCitation": '12 U.S.C. 1723',
        "basisFixture": 'ginnie_12_usc_1723.html',
        "basisQuote": (
            'There is hereby established in the Department of Housing and Urban Development the position of President, Government National Mortgage Association, who shall be appointed by the President, by and with the advice and consent of the Senate.'
        ),
        "basis": (
            'the same office: 12 U.S.C. 1723(a) establishes in the Department the position of President, Government National Mortgage Association, and 5 U.S.C. 5315 places it at Level IV; the graph names the Association by the name it trades under'
        ),
    },
    'exec-dept-dol-whd-administrator-whd': {
        "nodeName": 'Administrator, WHD',
        "statutoryTitle": 'Administrator, Wage and Hour Division, Department of Labor',
        "basisCitation": '29 U.S.C. 204',
        "basisFixture": 'whd_29_usc_204.html',
        "basisQuote": (
            'There is created in the Department of Labor a Wage and Hour Division which shall be under the direction of an Administrator, to be known as the Administrator of the Wage and Hour Division'
        ),
        "basis": (
            'the same office: 29 U.S.C. 204(a) creates the Wage and Hour Division under the direction of the Administrator of the Wage and Hour Division, and 5 U.S.C. 5315 places that Administrator at Level IV; the graph names the Division by its acronym'
        ),
    },
    'exec-eop-omb-office-of-federal-procurement-policy-administrator-chief-office-of-federal-procurement-policy': {
        "nodeName": 'Administrator / Chief, Office of Federal Procurement Policy',
        "statutoryTitle": 'Administrator for Federal Procurement Policy',
        "basisCitation": '41 U.S.C. 1102',
        "basisFixture": 'ofpp_41_usc_1102.html',
        "basisQuote": (
            'The head of the Office of Federal Procurement Policy is the Administrator for Federal Procurement Policy.'
        ),
        "basis": (
            "the same office: 41 U.S.C. 1102(a) makes the Administrator for Federal Procurement Policy the head of the Office, and 5 U.S.C. 5314 places that Administrator at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which is that Administrator"
        ),
    },
    'exec-eop-omb-office-of-federal-financial-management-administrator-chief-office-of-federal-financial-management': {
        "nodeName": 'Administrator / Chief, Office of Federal Financial Management',
        "statutoryTitle": 'Controller, Office of Federal Financial Management, Office of Management and Budget',
        "basisCitation": '31 U.S.C. 504',
        "basisFixture": 'offm_31_usc_504.html',
        "basisQuote": (
            'There shall be at the head of the Office of Federal Financial Management a Controller, who shall be appointed by the President, by and with the advice and consent of the Senate.'
        ),
        "basis": (
            "the same office: 31 U.S.C. 504(b) puts a Controller at the head of the Office of Federal Financial Management, and 5 U.S.C. 5314 places that Controller at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which the statute styles Controller"
        ),
    },
    'exec-eop-omb-office-of-e-government-it-federal-cio-administrator-chief-office-of-e-government-it-federal-cio': {
        "nodeName": 'Administrator / Chief, Office of E-Government & IT (Federal CIO)',
        "statutoryTitle": 'Administrator of the Office of Electronic Government',
        "basisCitation": '44 U.S.C. 3602',
        "basisFixture": 'egov_44_usc_3602.html',
        "basisQuote": (
            'There shall be at the head of the Office an Administrator who shall be appointed by the President.'
        ),
        "basis": (
            "the same office: 44 U.S.C. 3602(a)-(b) establishes the Office of Electronic Government in the Office of Management and Budget with an Administrator at its head, and 5 U.S.C. 5314 places that Administrator at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which it names as the Office of E-Government & IT"
        ),
    },
    'exec-eop-omb-director-omb': {
        "nodeName": 'Director, OMB',
        "statutoryTitle": 'Director of the Office of Management and Budget',
        "basisCitation": '31 U.S.C. 502',
        "basisFixture": 'omb_31_usc_502.html',
        "basisQuote": (
            'The head of the Office of Management and Budget is the Director of the Office of Management and Budget.'
        ),
        "basis": (
            'the same office: 31 U.S.C. 502(a) makes the Director the head of the Office, and 5 U.S.C. 5312 places the Director of the Office of Management and Budget at Level I; the graph names the Office by its acronym'
        ),
    },
    'exec-eop-omb-deputy-director-omb': {
        "nodeName": 'Deputy Director, OMB',
        "statutoryTitle": 'Deputy Director of the Office of Management and Budget',
        "basisCitation": '31 U.S.C. 502',
        "basisFixture": 'omb_31_usc_502.html',
        "basisQuote": (
            'The Office has a Deputy Director of the Office of Management and Budget, appointed by the President, by and with the advice and consent of the Senate.'
        ),
        "basis": (
            'the same office: 31 U.S.C. 502(b) gives the Office a Deputy Director, and 5 U.S.C. 5313 places the Deputy Director of the Office of Management and Budget at Level II (the Deputy Director for Management is placed separately and is a separate node here); the graph names the Office by its acronym'
        ),
    },
    'exec-dept-dot-phmsa-administrator-phmsa': {
        "nodeName": 'Administrator, PHMSA',
        "statutoryTitle": 'Administrator, Pipeline and Hazardous Materials Safety Administration',
        "basisCitation": '49 U.S.C. 108',
        "basisFixture": 'phmsa_49_usc_108.html',
        "basisQuote": (
            'The head of the Administration shall be the Administrator who shall be appointed by the President, by and with the advice and consent of the Senate'
        ),
        "basis": (
            "the same office: 49 U.S.C. 108(c) makes the Administrator the head of the Pipeline and Hazardous Materials Safety Administration, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym, and OPM's current export lists the post at EX-III under it"
        ),
    },
    'exec-regulatory-cpsc-commissioner-4': {
        "nodeName": 'Commissioner (×4)',
        "statutoryTitle": 'Members, Consumer Product Safety Commission (4)',
        "basisCitation": '15 U.S.C. 2053',
        "basisFixture": 'cpsc_15_usc_2053.html',
        "basisQuote": (
            'An independent regulatory commission is hereby established, to be known as the Consumer Product Safety Commission, consisting of five Commissioners who shall be appointed by the President, by and with the advice and consent of the Senate.'
        ),
        "basis": (
            "a class title: 5 U.S.C. 5315 places 'Members, Consumer Product Safety Commission (4)' at Level IV, the four Commissioners other than the Chairman (placed separately at 5314), and 15 U.S.C. 2053(a) composes the Commission of five Commissioners; the graph's bench of four is exactly the four the Code counts, and the count is checked on every run"
        ),
        "classTitle": True,
    },
    'exec-regulatory-sec-commissioner-4': {
        "nodeName": 'Commissioner (×4)',
        "statutoryTitle": 'Members, Securities and Exchange Commission',
        "basisCitation": '15 U.S.C. 78d',
        "basisFixture": 'sec_15_usc_78d.html',
        "basisQuote": (
            'to be composed of five commissioners to be appointed by the President by and with the advice and consent of the Senate'
        ),
        "basis": (
            "a class title: 5 U.S.C. 5315 places 'Members, Securities and Exchange Commission' at Level IV, and the Chairman separately at 5314; 15 U.S.C. 78d(a) composes the Commission of five commissioners, so the bench of four is the members other than the Chairman"
        ),
        "classTitle": True,
    },
}


#: The Code's class-title form: one entry placing every member of a body at
#: one level ("Members, Federal Trade Commission"). The only shape a
#: `classTitle` row may cite; "Independent Members, ..." and every singular
#: title are refused, because a singular title names one office and the
#: graph's "(×N)" node stands for N.
CLASS_TITLE_PREFIX = "Members, "


def is_class_title(title: str) -> bool:
    """Whether a statutory title places a whole class of members at one level."""
    return str(title or "").startswith(CLASS_TITLE_PREFIX)


def states_a_multiplicity(name: str) -> bool:
    """Whether a node's own name says it stands for several posts -- the same
    "(×N)" the exporter's `annotate_stated_counts` reads."""
    return STATED_MULTIPLICITY.search(str(name or "")) is not None


def _operative_text(raw_html: str) -> str:
    """The section's own text, cut at the publisher's notes -- the same rule
    `derived_pay.operative_text` applies, restated here so this module does
    not import that one. A quote found only beneath the law is repealed text."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_html)
    text = _SPACE.sub(" ", html_module.unescape(_TAGS.sub(" ", text))).strip()
    start = re.search(r"\u00a7\s?\d+[A-Za-z]?(?:[-\u2013]\d+)?\.", text)
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


#: Since 2026-10-07 (the owner's decision, CURATION.md §19.20): reviewed rows
#: whose BASIS is not a section of the Code but an instrument the Code prints
#: outside its sections -- here a Reorganization Plan in Title 5's Appendix --
#: read by `notes_instruments.py`, which locates the one plan by its own
#: printed heading. Kept apart from `REVIEWED_TITLE_ROWS` because every check
#: on those reads a section's operative text, and an Appendix page has none;
#: the gate mirrors these in `US_CODE_REVIEWED_INSTRUMENT_IDENTIFICATIONS`.
#: The identification carries `basisDocumentKind` and the instrument's name,
#: date and issuer.
REVIEWED_INSTRUMENT_ROWS: dict[str, dict[str, Any]] = {
    # §19.14 declined the SEC's Chairman because 15 U.S.C. 78d does not
    # designate one; Reorganization Plan No. 10 of 1950 does. §1(a) transfers
    # the Commission's executive and administrative functions "to the
    # Chairman of the Commission", and §3 transfers to the President the
    # choosing of "a Chairman from among the Commissioners composing the
    # Commission"; 5 U.S.C. 5314 places "Chairman, Securities and Exchange
    # Commission" at Level III.
    "exec-regulatory-sec-chair-sec": {
        "nodeName": "Chair, SEC",
        "statutoryTitle": "Chairman, Securities and Exchange Commission",
        "basisCitation": "Reorganization Plan No. 10 of 1950, §3",
        "basisInstrument": "reorganization-plan-no-10-of-1950",
        "basisFixture": "reorganization_plans_5_usc_app_govinfo2024.html",
        "basisQuote": (
            "The functions of the Commission with respect to choosing a Chairman from among the Commissioners "
            "composing the Commission are hereby transferred to the President."
        ),
        "basis": (
            "the office under the graph's 'Chair' is the Chairman: Reorganization Plan No. 10 of 1950, a plan "
            "the President transmitted under the Reorganization Act of 1949 and which took effect May 24, 1950, "
            "transfers to the President the choosing of a Chairman from among the Commissioners (§3) and vests "
            "the Commission's executive and administrative functions in that Chairman (§1(a)); 5 U.S.C. 5314 "
            "places the Chairman, Securities and Exchange Commission at Level III; 15 U.S.C. 78d composes the "
            "Commission and designates no Chairman, which is why the basis is the Plan"
        ),
    },
}


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
    for node_id, row in sorted({**REVIEWED_TITLE_ROWS, **REVIEWED_INSTRUMENT_ROWS}.items()):
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
        class_row = row.get("classTitle") is True
        if class_row and not is_class_title(row["statutoryTitle"]):
            # A bench may be priced only from a title that places every
            # member of the body at one level; a singular title names one
            # office, and N holders are not that office.
            refusals.setdefault("reviewed_row_class_title_is_not_a_class_title", []).append(node_id)
            continue
        if class_row and not states_a_multiplicity(node.get("name")):
            refusals.setdefault("reviewed_row_class_title_on_a_single_post", []).append(node_id)
            continue
        if not class_row and states_a_multiplicity(node.get("name")):
            # The sweep would strip it on every build; a row that can never
            # publish is a row nobody reviewed for what it would claim.
            refusals.setdefault("reviewed_row_names_a_bench_without_a_class_title", []).append(node_id)
            continue
        if class_row and position["statedPosts"] != 1:
            # A COUNTED class title ("Members, Consumer Product Safety
            # Commission (4)") says how many members there are besides the
            # chair, and the bench's own name says how many posts it stands
            # for. They must agree exactly: a bench of five priced from a
            # class of four would publish one post the Code does not place.
            stated = STATED_MULTIPLICITY.search(str(node.get("name") or ""))
            bench = stated.group(1) if stated else ""
            if not bench.isdigit() or int(bench) != position["statedPosts"]:
                refusals.setdefault("reviewed_row_bench_count_disagrees_with_the_code", []).append(node_id)
                continue
        instrument_id = row.get("basisInstrument")
        if instrument_id:
            # An instrument outside the Code's sections: the quote must be the
            # instrument's own words, found inside the one plan its heading
            # names -- never elsewhere on the Appendix page, never inside the
            # publisher's square-bracketed insertions.
            from data_pipeline.verification import notes_instruments

            try:
                instrument = basis_cache.get("instrument:" + instrument_id) or notes_instruments.load_instrument(
                    instrument_id, directory)
            except notes_instruments.Unreadable:
                refusals.setdefault("reviewed_row_basis_unreadable", []).append(node_id)
                continue
            basis_cache["instrument:" + instrument_id] = instrument
            if notes_instruments.where_is(instrument, row["basisQuote"]) is not None:
                refusals.setdefault("reviewed_row_basis_quote_not_in_its_instrument", []).append(node_id)
                continue
            basis = {"url": instrument["url"], "sha256": instrument["sha256"], "fetchedAt": instrument["fetched_at"]}
        else:
            try:
                basis = basis_cache.get(row["basisFixture"]) or load_basis_section(row["basisFixture"], directory)
            except Unreadable:
                refusals.setdefault("reviewed_row_basis_unreadable", []).append(node_id)
                continue
            basis_cache[row["basisFixture"]] = basis
            if row["basisQuote"] not in basis["operative"]:
                refusals.setdefault("reviewed_row_basis_quote_not_in_operative_text", []).append(node_id)
                continue
            instrument = None
        entry = dict(position)
        entry["method"] = METHOD_REVIEWED
        if class_row:
            entry["classTitle"] = True
        entry["identification"] = {
            "nodeName": row["nodeName"],
            "basis": row["basis"],
            "basisCitation": row["basisCitation"],
            "basisQuote": row["basisQuote"],
            "basisUrl": basis["url"],
            "basisSha256": basis["sha256"],
            "basisCheckedAt": basis["fetchedAt"],
        }
        if instrument is not None:
            from data_pipeline.verification.notes_instruments import instrument_block

            entry["identification"]["basisDocumentKind"] = instrument["kind"]
            entry["identification"]["basisInstrument"] = instrument_block(instrument)
        matched[node_id] = entry
    return {"matched": matched, "refusals": {k: sorted(v) for k, v in sorted(refusals.items())}}



# --------------------------------------------------------------------------
# The fourth route: a COUNTED class, since 2026-09-30 (the owner's decision)

#: The Code places some offices one at a time and some as a counted class:
#: "Assistant Attorneys General (11)" at Level IV places eleven offices at
#: once and names none of them. Every other route refused such a title --
#: `match_positions` because it states several posts, the scoped route because
#: it names no organisation, the reviewed route because a bench row needs a
#: "Members, ..." title. What a counted class licenses is narrower than a
#: name and wider than a bench: every one of the N offices is at that level,
#: and the Code says how many there are. So a member is priced only when
#: (1) the Code's own section prints the class title with its count,
#: (2) the node is a single post, named as the class's singular office and
#: nothing else -- the singular first, then a separator, and where the name
#: says "of <department>" that department is the class's own,
#: (3) the node sits inside the organisation the class belongs to,
#: (4) no listing on the node reports another pay plan or level,
#: (5) the graph names no more members than the Code counts, and
#: (6) the node id is in this table: which nodes are members is a REVIEW,
#: because this graph's post names are templated in places -- the State
#: Department stamp names an "Assistant Secretary" over the Foreign Service
#: Institute, whose head is a Director -- and a name rule alone would price
#: the template. Where a second statute composes the class (28 U.S.C. 506:
#: "11 Assistant Attorneys General") it is the record's third document, and
#: where that statute names the office itself ("The Assistant Secretary for
#: African Affairs shall be the head of the Bureau of African Affairs") the
#: sentence rides on the record as `namedAs`. A class with no composition
#: statute in hand (the EPA's Assistant Administrators, Commerce's Assistant
#: Secretaries) rests on two documents and the panel says so.
METHOD_COUNTED = "level_assigned_by_5_usc_5312_5316_to_a_counted_class_of_offices_this_post_is_one_of"
COUNTED_CLASS_COUNT = re.compile(r"\((\d+)\)")
#: What may follow the singular office in a member's name.
COUNTED_CLASS_SEPARATORS = (", ", " for ", " of the ", " of ", " — ", " / ", " - ")

COUNTED_CLASSES: dict[str, dict[str, Any]] = {
    'Assistant Attorneys General (11)': {
        "section": '5315',
        "singular": 'Assistant Attorney General',
        "scopeId": 'exec-dept-doj',
        "departmentWords": (),
        "composition": {"citation": '28 U.S.C. 506', "fixture": 'aag_28_usc_506.html', "quote": (
            'The President shall appoint, by and with the advice and consent of the Senate, 11 Assistant Attorneys General, who shall assist the Attorney General in the performance of his duties.'
        )},
        "basis": (
            "5 U.S.C. 5315 places the eleven Assistant Attorneys General at Level IV as a class and names none of them; 28 U.S.C. 506 creates the eleven offices; each of these nodes is named as the Assistant Attorney General heading one of the Department's litigating divisions"
        ),
        "members": {
            'exec-dept-doj-div-antitrust-assistant-attorney-general-antitrust-division': None,
            'exec-dept-doj-div-civil-assistant-attorney-general-civil-division': None,
            'exec-dept-doj-div-civil-rights-assistant-attorney-general-civil-rights-division': None,
            'exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division': None,
            'exec-dept-doj-div-enrd-assistant-attorney-general-environment-natural-resources-division': None,
            'exec-dept-doj-div-nsd-assistant-attorney-general-national-security-division': None,
            'exec-dept-doj-div-tax-assistant-attorney-general-tax-division': None,
        },
    },
    'Assistant Administrators, Environmental Protection Agency (8)': {
        "section": '5315',
        "singular": 'Assistant Administrator',
        "scopeId": 'exec-ind-epa',
        "departmentWords": (),
        "composition": None,
        "basis": (
            "5 U.S.C. 5315 places the Agency's eight Assistant Administrators at Level IV as a class and names none of them (it also prints two of them under older office names, at the same level); no statute composing the class has been read here, so the record rests on the Code and the table alone; each node is named as the Assistant Administrator heading one of the Agency's national programme offices"
        ),
        "members": {
            'exec-ind-epa-office-of-air-radiation-oar-assistant-administrator-office-of-air-radiation': None,
            'exec-ind-epa-office-of-water-ow-assistant-administrator-office-of-water': None,
            'exec-ind-epa-office-of-land-emergency-management-olem-assistant-administrator-office-of-land-emergency-management': None,
            'exec-ind-epa-office-of-chemical-safety-pollution-prevention-ocspp-assistant-administrator-office-of-chemical-safety-pollution-prevention': None,
            'exec-ind-epa-office-of-research-development-ord-assistant-administrator-office-of-research-development': None,
            'exec-ind-epa-office-of-enforcement-compliance-assurance-oeca-assistant-administrator-office-of-enforcement-compliance-assurance': None,
            'exec-ind-epa-office-of-international-tribal-affairs-oita-assistant-administrator-office-of-international-tribal-affairs': None,
        },
    },
    'Assistant Secretaries of State (24)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-state',
        "departmentWords": ('State',),
        "composition": {"citation": '22 U.S.C. 2651a', "fixture": 'state_22_usc_2651a.html', "quote": (
            'There shall be in the Department of State not more than 24 Assistant Secretaries of State who shall be compensated at the rate provided for at level IV of the Executive Schedule under section 5315 of title 5'
        )},
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of State at Level IV as a class of not more than 24 (the section prints the class inside a longer paragraph naming four other officials, which the title parser sets aside, so the printed words are checked directly); 22 U.S.C. 2651a(c) composes the class at the same level and itself names eight of these bureaux' heads as Assistant Secretaries; each node is named as the Assistant Secretary heading one bureau"
        ),
        "members": {
            'exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs': 'The Assistant Secretary for African Affairs shall be the head of the Bureau of African Affairs.',
            'exec-dept-state-bureau-of-east-asian-pacific-affairs-assistant-secretary-bureau-of-east-asian-pacific-affairs': 'The Assistant Secretary for East Asian and Pacific Affairs shall be the head of the Bureau of East Asian and Pacific Affairs.',
            'exec-dept-state-bureau-of-european-eurasian-affairs-assistant-secretary-bureau-of-european-eurasian-affairs': 'The Assistant Secretary for European and Eurasian Affairs shall be the head of the Bureau of European and Eurasian Affairs.',
            'exec-dept-state-bureau-of-near-eastern-affairs-assistant-secretary-bureau-of-near-eastern-affairs': 'The Assistant Secretary for Near Eastern Affairs shall be the head of the Bureau of Near Eastern Affairs.',
            'exec-dept-state-bureau-of-south-central-asian-affairs-assistant-secretary-bureau-of-south-central-asian-affairs': 'The Assistant Secretary for South and Central Asian Affairs shall be the head of the Bureau of South and Central Asian Affairs.',
            'exec-dept-state-bureau-of-western-hemisphere-affairs-assistant-secretary-bureau-of-western-hemisphere-affairs': 'The Assistant Secretary for Western Hemisphere Affairs shall be the head of the Bureau of Western Hemisphere Affairs.',
            'exec-dept-state-bureau-of-international-organization-affairs-assistant-secretary-bureau-of-international-organization-affairs': 'The Assistant Secretary for International Organization Affairs shall be the head of the Bureau of International Organization Affairs.',
            'exec-dept-state-bureau-of-consular-affairs-assistant-secretary-bureau-of-consular-affairs': 'The Assistant Secretary for Consular Affairs shall be the head of the Bureau of Consular Affairs.',
            'exec-dept-state-bureau-of-arms-control-verification-compliance-assistant-secretary-bureau-of-arms-control-verification-compliance': None,
            'exec-dept-state-bureau-of-international-security-nonproliferation-assistant-secretary-bureau-of-international-security-nonproliferation': None,
            'exec-dept-state-bureau-of-political-military-affairs-assistant-secretary-bureau-of-political-military-affairs': None,
            'exec-dept-state-bureau-of-diplomatic-security-assistant-secretary-bureau-of-diplomatic-security': None,
            'exec-dept-state-bureau-of-global-public-affairs-assistant-secretary-bureau-of-global-public-affairs': None,
        },
    },
    'Assistant Secretaries of Labor (10)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-dol',
        "departmentWords": ('Labor',),
        "composition": {"citation": '29 U.S.C. 553', "fixture": 'labor_29_usc_553.html', "quote": (
            'There are established in the Department of Labor nine offices of Assistant Secretary of Labor, which shall be filled by appointment by the President, by and with the advice and consent of the Senate.'
        )},
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of Labor at Level IV as a class of ten (its paragraph goes on to name the one for Veterans' Employment and Training, which is why the title parser reads it as a single post and the printed words are checked directly); 29 U.S.C. 553 establishes nine of the offices and names the one for Occupational Safety and Health; each node is named as an Assistant Secretary heading one of the Department's agencies"
        ),
        "members": {
            'exec-dept-dol-osha-assistant-secretary-of-labor-for-occupational-safety-health': 'One of such Assistant Secretaries shall be an Assistant Secretary of Labor for Occupational Safety and Health.',
            'exec-dept-dol-eta-assistant-secretary-for-employment-training': None,
            'exec-dept-dol-ebsa-assistant-secretary-of-labor-for-ebsa': None,
        },
    },
    'Assistant Secretaries of Education (10)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-ed',
        "departmentWords": ('Education',),
        "composition": {"citation": '20 U.S.C. 3412', "fixture": 'education_20_usc_3412.html', "quote": (
            'There shall be in the Department- (A) an Assistant Secretary for Elementary and Secondary Education; (B) an Assistant Secretary for Postsecondary Education; (C) an Assistant Secretary for Career, Technical, and Adult Education; (D) an Assistant Secretary for Special Education and Rehabilitative Services; (E) an Assistant Secretary for Civil Rights'
        )},
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of Education at Level IV as a class of ten; 20 U.S.C. 3412(b) establishes the offices and names each of these two by title; each node is named as the Assistant Secretary heading one of the Department's principal offices"
        ),
        "members": {
            'exec-dept-ed-oese-assistant-secretary-for-oese': '(A) an Assistant Secretary for Elementary and Secondary Education',
            'exec-dept-ed-ocr-assistant-secretary-for-civil-rights': '(E) an Assistant Secretary for Civil Rights',
        },
    },
    'Assistant Secretaries of Housing and Urban Development (8)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-hud',
        "departmentWords": ('Housing and Urban Development', 'Housing & Urban Development', 'HUD'),
        "composition": {"citation": '42 U.S.C. 3533', "fixture": 'hud_42_usc_3533.html', "quote": (
            'There shall be in the Department a Deputy Secretary, 7 Assistant Secretaries, and a General Counsel, who shall be appointed by the President by and with the advice and consent of the Senate'
        )},
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of Housing and Urban Development at Level IV as a class of eight; 42 U.S.C. 3533(a) establishes seven Assistant Secretaries (the two documents disagree by one, and the Code's own count is the bound used here) and names the Federal Housing Commissioner as one of them; each node is named as the Assistant Secretary heading one of the Department's programme offices"
        ),
        "members": {
            'exec-dept-hud-fha-assistant-secretary-for-housing-fha-commissioner': 'There shall be in the Department a Federal Housing Commissioner, who shall be one of the Assistant Secretaries, who shall head a Federal Housing Administration within the Department',
            'exec-dept-hud-pih-assistant-secretary-for-public-indian-housing': None,
            'exec-dept-hud-cpd-assistant-secretary-for-community-planning-development': None,
            'exec-dept-hud-fheo-assistant-secretary-for-fair-housing-equal-opportunity': None,
        },
    },
    'Assistant Secretaries of Energy (8)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-doe',
        "departmentWords": ('Energy',),
        "composition": {"citation": '42 U.S.C. 7133', "fixture": 'energy_42_usc_7133.html', "quote": (
            'There shall be in the Department 8 Assistant Secretaries, each of whom shall be appointed by the President, by and with the advice and consent of the Senate; who shall be compensated at the rate provided for at level IV of the Executive Schedule under section 5315 of title 5'
        )},
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of Energy at Level IV as a class of eight; 42 U.S.C. 7133(a) establishes the eight at the same level and assigns their functions without naming the offices; each node is named as the Assistant Secretary heading one of the Department's programme offices"
        ),
        "members": {
            'exec-dept-doe-eere-assistant-secretary-eere': None,
            'exec-dept-doe-em-assistant-secretary-for-environmental-management': None,
        },
    },
    'Assistant Secretaries of Commerce (11)': {
        "section": '5315',
        "singular": 'Assistant Secretary',
        "scopeId": 'exec-dept-doc',
        "departmentWords": ('Commerce',),
        "composition": None,
        "basis": (
            "5 U.S.C. 5315 places the Assistant Secretaries of Commerce at Level IV as a class of eleven and names none of them; no statute composing the class has been read here (15 U.S.C. 1506 was read and adds one office to those 'now provided for by law' without counting them), so the record rests on the Code and the table alone; each node is named as an Assistant Secretary heading one of the International Trade Administration's units"
        ),
        "members": {
            'exec-dept-doc-ita-assistant-secretary-global-markets': None,
            'exec-dept-doc-ita-assistant-secretary-enforcement-compliance': None,
        },
    },
}


def counted_class_count(code_title: str) -> int | None:
    """The N a counted class title states, or None when it states none."""
    found = COUNTED_CLASS_COUNT.search(str(code_title or ""))
    return int(found.group(1)) if found else None


def counted_class_member_name_reason(name: str, singular: str, department_words: tuple[str, ...]) -> str | None:
    """Why a node's name is NOT the class's singular office, or None when it is.

    The singular must come first and whole, then a separator from a closed
    list, and where the remainder says "of <department>" the department must
    be the class's own: "Assistant Secretary of Labor for EBSA" belongs to the
    Labor class and to no other, and a node so named under the Department of
    Energy would be refused rather than priced as one of Energy's eight. A
    parenthetical is refused outright -- "(dual-hat)" is curation, not a
    title -- and so is a multiplicity, because a class member is one post.
    """
    text = str(name or "")
    if states_a_multiplicity(text):
        return "names a bench, not one post"
    if "(" in text:
        return "carries a parenthetical qualifier"
    if not text.startswith(singular):
        return "does not begin with the class's singular office"
    rest = text[len(singular):]
    if not rest:
        return None
    separator = next((sep for sep in COUNTED_CLASS_SEPARATORS if rest.startswith(sep)), None)
    if separator is None:
        return "does not separate the office from its qualifier"
    if separator in (" of ", " of the "):
        after = rest[len(separator):]
        for word in department_words:
            if after == word or any(after.startswith(word + sep) for sep in COUNTED_CLASS_SEPARATORS):
                return None
        return "names a department that is not the class's own"
    return None


def _ancestor_ids(node_id: str, parent_map: Mapping[str, str]) -> list[str]:
    seen: list[str] = []
    current = parent_map.get(node_id)
    while current and current not in seen:
        seen.append(current)
        current = parent_map.get(current)
    return seen


def listing_contradicts_level(node: Mapping[str, Any], level: str) -> str | None:
    """A listing on the node (OPM's archive or current export) that reports a
    pay plan other than EX, or an EX level other than the class's, is the
    document that says this post is NOT one of the class -- and it wins."""
    for field, level_key in (("positionListing", "payLevel"), ("positionCurrentListing", "level")):
        listing = node.get(field)
        if not isinstance(listing, Mapping):
            continue
        plan = str(listing.get("payPlan") or "").strip().upper()
        if plan and plan != "EX":
            return f"{field} reports pay plan {plan}"
        listed_level = str(listing.get(level_key) or "").strip().upper()
        if listed_level and listed_level != level:
            return f"{field} reports Level {listed_level}"
    return None


def match_counted_classes(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str],
    schedule: Mapping[str, Any],
    *,
    already_matched: Mapping[str, Any] | None = None,
    directory: str | Path = FIXTURE_DIR,
) -> dict[str, Any]:
    """The members of `COUNTED_CLASSES`, each re-adjudicated on every run
    under the six conditions the table's comment lists. A class whose graph
    membership exceeds the Code's count prices nobody: the Code says how
    many such offices exist, and a graph naming more of them is wrong about
    at least one."""
    taken = set(already_matched or {})
    matched: dict[str, dict[str, Any]] = {}
    refusals: dict[str, list[str]] = {}
    classes: dict[str, dict[str, Any]] = {}
    for code_title, spec in COUNTED_CLASSES.items():
        section = spec["section"]
        level = SECTION_LEVELS[section]
        try:
            printed = load_basis_section(f"exec_schedule_{section}.html", directory)
        except Unreadable:
            refusals.setdefault("counted_class_section_unreadable", []).append(code_title)
            continue
        if code_title not in printed["operative"]:
            refusals.setdefault("counted_class_title_not_printed_by_the_code", []).append(code_title)
            continue
        count = counted_class_count(code_title)
        if not count:
            refusals.setdefault("counted_class_title_states_no_count", []).append(code_title)
            continue
        composition = None
        if spec.get("composition"):
            try:
                basis = load_basis_section(spec["composition"]["fixture"], directory)
            except Unreadable:
                refusals.setdefault("counted_class_composition_unreadable", []).append(code_title)
                continue
            if spec["composition"]["quote"] not in basis["operative"]:
                refusals.setdefault("counted_class_composition_quote_not_in_operative_text", []).append(code_title)
                continue
            composition = {**spec["composition"], "url": basis["url"], "sha256": basis["sha256"],
                           "checkedAt": basis["fetchedAt"], "operative": basis["operative"]}
        scope = node_map.get(spec["scopeId"])
        if scope is None or is_post_node(scope):
            refusals.setdefault("counted_class_scope_is_not_an_organisation", []).append(code_title)
            continue
        passing: dict[str, dict[str, Any]] = {}
        for node_id, named_as in spec["members"].items():
            node = node_map.get(node_id)
            if node is None:
                refusals.setdefault("counted_class_member_names_no_node", []).append(node_id)
                continue
            if not is_post_node(node):
                refusals.setdefault("counted_class_member_is_not_a_post", []).append(node_id)
                continue
            if node_id in taken:
                refusals.setdefault("counted_class_member_already_matched", []).append(node_id)
                continue
            why = counted_class_member_name_reason(node.get("name"), spec["singular"], tuple(spec["departmentWords"]))
            if why:
                refusals.setdefault("counted_class_member_" + why.replace(" ", "_").replace("'", ""), []).append(node_id)
                continue
            if spec["scopeId"] not in _ancestor_ids(node_id, parent_map):
                refusals.setdefault("counted_class_member_outside_the_class_organisation", []).append(node_id)
                continue
            if named_as and (composition is None or named_as not in composition["operative"]):
                refusals.setdefault("counted_class_member_naming_sentence_not_in_operative_text", []).append(node_id)
                continue
            contradiction = listing_contradicts_level(node, level)
            if contradiction:
                refusals.setdefault("counted_class_member_listing_contradicts_the_class", []).append(node_id)
                continue
            passing[node_id] = {"namedAs": named_as, "nodeName": str(node.get("name") or "")}
        if len(passing) > count:
            refusals.setdefault("counted_class_graph_names_more_offices_than_the_code_counts", []).extend(sorted(passing))
            continue
        classes[code_title] = {"count": count, "members": len(passing)}
        for node_id, found in passing.items():
            entry: dict[str, Any] = {
                "title": code_title,
                "key": canonical_name_key(code_title),
                "level": level,
                "section": section,
                "citation": CITATION.format(section=section),
                "statedPosts": count,
                "url": printed["url"],
                "sha256": printed["sha256"],
                "fetchedAt": printed["fetchedAt"],
                "method": METHOD_COUNTED,
                "countedClass": {
                    "codeTitle": code_title,
                    "statedPosts": count,
                    "membersInGraph": len(passing),
                    "singular": spec["singular"],
                    "scopeId": spec["scopeId"],
                    "scopeName": str(scope.get("name") or ""),
                    "namedAs": found["namedAs"],
                    "compositionCitation": composition["citation"] if composition else None,
                },
            }
            entry["identification"] = {
                "nodeName": found["nodeName"],
                "basis": spec["basis"],
                "basisCitation": composition["citation"] if composition else None,
                "basisQuote": composition["quote"] if composition else None,
                "basisUrl": composition["url"] if composition else None,
                "basisSha256": composition["sha256"] if composition else None,
                "basisCheckedAt": composition["checkedAt"] if composition else None,
            }
            matched[node_id] = entry
    return {"matched": matched, "classes": classes,
            "refusals": {k: sorted(v) for k, v in sorted(refusals.items())}}

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
                # Present only on a class-title row: the level is every
                # member's, so the multi-post sweep keeps the block.
                **({"classTitle": True} if position.get("classTitle") is True else {}),
                # Present only on a counted-class member: which class, how
                # many the Code counts, and how many this graph names.
                **({"countedClass": dict(position["countedClass"])} if isinstance(position.get("countedClass"), dict) else {}),
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
        claim = record.get("levelClaim") or {}
        if node.get("representsPosts") and claim.get("classTitle") is not True:
            # One rate on a node standing for several posts reads as what a
            # single holder is paid, against a panel that says the figure is
            # the group's. pay_tables.withdraw_pay_from_multi_post_nodes sweeps
            # this field too, after the counts exist; this is the earlier guard.
            # A class-title row is the exception: the Code sets the level for
            # every member of the body, and the sweep stamps `holders`.
            stats["stands_for_many_posts"] += 1
            continue
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
        elif isinstance(claim.get("countedClass"), dict):
            # A counted-class member rests on its name being the class's
            # singular office, on sitting inside the class's organisation,
            # and on no listing saying otherwise; each is re-checked here,
            # against the tree being built and not the one the match saw.
            counted = claim["countedClass"]
            spec = COUNTED_CLASSES.get(str(counted.get("codeTitle") or ""))
            if spec is None or counted_class_member_name_reason(
                    node.get("name"), spec["singular"], tuple(spec["departmentWords"])):
                stats["renamed_since_the_match"] += 1
                continue
            if spec["scopeId"] not in _ancestor_ids(node_id, parent_map):
                stats["reparented_since_the_match"] += 1
                continue
            if listing_contradicts_level(node, str(claim.get("payLevel") or "")):
                stats["listing_contradicts_the_class"] = stats.get("listing_contradicts_the_class", 0) + 1
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
            **({"countedClass": dict(claim["countedClass"])} if isinstance(claim.get("countedClass"), dict) else {}),
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
        if claim.get("classTitle") is True:
            node["positionSchedulePay"]["classTitle"] = True
            stats["priced_class_title"] = stats.get("priced_class_title", 0) + 1
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
