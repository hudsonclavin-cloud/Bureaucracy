"""Who pays a post, where a committed official document says it is not the
federal government: the posts of the sixteen Department of Energy national
laboratories that a contractor operates.

## The owner's decision, and the claim it supports (2026-10-07)

A post with no pay claim is counted as an unpriced post a research pass
should find a salary for. For some posts no federal pay document will ever
name the title, because the people who hold them are not paid on a federal
pay schedule at all. The owner's decision was to say so for a post only where
a committed official document establishes it. This module is that, for one
case, and the claim is deliberately narrower than "not federally paid" reads.

## Three documents, each saying one part

1. **The operator.** NETL's own page, "The NETL Unique Advantage of Being a
   Government-Owned, Government-Operated Laboratory" (May 22, 2023,
   `tests/fixtures/doe/netl_operating_model.html`): "The U.S. Department of
   Energy operates 17 national laboratories. NETL is the only government-owned,
   government-operated facility. The other 16 are government-owned,
   contractor-operated." It names only NETL.

2. **Which sixteen.** DOE's own index of its laboratories
   (`www.energy.gov/national-laboratories`, `tests/fixtures/doe/
   national_laboratories.html`) prints "The Energy Department's 17 National
   Labs" and labels each of the seventeen as an accordion heading; it says of
   NETL alone that it "is government-owned and government-operated (GOGO)".
   `CONTRACTOR_OPERATED_LABS` maps each of this graph's sixteen other lab
   nodes to the label that page prints for it. The table is reviewed and keyed
   by node id, and it is re-checked against the page on every run: the page
   must label exactly seventeen laboratories, the sixteen rows plus NETL must
   be those seventeen labels exactly, and each node must still carry a name
   that reduces to its label. So "the other 16" is read off DOE's page, not
   inferred from the graph's own grouping.

3. **What an operator's staff are.** "Operated by a contractor" is a
   statement about the operator, not literally about who employs each post.
   The Department of Energy Acquisition Regulation, 48 CFR part 970 (GPO's
   2025 edition on www.govinfo.gov, `tests/fixtures/doe/
   dear_48_cfr_970_govinfo2025.xml`), closes most of that gap in its own
   words: DOE "has negotiated technology transfer clauses with the
   contractors managing and operating its laboratories" (970.2770-3);
   "Employees of a management and operating contractor are entitled to the
   same rights and privileges with respect to outside employment as other
   citizens" (970.0371-7); and "the compensation paid individual employees
   should be left to the judgment of contractors subject to the limitations
   of DOE-approved compensation policies, programs, classification systems,
   and schedules" (970.3102-506). The same part says the other thing a reader
   must not lose: "The contracts are totally financed by DOE advance
   payments" (970.3102-370). So the pay is a contract cost DOE finances, set
   by the contractor -- not a federal salary on a federal schedule. That is
   what `federallyPaid: false` means here, and the published sentence says
   so in words.

What no document here states: who holds a given post, or that every holder
is the contractor's employee (a laboratory can host people employed by
someone else). And the seven curated titles are the same template under all
seventeen laboratory nodes, not titles any laboratory's own documents print.
The block's `notEstablished` sentence carries both.

## NETL's posts are left alone

NETL is the government-owned, government-operated one. Its posts are federal
and stay unpriced: nothing here writes the block on them, and the gate
refuses it there.

## What it writes, and does not

`positionEmployer` on each Position node DIRECTLY under one of the sixteen
laboratory nodes, nothing else. It writes no `sourceUrls`, `sourceTypes`,
`lastVerified` or `verificationMethod` -- the channel by which a five-row pay
table carried 29 positions to `verified` on 2026-09-11 -- no cost field and
no pay field. A post some pay document has priced is left alone. The field
is in `evidence.EVIDENCE_OWNED_FIELDS`, so a withdrawn record is withdrawn on
the next build.

Every fixture's digest is recomputed from the bytes before it is read, and
every quote is re-found in the document's text on every run.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "doe"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "employment_status_evidence.json"

FIELD = "positionEmployer"
KIND = "contractor_operated_laboratory"
METHOD = "laboratory_doe_states_is_contractor_operated"
SOURCE = "doe_contractor_operated_laboratories"

LABS_GROUP_ID = "exec-dept-doe-natl-labs"
LAB_TYPE = "National Laboratory"
NETL_ID = "exec-dept-doe-national-energy-technology-laboratory"
NETL_NAME = "National Energy Technology Laboratory"
NETL_LISTED_AS = "National Energy Technology Laboratory"

#: The count both DOE documents print. Not a constant anybody tunes: the
#: module refuses a page that labels any other number.
LABORATORY_COUNT = 17
CONTRACTOR_OPERATED_COUNT = 16

#: node id -> the name the row was written against, and the label DOE's index
#: prints for that laboratory. Reviewed, keyed by id, re-checked every run.
CONTRACTOR_OPERATED_LABS: dict[str, dict[str, str]] = {
    "exec-dept-doe-ames-national-laboratory": {
        "nodeName": "Ames National Laboratory", "listedAs": "Ames National Laboratory"},
    "exec-dept-doe-argonne-national-laboratory": {
        "nodeName": "Argonne National Laboratory", "listedAs": "Argonne National Laboratory"},
    "exec-dept-doe-brookhaven-national-laboratory": {
        "nodeName": "Brookhaven National Laboratory", "listedAs": "Brookhaven National Laboratory"},
    "exec-dept-doe-fermi-national-accelerator-laboratory": {
        "nodeName": "Fermi National Accelerator Laboratory", "listedAs": "Fermi National Accelerator Laboratory"},
    "exec-dept-doe-idaho-national-laboratory": {
        "nodeName": "Idaho National Laboratory", "listedAs": "Idaho National Laboratory"},
    "exec-dept-doe-lawrence-berkeley-national-laboratory": {
        "nodeName": "Lawrence Berkeley National Laboratory", "listedAs": "Lawrence Berkeley National Laboratory"},
    "exec-dept-doe-lawrence-livermore-national-laboratory": {
        "nodeName": "Lawrence Livermore National Laboratory", "listedAs": "Lawrence Livermore National Laboratory"},
    "exec-dept-doe-los-alamos-national-laboratory": {
        "nodeName": "Los Alamos National Laboratory", "listedAs": "Los Alamos National Laboratory"},
    "exec-dept-doe-national-renewable-energy-laboratory": {
        "nodeName": "National Laboratory of the Rockies (NLR)", "listedAs": "National Laboratory of the Rockies"},
    "exec-dept-doe-oak-ridge-national-laboratory": {
        "nodeName": "Oak Ridge National Laboratory", "listedAs": "Oak Ridge National Laboratory"},
    "exec-dept-doe-pacific-northwest-national-laboratory": {
        "nodeName": "Pacific Northwest National Laboratory", "listedAs": "Pacific Northwest National Laboratory"},
    "exec-dept-doe-princeton-plasma-physics-laboratory": {
        "nodeName": "Princeton Plasma Physics Laboratory", "listedAs": "Princeton Plasma Physics Laboratory"},
    "exec-dept-doe-sandia-national-laboratories": {
        "nodeName": "Sandia National Laboratories", "listedAs": "Sandia National Laboratories"},
    "exec-dept-doe-savannah-river-national-laboratory": {
        "nodeName": "Savannah River National Laboratory", "listedAs": "Savannah River National Laboratory"},
    "exec-dept-doe-slac-national-accelerator-laboratory": {
        "nodeName": "SLAC National Accelerator Laboratory", "listedAs": "SLAC National Accelerator Laboratory"},
    "exec-dept-doe-thomas-jefferson-national-accelerator-facility": {
        "nodeName": "Thomas Jefferson National Accelerator Facility",
        "listedAs": "Thomas Jefferson National Accelerator Facility"},
}

#: The ten fields a pay document writes on a post. A post carrying any of
#: them is left alone: a pay claim and an employer claim on one post would be
#: two sources disagreeing about who pays it, and nothing here resolves that.
PAY_FIELDS = (
    "positionPayRate", "positionGradePay", "positionCurrentPay", "positionSchedulePay",
    "positionStatutoryPay", "positionDerivedPay", "positionTierPay", "positionTierReferencePay",
    "positionMilitaryPay", "positionReportedPay",
)
MEASURED_COST_STATUSES = ("official", "root_total", "scaled_official")

OPERATOR_PAGE_DATE = "May 22, 2023"

#: role -> the committed document and what is quoted from it. Every quote is
#: re-found on every run; a CFR quote is re-found inside the one SECTION whose
#: SECTNO it names, never anywhere in the part. Each quote is the shortest
#: verbatim span that carries its part of the claim: the block rides on 112
#: posts in the viewer copy, which must stay under half the full graph.
#: `publisher` and `says` go to the evidence file's report, not onto a node.
DOCUMENTS: dict[str, dict[str, Any]] = {
    "operator": {
        "fixture": "netl_operating_model.html",
        "format": "html",
        "title": "The NETL Unique Advantage of Being a Government-Owned, Government-Operated Laboratory",
        "publisher": "National Energy Technology Laboratory, U.S. Department of Energy",
        "dated": OPERATOR_PAGE_DATE,
        "says": "which of DOE's laboratories a contractor operates",
        "quotes": [
            {"text": "The U.S. Department of Energy operates 17 national laboratories. NETL is the only "
                     "government-owned, government-operated facility. The other 16 are government-owned, "
                     "contractor-operated."},
        ],
    },
    "laboratories": {
        "fixture": "national_laboratories.html",
        "format": "html",
        "title": "National Laboratories (energy.gov)",
        "publisher": "U.S. Department of Energy",
        "dated": None,
        "says": "which seventeen laboratories DOE counts, by name, and that NETL is the government-operated one",
        "quotes": [
            {"text": "The Energy Department's 17 National Labs"},
            {"text": "NETL is government-owned and government-operated (GOGO)"},
        ],
    },
    "regulation": {
        "fixture": "dear_48_cfr_970_govinfo2025.xml",
        "format": "cfr_xml",
        "title": "48 CFR part 970 (Department of Energy Acquisition Regulation)",
        "publisher": "U.S. Government Publishing Office (Code of Federal Regulations)",
        "dated": None,
        "says": "that DOE's laboratories are run by management and operating contractors, what such a contractor "
                "does about its employees' pay, and who finances the contract",
        "quotes": [
            {"section": "970.2770-3",
             "text": "DOE has negotiated technology transfer clauses with the contractors managing and operating "
                     "its laboratories."},
            {"section": "970.0371-7",
             "text": "Employees of a management and operating contractor are entitled to the same rights and "
                     "privileges with respect to outside employment as other citizens."},
            {"section": "970.3102-506",
             "text": "Generally, the compensation paid individual employees should be left to the judgment of "
                     "contractors subject to the limitations of DOE-approved compensation policies, programs, "
                     "classification systems, and schedules"},
            {"section": "970.3102-370",
             "text": "The contracts are totally financed by DOE advance payments"},
        ],
    },
}

#: The three sentences the panel prints. Generated, never edited per node;
#: the gate mirrors each template, because a sentence the panel prints as the
#: reason is a claim like any figure.
HEADLINE_TEMPLATE = (
    "Not on a federal pay schedule: {laboratory} is one of the 16 DOE laboratories operated by a contractor "
    "(DOE, NETL page, May 22, 2023)."
)
#: What the documents DO establish is not paraphrased onto the node: the
#: block carries their own words, and the panel prints those quotes verbatim
#: beside the headline. (A paraphrase would also cost about 330 bytes on each
#: of 112 nodes, and the viewer copy must stay under half the full graph.)
NOT_ESTABLISHED = (
    "No document here names who holds this post or says every holder is the contractor's employee, and the "
    "title is a template every DOE laboratory node carries. Not federally paid means not paid as a federal "
    "employee on a federal pay schedule; the money is DOE's, through the contract."
)


class Unreadable(ValueError):
    """A committed document could not be read as this module expects."""


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


class _TextParser(HTMLParser):
    """Visible text of a page, scripts and styles dropped, and the labels of
    DOE's laboratory accordion (a <button> whose aria-controls names an
    `energy-accordion` panel)."""

    _SKIP = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.labels: list[str] = []
        self._skip = 0
        self._label: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip += 1
            return
        self.parts.append(" ")
        if tag == "button":
            attributes = {k: (v or "") for k, v in attrs}
            if "usa-accordion__button" in attributes.get("class", "").split() and attributes.get(
                "aria-controls", ""
            ).startswith("energy-accordion"):
                self._label = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        self.parts.append(" ")
        if tag == "button" and self._label is not None:
            self.labels.append(_collapse("".join(self._label)))
            self._label = None

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.parts.append(data)
        if self._label is not None:
            self._label.append(data)


def _read_fixture(name: str, directory: Path) -> tuple[bytes, dict[str, Any]]:
    path = Path(directory) / name
    meta_path = path.with_name(path.name + ".meta.json")
    try:
        raw = path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Unreadable(f"{path.name}: {error}") from error
    digest = hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        raise Unreadable(f"{path.name}: sha256 {digest} is not the {meta.get('sha256')} its fetch recorded")
    if int(meta.get("status") or 0) != 200 or meta.get("error"):
        raise Unreadable(f"{path.name}: its fetch did not record a clean 200")
    if str(meta.get("final_url") or "") != str(meta.get("url") or ""):
        raise Unreadable(f"{path.name}: served from {meta.get('final_url')}, not the address recorded")
    return raw, meta


def _cfr_sections(raw: bytes) -> tuple[dict[str, list[str]], str]:
    """SECTNO -> the text of each SECTION carrying it, and the edition date."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise Unreadable(f"48 CFR part 970: {error}") from error
    sections: dict[str, list[str]] = {}
    for section in root.iter("SECTION"):
        number = _collapse(section.findtext("SECTNO") or "")
        sections.setdefault(number, []).append(_collapse(html.unescape(" ".join(section.itertext()))))
    date = _collapse(root.findtext("./FDSYS/DATE") or "")
    return sections, date


def load_documents(directory: str | Path = FIXTURE_DIR) -> dict[str, dict[str, Any]]:
    """Read the three documents, digests recomputed, every quote re-found.
    Raises Unreadable rather than returning a partial reading."""
    directory = Path(directory)
    out: dict[str, dict[str, Any]] = {}
    for role, spec in DOCUMENTS.items():
        raw, meta = _read_fixture(spec["fixture"], directory)
        doc: dict[str, Any] = {
            "role": role,
            "title": spec["title"],
            "publisher": spec["publisher"],
            "dated": spec["dated"],
            "says": spec["says"],
            "url": str(meta.get("url")),
            "sha256": str(meta.get("sha256")),
            "fetchedAt": str(meta.get("fetched_at")),
            "fixture": f"doe/{spec['fixture']}",
        }
        if spec["format"] == "html":
            parser = _TextParser()
            parser.feed(raw.decode("utf-8"))
            text = _collapse("".join(parser.parts))
            for quote in spec["quotes"]:
                if quote["text"] not in text:
                    raise Unreadable(f"{spec['fixture']} no longer prints: {quote['text']!r}")
            # A dated page must still print its title and date: the panel
            # cites it by both.
            if spec["dated"]:
                for extra in (spec["title"], spec["dated"]):
                    if extra not in text:
                        raise Unreadable(f"{spec['fixture']} no longer prints {extra!r}")
            doc["labels"] = parser.labels
        else:
            sections, date = _cfr_sections(raw)
            for quote in spec["quotes"]:
                found = sections.get(quote["section"]) or []
                if len(found) != 1:
                    raise Unreadable(f"48 CFR {quote['section']}: {len(found)} sections carry that number, not one")
                if quote["text"] not in found[0]:
                    raise Unreadable(f"48 CFR {quote['section']} no longer prints: {quote['text']!r}")
            doc["edition"] = f"Code of Federal Regulations, title 48, revised as of {date}" if date else None
        doc["quotes"] = [dict(q) for q in spec["quotes"]]
        out[role] = doc
    labels = out["laboratories"].pop("labels")
    out["operator"].pop("labels", None)
    if len(labels) != LABORATORY_COUNT or len(set(labels)) != LABORATORY_COUNT:
        raise Unreadable(f"DOE's index labels {len(labels)} laboratories, not the {LABORATORY_COUNT} it states")
    expected = {row["listedAs"] for row in CONTRACTOR_OPERATED_LABS.values()} | {NETL_LISTED_AS}
    if set(labels) != expected:
        raise Unreadable(
            "DOE's index no longer labels exactly the reviewed laboratories: "
            f"missing {sorted(expected - set(labels))}, unexpected {sorted(set(labels) - expected)}"
        )
    out["laboratories"]["laboratoryLabels"] = list(labels)
    return out


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def _is_post(node: Mapping[str, Any]) -> bool:
    text = str(node.get("type") or "").casefold()
    return any(word in text for word in ("position", "role", "office holder"))


#: What a node's block carries of each document. The rest (publisher, what
#: the document says, the fixture path, the edition) is in the evidence
#: file's report, once.
PUBLISHED_DOCUMENT_KEYS = ("role", "title", "url", "sha256", "fetchedAt", "dated", "quotes")


def _published_documents(documents: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    order = ("operator", "laboratories", "regulation")
    return [
        {key: documents[role][key] for key in PUBLISHED_DOCUMENT_KEYS
         if documents[role].get(key) is not None}
        for role in order
    ]


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str | None],
    *,
    read_on: str,
    directory: str | Path = FIXTURE_DIR,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per Position directly under one of the sixteen laboratory
    nodes. Each laboratory row is re-adjudicated: the node still exists under
    the laboratories grouping, is still typed a laboratory, still carries the
    name the row was written against, and that name still reduces to the
    label DOE's index prints."""
    from data_pipeline.exporter.build_graph import canonical_name_key

    documents = load_documents(directory)
    published = _published_documents(documents)
    records: dict[str, dict[str, Any]] = {}
    refused_labs: dict[str, str] = {}
    refused_posts: dict[str, str] = {}

    netl = node_map.get(NETL_ID)
    if netl is None or canonical_name_key(netl.get("name")) != canonical_name_key(NETL_LISTED_AS):
        raise Unreadable("NETL's node is missing or renamed; the sixteen are only 'the other 16' beside it")
    children_of: dict[str, list[str]] = {}
    for child_id, parent_id in parent_map.items():
        if parent_id:
            children_of.setdefault(str(parent_id), []).append(child_id)
    netl_posts = sorted(c for c in children_of.get(NETL_ID, []) if _is_post(node_map.get(c) or {}))

    for lab_id, row in sorted(CONTRACTOR_OPERATED_LABS.items()):
        lab = node_map.get(lab_id)
        if lab is None:
            refused_labs[lab_id] = "node not in the graph"
            continue
        if parent_map.get(lab_id) != LABS_GROUP_ID:
            refused_labs[lab_id] = f"not under {LABS_GROUP_ID}"
            continue
        if str(lab.get("type") or "") != LAB_TYPE:
            refused_labs[lab_id] = f"typed {lab.get('type')!r}, not {LAB_TYPE!r}"
            continue
        if str(lab.get("name") or "") != row["nodeName"]:
            refused_labs[lab_id] = f"renamed since the row was written (row: {row['nodeName']!r}, node: {lab.get('name')!r})"
            continue
        if canonical_name_key(lab.get("name")) != canonical_name_key(row["listedAs"]):
            refused_labs[lab_id] = f"its name does not reduce to DOE's label {row['listedAs']!r}"
            continue
        if str(lab.get("lifecycle") or "") == "superseded":
            refused_labs[lab_id] = "marked superseded"
            continue
        for post_id in sorted(children_of.get(lab_id, [])):
            post = node_map.get(post_id) or {}
            if not _is_post(post):
                continue
            present = [field for field in PAY_FIELDS if field in post]
            if present:
                refused_posts[post_id] = f"already carries a pay claim ({', '.join(present)})"
                continue
            laboratory = str(lab.get("name"))
            records[post_id] = {
                "nodeId": post_id,
                "nodeName": str(post.get("name") or ""),
                "federallyPaid": False,
                "kind": KIND,
                "method": METHOD,
                "laboratoryId": lab_id,
                "laboratoryName": laboratory,
                "laboratoryListedAs": row["listedAs"],
                "headline": HEADLINE_TEMPLATE.format(laboratory=laboratory),
                "notEstablished": NOT_ESTABLISHED,
                "documents": published,
                "documentCount": len({doc["url"] for doc in published}),
                "readOn": read_on,
            }
    report = {
        "source": SOURCE,
        "documents": {
            role: {key: value for key, value in doc.items() if key not in ("quotes", "laboratoryLabels")}
            for role, doc in documents.items()
        },
        "laboratoryLabels": documents["laboratories"]["laboratoryLabels"],
        "reviewedLaboratories": len(CONTRACTOR_OPERATED_LABS),
        "laboratoriesRefused": refused_labs,
        "postsWithTheBlock": len(records),
        "postsRefused": refused_posts,
        "netlPostsLeftAlone": len(netl_posts),
    }
    return records, report


def apply_employment_status(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, int]:
    """Stamp `positionEmployer` on each record's post. Run after every pay
    pass and the multi-post sweep, so "no pay field" is read off the final
    tree. The parent is read off the tree, never off `parentId`."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {"stamped": 0, "unknown_node": 0, "not_a_post": 0, "renamed_since_the_derivation": 0,
             "moved_since_the_derivation": 0, "under_netl": 0, "not_a_reviewed_laboratory": 0,
             "carries_a_pay_claim": 0, "beside_a_measured_cost": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not _is_post(node):
            stats["not_a_post"] += 1
            continue
        if str(node.get("name") or "") != str(record.get("nodeName") or ""):
            stats["renamed_since_the_derivation"] += 1
            continue
        parent_id = parent_map.get(node_id)
        if parent_id == NETL_ID:
            stats["under_netl"] += 1
            continue
        if parent_id != record.get("laboratoryId"):
            stats["moved_since_the_derivation"] += 1
            continue
        if parent_id not in CONTRACTOR_OPERATED_LABS:
            stats["not_a_reviewed_laboratory"] += 1
            continue
        if any(field in node for field in PAY_FIELDS):
            stats["carries_a_pay_claim"] += 1
            continue
        if str(node.get("cost_status") or "") in MEASURED_COST_STATUSES:
            stats["beside_a_measured_cost"] += 1
            continue
        node[FIELD] = {
            "federallyPaid": False,
            "kind": KIND,
            "method": METHOD,
            "laboratoryId": record.get("laboratoryId"),
            "laboratoryName": record.get("laboratoryName"),
            "laboratoryListedAs": record.get("laboratoryListedAs"),
            "headline": record.get("headline"),
            "notEstablished": record.get("notEstablished"),
            "documents": json.loads(json.dumps(record.get("documents") or [])),
            "documentCount": record.get("documentCount"),
            "readOn": record.get("readOn"),
        }
        stats["stamped"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod, any cost field, any pay field.
    return stats
