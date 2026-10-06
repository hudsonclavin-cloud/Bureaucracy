"""Instruments the United States Code prints that are not sections of the Code:
Reorganization Plans in Title 5's Appendix, and the two chambers' pay orders
the Code reprints in its Statutory Notes.

## Why these needed a reader of their own

Every statute this repository reads is checked against a section's OPERATIVE
text (`derived_pay.operative_text`): the page from its "§N." heading to the
first publisher's-note heading. The cut is the whole guard -- beneath it the
publisher prints repealed text ("Prior to amendment, text read as follows:"),
amendment histories and decades of superseded salary figures, in the same
prose as the law -- and it is why 38 U.S.C. 7253's repealed sentence never
priced the CAVC's chief judge at the circuit rate.

Two kinds of document fall outside that cut and are law-like all the same:

- **Reorganization Plans** (5 U.S.C. App.). A plan transmitted by the
  President under chapter 9 of Title 5 that took effect has the force of law;
  GPO prints every one on a single Appendix page with no "§N." heading, so
  `operative_text` refuses the page outright. Reorganization Plan No. 4 of
  1970 establishes NOAA and sets its officers' pay by reference to Executive
  Schedule levels; No. 3 of 1979 provides a Deputy Secretary of Commerce at
  Level II; No. 10 of 1950 transfers the choosing of the SEC's Chairman to the
  President.
- **The chambers' pay orders.** The Order of the President pro tempore of the
  Senate (issued under 2 U.S.C. 4571 and 4575a) and the Order of the Speaker
  (issued under 2 U.S.C. 4532) set the pay of each chamber's officers. The
  Code reprints them only in its Statutory Notes -- BENEATH the cut -- on the
  same pages that carry the Amendments notes and their struck-out text.

Reading "the notes" generally would let repealed law through, which is the one
thing the cut exists to prevent. So this module never reads the notes; it
reads ONE instrument, located by its own printed heading, and nothing else:

1. The heading must appear exactly once, as an element of the kind the
   publisher prints that instrument's heading in (`<h2
   class="reorganizationplan-head">` for a plan; `<h4 class="note-head">`
   inside the page's notes for an order), and its text must equal the heading
   the row names.
2. The instrument runs from that heading to the next heading of the same kind
   -- the next plan's heading, or the next note of the kind the order is
   printed as (`field-start:miscellaneous-note`) -- or the end of the
   enclosing field, whichever comes first. A plan stops earlier still, at the
   "Message of the President" printed with it: the message is the President's
   reasons, not the plan.
3. An order's heading must not sit inside an Amendments note, and its text is
   cut at the first "Prior to amendment" / "read as follows" marker should one
   ever appear inside it; any Amendments-note field inside the range is
   removed. A quote found only there is refused with that reason.
4. A quote must be found OUTSIDE the publisher's square-bracketed editorial
   insertions ("[As amended ...]", "[Superseded. ...]"), which are GPO's
   words, not the instrument's.

Every record carries the instrument's name, its date and its issuer, read
from the instrument's own printed lines.

## Nothing reads a person's name

A pay order's date line is printed as "<Speaker> <surname>, January 17, 2025"
and a plan or an order closes with a `presidential-signature` paragraph that
names the official who signed it. Signature paragraphs are removed from the
markup before any text is formed, and the date line is matched only for the
date at its END -- the text before it is never bound to anything, never
returned and never published. The tests plant a sentinel in both places and
assert it reaches nothing this module returns.

## What an order claim can and cannot say

The orders are reprinted by the 2024 edition of the Code; each chamber has
issued a LATER order that this repository has not read (the OLRC host that
would carry the current notes was under maintenance; CURATION.md §19.20). So
every order-based record carries `laterOrderCaution`, saying the order is the
one the 2024 edition reprints and that a later order may have changed it, and
the panel prints that caution beside the figure.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.verification.derived_pay import Unreadable, statute_publisher

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"

KIND_REORGANIZATION_PLAN = "reorganization_plan"
KIND_CHAMBER_PAY_ORDER = "chamber_pay_order"
INSTRUMENT_KINDS = (KIND_REORGANIZATION_PLAN, KIND_CHAMBER_PAY_ORDER)

#: What each kind is, in words the panel prints.
KIND_WORDS = {
    KIND_REORGANIZATION_PLAN: (
        "a Reorganization Plan, transmitted by the President under chapter 9 of Title 5 and in effect, "
        "which the United States Code prints in Title 5's Appendix rather than as a section of the Code"
    ),
    KIND_CHAMBER_PAY_ORDER: (
        "a pay order issued under a statute by the officer the statute names, which the United States Code "
        "reprints only in a Statutory Note beneath a section, not as a section of the Code"
    ),
}

_LATER_ORDER_CAUTION = (
    "This is the {name}, as the 2024 edition of the United States Code reprints it in a Statutory Note to "
    "{section}. A later order of the {officer} exists that this repository has not read, and it may have "
    "changed this rate."
)

#: The instruments, by id. `heading` is the instrument's own printed heading;
#: `date` is checked against the instrument's own printed date line (an order)
#: or transmittal sentence (a plan); `effective` against its printed
#: effective-date line. The gate mirrors every field.
INSTRUMENTS: dict[str, dict[str, Any]] = {
    "reorganization-plan-no-10-of-1950": {
        "kind": KIND_REORGANIZATION_PLAN,
        "fixture": "reorganization_plans_5_usc_app_govinfo2024.html",
        "heading": "REORGANIZATION PLAN NO. 10 OF 1950",
        "name": "Reorganization Plan No. 10 of 1950",
        "issuer": "the President",
        "date": "March 13, 1950",
        "effective": "Eff. May 24, 1950, 15 F.R. 3175, 64 Stat. 1265",
        "printedIn": "5 U.S.C. App., Reorganization Plans",
    },
    "reorganization-plan-no-3-of-1970": {
        "kind": KIND_REORGANIZATION_PLAN,
        "fixture": "reorganization_plans_5_usc_app_govinfo2024.html",
        "heading": "REORGANIZATION PLAN NO. 3 OF 1970",
        "name": "Reorganization Plan No. 3 of 1970",
        "issuer": "the President",
        "date": "July 9, 1970",
        "effective": (
            "Eff. Dec. 2, 1970, 35 F.R. 15623, 84 Stat. 2086, as amended Pub. L. 98–80, §2(a)(2), (b)(2), "
            "(c)(2)(C), Aug. 23, 1983, 97 Stat. 485, 486"
        ),
        "printedIn": "5 U.S.C. App., Reorganization Plans",
    },
    "reorganization-plan-no-4-of-1970": {
        "kind": KIND_REORGANIZATION_PLAN,
        "fixture": "reorganization_plans_5_usc_app_govinfo2024.html",
        "heading": "REORGANIZATION PLAN NO. 4 OF 1970",
        "name": "Reorganization Plan No. 4 of 1970",
        "issuer": "the President",
        "date": "July 9, 1970",
        "effective": (
            "Eff. Oct. 3, 1970, 35 F.R. 15627, 84 Stat. 2090, as amended Pub. L. 94–461, §4(c)(1), Oct. 8, "
            "1976, 90 Stat. 1969; Pub. L. 95–219, §3(a)(1), Dec. 28, 1977, 91 Stat. 1613; Pub. L. 98–498, "
            "title III, §320(c)(3), Oct. 19, 1984, 98 Stat. 2309; Pub. L. 99–659, title IV, §407(d), Nov. 14, "
            "1986, 100 Stat. 3739; Pub. L. 112–166, §2(b)(1), Aug. 10, 2012, 126 Stat. 1283"
        ),
        "printedIn": "5 U.S.C. App., Reorganization Plans",
    },
    "reorganization-plan-no-3-of-1979": {
        "kind": KIND_REORGANIZATION_PLAN,
        "fixture": "reorganization_plans_5_usc_app_govinfo2024.html",
        "heading": "REORGANIZATION PLAN NO. 3 OF 1979",
        "name": "Reorganization Plan No. 3 of 1979",
        "issuer": "the President",
        "date": "September 25, 1979",
        # The 2024 edition prints no "Eff." line for this plan.
        "effective": (
            "44 F.R. 69273, 93 Stat. 1381, as amended Pub. L. 97–195, §1(c)(6), June 16, 1982, 96 Stat. 115; "
            "Pub. L. 97–377, title I, §122, Dec. 21, 1982, 96 Stat. 1913; Pub. L. 117–328, div. BB, title VI, "
            "§604, Dec. 29, 2022, 136 Stat. 5566"
        ),
        "printedIn": "5 U.S.C. App., Reorganization Plans",
    },
    "order-of-the-president-pro-tempore-2024-03-25": {
        "kind": KIND_CHAMBER_PAY_ORDER,
        "fixture": "senate_pay_order_2_usc_4571_govinfo2024.html",
        "heading": "Order of the President Pro Tempore of the United States Senate",
        "name": "Order of the President pro tempore of the Senate of March 25, 2024",
        "issuer": "the President pro tempore of the Senate",
        "date": "March 25, 2024",
        "effective": "Sections 1 through 10 of this Order are effective on and after January 1, 2024.",
        "printedIn": "a Statutory Note to 2 U.S.C. 4571, 2024 edition of the United States Code",
        "notesSection": "2 U.S.C. 4571",
        "officer": "President pro tempore",
    },
    "order-of-the-speaker-2025-01-17": {
        "kind": KIND_CHAMBER_PAY_ORDER,
        "fixture": "house_pay_order_2_usc_4532_govinfo2024.html",
        "heading": "Order of the Speaker of the House of Representatives",
        "name": "Order of the Speaker of the House of Representatives of January 17, 2025",
        "issuer": "the Speaker of the House of Representatives",
        "date": "January 17, 2025",
        "effective": (
            "This Order shall be effective January 1, 2025, and each provision herein shall continue in place "
            "until such time as it is superseded by the issuance of a future Order."
        ),
        "printedIn": "a Statutory Note to 2 U.S.C. 4532, 2024 edition of the United States Code",
        "notesSection": "2 U.S.C. 4532",
        "officer": "Speaker",
    },
}


def later_order_caution(spec: Mapping[str, Any]) -> str:
    """The sentence every order-based record carries and the panel prints."""
    return _LATER_ORDER_CAUTION.format(name=spec["name"], section=spec["notesSection"], officer=spec["officer"])


_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAGS = re.compile(r"<[^>]+>")
_SIGNATURE = re.compile(r'<p class="presidential-signature"[^>]*>.*?</p>', re.S | re.I)
_PLAN_HEAD = re.compile(r'<h2 class="reorganizationplan-head"[^>]*>(.*?)</h2>', re.S)
_NOTE_HEAD = re.compile(r'<h4 class="note-head"[^>]*>(.*?)</h4>', re.S)
_SUBHEAD = re.compile(r'<h4 class="reorganizationplan-subhead"[^>]*>(.*?)</h4>', re.S)
_AMENDMENT_FIELD = re.compile(r"<!-- field-start:amendment-note -->.*?<!-- field-end:amendment-note -->", re.S)
#: Where struck-out text begins on these pages. Text after either is the law
#: as it USED to read.
PRIOR_TEXT_MARKERS = ("Prior to amendment", "read as follows")
_MONTH_DATE = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r" \d{1,2}, \d{4}"
)
#: The date at the END of an order's date line. Nothing before it is bound.
_DATE_AT_END = re.compile(r"(" + _MONTH_DATE + r")$")
_TRANSMITTED = re.compile(
    r"^Prepared by the President and transmitted to the Senate and the House of Representatives in Congress "
    r"assembled, (" + _MONTH_DATE + r"), pursuant to"
)
_BRACKET = re.compile(r"\[[^\[\]]*\]")


def text_of(fragment: str) -> str:
    """Markup to text: comments and tags out, entities unescaped, whitespace
    collapsed. Comments first, because GPO puts `<!-- PDFPage:543 -->`
    mid-word ("re<!-- PDFPage:542 -->spectively")."""
    text = _COMMENT.sub("", fragment)
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    text = _TAGS.sub(" ", text)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


def _span_inside(spans: list[tuple[int, int]], index: int) -> bool:
    return any(start <= index < end for start, end in spans)


def read_instrument(raw_html: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    """The instrument's own text and its printed date and effective line.

    Raises `Unreadable` when the heading is not printed exactly once in the
    form the kind requires, when an order's heading sits in an Amendments
    note, or when the printed date or effective line is not the one the row
    names. Signature paragraphs are removed before anything is read.
    """
    kind = spec["kind"]
    raw = _SIGNATURE.sub(" ", raw_html)
    page_raw = raw
    if kind == KIND_REORGANIZATION_PLAN:
        heads = [m for m in _PLAN_HEAD.finditer(raw) if text_of(m.group(1)) == spec["heading"]]
        if len(heads) != 1:
            raise Unreadable(f"the page prints {spec['heading']!r} as a plan heading {len(heads)} times, not once")
        start = heads[0].end()
        ends = [raw.find('<h2 class="reorganizationplan-head"', start), raw.find("<!-- field-end:reorganizationplan -->", start)]
        ends = [e for e in ends if e > 0]
        if not ends:
            raise Unreadable(f"{spec['heading']} has no end the page marks")
        body = raw[start:min(ends)]
        message = [m.start() for m in _NOTE_HEAD.finditer(body) if text_of(m.group(1)) == "Message of the President"]
        if message:
            body = body[: message[0]]
        subheads = [text_of(m.group(1)) for m in _SUBHEAD.finditer(body)]
        if not subheads or subheads[0] != spec["effective"]:
            raise Unreadable(f"{spec['name']}'s effective line is not the one the row names")
        transmittal = None
        for paragraph in re.finditer(r"<p\b[^>]*>(.*?)</p>", body, re.S):
            match = _TRANSMITTED.match(text_of(paragraph.group(1)))
            if match:
                transmittal = match.group(1)
                break
        if transmittal != spec["date"]:
            raise Unreadable(f"{spec['name']} is printed as transmitted {transmittal!r}, not {spec['date']!r}")
    elif kind == KIND_CHAMBER_PAY_ORDER:
        notes_start = raw.find("<!-- field-start:notes -->")
        notes_end = raw.find("<!-- field-end:notes -->", notes_start)
        if notes_start < 0 or notes_end < 0:
            raise Unreadable("the page carries no notes field for an order to be printed in")
        amendment_spans = [(m.start(), m.end()) for m in _AMENDMENT_FIELD.finditer(raw)]
        heads = [m for m in _NOTE_HEAD.finditer(raw, notes_start, notes_end) if text_of(m.group(1)) == spec["heading"]]
        if len(heads) != 1:
            raise Unreadable(f"the notes print {spec['heading']!r} as a note heading {len(heads)} times, not once")
        head = heads[0]
        if _span_inside(amendment_spans, head.start()):
            raise Unreadable(f"{spec['heading']!r} is printed inside an Amendments note")
        date_line = _NOTE_HEAD.match(raw, re.match(r"\s*", raw[head.end():]).end() + head.end())
        if date_line is None:
            raise Unreadable(f"{spec['heading']!r} is not followed by a date line")
        found = _DATE_AT_END.search(text_of(date_line.group(1)))
        if found is None or found.group(1) != spec["date"]:
            raise Unreadable(f"{spec['heading']!r} is not dated {spec['date']!r} on its own date line")
        # The date line is left out of the instrument's text whole: before its
        # date it may print the issuer's name, which nothing here reads.
        page_raw = raw[: date_line.start()] + " " + raw[date_line.end():]
        start = date_line.end()
        ends = [raw.find("<!-- field-start:miscellaneous-note -->", start), notes_end]
        later_heads = [m.start() for m in _NOTE_HEAD.finditer(raw, start, notes_end)
                       if text_of(m.group(1)).startswith("Order of the ")]
        ends.extend(later_heads)
        ends = [e for e in ends if e > 0]
        body = raw[start:min(ends)]
        body = _AMENDMENT_FIELD.sub(" ", body)
        effective_found = spec["effective"] in text_of(body)
        if not effective_found:
            raise Unreadable(f"{spec['name']}'s effective sentence is not the one the row names")
    else:
        raise Unreadable(f"{kind!r} is not an instrument kind this reader handles")
    text = text_of(body)
    for marker in PRIOR_TEXT_MARKERS:
        cut = text.find(marker)
        if cut >= 0:
            text = text[:cut].strip()
    # The whole page with signatures and the date line removed: what
    # `where_is` searches to say where a stray quote was found.
    return {"text": text, "page": text_of(page_raw)}


def quote_outside_brackets(text: str, quote: str) -> bool:
    """Whether `quote` occurs in `text` at a place not wholly inside one of the
    publisher's square-bracketed insertions."""
    spans = [(m.start(), m.end()) for m in _BRACKET.finditer(text)]
    start = text.find(quote)
    while start >= 0:
        end = start + len(quote)
        if not any(s <= start and end <= e for s, e in spans):
            return True
        start = text.find(quote, start + 1)
    return False


def load_instrument(instrument_id: str, directory: str | Path = FIXTURE_DIR) -> dict[str, Any]:
    """One instrument from its committed page, the digest recomputed from the
    bytes before anything is read -- the refusal `pay_tables` makes."""
    spec = INSTRUMENTS.get(instrument_id)
    if spec is None:
        raise Unreadable(f"{instrument_id!r} is not an instrument this module reads")
    path = Path(directory) / spec["fixture"]
    meta_path = path.with_name(path.name + ".meta.json")
    if not path.exists() or not meta_path.exists():
        raise Unreadable(f"{spec['fixture']} or its .meta.json is not committed")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        raise Unreadable(f"{spec['fixture']} does not match the digest its fetch recorded")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the page")
    url = str(meta.get("url") or "")
    if "www.govinfo.gov" not in url and "uscode.house.gov" not in url:
        raise Unreadable(f"{spec['fixture']} was not read from a host this pipeline reads the Code from")
    decoded = raw.decode("utf-8", errors="replace")
    read = read_instrument(decoded, spec)
    final_url = str(meta.get("final_url") or url)
    publisher, edition = statute_publisher(url, final_url)
    record = {
        "id": instrument_id,
        "kind": spec["kind"],
        "name": spec["name"],
        "heading": spec["heading"],
        "issuer": spec["issuer"],
        "date": spec["date"],
        "effective": spec["effective"],
        "printedIn": spec["printedIn"],
        "publisher": publisher,
        "edition": edition,
        "url": url,
        "final_url": final_url,
        "sha256": digest,
        "fetched_at": str(meta.get("fetched_at") or ""),
        "text": read["text"],
        # Everything outside the instrument, for saying where a stray quote
        # was found: the whole page with signatures and the date line
        # removed, and the Amendments notes alone.
        "page": read["page"],
        "amendments": " ".join(text_of(m.group(0)) for m in _AMENDMENT_FIELD.finditer(decoded)),
    }
    if spec["kind"] == KIND_CHAMBER_PAY_ORDER:
        record["laterOrderCaution"] = later_order_caution(spec)
    return record


def where_is(instrument: Mapping[str, Any], quote: str) -> str | None:
    """None when the quote is the instrument's own words; otherwise why not."""
    if quote_outside_brackets(instrument["text"], quote):
        return None
    if quote in instrument["text"]:
        return "only inside the publisher's square-bracketed editorial insertions"
    if quote in instrument.get("amendments", ""):
        return "only in an Amendments note, which prints the law as it used to read"
    if quote in instrument.get("page", ""):
        return "on the page but outside the instrument"
    return "nowhere on the page"


def instrument_block(instrument: Mapping[str, Any]) -> dict[str, Any]:
    """What a record and a published block carry about the instrument."""
    block = {
        "id": instrument["id"],
        "kind": instrument["kind"],
        "kindWords": KIND_WORDS[instrument["kind"]],
        "name": instrument["name"],
        "heading": instrument["heading"],
        "issuer": instrument["issuer"],
        "date": instrument["date"],
        "effective": instrument["effective"],
        "printedIn": instrument["printedIn"],
        "publisher": instrument["publisher"],
        "edition": instrument["edition"],
        "url": instrument["url"],
        "documentSha256": instrument["sha256"],
        "retrievedAt": instrument["fetched_at"],
    }
    if instrument.get("laterOrderCaution"):
        block["laterOrderCaution"] = instrument["laterOrderCaution"]
    return block
