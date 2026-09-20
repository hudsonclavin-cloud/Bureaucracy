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
        })
    return {"package": package, "edition": edition_date(package), "sha256": loaded["sha256"],
            "url": loaded["url"], "fetchedAt": loaded["fetchedAt"], "entities": entities}


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
        "entry_names_no_node": 0, "posts_listed": 0,
        "refused_title_not_listed": 0, "refused_title_listed_twice": 0,
        "refused_siblings_share_the_name": 0, "refused_name_too_short": 0,
        "refused_no_access_id": 0,
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
