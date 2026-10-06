"""USAJOBS vacancy announcements as a LISTING that states a post's pay plan
and grade -- the role OPM's PLUM listings play for `gs_pay.py`'s range.

The owner's decision (2026-10-07): an official vacancy announcement on
www.usajobs.gov, the federal government's own job board, operated by OPM, may
stand where a PLUM listing stands -- as the document that says which pay plan
and grade a title is filed at -- so that OPM's committed 2026 General Schedule
table can bound it. This module reads the announcements; `gs_pay.py` builds
the range exactly as it does for a PLUM listing, naming this listing as its
`listingSource`, so the range is withdrawn with the listing.

## What an announcement says, and what it does not

An announcement advertises ONE vacancy (or a handful) at ONE facility, on a
date. Its "Pay scale & grade" cell states the pay plan and grade of that
vacancy -- "GS 15" -- and its "Occupations and job series" list states the
series. Its "Salary" cell states that vacancy's range WITH the locality
adjustment of the duty station, which is a fact about one place and no use
to a node that stands for a title across a network. So:

- **The salary cell is never read.** Not read and declined: the parser
  collects text only from the elements it names (the banner's title,
  department, agency and hiring organisation, the open and close dates, the
  location items, the pay-scale-and-grade cell and the series list), and the
  published figure is OPM's committed 2026 GS base range for the grade,
  step 1 to step 10, before locality -- `gs_pay`'s own range, nothing new.
- **No person is read.** Every announcement prints an agency contact -- a
  named HR specialist, an e-mail address, a telephone number -- in its "How
  to apply" section. The parser is handed only the page's overview: the text
  between `<main id="main_content">` and the first `id="joa-hiring-paths"`,
  which ends the summary block, and it refuses a slice that carries a
  `mailto:` link or the words "Agency contact" at all. The rule
  `positions.py` sets for the PLUM archive's incumbent columns binds here:
  the contact is not read and declined, it is never handed to the parser,
  and `tests/test_usajobs.py` plants a sentinel in the contact section of
  every committed announcement and asserts it appears nowhere in what this
  module returns, writes or prints.
- **One posting is one vacancy.** A family of curated titles is listed only
  when at least two committed announcements list it and EVERY one of them
  states the same pay plan and grade. One announcement at one facility says
  how one vacancy was classified; two or more agreeing say how the title is
  classified, which is the claim a range needs.

## A family, not a node -- and why this listing verifies nothing

No announcement names a node in this graph. The VA's medical centres are
curated as one template subtree per VISN grouping ("VAMC Associate Director
(Administrative)" under each network's "VA Medical Centers"), and every one
of those groupings is a network the VA has replaced (`lifecycle:
superseded`, CURATION.md §10). An announcement for the Associate Director of
the Kansas City VA Medical Center is about a vacancy in Kansas City, not about
the node under "VISN 15 -- Heartland"; that its "Associate (Medical Center)
Director" is the post this graph calls "VAMC Associate Director
(Administrative)" is a REVIEWED identification of a title family, written
down in `VACANCY_FAMILIES` with its basis and re-checked against the pages on
every run (the printed title, the department, the agency, the series and the
grade must all still be what the row says).

So the block is published as a listing of the title family and NOT as
evidence that the node exists. It writes no `sourceUrls`, `sourceTypes`,
`lastVerified` or `verificationMethod`, and claims no placement -- unlike
`plum_current.py`, whose export files a title under the very organisation the
node sits under, by name equality, and so may verify the post. Matching that
treatment here would let a vacancy in Montana confirm a template node under a
network that no longer exists. The range it supports is graded `partial`
exactly as every other GS range is.

The nodes it reaches sit under superseded VISN groupings. That follows the
precedent `va_title38_pay.py` set for the VAMC Directors and Chiefs of Staff
under the same groupings: a pay claim about a title is published where the
title is drawn, and the viewer hides the superseded subtree unless asked.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "usajobs"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "usajobs_evidence.json"

SOURCE = "usajobs_vacancy_announcements"
SOURCE_TYPE = "usajobs_vacancy_announcement"
FIELD = "positionVacancyListing"
METHOD = "pay_plan_and_grade_stated_by_every_usajobs_announcement_for_the_title_family"
HOST = "www.usajobs.gov"
ANNOUNCEMENT_URL = "https://www.usajobs.gov/job/{id}"

#: A family is listed only when at least this many announcements agree.
MINIMUM_ANNOUNCEMENTS = 2

#: The slice of the page this module reads: the overview, ending where the
#: "This job is open to" section begins. Everything after it -- duties,
#: requirements, how to apply and the agency contact -- is never parsed.
SLICE_START = '<main id="main_content">'
SLICE_END = 'id="joa-hiring-paths"'
#: Markers that may never appear inside the slice. A page whose overview
#: carries a contact is a page laid out differently from the ones reviewed,
#: and it is refused rather than read around.
CONTACT_MARKERS = ("mailto:", "tel:", "agency contact")

BANNER_CLASSES = {
    "usajobs-joa-banner__title": "title",
    "usajobs-joa-banner__dept": "department",
    "usajobs-joa-banner__agency": "agency",
    "usajobs-joa-banner__hiring-organization": "hiringOrganization",
}
PAY_SCALE_LABEL = "Pay scale & grade"
SERIES_LABEL = "Occupations and job series"
DATE_LABELS = {"Open date:": "openDate", "Close date:": "closeDate", "Closed date:": "closeDate",
               "Closing date:": "closeDate"}

_PAY_SCALE = re.compile(r"^([A-Z]{2})\s+(\d{1,2})$")
_SERIES = re.compile(r"^(\d{4})\s+(.+)$")
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Unreadable(ValueError):
    """The announcement could not be read as this module reads one."""


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ---------------------------------------------------------------------------
# The page: a small element tree over the overview slice only.


class _Element:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: Mapping[str, str], parent: "_Element | None") -> None:
        self.tag = tag
        self.attrs = dict(attrs)
        self.children: list[Any] = []
        self.parent = parent

    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    def text(self) -> str:
        parts: list[str] = []
        for child in self.children:
            parts.append(child.text() if isinstance(child, _Element) else child)
        return "".join(parts)

    def elements(self) -> list["_Element"]:
        return [c for c in self.children if isinstance(c, _Element)]

    def walk(self):
        yield self
        for child in self.elements():
            yield from child.walk()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("#root", {}, None)
        self._current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        element = _Element(tag, {k: (v or "") for k, v in attrs}, self._current)
        self._current.children.append(element)
        if tag not in _VOID:
            self._current = element

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current.children.append(_Element(tag, {k: (v or "") for k, v in attrs}, self._current))

    def handle_endtag(self, tag: str) -> None:
        node = self._current
        while node is not self.root and node.tag != tag:
            node = node.parent  # tolerate an unclosed child, as browsers do
        if node is not self.root:
            self._current = node.parent

    def handle_data(self, data: str) -> None:
        self._current.children.append(data)


def overview_slice(html: str) -> str:
    """The part of the page this module reads, or `Unreadable`.

    From the main content's opening tag to the first element of the "This job
    is open to" section. The agency contact sits several sections below the
    end, and a slice that carries a contact marker is refused outright.
    """
    start = html.find(SLICE_START)
    if start < 0:
        raise Unreadable("the page has no main content element; it is not an announcement page")
    end = html.find(SLICE_END, start)
    if end < 0:
        raise Unreadable("the page has no 'This job is open to' section to end the overview at")
    piece = html[start:end]
    lowered = piece.casefold()
    for marker in CONTACT_MARKERS:
        if marker in lowered:
            raise Unreadable(
                f"the overview carries {marker!r}; a contact is never read, so a page laid out with one "
                "inside the overview is refused rather than read around"
            )
    return piece


def _iso(text: str) -> str:
    match = _DATE.match(text)
    if not match:
        raise Unreadable(f"date {text!r} is not printed as MM/DD/YYYY")
    month, day, year = (int(g) for g in match.groups())
    return date(year, month, day).isoformat()


def parse_announcement(html: str) -> dict[str, Any]:
    """The fields this module reads off one announcement, or `Unreadable`.

    Title, department, agency, hiring organisation, open and close dates,
    the locations listed, the pay scale and grade, the series. Nothing else
    -- in particular not the salary, which is the duty station's locality
    range, and never the contact, which is outside the slice.
    """
    builder = _TreeBuilder()
    builder.feed(overview_slice(html))
    builder.close()
    found: dict[str, list[str]] = {}
    dates: dict[str, list[str]] = {}
    pay_scales: list[str] = []
    series_lists: list[tuple[str, ...]] = []
    locations: list[str] = []
    for element in builder.root.walk():
        for cls in element.classes():
            if cls in BANNER_CLASSES:
                found.setdefault(BANNER_CLASSES[cls], []).append(_collapse(element.text()))
        if element.tag == "span" and "font-bold" in element.classes():
            label = _collapse(element.text())
            if label in DATE_LABELS and element.parent is not None:
                whole = _collapse(element.parent.text())
                dates.setdefault(DATE_LABELS[label], []).append(_collapse(whole[len(label):] if whole.startswith(label) else ""))
        if element.tag == "dt" and _collapse(element.text()) == PAY_SCALE_LABEL and element.parent is not None:
            siblings = element.parent.elements()
            index = siblings.index(element)
            dd = siblings[index + 1] if index + 1 < len(siblings) else None
            if dd is None or dd.tag != "dd":
                raise Unreadable("the pay-scale-and-grade label has no value beside it")
            first_div = next((c for c in dd.elements() if c.tag == "div"), None)
            if first_div is None:
                raise Unreadable("the pay-scale-and-grade value is not set as the page sets it")
            pay_scales.append(_collapse(first_div.text()))
        if element.tag == "div" and "font-bold" in element.classes() and _collapse(element.text()) == SERIES_LABEL:
            siblings = element.parent.elements() if element.parent is not None else []
            index = siblings.index(element)
            ul = siblings[index + 1] if index + 1 < len(siblings) else None
            if ul is None or ul.tag != "ul":
                raise Unreadable("the series label has no list beside it")
            series_lists.append(tuple(_collapse(li.text()) for li in ul.elements() if li.tag == "li"))
        if element.tag == "div" and "location-item" in element.classes():
            first_bold = next((c for c in element.elements() if c.tag == "div" and "font-bold" in c.classes()), None)
            if first_bold is not None:
                place = _collapse(first_bold.text())
                if place and place not in locations:
                    locations.append(place)

    def one(name: str, values: Sequence[str] | None) -> str:
        distinct = sorted({v for v in (values or []) if v})
        if len(distinct) != 1:
            raise Unreadable(f"the overview prints {len(distinct)} distinct values for the {name}; it is read only when it prints one")
        return distinct[0]

    record = {key: one(key, found.get(key)) for key in BANNER_CLASSES.values()}
    record["openDate"] = _iso(one("open date", dates.get("openDate")))
    record["closeDate"] = _iso(one("close date", dates.get("closeDate")))
    if record["closeDate"] < record["openDate"]:
        raise Unreadable("the announcement closes before it opens")
    pay_scale = one("pay scale and grade", pay_scales)
    match = _PAY_SCALE.match(pay_scale)
    if not match:
        # "GS 13 - 15" is a ladder of grades, not one; it is not a listing at
        # a grade, so it is refused rather than read as its top or bottom.
        raise Unreadable(f"the pay scale and grade is printed {pay_scale!r}, not one pay plan and one grade")
    if len(set(series_lists)) != 1 or not series_lists[0]:
        raise Unreadable("the overview does not print one list of job series")
    series = []
    for item in series_lists[0]:
        series_match = _SERIES.match(item)
        if not series_match:
            raise Unreadable(f"series {item!r} is not a four-digit code and a name")
        series.append({"code": series_match.group(1), "name": series_match.group(2)})
    if not locations:
        raise Unreadable("the overview lists no location")
    record.update({
        "payScaleAndGrade": pay_scale,
        "payPlan": match.group(1),
        "grade": str(int(match.group(2))),
        "series": series,
        "locations": locations,
    })
    return record


# ---------------------------------------------------------------------------
# Loading, with the digest recomputed before anything is read.


def load_announcement(announcement_id: str, fixture_dir: str | Path = FIXTURE_DIR) -> dict[str, Any]:
    """One committed announcement, parsed, with its provenance; or `Unreadable`.

    The digest is recomputed from the bytes and must equal the one the fetch
    recorded -- the refusal every module here makes, because a
    `documentSha256` is a claim that this listing came out of that page. The
    fetch must have been of the announcement's own address and must not have
    landed anywhere else.
    """
    if not re.fullmatch(r"\d{6,12}", str(announcement_id)):
        raise Unreadable(f"{announcement_id!r} is not a USAJOBS announcement number")
    path = Path(fixture_dir) / f"{announcement_id}.html"
    meta_path = path.with_name(path.name + ".meta.json")
    if not path.exists() or not meta_path.exists():
        raise Unreadable(f"announcement {announcement_id} is not committed with the record of its fetch")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        raise Unreadable(f"{path.name} does not match the digest its fetch recorded; the committed file is not the page that was served")
    url = ANNOUNCEMENT_URL.format(id=announcement_id)
    if str(meta.get("url") or "") != url:
        raise Unreadable(f"{meta_path.name} records a fetch of {meta.get('url')!r}, not {url!r}")
    if str(meta.get("final_url") or "") != url:
        raise Unreadable(f"{meta_path.name} records a redirect to {meta.get('final_url')!r}; the page fetched is not the announcement")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the announcement")
    fetched_at = str(meta.get("fetched_at") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}T", fetched_at):
        raise Unreadable(f"{meta_path.name} records no fetch time")
    parsed = parse_announcement(raw.decode("utf-8", errors="replace"))
    return {
        "id": str(announcement_id),
        "url": url,
        "fetchedAt": fetched_at,
        "documentSha256": digest,
        **parsed,
    }


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    """The derived listings, or nothing. A missing file is not an error."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


# ---------------------------------------------------------------------------
# The reviewed table: which curated title family the announcements list.

#: Membership rules, each read off the tree and never off a stored id:
#: - `whole_name_under_parent`: the node is named exactly `nodeName`, its tree
#:   parent exactly `parentName`, and its grandparent is typed
#:   `grandparentType`.
#: - `office_scoped_to_its_own_parent`: the node is named `<nodePrefix><its
#:   own parent's name>` and the parent is typed `parentType`.
RULE_WHOLE_NAME = "whole_name_under_parent"
RULE_SCOPED = "office_scoped_to_its_own_parent"

VACANCY_FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "family": "vamc_associate_director_administrative",
        "rule": RULE_WHOLE_NAME,
        "nodeName": "VAMC Associate Director (Administrative)",
        "parentName": "VA Medical Centers",
        "grandparentType": "VISN",
        "payPlan": "GS",
        "grade": "15",
        "series": "0670",
        "department": "Department of Veterans Affairs",
        "basis": (
            "Each announcement advertises the Associate Director of a VA medical centre or health care "
            "system -- the administrative associate director beside the Medical Center Director, the "
            "Chief of Staff and the Associate Director for Patient Care Services -- in series 0670, "
            "Health System Administration. This graph's 'VAMC Associate Director (Administrative)' is "
            "that post, drawn once per VISN grouping as a template; the identification is reviewed, and "
            "no announcement names a node here."
        ),
        "announcements": (
            {"id": "848110500", "title": "Health Systems Administrator (Associate Director) - Not to Exceed 1 Year",
             "agency": "Veterans Health Administration", "hiringOrganization": "Kansas City VA Medical Center"},
            {"id": "848756100", "title": "Health System Administrator- Associate Medical Center Director",
             "agency": "Veterans Health Administration", "hiringOrganization": "Veterans Health Administration"},
            {"id": "860101900", "title": "Health Systems Administrator (Associate Director) - Not to Exceed 1 Year",
             "agency": "Veterans Health Administration", "hiringOrganization": "Marion VA Health Care System"},
            {"id": "863018500", "title": "Health System Administrator (Associate Director) - Detail NTE 1 Year",
             "agency": "Veterans Health Administration",
             "hiringOrganization": "South Texas VA Health Care System (STVHCS)"},
            {"id": "880101300", "title": "Health Systems Administrator (Associate Director)",
             "agency": "Veterans Health Administration", "hiringOrganization": "Veterans Health Administration"},
        ),
    },
    {
        # Refused by the two-announcement rule on the committed data, and
        # kept in the table so that the rule, not an omission, is what
        # refuses it: one announcement is one vacancy.
        "family": "network_cfo_visn",
        "rule": RULE_SCOPED,
        "nodePrefix": "Network CFO, ",
        "parentType": "VISN",
        "payPlan": "GS",
        "grade": "15",
        "series": "0505",
        "department": "Department of Veterans Affairs",
        "basis": (
            "The announcement advertises a VISN Chief Financial Officer (a detail not to exceed one "
            "year) reporting to the Director of VISN Financial Operations, filed under the Office of "
            "Management rather than the Veterans Health Administration."
        ),
        "announcements": (
            {"id": "880695200", "title": "Chief Financial Officer (CFO)",
             "agency": "Immediate Office of the Assistant Secretary for Management",
             "hiringOrganization": "Office of Management, VHA Chief Financial Officer"},
        ),
    },
)

#: Families looked at and declined with no announcement to read, recorded so
#: the next session does not redo the work.
DECLINED_FAMILIES: tuple[dict[str, str], ...] = (
    {
        "family": "associate_director_for_patient_care_services_cno",
        "nodeName": "Associate Director for Patient Care Services (CNO)",
        "reason": (
            "The twelfth research batch's VA cluster records the post as a Title 38 nurse executive "
            "(Nurse V), not a General Schedule post, and Nurse V has no national range: none of the "
            "committed salary tables prices it (the VA's Title 38 pay ranges this project reads cover "
            "physicians, dentists, podiatrists and optometrists, and print no 'Associate Director'). "
            "An announcement could only supply a grade nothing here bounds. Declined without a fetch."
        ),
    },
)


def family_members(root: Mapping[str, Any], family: Mapping[str, Any], *, index_tree: Any = None) -> list[str]:
    """Every node id the family's membership rule reaches, read off the tree."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    return [node_id for node_id in sorted(node_map) if is_member(node_id, family, node_map, parent_map)]


def is_member(node_id: str, family: Mapping[str, Any], node_map: Mapping[str, Any], parent_map: Mapping[str, Any]) -> bool:
    node = node_map.get(node_id)
    if not isinstance(node, Mapping):
        return False
    from data_pipeline.exporter.build_graph import is_post_node

    if not is_post_node(node) or node.get("representsPosts"):
        return False
    parent = node_map.get(str(parent_map.get(node_id) or ""))
    if not isinstance(parent, Mapping):
        return False
    name = str(node.get("name") or "")
    if family.get("rule") == RULE_WHOLE_NAME:
        grandparent = node_map.get(str(parent_map.get(str(parent.get("id") or "")) or ""))
        return (
            name == family.get("nodeName")
            and str(parent.get("name") or "") == family.get("parentName")
            and isinstance(grandparent, Mapping)
            and str(grandparent.get("type") or "") == family.get("grandparentType")
        )
    if family.get("rule") == RULE_SCOPED:
        return (
            str(parent.get("type") or "") == family.get("parentType")
            and name == f"{family.get('nodePrefix')}{parent.get('name')}"
        )
    return False


# ---------------------------------------------------------------------------
# Adjudicating a family against its announcements, and the listing record.


def adjudicate_family(
    family: Mapping[str, Any], fixture_dir: str | Path = FIXTURE_DIR
) -> tuple[list[dict[str, Any]] | None, str, list[str]]:
    """(announcements, verdict, notes): the family's announcements if every
    one of them still says what the reviewed row says and they agree, else
    None with the reason.

    The table proposes; the page decides. Each row is re-read from the
    committed bytes and must print the row's title, department, agency and
    hiring organisation, the family's series, and the family's pay plan and
    grade -- every one of them, or the family is refused.
    """
    notes: list[str] = []
    loaded: list[dict[str, Any]] = []
    for row in family.get("announcements") or ():
        try:
            announcement = load_announcement(row["id"], fixture_dir)
        except Unreadable as error:
            return None, "announcement_unreadable", [f"{row['id']}: {error}"]
        for key in ("title", "agency", "hiringOrganization"):
            if announcement[key] != row[key]:
                return None, "announcement_no_longer_prints_the_reviewed_row", [
                    f"{row['id']}: the page prints {key} {announcement[key]!r}; the row says {row[key]!r}"]
        if announcement["department"] != family.get("department"):
            return None, "announcement_is_another_departments", [f"{row['id']}: {announcement['department']!r}"]
        if family.get("series") not in [s["code"] for s in announcement["series"]]:
            return None, "announcement_is_in_another_series", [f"{row['id']}: {announcement['series']!r}"]
        loaded.append(announcement)
    if len(loaded) < MINIMUM_ANNOUNCEMENTS:
        return None, "fewer_than_two_announcements", [
            f"{len(loaded)} announcement(s); one posting is one vacancy, and a range needs the title's grade"]
    grades = {(a["payPlan"], a["grade"]) for a in loaded}
    if len(grades) != 1:
        return None, "announcements_disagree_on_the_grade", [f"{sorted(grades)}"]
    if grades != {(family.get("payPlan"), family.get("grade"))}:
        return None, "announcements_state_another_grade_than_the_row", [f"{sorted(grades)}"]
    return sorted(loaded, key=lambda a: (a["openDate"], a["id"])), "listed", notes


def listing_record(family: Mapping[str, Any], announcements: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The listing a node of the family carries, in the shape `gs_pay`
    reads a PLUM listing in: a pay plan, a level, and the two printed on one
    cell. The announcement whose page is the listing's `url` is the earliest
    opened; every one is listed under `announcements`."""
    pay_plan, grade = announcements[0]["payPlan"], announcements[0]["grade"]
    first, last = announcements[0], announcements[-1]
    ids = ", ".join(a["id"] for a in announcements)
    facilities = [
        {"id": a["id"], "hiringOrganization": a["hiringOrganization"], "locations": list(a["locations"])}
        for a in announcements
    ]
    return {
        "source": SOURCE,
        "method": METHOD,
        "family": family["family"],
        "familyRule": family["rule"],
        "basis": family["basis"],
        "payPlan": pay_plan,
        "level": grade,
        "payLevel": grade,
        # Every announcement prints the plan and the grade in one cell
        # ("GS 15"), which is what this flag means on a PLUM listing.
        "payPlanAndLevelOnOneRow": True,
        "reportedPay": None,
        "series": family["series"],
        "listedTitle": None,
        "listedTitles": sorted({a["title"] for a in announcements}),
        "announcementCount": len(announcements),
        "announcements": [
            {
                "id": a["id"], "url": a["url"], "title": a["title"], "department": a["department"],
                "agency": a["agency"], "hiringOrganization": a["hiringOrganization"],
                "locations": list(a["locations"]), "openDate": a["openDate"], "closeDate": a["closeDate"],
                "payScaleAndGrade": a["payScaleAndGrade"], "series": [dict(s) for s in a["series"]],
                "documentSha256": a["documentSha256"], "fetchedAt": a["fetchedAt"],
            }
            for a in announcements
        ],
        "facilities": facilities,
        "edition": f"USAJOBS vacancy announcements {ids}",
        "period": f"announcements opened {first['openDate']} to {last['openDate']}",
        "url": first["url"],
        "checkedAt": max(a["fetchedAt"] for a in announcements),
        "valuesFrom": "vacancy_announcements",
        "statement": (
            f"{len(announcements)} USAJOBS announcements, at "
            + "; ".join(f"{f['hiringOrganization']} ({', '.join(f['locations'])})" for f in facilities)
            + f", list a post of this title family at {pay_plan}-{grade}. Each states the pay plan and grade of "
            "one vacancy at one facility on a date; none names this node, and the identification of the "
            "title family is reviewed. The announcements' own salaries include locality pay and are not "
            "published here."
        ),
    }


def build_listings(
    root: Mapping[str, Any],
    families: Sequence[Mapping[str, Any]] = VACANCY_FAMILIES,
    *,
    fixture_dir: str | Path = FIXTURE_DIR,
    index_tree: Any = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A listing record for every member of every family whose announcements
    agree, and a report saying what each family came to."""
    records: dict[str, dict[str, Any]] = {}
    report: dict[str, Any] = {"source": SOURCE, "families": {}, "declined": [dict(d) for d in DECLINED_FAMILIES]}
    for family in families:
        members = family_members(root, family, index_tree=index_tree)
        announcements, verdict, notes = adjudicate_family(family, fixture_dir)
        entry = {
            "verdict": verdict,
            "members": len(members),
            "announcements": [row["id"] for row in family.get("announcements") or ()],
            "notes": notes,
        }
        report["families"][family["family"]] = entry
        if announcements is None:
            continue
        record = listing_record(family, announcements)
        for node_id in members:
            records[node_id] = {**record, "nodeId": node_id}
        entry["listed"] = len(members)
    report["listed"] = len(records)
    return records, report


# ---------------------------------------------------------------------------
# Applying to the tree.


def apply_vacancy_listing(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
    families: Sequence[Mapping[str, Any]] = VACANCY_FAMILIES,
) -> dict[str, Any]:
    """Stamp `positionVacancyListing` on every family member a record names.

    Membership is re-checked off the published tree, so a re-parenting or a
    rename withdraws the listing (and the range `gs_pay` hangs off it). The
    block verifies nothing: no `sourceUrls`, `sourceTypes`, `lastVerified`,
    `verificationMethod` or placement is written -- see the module docstring.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    by_family = {f["family"]: f for f in families}
    stats = {"listed": 0, "unknown_node": 0, "not_a_member": 0, "malformed": 0, "families": {}}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        family = by_family.get(str(record.get("family") or ""))
        if family is None or not is_member(node_id, family, node_map, parent_map):
            stats["not_a_member"] += 1
            continue
        announcements = record.get("announcements")
        if (
            record.get("source") != SOURCE
            or not isinstance(announcements, list)
            or len(announcements) < MINIMUM_ANNOUNCEMENTS
            or len({(a.get("payScaleAndGrade")) for a in announcements if isinstance(a, Mapping)}) != 1
            or not str(record.get("url") or "").startswith(f"https://{HOST}/job/")
        ):
            stats["malformed"] += 1
            continue
        block = {
            key: record.get(key)
            for key in (
                "source", "method", "family", "familyRule", "basis", "payPlan", "level", "payLevel",
                "payPlanAndLevelOnOneRow", "reportedPay", "series", "listedTitle", "listedTitles",
                "announcementCount", "announcements", "facilities", "edition", "period", "url",
                "checkedAt", "valuesFrom", "statement",
            )
        }
        node[FIELD] = json.loads(json.dumps(block))
        stats["listed"] += 1
        stats["families"][family["family"]] = stats["families"].get(family["family"], 0) + 1
    return stats
