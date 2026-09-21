"""Posts, as the government's own handbook of itself lists them.

`CLAUDE.md` records that 4,604 of this graph's nodes are positions and that
the page method reaches 25 of them. It records why: an agency's website is
not obliged to name its own officers, twelve of the largest hosts refuse
`robots.txt`, and the one rule that could have lifted the count -- accepting
a title found in a site's navigation -- was measured and refused, because 18
of the 27 titles found in chrome were `Inspector General` sitting in 18
different agencies' footers, which is federal web convention rather than a
fact about any of those agencies.

The United States Government Manual is the answer to exactly that gap. It is
the official handbook of the federal government, prepared by the Office of
the Federal Register, and each agency's entry carries a leadership table of
that agency's own posts. It is one document, published by the government,
naming an agency and then naming the officers of that agency -- so a match
is scoped by construction in the way a footer link never is.

`www.govinfo.gov` answers `robots.txt` 200 and allows both paths this module
reads. The package is committed verbatim -- `GOVMAN-2025-12-31.xml`, the
whole Manual as the publisher serves it -- with its `.meta.json`, and the
digest is recomputed from the bytes before anything is read, the refusal
`pay_tables` and `net_cost` make and for the same reason.

**The names of office holders are discarded at parse time.** Each leadership
row is a pair: `<NameColumnValue>` is a living person and
`<TitleColumnValue>` is the post. This module reads the second and never the
first -- not "reads and declines to publish", but never reads, the rule
`positions.py` sets for the PLUM archive's incumbent columns and
`whitehouse_pay.py` binds harder still. The claim made here is about the
post, and the incumbent is not needed to make it.

**Only rows that are complete titles on their own face.** The Manual's
leadership tables are typeset, not tabular, and they use a group heading
followed by qualifiers:

    Header: "Assistant Administrators"        <- the role
        Air and Radiation                     <- ...for Air and Radiation
        Water                                 <- ...for Water

    ADMINISTRATOR                             <- an ALL-CAPS row, then
    Deputy Administrator                      <- rows it governs
    -----------------------------             <- a separator ends the group
    Chief of Staff                            <- complete on its own face

Reconstructing "Assistant Administrator for Water" from those two cells
would be *producing* a title, which is the failure this repository already
refuses by name: `rename_templated_post_titles.py` uses its transform to
recognise a templated name and never to produce the replacement. So the
qualifiers are discarded wholesale rather than assembled, by a rule that is
purely structural and needs no vocabulary and no grammar:

  - a row in a table that carries a `<Header>` at all (anything but empty or
    the footnote mark `*`) is governed by that header and refused;
  - a row after an ALL-CAPS row is governed by it and refused, until a
    separator row resets;
  - a separator row is any row of dashes.

That is deliberately blunt, and it costs real evidence: EPA's `Deputy
Administrator` is refused because `ADMINISTRATOR` sits above it, and every
Assistant Administrator is refused with its header. Measured rather than
assumed: the blunt rule admits 314 rows and confirms 64 posts; relaxing the
header half to "a header that reads as plural" admits 459 and confirms 95,
and the extra rows demonstrably include qualifiers -- `Financial` under
`Chief Officers`, `Under Secretary` under `Food Safety`, which means the
Under Secretary *for* Food Safety. Closing those leaks needs a plural test on
free text, and a plural test is wrong about `Chief of Naval Operations` and
`Chief of Chaplains`, which are titles ending in "s". 64 structurally sound
confirmations are worth more than 95 with a known leak, which is the same
trade the navigation rule made.

**Scoped to the agency's own direct children, never its descendants.** The
graph's post nodes carry the stamped administrative titles this file
documents -- `General Counsel` names 84 nodes, `Inspector General` 72 -- so
the scope of a match is the whole claim. Matching a post to the nearest
ancestor that has a Manual entry was tried and rejected on measurement: it
lifts 64 to 86, and the extra 22 are `General Counsel`, `Inspector General`
and `Chief Information Officer` nodes belonging to DIA, NSA, DLA and other
Defense agencies, all confirmed from the Department of Defense's own row.
One row would have become four agencies' confirmations, which is the footer
problem again wearing a better source. A post is matched only against the
entry for the organisation that is its own parent.

**No placement claim.** One document was read, and it yields one
observation. `CLAUDE.md` sets this rule for a post confirmed on its
organisation's web page -- publishing existence and placement from a single
fetch would present one finding as two corroborating ones -- and a single
Manual entry is the same case. This module writes no placement field, and
the gate refuses one derived from it.

**What a confirmation is worth, and what it is not.** It is evidence that
the post exists and that the Manual files it under this agency. It is not
evidence about who holds it: the Manual's leadership tables carry their own
"Sources of Information were updated" footers, and some are years older than
the edition date, which is why the footer rides on every record and the
panel prints it. Since the incumbent is never read, staleness costs much
less here than it would in a roster -- a job title outlives its holder --
but the record says the edition it came from and claims nothing about today.
One official URL scores 0.4 + 0.3 in `verify_node_sources`, so a post
confirmed here alone publishes `partial`, not `verified`.

**The entry's own description, since 2026-09-21.** Every one of the curated
descriptions in this graph is published as "uncited prose -- not checked
against any source", and the Manual carries, per entry, the government's own
statement of what the unit is for. `entity_description_texts` reads two
elements and nothing else, and the rule is structural:

  - `MissionStatement/Record[1]/Paragraph` -- the element the publisher
    itself labels as the entry's mission statement. 131 of the 231 entries
    carry one (no sub-entity does), the longest is 544 characters, and 118
    open with the entry's own name. Only the FIRST record is read: Congress
    carries two, and the second is history rather than mission.
  - otherwise the entry's OPENING paragraph -- the first non-empty
    `Detail/Paragraph` under `ProgramAndActivities`, in document order --
    and only when it carries the entry's printed name as a substring. The
    guard is what ties the paragraph to the unit, the same job label
    equality does for a page: four sub-entities open with "The Administration
    posts an organizational chart on its 'Offices' web page", which is a
    navigation note and not a description, and the guard refuses all four.
    It also refuses "The U.S. Naval Academy is the undergraduate college of
    the Naval Service" for the entry named "United States Naval Academy",
    which is a real cost, recorded here rather than argued away: 14 of the
    163 matched entries are refused this way, 2 carry no text at all, and 1
    has no sentence boundary inside the bound. The guard is not enough on
    its own: four HHS sub-entities open with "The Centers for Medicare and
    Medicaid Services (CMS) posts an organizational chart in Portable
    Document Format", which names the unit in full and describes its
    website. `NAVIGATION_NOTE_MARKERS`, a closed list that can only withhold,
    refuses those four and nothing else on the real Manual.

The text is published verbatim and bounded: `DESCRIPTION_MAX_CHARS` (600),
cut only at a sentence boundary -- a terminator after a lower-case letter, a
digit or a closing bracket, followed by a capital -- so "15 U.S.C. 271" and
"(ch. 872)" are never taken for the end of a sentence. No mission statement
needs the cut; 17 opening paragraphs take it, and the record says so
(`truncated`, with the full length), so the panel can say "the opening of
its entry" and never present a cut as the whole. The name guard is tested on
the text that is PUBLISHED, not on the whole paragraph -- the first version
tested the whole, and the test suite found the Court of International Trade
named only after the cut, so the reader would have seen a paragraph that
never names the court. 142 of the 163 matched units carry one (89 mission
statements, 53 opening paragraphs). Never a leadership row,
never a footer, never an address: those elements are not read here. The
curated `desc` is never overwritten -- the Manual's text sits BESIDE it as
`descriptionOfficial`, the curated prose keeps its "uncited" label, and the
gate re-derives the text from the committed package and refuses a block
that is not verbatim in the granule it cites.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "govman"
DEFAULT_PACKAGE = FIXTURE_DIR / "GOVMAN-2025-12-31.xml"
DEFAULT_MODS = FIXTURE_DIR / "GOVMAN-2025-12-31.mods.xml"

SOURCE = "us_government_manual"
SOURCE_TYPE = "us_government_manual"
METHOD = "listed_in_its_organisations_us_government_manual_entry"
#: The organisation route, since 2026-09-20. A different claim from METHOD --
#: "the Manual carries an entry for this unit" rather than "an entry lists
#: this post" -- so a different string, and the panel prints a different
#: sentence. It exists because 67 of the 68 hosts this project had recorded
#: as refusing robots.txt refuse the page too (docs/NETWORK_ACCESS.md 11), so
#: for the units on them a page can never be the route; the Manual is the
#: government's own handbook of itself, committed verbatim, and it names 38
#: of the 344 organisations that carried no verification when this landed.
ORG_METHOD = "listed_in_us_government_manual"
ORG_PLACEMENT_METHOD = "listed_under_parent_in_us_government_manual"
DETAILS_BASE = "https://www.govinfo.gov/app/details"

#: The tags an entity is published under. The Manual nests an agency's
#: sub-agencies inside a <Childrens> element rather than repeating <Entity>,
#: so a walk that looked only for <Entity> finds 105 of the 231 agencies.
ENTITY_TAGS = ("Entity", "SubEntityLevelOne", "SubEntityLevelTwo", "SubEntityLevelThree")

#: A row of dashes. The Manual uses one to end a group and start a new one.
SEPARATOR_CHARACTERS = set("-–—_ ")

#: A header that governs nothing: an empty one, and the footnote mark the
#: Manual puts on a table whose footnote is printed beneath it.
NON_GOVERNING_HEADERS = ("", "*")

#: A post's canonical key must carry at least this many tokens. The same floor
#: `evidence.uncheckable_reason` applies to a post found on its organisation's
#: web page, and for the same reason: scoping to one agency supplies the
#: context a qualified title lacks and supplies nothing at all to a single
#: common noun.
MIN_POST_TOKENS = 2

#: The bound on a published description. The Manual's mission statements
#: never reach it (the longest is 544 characters); an opening paragraph is
#: cut at the last sentence boundary at or before it, and the record says so.
DESCRIPTION_MAX_CHARS = 600
DESCRIPTION_KIND_MISSION = "mission_statement"
DESCRIPTION_KIND_OPENING = "opening_paragraph"
DESCRIPTION_KINDS = (DESCRIPTION_KIND_MISSION, DESCRIPTION_KIND_OPENING)
#: The element path each kind is read from, as the record cites it.
DESCRIPTION_PATHS = {
    DESCRIPTION_KIND_MISSION: "MissionStatement/Record[1]/Paragraph",
    DESCRIPTION_KIND_OPENING: "ProgramAndActivities//Detail/Paragraph[first non-empty]",
}
#: An opening paragraph that describes the unit's WEBSITE rather than the
#: unit: "The Centers for Medicare and Medicaid Services (CMS) posts an
#: organizational chart in Portable Document Format (PDF) for viewing and
#: downloading." It names the unit in full, so the name guard passes it, and
#: it is not a description. A closed list, matched case-insensitively, that
#: can only ever WITHHOLD a description and never produce one -- the same
#: direction `name_appears_unlabelled` is allowed to work in. Measured on the
#: real Manual: it refuses exactly four, all HHS sub-entities, and no
#: mission statement contains any of these words.
NAVIGATION_NOTE_MARKERS = ("organizational chart", "organization chart", "web page", "website")
#: A sentence boundary: a terminator that follows a lower-case letter, a
#: digit or a closing mark, optionally closed by a quote or bracket, followed
#: by whitespace and a capital or an opening mark. "15 U.S.C. 271" and
#: "(ch. 872)" are not boundaries; "...Organization Act." President" is.
SENTENCE_BOUNDARY = re.compile(
    r'(?<=[a-z0-9\)\]"”’])[.!?]["”’)]*(?=\s+[A-Z"“(])'
)

WHITESPACE = re.compile(r"\s+")


def normalise(value: Any) -> str:
    """Collapse the XML's own line breaks and indentation inside a value.

    Four of the Manual's `AgencyName` elements are hard-wrapped across lines,
    so the raw text of "Uniformed Services University of the Health\n
    Sciences" is not the name the publisher's own manifest prints.
    """
    return WHITESPACE.sub(" ", str(value or "")).strip()


def fixture_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_fixture(path: Path | str) -> dict[str, Any]:
    """Parse a committed fixture after recomputing its digest from the bytes.

    A hand-written file under a `govinfo.gov` URL would read on the site
    exactly like a fetched one; only the digest tells them apart, and the
    `.meta.json` beside the fixture is where the fetch recorded it.
    """
    path = Path(path)
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    digest = fixture_digest(path)
    meta: dict[str, Any] = {}
    if meta_path.exists():
        import json

        meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
    recorded = meta.get("sha256")
    if recorded and recorded != digest:
        raise ValueError(
            f"{path.name}: sha256 on disk {digest} does not match the fetch record {recorded}"
        )
    return {"root": ET.parse(path).getroot(), "sha256": digest,
            "url": meta.get("url"), "fetchedAt": meta.get("fetched_at")}


def package_id(url: Any, default: str = "GOVMAN-2025-12-31") -> str:
    match = re.search(r"(GOVMAN-\d{4}-\d{2}-\d{2})", str(url or ""))
    return match.group(1) if match else default


def edition_date(package: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", package)
    return match.group(1) if match else ""


def access_id(package: str, entity_id: Any) -> str | None:
    """The publisher's own granule id for an entity.

    Zero-padded to three digits: `app/details/.../GOVMAN-2025-12-31-072`
    serves the House of Representatives and `...-72` serves a page whose
    title is the raw id. The construction is not assumed -- it reproduces
    every one of the 241 accessIds in the committed manifest, which
    `tests/test_govman.py` asserts against the file rather than in prose.
    """
    text = str(entity_id or "").strip()
    if not text.isdigit():
        return None
    return f"{package}-{int(text):03d}"


def manifest_access_ids(mods_root: ET.Element) -> dict[str, str]:
    """accessId -> the title the publisher's manifest gives it."""
    ns = {"m": "http://www.loc.gov/mods/v3"}
    out: dict[str, str] = {}
    for item in mods_root.findall(".//m:relatedItem[@type='constituent']", ns):
        aid = item.findtext(".//m:accessId", default="", namespaces=ns)
        info = item.find("m:titleInfo", ns)
        title = info.findtext("m:title", default="", namespaces=ns) if info is not None else ""
        if aid:
            out[aid.strip()] = normalise(title)
    return out


def is_separator(text: str) -> bool:
    return bool(text) and set(text) <= SEPARATOR_CHARACTERS


def is_all_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def iter_entities(root: ET.Element) -> Iterator[ET.Element]:
    """Every agency entry, parents and nested sub-entities alike."""

    def walk(element: ET.Element) -> Iterator[ET.Element]:
        if element.tag in ENTITY_TAGS:
            yield element
        children = element.find("Childrens")
        if children is not None:
            for sub in children:
                yield from walk(sub)

    for entity in root:
        yield from walk(entity)


def entity_titles(entity: ET.Element) -> list[dict[str, str]]:
    """Leadership rows that are complete titles on their own face.

    Reads `TitleColumnValue` only. `NameColumnValue` holds a living person
    and is never read.
    """
    out: list[dict[str, str]] = []
    tables = entity.find("LeaderShipTables")
    if tables is None:
        return out
    for table in tables.findall("LeaderShipTable"):
        header = normalise(table.findtext("Header"))
        if header not in NON_GOVERNING_HEADERS:
            continue
        footer = normalise(table.findtext("FooterDetails/Footer"))
        governed = False
        for row in table.findall("LeaderShipTableValues/Values"):
            title = normalise(row.findtext("TitleColumnValue"))
            if not title:
                continue
            if is_separator(title):
                governed = False
                continue
            if is_all_caps(title):
                governed = True
                continue
            if governed:
                continue
            out.append({"title": title, "footer": footer})
    return out


def entity_description_texts(entity: ET.Element) -> dict[str, str | None]:
    """The two elements a description may be read from, and nothing else.

    `mission` is the FIRST `MissionStatement/Record`'s paragraph -- Congress
    carries two records and the second is history. `opening` is the first
    non-empty `Detail/Paragraph` under `ProgramAndActivities`, in document
    order. Leadership tables, addresses and footers are other elements and
    are never read here.
    """
    mission = None
    statement = entity.find("MissionStatement")
    if statement is not None:
        first = statement.find("Record")
        if first is not None:
            mission = normalise(first.findtext("Paragraph")) or None
    opening = None
    programmes = entity.find("ProgramAndActivities")
    if programmes is not None:
        for paragraph in programmes.findall(".//Detail/Paragraph"):
            text = normalise(paragraph.text)
            if text:
                opening = text
                break
    return {"mission": mission, "opening": opening}


def sentence_bounded(text: str, limit: int = DESCRIPTION_MAX_CHARS) -> tuple[str | None, bool]:
    """`text` whole when it fits, else its longest prefix that ends at a
    sentence boundary within `limit` -- or None when no boundary falls
    inside it, since a cut mid-sentence would not be the Manual's sentence."""
    text = normalise(text)
    if len(text) <= limit:
        return text, False
    ends = [match.end() for match in SENTENCE_BOUNDARY.finditer(text) if match.end() <= limit]
    if not ends:
        return None, True
    return text[:ends[-1]], True


def entry_description(name: str, texts: dict[str, str | None]) -> tuple[dict[str, Any] | None, str]:
    """The description block for an entry, or None with the reason.

    The mission statement wins where the publisher labels one. Otherwise the
    opening paragraph is taken only when it carries the entry's printed name
    -- the guard that refuses "The Administration posts an organizational
    chart on its 'Offices' web page" as a description of the Administration
    for Children and Families.
    """
    mission = normalise(texts.get("mission"))
    opening = normalise(texts.get("opening"))
    if mission:
        kind, text = DESCRIPTION_KIND_MISSION, mission
    elif opening:
        kind, text = DESCRIPTION_KIND_OPENING, opening
    else:
        return None, "no_descriptive_text"
    bounded, truncated = sentence_bounded(text)
    if bounded is None:
        return None, "no_sentence_boundary_within_bound"
    # The guard is tested on the text that is PUBLISHED, not on the whole
    # paragraph: the Court of International Trade's opening paragraph names
    # the court only after the cut, and a reader sees the cut.
    if kind == DESCRIPTION_KIND_OPENING and normalise(name) not in bounded:
        return None, "opening_paragraph_does_not_name_the_unit"
    if kind == DESCRIPTION_KIND_OPENING and any(marker in bounded.casefold() for marker in NAVIGATION_NOTE_MARKERS):
        return None, "opening_paragraph_is_a_navigation_note"
    return {
        "kind": kind,
        "extractedFrom": DESCRIPTION_PATHS[kind],
        "text": bounded,
        "truncated": truncated,
        "fullLength": len(text),
    }, "extracted"


def read_manual(package_path: Path | str | None = None) -> dict[str, Any]:
    """The committed Manual, indexed by agency."""
    loaded = load_fixture(package_path or DEFAULT_PACKAGE)
    package = package_id(loaded["url"])
    entities = []
    for element in iter_entities(loaded["root"]):
        name = normalise(element.findtext("AgencyName"))
        if not name:
            continue
        entities.append({
            "entityId": (element.get("EntityId") or "").strip(),
            "parentId": (element.get("ParentId") or "").strip(),
            "name": name,
            "titles": entity_titles(element),
            "descriptionTexts": entity_description_texts(element),
        })
    return {"package": package, "edition": edition_date(package), "sha256": loaded["sha256"],
            "url": loaded["url"], "fetchedAt": loaded["fetchedAt"], "entities": entities}


def match_organisations(
    manual: dict[str, Any], node_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Organisation node id -> the one Manual entry that names it.

    Unambiguous on both sides or nothing: an entry naming two nodes claims
    neither, and a name two entries carry identifies no entry. Shared by the
    post route and the organisation route so the two can never disagree
    about which entry is which agency.
    """
    org_by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if is_post_node(node):
            continue
        key = canonical_name_key(node.get("name"))
        if key:
            org_by_key.setdefault(key, []).append(node_id)
    entry_by_key: dict[str, list[dict[str, Any]]] = {}
    for entry in manual["entities"]:
        key = canonical_name_key(entry["name"])
        if key:
            entry_by_key.setdefault(key, []).append(entry)
    stats = {
        "entries": len(manual["entities"]), "organisations_matched": 0,
        "entry_names_several_entries": 0, "entry_names_several_nodes": 0,
        "entry_names_no_node": 0,
    }
    matched: dict[str, dict[str, Any]] = {}
    for key, entries in entry_by_key.items():
        node_ids = org_by_key.get(key) or []
        if len(entries) > 1:
            if node_ids:
                stats["entry_names_several_entries"] += 1
            continue
        if not node_ids:
            stats["entry_names_no_node"] += 1
            continue
        if len(node_ids) > 1:
            stats["entry_names_several_nodes"] += 1
            continue
        matched[node_ids[0]] = entries[0]
    stats["organisations_matched"] = len(matched)
    return matched, stats


def build_org_records(
    manual: dict[str, Any],
    root: dict[str, Any],
    *,
    index_tree=None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """One record per organisation the Manual carries an entry for.

    The claim is the entry's existence and where the Manual files it -- the
    parent entry's name rides on the record so the exporter can compare it
    with the tree, the way the Federal Register directory's parent is. No
    leadership row is read here; that is the post route's job.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    matched, stats = match_organisations(manual, node_map)
    stats.update({"organisations_listed": 0, "refused_no_access_id": 0, "top_level_entries": 0,
                  # The entry's own description (module docstring, last section).
                  "descriptions_extracted": 0, "descriptions_mission_statement": 0,
                  "descriptions_opening_paragraph": 0, "descriptions_truncated": 0,
                  "descriptions_refused_opening_paragraph_does_not_name_the_unit": 0,
                  "descriptions_refused_opening_paragraph_is_a_navigation_note": 0,
                  "descriptions_refused_no_descriptive_text": 0,
                  "descriptions_refused_no_sentence_boundary_within_bound": 0})
    by_entity = {e["entityId"]: e for e in manual["entities"]}
    records: dict[str, dict[str, Any]] = {}
    for org_id, entry in matched.items():
        granule = access_id(manual["package"], entry["entityId"])
        if not granule:
            stats["refused_no_access_id"] += 1
            continue
        parent = by_entity.get(entry.get("parentId") or "")
        if parent is None:
            stats["top_level_entries"] += 1
        description, why = entry_description(entry["name"], entry.get("descriptionTexts") or {})
        if description is None:
            stats["descriptions_refused_" + why] += 1
        else:
            stats["descriptions_extracted"] += 1
            stats["descriptions_" + description["kind"]] += 1
            stats["descriptions_truncated"] += int(description["truncated"])
        records[org_id] = {
            "description": description,
            "source": SOURCE,
            "nodeName": node_map[org_id].get("name"),
            "listedName": entry["name"],
            "entityId": entry["entityId"],
            "parentListedName": parent["name"] if parent else None,
            "parentEntityId": parent["entityId"] if parent else None,
            "package": manual["package"],
            "edition": manual["edition"],
            "granule": granule,
            "url": f"{DETAILS_BASE}/{manual['package']}/{granule}",
            "documentSha256": manual["sha256"],
        }
        stats["organisations_listed"] += 1
    return records, stats


def apply_govman_org_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp a Manual entry onto the organisation it names, beside any page
    claim and never over it; place the node under its parent only when the
    Manual's own parent entry names the parent the tree gives it, and say so
    when the Manual files it elsewhere. Runs after `apply_evidence_to_tree`
    has withdrawn every field this module owns."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    from data_pipeline.processors.normalize_nodes import verify_node_sources

    node_map, parent_map = index_tree(root)
    org_by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if not is_post_node(node):
            key = canonical_name_key(node.get("name"))
            if key:
                org_by_key.setdefault(key, []).append(node_id)
    stats = {"listed": 0, "unknown_node": 0, "stale_name": 0, "is_a_post": 0,
             "urls_added": 0, "method_kept": 0, "method_set": 0, "failed_checks_withdrawn": 0,
             "placements_listed": 0, "placements_disagree": 0, "placements_unresolved": 0,
             "placements_already_evidenced": 0, "top_level": 0, "descriptions_published": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if is_post_node(node):
            stats["is_a_post"] += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("listedName")):
            stats["stale_name"] += 1
            continue
        url = str(record.get("url") or "")
        if not url:
            continue
        if node.get("verificationFailure"):
            # The rule directories.py sets: the badge goes, the fact does not.
            if str(node.get("lastVerified") or "") == str(node.get("evidenceVerifiedAt") or ""):
                node.pop("lastVerified", None)
            node.pop("evidenceVerifiedAt", None)
            failed_kind = str(node.pop("verificationFailure", None) or "")
            failed_source = node.pop("verificationFailureSource", None)
            node.pop("verificationSiteFrom", None)
            if failed_kind == "not_found" and isinstance(failed_source, dict) and failed_source.get("url"):
                node["pageReadNotNamed"] = {
                    "url": str(failed_source["url"]), "checkedAt": failed_source.get("checkedAt"),
                }
            stats["failed_checks_withdrawn"] += 1
        urls = [str(u) for u in (node.get("sourceUrls") or [])]
        if url not in urls:
            urls.append(url)
            stats["urls_added"] += 1
        node["sourceUrls"] = urls
        mine = [str(u) for u in (node.get("evidenceUrls") or [])]
        if url not in mine:
            mine.append(url)
        node["evidenceUrls"] = mine
        types = [str(t) for t in (node.get("sourceTypes") or [])]
        if SOURCE_TYPE not in types:
            types.append(SOURCE_TYPE)
        node["sourceTypes"] = types
        node["govmanEntry"] = {
            "source": SOURCE,
            "listedName": record.get("listedName"),
            "parentListedName": record.get("parentListedName"),
            "edition": record.get("edition"),
            "package": record.get("package"),
            "granule": record.get("granule"),
            "url": url,
        }
        if node.get("verificationMethod"):
            stats["method_kept"] += 1
        else:
            node["verificationMethod"] = ORG_METHOD
            stats["method_set"] += 1
        # The entry's own description, BESIDE the curated prose and never in
        # its place: `desc` is not touched, and the curated text keeps its
        # "uncited" label on the panel. Withdrawn by the evidence sweep with
        # the entry block it depends on.
        description = record.get("description")
        if (isinstance(description, dict) and str(description.get("text") or "").strip()
                and description.get("kind") in DESCRIPTION_KINDS
                and len(str(description["text"])) <= DESCRIPTION_MAX_CHARS):
            node["descriptionOfficial"] = {
                "text": str(description["text"]),
                "kind": description["kind"],
                "extractedFrom": str(description.get("extractedFrom") or DESCRIPTION_PATHS[description["kind"]]),
                "truncated": bool(description.get("truncated")),
                "fullLength": int(description.get("fullLength") or len(str(description["text"]))),
                "source": SOURCE,
                "listedName": record.get("listedName"),
                "edition": record.get("edition"),
                "package": record.get("package"),
                "granule": record.get("granule"),
                "url": url,
                "documentSha256": record.get("documentSha256"),
            }
            stats["descriptions_published"] += 1
        edition = str(record.get("edition") or "")
        if edition and (not node.get("lastVerified") or edition > str(node.get("lastVerified"))):
            node["lastVerified"] = edition
            node["evidenceVerifiedAt"] = edition
        # Placement: the Manual prints a hierarchy, so its parent entry is a
        # claim about the edge above this node, checked against the tree.
        parent_listed = record.get("parentListedName")
        tree_parent_id = parent_map.get(node_id)
        tree_parent = node_map.get(tree_parent_id or "")
        if not parent_listed:
            stats["top_level"] += 1
        elif tree_parent is not None and canonical_name_key(tree_parent.get("name")) == canonical_name_key(parent_listed):
            if node.get("placementVerified") is True:
                stats["placements_already_evidenced"] += 1
            else:
                node["placementVerified"] = True
                node["placementUrl"] = url
                node["placementVerifiedAt"] = edition or None
                node["placementParentId"] = tree_parent_id
                # The text that names the CHILD as the source prints it, as
                # every other placement route stamps it; the parent's name
                # is in the entry block beside it.
                node["placementMatchedText"] = record.get("listedName")
                node["placementMethod"] = ORG_PLACEMENT_METHOD
                node.pop("placementCheckable", None)
                stats["placements_listed"] += 1
        else:
            other = org_by_key.get(canonical_name_key(parent_listed)) or []
            if len(other) == 1 and other[0] != tree_parent_id:
                node["placementDirectoryDisagreement"] = {
                    "source": SOURCE, "listedUnder": parent_listed,
                    "directoryParentId": other[0], "url": url, "checkedAt": edition or None,
                }
                stats["placements_disagree"] += 1
            else:
                # The Manual's parent is its own scaffolding ("Defense
                # Agencies", "Bureaus") or names nothing here: no claim.
                stats["placements_unresolved"] += 1
        verify_node_sources(node)
        stats["listed"] += 1
    return stats


def load_govman_org_evidence(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """The organisation records, stored beside the post records."""
    import json

    resolved = Path(path or (PROJECT_ROOT / "data" / "verification" / "govman_evidence.json"))
    if not resolved.exists():
        return {}
    store = json.loads(resolved.read_text(encoding="utf-8")) or {}
    orgs = store.get("organisations")
    return {str(k): v for k, v in (orgs or {}).items() if isinstance(v, dict)}


def build_records(
    manual: dict[str, Any],
    root: dict[str, Any],
    *,
    index_tree=None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """One record per post the Manual names under its own organisation.

    Both sides must be unambiguous, which is four separate refusals rather
    than one: the Manual entry must name exactly one organisation in the
    graph; that organisation must answer to exactly one Manual entry; the
    entry's eligible rows must carry the post's name once; and the
    organisation must carry one child of that name. A stamped title that
    appears twice on either side claims nothing.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    children: dict[str, list[dict[str, Any]]] = {}
    for node_id, node in node_map.items():
        parent_id = parent_map.get(node_id)
        if parent_id:
            children.setdefault(parent_id, []).append(node)

    matched, stats = match_organisations(manual, node_map)
    stats.update({
        "posts_listed": 0,
        "refused_title_not_listed": 0, "refused_title_listed_twice": 0,
        "refused_siblings_share_the_name": 0, "refused_name_too_short": 0,
        "refused_no_access_id": 0,
    })

    records: dict[str, dict[str, Any]] = {}
    for org_id, entry in matched.items():
        granule = access_id(manual["package"], entry["entityId"])
        if not granule:
            stats["refused_no_access_id"] += 1
            continue
        rows: dict[str, list[dict[str, str]]] = {}
        for row in entry["titles"]:
            rows.setdefault(canonical_name_key(row["title"]), []).append(row)
        siblings: dict[str, int] = {}
        for child in children.get(org_id, []):
            if is_post_node(child):
                child_key = canonical_name_key(child.get("name"))
                siblings[child_key] = siblings.get(child_key, 0) + 1
        for child in children.get(org_id, []):
            if not is_post_node(child) or not child.get("id"):
                continue
            key = canonical_name_key(child.get("name"))
            if len(key.split()) < MIN_POST_TOKENS:
                stats["refused_name_too_short"] += 1
                continue
            found = rows.get(key)
            if not found:
                stats["refused_title_not_listed"] += 1
                continue
            if len(found) > 1:
                stats["refused_title_listed_twice"] += 1
                continue
            if siblings.get(key, 0) > 1:
                stats["refused_siblings_share_the_name"] += 1
                continue
            records[child["id"]] = {
                "source": SOURCE,
                "nodeName": child.get("name"),
                "listedTitle": found[0]["title"],
                "listedUnder": entry["name"],
                "organisationId": org_id,
                "package": manual["package"],
                "edition": manual["edition"],
                "granule": granule,
                "url": f"{DETAILS_BASE}/{manual['package']}/{granule}",
                "tableFooter": found[0]["footer"] or None,
                "documentSha256": manual["sha256"],
            }
            stats["posts_listed"] += 1
    return records, stats


def apply_govman_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp Manual listings onto the posts they name.

    Runs after `apply_evidence_to_tree`, which has already withdrawn every
    field this module owns, so a record dropped since the last build stops
    being published even though the previous graph is re-fed as a payload.
    A page-based claim on the same node is kept and this is added beside it,
    never over it -- the rule `directories.py` follows.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    from data_pipeline.processors.normalize_nodes import verify_node_sources

    node_map, parent_map = index_tree(root)
    stats = {"listed": 0, "unknown_node": 0, "stale_name": 0, "not_a_post": 0,
             "reparented": 0, "urls_added": 0, "method_kept_from_page": 0,
             "failed_checks_withdrawn": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_post_node(node):
            # The claim is "an agency's entry lists this post". A node that
            # is no longer a post has no claim on it.
            stats["not_a_post"] += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("listedTitle")):
            stats["stale_name"] += 1
            continue
        if parent_map.get(node_id) != record.get("organisationId"):
            # The scope IS the claim: this title was read off one agency's
            # entry, and a post moved to another parent was never checked
            # against that parent's entry.
            stats["reparented"] += 1
            continue
        url = str(record.get("url") or "")
        if not url:
            continue
        if node.get("verificationFailure"):
            # A checked negative is published only where nothing gives the
            # node a source, and this listing is about to.
            if str(node.get("lastVerified") or "") == str(node.get("evidenceVerifiedAt") or ""):
                node.pop("lastVerified", None)
            node.pop("evidenceVerifiedAt", None)
            node.pop("verificationFailure", None)
            node.pop("verificationFailureSource", None)
            node.pop("verificationSiteFrom", None)
            stats["failed_checks_withdrawn"] += 1
        urls = [str(u) for u in (node.get("sourceUrls") or [])]
        if url not in urls:
            urls.append(url)
            stats["urls_added"] += 1
        node["sourceUrls"] = urls
        mine = [str(u) for u in (node.get("evidenceUrls") or [])]
        if url not in mine:
            mine.append(url)
        node["evidenceUrls"] = mine
        types = [str(t) for t in (node.get("sourceTypes") or [])]
        if SOURCE_TYPE not in types:
            types.append(SOURCE_TYPE)
        node["sourceTypes"] = types
        node["govmanListing"] = {
            "source": SOURCE,
            "listedTitle": record.get("listedTitle"),
            "listedUnder": record.get("listedUnder"),
            "edition": record.get("edition"),
            "package": record.get("package"),
            "granule": record.get("granule"),
            "url": url,
            "tableFooter": record.get("tableFooter"),
        }
        if node.get("verificationMethod"):
            # A page read this post's own organisation and labelled it. That
            # is the stronger claim and it stays; the Manual is a second
            # source beside it, which the confidence arithmetic rewards on
            # its own without relabelling the method.
            stats["method_kept_from_page"] += 1
        else:
            node["verificationMethod"] = METHOD
        edition = str(record.get("edition") or "")
        if edition:
            node["lastVerified"] = edition
            node["evidenceVerifiedAt"] = edition
        verify_node_sources(node)
        stats["listed"] += 1
    return stats


def load_govman_evidence(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """The derived records, or nothing when the file is absent."""
    import json

    resolved = Path(path or (PROJECT_ROOT / "data" / "verification" / "govman_evidence.json"))
    if not resolved.exists():
        return {}
    store = json.loads(resolved.read_text(encoding="utf-8")) or {}
    nodes = store.get("nodes")
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}
