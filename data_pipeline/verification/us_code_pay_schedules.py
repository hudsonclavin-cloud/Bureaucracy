"""Schedule 6 of the annual pay-adjustment order, as the U.S. Code prints it:
the elected offices this project could not previously cite.

## The gap this closes, in this repository's own words

`congressional_pay.py` prices three Senate leadership roles from senate.gov's
own footnote and says, in its docstring, exactly what it could not reach:

- "**Not** the House's Speaker, Majority Leader or Minority Leader ... Left
  unpriced rather than guessed."
- "**Not** the President of the Senate (Vice President) node. The Vice
  President's salary is a different statutory figure entirely (3 U.S.C.
  § 104, not 2 U.S.C. § 4501), and this module has not read a source for it."

Both refusals were about the network, not the claim: the CRS reports that
carry those figures are Cloudflare-blocked from here. The figures are
published somewhere this project already reads. The annual Executive Order
adjusting rates of pay attaches its schedules by number --- "(b) The Vice
President (3 U.S.C. 104) and the Congress (2 U.S.C. 4501) at Schedule 6" ---
and the Office of the Law Revision Counsel reproduces those schedules
verbatim in the note to 5 U.S.C. 5332. `uscode.house.gov` answers robots.txt
200 and `statutory_schedule.py` has read it since 2026-09-18.

So this is one fetch of a host already in use, and the committed page carries
Schedule 5 (the Executive Schedule levels `pay_tables.py` prices), Schedule 6
(elected offices) and Schedule 7 (judicial salaries) in one document.

## What it prices, and the four refusals that are the point

**Schedule 6 reaches four nodes.** The Vice President, the Speaker of the
House, and the House Majority and Minority Leaders --- the offices named
above as unreachable.

- **The three Senate roles are refused, though Schedule 6 names them.** They
  already carry `positionStatutoryPay` from senate.gov. Writing this source
  over that one would replace a claim with a claim, not add evidence, and
  the field holds one source. The agreement is real and is recorded in the
  report rather than published twice: Schedule 6 prints 193,400 for the
  President pro tempore and for the Senate's leaders, which is the figure
  senate.gov's footnote states.
- **The Vice President's Senate-leadership node is refused.** This graph
  carries the office twice --- `exec-vp` under the Executive Branch and
  `leg-senate-leadership-president-of-the-senate-vice-president` under Senate
  Leadership --- and Schedule 6 states one salary for one officer. Pricing
  both would publish one salary as two. The executive node is the office.
- **No Member's SEAT is priced as such**, for the reason `congressional_pay.py`
  already records: 174,000 is what Schedule 6 pays Senators, Members,
  Delegates and the Resident Commissioner, and this graph curates no seat
  node for any of them. "Individual Senator Offices (100)" is a staff-office
  grouping, not a seat. What the graph DOES carry is the offices Members
  hold -- every committee's chair and ranking member, the whips, the
  conference and caucus chairs -- and since 2026-09-30 those are priced at
  the seat rate by the rule in the section below.
- **Schedule 7 prices nothing, and is still read.** Every tier it names is
  already priced from uscourts.gov, or reaches only nodes that state a
  multiplicity (`Circuit Judge (×28 active + senior judges)`), or reaches no
  post node at all --- the Court of International Trade has a court node and
  no judge node. It is parsed anyway and its rows are reported, because
  "nobody looked" and "looked and it reaches nothing" are different facts,
  and because its agreement with uscourts.gov is worth recording.

## Members of Congress, priced at the seat rate (since 2026-09-30, the owner's decision)

Every batch of research since the fourth reported the same figure for the
same posts -- $174,000 for every committee chair and ranking member, from
senate.gov's salary page, the House Clerk's Salary.pdf and CRS RL30064 --
and every batch was held under one open question, recorded in
`CURATION.md` §19.6 through §19.14: is a committee-chair node a seat? The
owner decided it. A committee's chair and ranking member ARE Members of the
chamber that constitutes the committee, and Schedule 6 prints a separate
rate only for the Vice President, the Speaker, the majority and minority
leaders of each chamber and the President pro tempore. It prints none for a
committee chair, a ranking member, a whip or a conference chair, so those
offices are priced at the seat's own rate and nothing is added for holding
them. That is the reading `CURATION.md` §7.1 already recorded as a finding
("a Member who holds one of those posts is paid the Member rate. Neither is
a committee chair separately compensated") -- it was recorded as a reason
NOT to price them, and the owner's decision reverses that conclusion while
keeping the premise.

**Which row.** The chamber is read off the tree, never off the name: a post
whose ancestors include `leg-senate` is priced from the row "Senators" and
one under `leg-house` from "Members of the House of Representatives". The
two joint-committee posts (the Joint Economic Committee's Chair, which
alternates between the chambers by Congress, and its Vice Chair) sit under
neither and are refused: the figure would be the same either way, since the
schedule prints one figure for both rows, but a record names one row, and
which chamber the current holder sits in is a fact about a person this
project never reads. The House rows for Delegates and the Resident
Commissioner print the same 174,000, and every House record says so, since a
subcommittee chair could in principle be a Delegate.

**Which posts.** Two shapes, both structural. A **committee post** is a
single-post Position whose name begins `Chair, ` or `Ranking Member, ` and
whose tree parent is typed Committee or Subcommittee -- 436 nodes, 218 of
each. `Staff Director` and `Minority Staff Director` sit under the same
parents and are staff, not Members, and the prefix rule never reaches them.
A **leadership office** is one of the 25 nodes `MEMBER_LEADERSHIP_NODES`
lists by id, each under a chamber's Leadership grouping: the Senate's eleven
(the whips, the assistant leaders, the conference chairs and secretary, the
policy, steering and campaign committee chairs -- the "eleven Senate
leadership roles" the fourth batch reported) and the House's fourteen. The
table is reviewed by id, the shape `SCHEDULE_6_NODE_ROWS` already takes,
because those names are the graph's own and no rule distinguishes
"Republican Study Committee Chair" from a staff title. Two leadership nodes
are refused by name in `MEMBER_SEATS_NOT_PRICED`: the Problem Solvers
Caucus's "Co-Chairs" node stands for two people in a form the multi-post
rule cannot read, and the Senate's "President of the Senate (Vice
President)" is the office `exec-vp` already carries at its own row.

**What the record says.** The method is its own string,
`METHOD_MEMBER_SEAT`, so the panel prints a different sentence from the four
offices Schedule 6 names outright: the block carries `memberSeat` with the
role, the body, the chamber and the basis in words, and the document count
is one document stating the figure -- for the SEAT. That the post is a
Member's is the reviewed rule above, and the panel says so. `scopeMatch` is
`proxy` and the grade `partial`: the schedule names a class of seats, not
this post. The gate mirrors the rule rather than 461 ids -- the method, the
two chamber rows, the role prefixes, the committee types and the leadership
table -- reads the parent and the chamber off the tree it is walking, and
refuses a member-seat block on a leadership office that has its own
Schedule 6 row, on a node outside both chambers, on a post whose name has no
Member-role prefix, under a parent that is not a committee, on a node that
stands for several posts, at the other chamber's row, or with a basis that
does not carry the schedule's own reason.

## Two rows are grouped, and the record says so

Schedule 6 prints one row for "Majority leader and minority leader of the
House of Representatives". That is one rate stated once for two offices, the
same shape as the Senate footnote naming three roles together, so both nodes
are filed `scopeMatch: "proxy"` for the reason `congressional_pay.py` gives:
a grouped statement does not individually name each role, and `"exact"`
would grade `verified`. The Vice President's and the Speaker's rows name one
office each and are still filed `proxy`, because nothing here reads a rate
off a row without a reviewed identification of which node that row's words
name --- the table below --- and a reviewed identification is not the source
naming the node.

## The scale, and why the mark appears once

Schedule 6 prints "$292,300" on its first row and "174,000" on every row
beneath: the currency mark sits once at the head of the column, which is
ordinary typesetting and is exactly the case `financial_evidence`'s
`COLUMN_HEAD_MARK_SOURCE_TYPES` was written for when OPM's GS table did the
same thing. A record for a bare row quotes the column's first figure WITH
its mark beside its own figure without one; the Vice President's own row
carries the mark and takes the stronger rule.

Basic pay is not the node's cost, for the reason `pay_tables.py` states, and
nothing here writes `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod` --- the channel by which a five-row table carried 29
positions to `verified` on 2026-09-11.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_SCHEDULE_HTML = FIXTURE_DIR / "pay_schedules_5_usc_5332.html"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "us_code_pay_schedule_evidence.json"
)

PAY_SOURCE = "us_code_pay_schedules"
PAY_SOURCE_TYPE = "us_code_pay_schedules"
PAY_METHOD = "office_named_in_schedule_6_of_the_annual_pay_adjustment_order"
SCHEDULE_LABEL = "Schedule 6 — Vice President and Members Of Congress"

#: Node id -> the words Schedule 6 prints for that office. An explicit,
#: reviewed map rather than a name-matching rule, for the reason
#: `congressional_pay.LEADERSHIP_NODE_IDS` gives: there are four of them, the
#: stakes of mismatching a statutory salary are real, and a map this short is
#: more auditable than a pattern that would also have to be proven not to
#: catch anything else. It is needed here because not one of the four matches
#: its row by name: the Code says "Vice President" where this graph says "The
#: Vice President of the United States", and "Speaker of the House of
#: Representatives" where it says "Speaker of the House".
#:
#: The alias table is deliberately NOT consulted. `aliases.py` is read by name
#: and existence evidence only and by no join that lands a number, and this
#: is a join that lands a number.
SCHEDULE_6_NODE_ROWS = {
    "exec-vp": "Vice President",
    "leg-house-leadership-speaker-of-the-house": "Speaker of the House of Representatives",
    "leg-house-leadership-majority-leader": "Majority leader and minority leader of the House of Representatives",
    "leg-house-leadership-minority-leader": "Majority leader and minority leader of the House of Representatives",
}

#: Rows this module reads and deliberately does not price, with the reason.
#: Kept as data rather than prose so the derive step can print it and a
#: reviewer can see that the refusal is a decision and not an oversight.
SCHEDULE_6_ROWS_NOT_PRICED = {
    "Delegates to the House of Representatives": (
        "no curated seat node; the row prints the figure every House record notes for a seat a Delegate holds"
    ),
    "Resident Commissioner from Puerto Rico": (
        "no curated seat node; the row prints the figure every House record notes for a seat the Commissioner holds"
    ),
    "President pro tempore of the Senate": "already priced from senate.gov's own footnote",
    "Majority leader and minority leader of the Senate": "already priced from senate.gov's own footnote",
}

#: The offices Members hold, priced at the seat rate since 2026-09-30 (the
#: owner's decision; the module docstring says why). A committee post is
#: found by rule; a leadership office by this reviewed table of node id ->
#: the chamber grouping it sits under. Mirrored by id in the gate
#: (`US_CODE_MEMBER_LEADERSHIP_NODES`), pinned equal by
#: tests/test_us_code_pay_schedules.py.
METHOD_MEMBER_SEAT = "member_of_congress_priced_at_the_seat_rate_of_schedule_6_of_the_annual_pay_adjustment_order"
#: Chamber grouping id -> the Schedule 6 row that prices a seat in it. The
#: chamber is read off the tree (the post's ancestors), never off its name.
CHAMBER_SEAT_ROWS = {
    "leg-senate": "Senators",
    "leg-house": "Members of the House of Representatives",
}
CHAMBER_NAMES = {"leg-senate": "Senate", "leg-house": "House of Representatives"}
CHAMBER_SEAT_WORDS = {"leg-senate": "a Senator", "leg-house": "a Member of the House of Representatives"}
#: A committee post's name begins with the role and a comma; the rest is the
#: body. `Staff Director` and `Minority Staff Director` share the parents and
#: are never reached.
MEMBER_ROLE_PREFIXES = ("Chair, ", "Ranking Member, ")
MEMBER_COMMITTEE_TYPES = ("committee", "subcommittee")
MEMBER_LEADERSHIP_NODES = {
    # The Senate's eleven, the "eleven Senate leadership roles" the fourth
    # research batch reported at $174,000 (CURATION.md §19.7).
    "leg-senate-leadership-majority-whip": "leg-senate",
    "leg-senate-leadership-minority-whip": "leg-senate",
    "leg-senate-leadership-assistant-majority-leader": "leg-senate",
    "leg-senate-leadership-assistant-minority-leader": "leg-senate",
    "leg-senate-leadership-majority-conference-chair": "leg-senate",
    "leg-senate-leadership-minority-conference-chair": "leg-senate",
    "leg-senate-leadership-majority-conference-secretary": "leg-senate",
    "leg-senate-leadership-majority-policy-committee-chair": "leg-senate",
    "leg-senate-leadership-minority-policy-committee-chair": "leg-senate",
    "leg-senate-leadership-majority-steering-committee-chair": "leg-senate",
    "leg-senate-leadership-majority-campaign-committee-chair": "leg-senate",
    # The House's fourteen: CURATION.md §7.1's "other 15 House leadership
    # nodes" less the Co-Chairs node refused below.
    "leg-house-leadership-speaker-pro-tempore": "leg-house",
    "leg-house-leadership-majority-whip": "leg-house",
    "leg-house-leadership-minority-whip": "leg-house",
    "leg-house-leadership-chief-deputy-majority-whip": "leg-house",
    "leg-house-leadership-chief-deputy-minority-whip": "leg-house",
    "leg-house-leadership-democratic-caucus-chair": "leg-house",
    "leg-house-leadership-democratic-caucus-vice-chair": "leg-house",
    "leg-house-leadership-republican-conference-chair": "leg-house",
    "leg-house-leadership-republican-conference-vice-chair": "leg-house",
    "leg-house-leadership-republican-conference-secretary": "leg-house",
    "leg-house-leadership-democratic-steering-policy-committee-chair": "leg-house",
    "leg-house-leadership-republican-study-committee-chair": "leg-house",
    "leg-house-leadership-house-freedom-caucus-chair": "leg-house",
    "leg-house-leadership-new-democrat-coalition-chair": "leg-house",
}
#: Leadership and joint-committee posts considered and refused by name, with
#: the reason, so the derive step prints the refusal as a decision.
MEMBER_SEATS_NOT_PRICED = {
    "leg-house-leadership-problem-solvers-caucus-co-chairs": (
        "stands for two co-chairs in a form the multi-post rule cannot read (no stated count)"
    ),
    "leg-senate-leadership-president-of-the-senate-vice-president": (
        "the office exec-vp already carries at Schedule 6's own Vice President row; one officer, one salary"
    ),
    "leg-joint-econ-chair-alternates-senate-house": (
        "the chair alternates between the chambers by Congress; which row applies is a fact about the "
        "holder, whom this project never reads"
    ),
    "leg-joint-econ-vice-chair": (
        "the vice chair is from whichever chamber does not hold the chair; which row applies is a fact "
        "about the holder, whom this project never reads"
    ),
}
#: The schedule's own reason, quoted in every record's basis and required by
#: the gate: the offices Schedule 6 does price separately.
SEPARATE_RATES_SENTENCE = (
    "Schedule 6 prints a separate rate only for the Vice President, the Speaker, the majority and "
    "minority leaders of each chamber and the President pro tempore"
)
HOUSE_SEAT_ROWS_NOTE = (
    "Schedule 6 prints the same 174,000 for Delegates to the House of Representatives and for the "
    "Resident Commissioner from Puerto Rico, so a seat held by either is priced the same."
)

_MONEY = re.compile(r"^\$?\s*([0-9][0-9,]*)$")
_EFFECTIVE = re.compile(r"^\(Effective\b.*\)$", re.IGNORECASE)
_YEAR_IN_EFFECTIVE = re.compile(r"January\s+1,\s+(\d{4})", re.IGNORECASE)


class Unreadable(Exception):
    """The page is not the schedule note this parser knows how to read."""


def _visible_lines(raw_html: str) -> list[str]:
    """Every non-empty run of visible text, in document order.

    The note is typeset rather than tabular -- a label and its figure are two
    text runs, not two cells -- so the reader works on the run sequence. Tags
    become breaks so two runs never fuse into one line.
    """
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_html)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html_module.unescape(text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_pay_schedules(raw_html: str) -> dict[str, Any]:
    """Schedules 5, 6 and 7 as the note prints them.

    Raises `Unreadable` rather than guessing at a reshaped page: a schedule
    whose heading, effective line or row shape is not what this reader knows
    yields nothing at all.
    """
    lines = _visible_lines(raw_html)
    schedules: dict[str, dict[str, Any]] = {}

    for index, line in enumerate(lines):
        if line != "Schedule" or index + 3 >= len(lines):
            continue
        number = lines[index + 1]
        if number not in ("5", "6", "7"):
            continue
        title = lines[index + 2]
        effective = lines[index + 3]
        if not _EFFECTIVE.match(effective):
            raise Unreadable(f"Schedule {number} is not followed by an effective-date line but by {effective!r}")
        year_match = _YEAR_IN_EFFECTIVE.search(effective)
        if not year_match:
            raise Unreadable(f"Schedule {number}'s effective line {effective!r} names no January 1 year")

        rows: list[dict[str, Any]] = []
        cursor = index + 4
        while cursor + 1 < len(lines):
            label = lines[cursor]
            if label == "Schedule":
                break
            figure = lines[cursor + 1]
            money = _MONEY.match(figure)
            if not money:
                break
            if _MONEY.match(label):
                raise Unreadable(f"Schedule {number} has two figures in a row at {label!r}/{figure!r}")
            amount = float(money.group(1).replace(",", ""))
            if amount <= 0:
                raise Unreadable(f"Schedule {number} prints {figure!r}, which is not a positive rate")
            rows.append(
                {
                    "office": label,
                    "amount": amount,
                    "amountRaw": money.group(1),
                    "printed": figure,
                    "marked": figure.lstrip().startswith("$"),
                }
            )
            cursor += 2
        if not rows:
            raise Unreadable(f"Schedule {number} carries no label/figure pairs")
        # The mark sits once, at the head of the column: the first row carries
        # it and no other may. A page that marked several rows would not be
        # the typesetting `COLUMN_HEAD_MARK_SOURCE_TYPES` is written for, and
        # a record built from it would quote the wrong head.
        if not rows[0]["marked"]:
            raise Unreadable(f"Schedule {number}'s first figure {rows[0]['printed']!r} carries no currency mark")
        for row in rows[1:]:
            if row["marked"]:
                raise Unreadable(
                    f"Schedule {number} marks {row['office']!r} as well as its first row; "
                    "the column is not marked once at its head"
                )
        schedules[number] = {
            "number": number,
            "title": title,
            "effective": effective,
            "year": year_match.group(1),
            "rows": rows,
            "columnHead": {
                "column": title,
                "amountRaw": rows[0]["amountRaw"],
                "text": "${}".format(rows[0]["amountRaw"]),
            },
        }

    for required in ("6", "7"):
        if required not in schedules:
            raise Unreadable(f"the note does not carry Schedule {required}")
    return {"source": PAY_SOURCE, "schedules": schedules}


def load_pay_schedules(html_path: str | Path = DEFAULT_SCHEDULE_HTML) -> dict[str, Any]:
    """The committed note, with the provenance its `.meta.json` recorded and
    the digest recomputed from the bytes -- the refusal `pay_tables` makes."""
    path = Path(html_path)
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
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the page")
    parsed = parse_pay_schedules(raw.decode("utf-8", errors="replace"))
    return {"schedules": parsed["schedules"], "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(path)}


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


def _quote_for(schedule: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    """The schedule's own heading, its effective line, its column head and the
    row being priced, in one auditable line.

    The head is quoted on every record, not only the bare ones, because the
    column-head scale rule needs it present in `unitsEvidence` and a reader
    of the panel is entitled to see where the currency mark actually sits.
    """
    head = schedule["rows"][0]
    parts = [
        "Schedule {} — {}".format(schedule["number"], schedule["title"]),
        schedule["effective"],
        "{} {}".format(head["office"], head["printed"]),
    ]
    if row["office"] != head["office"]:
        parts.append("{} {}".format(row["office"], row["printed"]))
    return " · ".join(parts)


def chamber_of(node_id: str, parent_map: Mapping[str, str]) -> str | None:
    """The chamber grouping (`leg-senate` / `leg-house`) among a node's
    ancestors, read off the tree; None for a joint committee or anything
    outside both chambers."""
    seen: set[str] = set()
    current = parent_map.get(node_id)
    while current and current not in seen:
        if current in CHAMBER_SEAT_ROWS:
            return current
        seen.add(current)
        current = parent_map.get(current)
    return None


def member_seat_basis(kind: str, role: str, body: str, chamber_id: str, name: str) -> str:
    """The reason the seat rate applies, in words the panel prints. Every
    sentence names the reviewed rule and the schedule's own list of the
    offices it does price separately; nothing here is a quotation of a
    document saying this post is a Member's."""
    seat = CHAMBER_SEAT_WORDS[chamber_id]
    chamber = CHAMBER_NAMES[chamber_id]
    if kind == "committee_post":
        opening = (
            f"The {role} of {body} is {seat}: the {chamber}'s committees are composed of its Members "
            "(a reviewed rule, not a document naming this post)."
        )
        closing = (
            f"{SEPARATE_RATES_SENTENCE}, and none for a committee chair or ranking member, so this post is "
            "priced at the seat's rate and nothing is added for holding it."
        )
    else:
        opening = f"The {name} is an office held by {seat} (a reviewed rule, not a document naming this post)."
        closing = (
            f"{SEPARATE_RATES_SENTENCE}, and none for this office, so it is priced at the seat's rate and "
            "nothing is added for holding it."
        )
    parts = [opening, closing, "Which Member holds it is never read."]
    if chamber_id == "leg-house":
        parts.append(HOUSE_SEAT_ROWS_NOTE)
    return " ".join(parts)


def match_member_seats(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, int], dict[str, str]]:
    """Every post a Member holds that the seat rate reaches, by the two
    structural shapes the module docstring describes, with the refusals.

    Returns (matches by node id, refusal counts, refusal reason by node id).
    A match carries `kind` (`committee_post` / `leadership_office`), `role`,
    `body`, `chamber` and the chamber's Schedule 6 row.
    """
    matches: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    reasons: dict[str, str] = {}

    def refuse(node_id: str, reason: str) -> None:
        refusals[reason] = refusals.get(reason, 0) + 1
        reasons[node_id] = reason

    considered: dict[str, str] = {}  # node id -> shape considered under
    for node_id, node in node_map.items():
        name = str(node.get("name") or "")
        parent_id = parent_map.get(node_id)
        parent = node_map.get(parent_id) if parent_id else None
        parent_type = str((parent or {}).get("type") or "").casefold()
        if parent is not None and parent_type in MEMBER_COMMITTEE_TYPES and name.startswith(
            ("Chair", "Ranking Member", "Vice Chair")
        ):
            considered[node_id] = "committee_post"
    for node_id in MEMBER_LEADERSHIP_NODES:
        considered[node_id] = "leadership_office"
    for node_id in MEMBER_SEATS_NOT_PRICED:
        considered.setdefault(node_id, "named_refusal")

    for node_id, kind in sorted(considered.items()):
        if node_id in MEMBER_SEATS_NOT_PRICED:
            refuse(node_id, "refused_by_name:" + MEMBER_SEATS_NOT_PRICED[node_id])
            continue
        node = node_map.get(node_id)
        if node is None:
            refuse(node_id, "node_not_in_graph")
            continue
        name = str(node.get("name") or "")
        if str(node.get("type") or "").casefold() != "position":
            refuse(node_id, "not_a_position")
            continue
        if node.get("representsPosts"):
            refuse(node_id, "stands_for_several_posts")
            continue
        chamber_id = chamber_of(node_id, parent_map)
        if chamber_id is None:
            refuse(node_id, "chamber_not_determinable_from_the_tree")
            continue
        if kind == "leadership_office":
            if MEMBER_LEADERSHIP_NODES[node_id] != chamber_id:
                refuse(node_id, "leadership_office_moved_to_another_chamber")
                continue
            role, body = name, str(node_map[parent_map[node_id]].get("name") or "")
        else:
            prefix = next((p for p in MEMBER_ROLE_PREFIXES if name.startswith(p)), None)
            if prefix is None:
                refuse(node_id, "name_is_not_a_member_role_prefix")
                continue
            role = prefix[:-2]
            body = name[len(prefix):].strip()
            if not body:
                refuse(node_id, "name_names_no_body")
                continue
        matches[node_id] = {
            "kind": kind,
            "role": role,
            "body": body,
            "chamber": chamber_id,
            "chamberName": CHAMBER_NAMES[chamber_id],
            "row": CHAMBER_SEAT_ROWS[chamber_id],
            "basis": member_seat_basis(kind, role, body, chamber_id, name),
        }
    return matches, dict(sorted(refusals.items())), reasons


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    schedules: Mapping[str, Mapping[str, Any]],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
    parent_map: Mapping[str, str] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record for each of the four offices Schedule 6
    names outright and -- when the tree's `parent_map` is given, since the
    chamber is read off the tree -- for every post a Member holds, at the
    seat rate. The caller validates each against its node."""
    schedule = schedules.get("6")
    if schedule is None:
        raise Unreadable("no Schedule 6 to price from")
    # Read by number, priced by heading. The reviewed table below identifies
    # nodes by the words a row prints, and those words only mean what they
    # say inside the schedule this module was written against -- so a note
    # that reorganised its schedules would otherwise have this module pricing
    # the right node from the wrong table.
    heading = "Schedule {} — {}".format(schedule["number"], schedule["title"])
    if heading != SCHEDULE_LABEL:
        raise Unreadable(f"Schedule 6 is headed {heading!r}, not {SCHEDULE_LABEL!r}; the note has been reorganised")
    by_office = {row["office"]: row for row in schedule["rows"]}
    year = str(schedule["year"])
    head = schedule["rows"][0]

    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}

    def refuse(reason: str) -> None:
        refusals[reason] = refusals.get(reason, 0) + 1

    for node_id, office in sorted(SCHEDULE_6_NODE_ROWS.items()):
        row = by_office.get(office)
        if row is None:
            refuse("schedule_does_not_print_this_office")
            continue
        node = node_map.get(node_id)
        if node is None:
            refuse("node_not_in_graph")
            continue
        if str(node.get("type") or "").casefold() != "position":
            refuse("not_a_position")
            continue
        if node.get("representsPosts"):
            refuse("stands_for_several_posts")
            continue
        quote = _quote_for(schedule, row)
        record: dict[str, Any] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(row["amount"]),
            "amountRaw": row["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": int(year),
            "periodCoverage": "annual_rate",
            "periodAsOf": f"{year}-01-01",
            "amountScope": office,
            # Never "exact": which node this row's words name is a reviewed
            # identification in SCHEDULE_6_NODE_ROWS, not something the Code
            # states, and two of the four rows price two offices at once.
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {"page": "5 U.S.C. 5332 note", "section": SCHEDULE_LABEL},
            "role": office.casefold(),
            "year": year,
            "rateText": "${} ({}, {})".format(row["amountRaw"], SCHEDULE_LABEL, schedule["effective"].strip("()")),
        }
        if not row["marked"]:
            # The mark sits on the column's first figure; this row's own is
            # bare. COLUMN_HEAD_MARK_SOURCE_TYPES is the rule for that.
            record["columnHead"] = dict(schedule["columnHead"])
        records[node_id] = record

    member_matches: dict[str, dict[str, Any]] = {}
    member_refusals: dict[str, int] = {}
    if parent_map is not None:
        member_matches, member_refusals, _ = match_member_seats(node_map, parent_map)
        for node_id, match in sorted(member_matches.items()):
            row = by_office.get(match["row"])
            if row is None:
                refuse("schedule_does_not_print_the_seat_row")
                continue
            if node_id in records:
                refuse("already_priced_at_its_own_schedule_6_row")
                continue
            quote = _quote_for(schedule, row)
            record = {
                "nodeId": node_id,
                "financialEvidenceStatus": "partial",
                "costBasis": "basic_pay",
                "amount": float(row["amount"]),
                "amountRaw": row["amountRaw"],
                "units": "usd",
                "normalizedMultiplier": 1,
                "unitsEvidence": quote,
                "quote": quote,
                "fiscalYear": int(year),
                "periodCoverage": "annual_rate",
                "periodAsOf": f"{year}-01-01",
                "amountScope": match["row"],
                # A class of seats, not this post: proxy, never exact.
                "scopeMatch": "proxy",
                "rollupRole": "line",
                "sourceType": PAY_SOURCE_TYPE,
                "sourceUrl": url,
                "documentSha256": sha256,
                "retrievedAt": retrieved_at,
                "locator": {"page": "5 U.S.C. 5332 note", "section": SCHEDULE_LABEL},
                "role": match["row"].casefold(),
                "year": year,
                "rateText": "${} ({}, {})".format(row["amountRaw"], SCHEDULE_LABEL, schedule["effective"].strip("()")),
                "method": METHOD_MEMBER_SEAT,
                "memberSeat": {
                    "kind": match["kind"],
                    "role": match["role"],
                    "body": match["body"],
                    "chamber": match["chamber"],
                    "chamberName": match["chamberName"],
                    "row": match["row"],
                    "basis": match["basis"],
                },
            }
            if not row["marked"]:
                record["columnHead"] = dict(schedule["columnHead"])
            records[node_id] = record

    considered = {row["office"] for row in schedule["rows"]}
    priced_offices = {SCHEDULE_6_NODE_ROWS[node_id] for node_id in records if node_id in SCHEDULE_6_NODE_ROWS}
    priced_offices |= {match["row"] for node_id, match in member_matches.items() if node_id in records}
    report = {
        "source": PAY_SOURCE,
        "year": year,
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "schedulesRead": sorted(schedules),
        "schedule6Rows": [
            {"office": row["office"], "printed": row["printed"], "amount": row["amount"]}
            for row in schedule["rows"]
        ],
        "columnHead": dict(schedule["columnHead"]),
        "considered": len(considered),
        "priced": len(records),
        "pricedOffices": sorted(priced_offices),
        "notPriced": {
            office: SCHEDULE_6_ROWS_NOT_PRICED.get(office, "not in the reviewed table")
            for office in sorted(considered - priced_offices)
        },
        "refused": dict(sorted(refusals.items())),
        "headMarked": head["printed"],
        "memberSeats": {
            "priced": sum(1 for node_id in member_matches if node_id in records),
            "byKind": {
                kind: sum(1 for n, m in member_matches.items() if n in records and m["kind"] == kind)
                for kind in ("committee_post", "leadership_office")
            },
            "byChamber": {
                chamber: sum(1 for n, m in member_matches.items() if n in records and m["chamber"] == chamber)
                for chamber in CHAMBER_SEAT_ROWS
            },
            "refused": member_refusals,
            "treeGiven": parent_map is not None,
        },
    }
    if "7" in schedules:
        report["schedule7Rows"] = [
            {"office": row["office"], "printed": row["printed"], "amount": row["amount"]}
            for row in schedules["7"]["rows"]
        ]
        report["schedule7Priced"] = 0
        report["schedule7Reason"] = (
            "every tier it names is already priced from uscourts.gov, or reaches only nodes stating a "
            "multiplicity, or reaches no post node at all (the Court of International Trade has a court "
            "node and no judge node)"
        )
    if "5" in schedules:
        report["schedule5Rows"] = [
            {"office": row["office"], "printed": row["printed"], "amount": row["amount"]}
            for row in schedules["5"]["rows"]
        ]
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionStatutoryPay` on the offices Schedule 6 prices.

    The same field `judicial_pay.py` and `congressional_pay.py` write, for
    the same reason: all three are single-source statutory claims naming a
    role and stating what it pays, so the panel needs one rendering path.
    A node that already carries the field is left alone -- the three Senate
    leadership roles Schedule 6 also names are priced from senate.gov, and
    replacing one source's claim with another's adds no evidence.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {
        "priced": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "stands_for_many_posts": 0,
        "already_priced_by_another_source": 0,
        "member_seats": 0,
    }
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
        if isinstance(node.get("positionStatutoryPay"), dict):
            stats["already_priced_by_another_source"] += 1
            continue
        node["positionStatutoryPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "Schedule 6 of the annual pay-adjustment order, as 5 U.S.C. 5332's note prints it",
            "method": str(record.get("method") or PAY_METHOD),
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "year": record.get("year"),
            "effective": record.get("periodAsOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "seatTier": record.get("role"),
            "quote": record.get("quote"),
            "footnotes": [record.get("quote")] if record.get("quote") else [],
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        if isinstance(record.get("memberSeat"), dict):
            node["positionStatutoryPay"]["memberSeat"] = dict(record["memberSeat"])
            stats["member_seats"] = stats.get("member_seats", 0) + 1
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod — see `judicial_pay.apply_pay_evidence`.
    return stats
