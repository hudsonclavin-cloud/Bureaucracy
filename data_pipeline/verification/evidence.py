"""Existence evidence for curated nodes.

The base graph names 5,170 units and positions and carries no source for any
of them. This module is the one route by which a curated node earns a source
without a human: an official .gov/.mil page is fetched on a date, the page is
searched for the node's name, and the outcome is recorded in a sidecar file
keyed by node id.

The evidence standard is deliberately strict: the page must name the unit as
a LABEL OF ITS OWN — a heading, a link, a list item whose text is the name —
not merely contain the name somewhere in prose. An earlier version searched
the whole page as one canonicalised string, and an adversarial review found
three independent ways that manufactures false confirmations:

  * "Engineering (ENG)" canonicalises to "engineering", which appears in
    any sentence about NSF's mission. 22 curated organisations reduce to a
    single common word ("Defense", "Energy", "Personnel").
  * "Office of Science" is a word-bounded prefix of "Office of Science and
    Technology Policy", so a page about OSTP confirmed the DOE office.
  * The page text was joined with spaces across DOM elements, so a phrase
    spanning two unrelated elements matched a string that is nowhere on the
    page.

Label equality answers all three: prose is not a label, a longer name is not
equal to a shorter one, and a fragment is one element's text.

A fourth was found on the 2026-09-06 run, when 48 more hosts became
reachable: `title` and `aria-label` were harvested from every element,
including ones that render nothing. www.fmc.gov and www.sba.gov both ship
<link rel="alternate" title="Federal Maritime Commission » Feed"> in <head>,
and the separator split leaves exactly the unit's name — a label from markup
no visitor can see. Both pages happened to carry a real heading too, so no
published confirmation rested on it; the harvest is now limited to elements
that render (see LabelParser.METADATA_TAGS).

Four statuses, and what each is allowed to claim:

  confirmed     a fragment of the fetched page is this unit's name
  not_found     the unit's OWN page was read and no fragment named it
  inconclusive  only an ancestor's page was read and it did not name the
                unit — which is no evidence either way, because a parent's
                About page is not required to list its children
  fetch_failed  no page was read: blocked network, 404, a 200 with no
                readable body, a host that is not official
  not_checkable the curated name cannot be evidence of anything (a curator's
                label like "Individual Senator Offices (100)")

Only `confirmed` and `not_found` are applied to a node. The other three
record what was attempted and change nothing, because nothing was learned.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.json_io import load_json_file
from data_pipeline.processors.normalize_nodes import classify_source_url, verify_node_sources


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "evidence.json"
DEFAULT_SITES_PATH = PROJECT_ROOT / "data" / "verification" / "official_sites.json"

CONFIRMED = "confirmed"
NOT_FOUND = "not_found"
INCONCLUSIVE = "inconclusive"
# Why a check came back inconclusive rather than negative.
REASON_ANCESTOR_PAGE = "only_an_ancestor_page_was_read"
REASON_NAMED_NOT_LABELLED = "named_on_the_page_but_not_as_a_label"
FETCH_FAILED = "fetch_failed"
NOT_CHECKABLE = "not_checkable"
APPLIED_STATUSES = (CONFIRMED, NOT_FOUND)

METHOD_OWN_PAGE = "name_labelled_on_own_official_page"
METHOD_PARENT_PAGE = "name_labelled_on_parent_official_page"
# Fields this module owns. They are cleared from every node before the current
# evidence is applied, so a record that is withdrawn, downgraded or deleted
# stops being published. Without this the previously published graph.json —
# which the exporter re-feeds as a payload on every run — made any claim
# permanent and no retraction could ever reach the site.
EVIDENCE_OWNED_FIELDS = (
    "verificationMethod",
    "verificationFailure",
    "verificationSiteFrom",
    "placementVerified",
    "placementUrl",
    "placementVerifiedAt",
    "placementParentId",
    "placementMatchedText",
    "placementMethod",
    "placementCheckable",
    # Exactly the URLs this module put on the node, so the next build can
    # remove exactly those and nothing else. The first version cleared the
    # node's whole list, which stripped the Treasury FiscalData URL from 26
    # measured nodes and left the Supreme Court citing a court About page as
    # the source of its outlays.
    "evidenceUrls",
    # The date this module set as lastVerified, so a withdrawal can take back
    # exactly that date and leave one a crawler record supplied.
    "evidenceVerifiedAt",
)
PLACEMENT_METHOD = "name_labelled_on_parent_official_page"
# A record created by the placement pass for a node whose own page was never
# read. It carries no existence claim and the existence pass applies nothing.
PLACEMENT_ONLY = "placement_only"
# Placement: evidence for the parent -> child EDGE, which is a different claim
# from either node's existence. A hierarchy is the site's central assertion
# and the one thing nothing had ever checked. The only evidence this module
# accepts for an edge is the parent's own official page naming the child as a
# label. Silence on that page is recorded (auditable) and claims nothing: a
# department's About page is not obliged to list every bureau.
PLACEMENT_LISTED = "listed"
PLACEMENT_NOT_LISTED = "not_listed"

# A fetched page has to yield some readable text before "we read it and the
# name was not there" is an honest thing to say. A JS-only shell, an empty
# body and a bot-challenge interstitial all return 200 with nearly nothing.
MIN_READABLE_CHARS = 400

# Text nodes are split on these before comparison, so "Office of Science —
# Advancing discovery" offers "Office of Science" as a label.
LABEL_SEPARATORS = re.compile(r"\s*[—–|·•:>›»/·]\s*|\s+[-–]\s+|\n+")
# Bounded scaffolding a real heading may wrap a name in: "About the U.S.
# Department of Energy" is the Department's own H1, not a sentence about it.
SCAFFOLD_TOKENS = frozenset(
    "about the a an our welcome to home homepage official website site page of us u s united states usa gov "
    "overview mission history contact leadership organization organisation".split()
)
MAX_SCAFFOLD_TOKENS = 5
# A curated label rather than an organisation's name: no official page can
# contain "Individual Senator Offices (100)", and publishing "we read the page
# and it was not there" about one asserts a failed existence check against a
# body that plainly exists.
COUNT_LABEL_PATTERN = re.compile(r"\(\s*[≈~]?\d[\d,]*\s*\+?\s*(?:[A-Za-z .&-]{0,30})?\)|\(\s*\d+\s*\)|\b\d+\s*\+")
GENERIC_SINGLE_TOKENS = frozenset(
    "defense energy personnel cybersecurity seapower airland constitution security policy operations "
    "administration management leadership committees districts offices staff research development "
    "science engineering geosciences education health justice labor commerce interior state treasury".split()
)

Fetcher = Callable[[str], str]


class LabelParser(HTMLParser):
    """Collect each element's text separately.

    Not the directory crawler's TextFragmentParser: that one skips nav,
    header, footer and title, which on an agency site is exactly where the
    sub-office list and the page's own H1 live — it would have made the
    evidence reader systematically unable to see the evidence. Only markup
    that is never displayed text is skipped here.
    """

    SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
    # `title`/`aria-label` name a thing a reader can see. On these elements
    # they name nothing: the element renders no box at all. www.fmc.gov and
    # www.sba.gov both carry <link rel="alternate" title="Federal Maritime
    # Commission » Feed"> in <head>, and LABEL_SEPARATORS splits that at "»"
    # into exactly the unit's name — a confirmation out of head metadata no
    # visitor ever sees. Worse, find_label returns the FIRST match in
    # document order, so on a page whose head precedes its visible heading
    # the recorded matchedText would be text an auditor cannot find on the
    # live page, which is the one thing that field exists to make possible.
    METADATA_TAGS = {
        "link", "meta", "base", "head", "html", "title",
        "script", "style", "noscript", "template", "param", "source", "track",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        # A link's accessible name is a label even when its text is an icon —
        # but only where there is something on the page to label.
        if tag in self.METADATA_TAGS or self._skip_depth:
            return
        for key, value in attrs:
            if key in ("title", "aria-label") and value and value.strip():
                self.fragments.append(" ".join(value.split()))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.fragments.append(text)


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def load_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    records = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else payload
    return {str(k): v for k, v in records.items() if isinstance(v, dict) and not str(k).startswith("_")}


def load_official_sites(path: str | Path | None) -> dict[str, list[str]]:
    """node id -> candidate official URLs. A candidate is something to fetch,
    not a claim: the file says so in its own `_note`."""
    if path is None:
        return {}
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    sites: dict[str, list[str]] = {}
    for node_id, value in payload.items():
        if str(node_id).startswith("_"):
            continue
        urls = value if isinstance(value, list) else [value]
        cleaned = [str(u).strip() for u in urls if isinstance(u, str) and u.strip().startswith("http")]
        if cleaned:
            sites[str(node_id)] = cleaned
    return sites


def candidate_urls(
    node_id: str, parent_map: dict[str, str], sites: dict[str, list[str]]
) -> tuple[list[str], str | None, int]:
    """The node's own official site, else the nearest ancestor's.

    Returns (urls, id of the node whose site was used, how many levels up it
    was found). The distance matters to what a miss means: a unit absent from
    its own page is a real negative; a unit absent from its parent's About
    page is nothing at all."""
    current: str | None = node_id
    distance = 0
    while current:
        if current in sites:
            return list(sites[current]), current, distance
        current = parent_map.get(current)
        distance += 1
    return [], None, distance


def page_fragments(html: str) -> list[str]:
    parser = LabelParser()
    parser.feed(html)
    return parser.fragments


def uncheckable_reason(name: str) -> str | None:
    """Why this curated name could never be evidence, or None if it can be."""
    text = str(name or "").strip()
    if not text:
        return "empty_name"
    if COUNT_LABEL_PATTERN.search(text):
        return "curated_count_label"
    key = canonical_name_key(text)
    if not key:
        return "no_canonical_key"
    tokens = key.split()
    if any(any(ch.isdigit() for ch in token) for token in tokens):
        return "curated_count_label"
    if len(tokens) == 1 and (len(key) < 4 or key in GENERIC_SINGLE_TOKENS):
        # "Energy", "Defense", "Personnel": a page using the word is not a
        # page naming the unit, and a bare word cannot distinguish them.
        return "name_too_generic"
    return None


def label_matches(key: str, fragment: str) -> bool:
    """Is this fragment the name, rather than text that contains the name?"""
    for part in LABEL_SEPARATORS.split(fragment):
        candidate = canonical_name_key(part)
        if not candidate:
            continue
        if candidate == key:
            return True
        # A heading may wrap the name in bounded scaffolding, but nothing else.
        if candidate.endswith(" " + key):
            prefix = candidate[: -len(key) - 1].split()
            if prefix and len(prefix) <= MAX_SCAFFOLD_TOKENS and all(t in SCAFFOLD_TOKENS for t in prefix):
                return True
        if candidate.startswith(key + " "):
            suffix = candidate[len(key) + 1 :].split()
            if suffix and len(suffix) <= MAX_SCAFFOLD_TOKENS and all(t in SCAFFOLD_TOKENS for t in suffix):
                return True
    return False


def name_appears_unlabelled(name: str, fragments: list[str]) -> bool:
    """Is the unit's name anywhere in this page's text, even if not as a label?

    Deliberately loose — it joins fragments, so it will match a phrase that
    spans two elements. That looseness is safe here and nowhere else: this
    answers "may we say the page does not name it?", and a false positive
    only makes the record more cautious. It must never be used to confirm.
    """
    key = canonical_name_key(name)
    if not key:
        return False
    haystack = canonical_name_key(" ".join(fragments))
    return bool(haystack) and key in haystack


def find_label(name: str, fragments: list[str]) -> str | None:
    """The page fragment that is this node's name, verbatim, or None.

    The returned string is text as it appears on the page — not a
    canonicalised slice — so a human auditing evidence.json can search for it
    on the live page.
    """
    if uncheckable_reason(name):
        return None
    key = canonical_name_key(name)
    for fragment in fragments:
        if label_matches(key, fragment):
            return fragment[:200]
    return None


def verify_node(
    node: dict[str, Any],
    urls: list[str],
    *,
    fetch: Fetcher,
    now: str | None = None,
    site_from: str | None = None,
    is_own_page: bool = False,
) -> dict[str, Any]:
    """Fetch each candidate URL and look for the node's name as a label.

    The record is the outcome of the checks that were actually made. Every
    URL whose page labelled the node is kept; when none did, the status says
    which of the four negative cases happened rather than collapsing them.
    """
    checked_at = now or utc_now_iso()
    name = str(node.get("name") or "")
    record: dict[str, Any] = {
        "name": name,
        "checkedAt": checked_at,
        "siteFrom": site_from,
        "ownPage": bool(is_own_page),
    }
    reason = uncheckable_reason(name)
    if reason:
        record["status"] = NOT_CHECKABLE
        record["reason"] = reason
        return record

    confirmed: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    pages_fragments: list[list[str]] = []
    pages_read = 0
    for url in urls:
        if classify_source_url(url) != "official_site":
            failures.append({"url": url, "reason": "not_an_official_host"})
            continue
        try:
            html = fetch(url)
        except Exception as error:  # noqa: BLE001 — any failure is evidence of a failed fetch
            failures.append({"url": url, "reason": f"{error.__class__.__name__}: {error}"[:200]})
            continue
        fragments = page_fragments(html)
        if sum(len(f) for f in fragments) < MIN_READABLE_CHARS:
            # 200 OK with no readable body: a JS shell, a bot challenge, a
            # soft 404. Nobody read this page, so nothing may be concluded.
            failures.append({"url": url, "reason": "no_readable_text"})
            continue
        pages_read += 1
        pages_fragments.append(fragments)
        matched = find_label(name, fragments)
        if matched:
            confirmed.append({"url": url, "matchedText": matched})
        else:
            failures.append({"url": url, "reason": "name_not_labelled_on_page"})

    if confirmed:
        record["status"] = CONFIRMED
        record["sources"] = confirmed
        record["method"] = METHOD_OWN_PAGE if is_own_page else METHOD_PARENT_PAGE
    elif pages_read == 0:
        record["status"] = FETCH_FAILED
    elif not is_own_page:
        # An ancestor's page is not obliged to list this unit. Its silence is
        # not evidence that the unit does not exist.
        record["status"] = INCONCLUSIVE
        record["reason"] = REASON_ANCESTOR_PAGE
    elif any(name_appears_unlabelled(name, frags) for frags in pages_fragments):
        # The unit's own page names it, just not as a heading, link or list
        # item. That is a fact about this matcher, not about the unit, and
        # publishing "its official page did not name it" would overstate it:
        # cia.gov/about does say "Central Intelligence Agency", in a sentence.
        # The loose test is used ONLY to withhold a negative claim, never to
        # make a positive one, so it can lower the count and never raise it.
        record["status"] = INCONCLUSIVE
        record["reason"] = REASON_NAMED_NOT_LABELLED
    else:
        # The name is nowhere on the page in any form. epa.gov/aboutepa calls
        # itself "US EPA" throughout and never spells the agency out.
        record["status"] = NOT_FOUND
    record["pagesRead"] = pages_read
    if failures:
        record["failures"] = failures
    return record


def verify_placement(
    node: dict[str, Any],
    parent_id: str,
    parent_urls: list[str],
    *,
    fetch: Fetcher,
    now: str | None = None,
) -> dict[str, Any] | None:
    """Does the parent's official page name this unit as a label?

    Returns a placement block, or None when nothing could be concluded
    because no parent page was readable — an unreadable page is a fact about
    the network and must not be recorded as "the parent does not list it".
    The block names the parent it was checked against, so a later re-parenting
    of the node in the curated file cannot inherit evidence for a different
    edge; apply_evidence_to_tree and the gate both compare it to the tree.
    """
    name = str(node.get("name") or "")
    if uncheckable_reason(name):
        return None
    checked_at = now or utc_now_iso()
    urls_read: list[str] = []
    failures: list[dict[str, str]] = []
    for url in parent_urls:
        if classify_source_url(url) != "official_site":
            failures.append({"url": url, "reason": "not_an_official_host"})
            continue
        try:
            html = fetch(url)
        except Exception as error:  # noqa: BLE001 — a failed fetch concludes nothing
            failures.append({"url": url, "reason": f"{error.__class__.__name__}: {error}"[:200]})
            continue
        fragments = page_fragments(html)
        if sum(len(f) for f in fragments) < MIN_READABLE_CHARS:
            failures.append({"url": url, "reason": "no_readable_text"})
            continue
        urls_read.append(url)
        matched = find_label(name, fragments)
        if matched:
            return {
                "status": PLACEMENT_LISTED,
                "parentId": parent_id,
                "url": url,
                "matchedText": matched,
                "checkedAt": checked_at,
            }
    if not urls_read:
        return None
    # Only the pages actually read are named: an auditor must not be told a
    # page that 404ed "was read and does not list it".
    block: dict[str, Any] = {"status": PLACEMENT_NOT_LISTED, "parentId": parent_id, "urlsRead": urls_read, "checkedAt": checked_at}
    if failures:
        block["failures"] = failures
    return block


def placement_from_record(record: dict[str, Any], parent_id: str | None) -> dict[str, Any] | None:
    """The placement evidence a record carries for the given parent, if any.

    An explicit `placement` block wins. Failing that, a confirmation made on
    the parent's own page (method parent, siteFrom == parent) is the same
    fetch and the same fact — the parent's page named the child — and counts
    without being fetched again. Anything checked against a different parent
    is not evidence for this edge and is ignored.
    """
    if not parent_id:
        return None
    block = record.get("placement")
    if isinstance(block, dict) and str(block.get("parentId") or "") == parent_id:
        # An explicit block for this parent decides, whichever way it went.
        # The first version let an older parent-page confirmation override a
        # NEWER not_listed block, so a retraction found by re-reading the very
        # page the claim rested on could never reach the site.
        return block if block.get("status") == PLACEMENT_LISTED else None
    if (
        record.get("status") == CONFIRMED
        and str(record.get("method") or "") == METHOD_PARENT_PAGE
        and str(record.get("siteFrom") or "") == parent_id
    ):
        sources = [src for src in (record.get("sources") or []) if isinstance(src, dict) and src.get("url")]
        if sources:
            return {
                "status": PLACEMENT_LISTED,
                "parentId": parent_id,
                "url": str(sources[0]["url"]),
                "matchedText": sources[0].get("matchedText"),
                "checkedAt": record.get("checkedAt"),
                "derivedFrom": "parent_page_confirmation",
            }
    return None


def evidence_names_this_node(node_name: str, matched_text: Any) -> bool:
    """Does the recorded label still name the node as it is now called?

    Records are keyed by id and never re-fetched once confirmed. A curator
    renaming a node while keeping its id would otherwise carry a green badge
    earned by a different name. When no text was recorded (older records)
    there is nothing to compare and the record stands."""
    if not matched_text:
        return True
    key = canonical_name_key(node_name)
    return bool(key) and label_matches(key, str(matched_text))


def clear_evidence_fields(node: dict[str, Any], official_urls: set[str]) -> bool:
    """Remove what a previous run's evidence put on this node. Returns True
    if anything was removed."""
    touched = False
    # The date is withdrawn with the fetch that supplied it. A node that
    # keeps a Treasury URL keeps its sources, but "last verified" must not go
    # on quoting a check whose record is gone.
    if node.get("evidenceVerifiedAt") and str(node.get("lastVerified") or "") == str(node.get("evidenceVerifiedAt")):
        node.pop("lastVerified", None)
        touched = True
    for field in EVIDENCE_OWNED_FIELDS:
        if field in node:
            node.pop(field, None)
            touched = True
    urls = [str(u) for u in (node.get("sourceUrls") or [])]
    kept = [u for u in urls if u not in official_urls]
    if len(kept) != len(urls):
        node["sourceUrls"] = kept
        touched = True
    # The type is a claim about the URLs. Withdrawing the last official URL
    # has to withdraw the label too, or the node goes on asserting an official
    # source with nothing behind it — which is exactly what the release gate
    # now refuses, and it caught this.
    if not any(classify_source_url(u) == "official_site" for u in kept):
        types = [str(t) for t in (node.get("sourceTypes") or []) if t != "official_site"]
        if len(types) != len(node.get("sourceTypes") or []):
            node["sourceTypes"] = types
            touched = True
    return touched


def apply_evidence_to_tree(
    root: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    *,
    index_tree=None,
    sites: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Stamp evidence onto the nodes it names, and only what was observed.

    Every node is first stripped of the fields this module owns, so a claim
    the current evidence no longer supports stops being published even though
    the previously published graph is re-fed as a payload on every build.

    confirmed  -> sourceUrls, sourceTypes official_site, lastVerified,
                  verificationMethod (own page or parent page — a different
                  claim, and the node says which).
    not_found  -> lastVerified and verificationFailure only, and only when no
                  other route gave the node a source. The site renders that as
                  checked-and-failed, distinct from never-checked.
    everything else -> counted, applied to nothing. No page was read, or the
                  page that was read was not obliged to name this unit, or the
                  curated name could never have been found.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    stats = {
        CONFIRMED: 0, NOT_FOUND: 0, INCONCLUSIVE: 0, FETCH_FAILED: 0, NOT_CHECKABLE: 0,
        "own_page_confirmations": 0, "parent_page_confirmations": 0,
        "unknown_node": 0, "unknown_status": 0, "urls_added": 0, "stale_claims_cleared": 0,
    }
    node_map, parent_map = index_tree(root)
    stats.update({
        "placements_evidenced": 0, "placements_checked_not_listed": 0, "placements_stale_parent": 0,
        "placements_stale_name": 0, "existence_stale_name": 0, "placements_not_checkable_no_parent_page": 0,
        PLACEMENT_ONLY: 0,
    })
    # Withdraw every claim this module previously published before applying
    # the current evidence. The URL set is exactly the URLs the current
    # evidence file confirms, plus any this module could have written before.
    official_urls = {
        str(source.get("url"))
        for record in evidence.values()
        for source in (record.get("sources") or [])
        if isinstance(source, dict) and source.get("url")
    }
    for node in node_map.values():
        # Any field this module owns marks a node it wrote to. The first
        # version keyed on four of them and left `placementCheckable: False`
        # standing on a node whose parent had since gained a page.
        if any(field in node for field in EVIDENCE_OWNED_FIELDS):
            # Strip only what this module put there: the node's own record of
            # it, falling back to the current evidence file's URLs for nodes
            # published before that record existed. Never the node's whole
            # list — that took the Treasury URL off 26 measured nodes.
            mine = {str(u) for u in (node.get("evidenceUrls") or [])} or set(official_urls)
            if clear_evidence_fields(node, mine):
                stats["stale_claims_cleared"] += 1
            if not node.get("sourceUrls"):
                node.pop("lastVerified", None)
            verify_node_sources(node)

    for node_id, record in evidence.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        status = str(record.get("status") or "")
        checked_at = str(record.get("checkedAt") or "").strip()
        if status not in (CONFIRMED, NOT_FOUND, INCONCLUSIVE, FETCH_FAILED, NOT_CHECKABLE, PLACEMENT_ONLY):
            stats["unknown_status"] += 1
            continue
        if status == PLACEMENT_ONLY:
            stats[PLACEMENT_ONLY] += 1
            continue
        if status != CONFIRMED:
            # Nothing was learned that can be published, except that a unit
            # absent from its own page is a real negative.
            stats[status] += 1
            if status == NOT_FOUND and not node.get("sourceUrls") and checked_at:
                node["lastVerified"] = checked_at
                node["evidenceVerifiedAt"] = checked_at
                node["verificationFailure"] = NOT_FOUND
                node["verificationSiteFrom"] = record.get("siteFrom")
                verify_node_sources(node)
            continue

        sources = [s for s in record.get("sources", []) if isinstance(s, dict) and s.get("url")]
        official = [s for s in sources if classify_source_url(str(s["url"])) == "official_site"]
        if not official:
            # No official URL behind it: not a confirmation at all.
            stats["unknown_status"] += 1
            continue
        sources = [s for s in official if evidence_names_this_node(str(node.get("name") or ""), s.get("matchedText"))]
        if not sources:
            # The label recorded names a unit this node is no longer called.
            stats["existence_stale_name"] += 1
            continue
        urls = [str(s["url"]) for s in sources]
        existing = [str(u) for u in (node.get("sourceUrls") or [])]
        for url in urls:
            if url not in existing:
                existing.append(url)
                stats["urls_added"] += 1
        node["sourceUrls"] = existing
        node["evidenceUrls"] = list(urls)
        types = [str(t) for t in (node.get("sourceTypes") or [])]
        if "official_site" not in types:
            types.append("official_site")
        node["sourceTypes"] = types
        if checked_at and (not node.get("lastVerified") or checked_at > str(node.get("lastVerified"))):
            node["lastVerified"] = checked_at
        if checked_at:
            node["evidenceVerifiedAt"] = checked_at
        method = str(record.get("method") or (METHOD_OWN_PAGE if record.get("ownPage") else METHOD_PARENT_PAGE))
        node["verificationMethod"] = method
        node["verificationSiteFrom"] = record.get("siteFrom")
        stats[CONFIRMED] += 1
        stats["own_page_confirmations" if method == METHOD_OWN_PAGE else "parent_page_confirmations"] += 1
        verify_node_sources(node)

    # Placement is applied in its own pass: a unit's existence and its
    # position in the hierarchy are separate claims, and a record may carry
    # evidence for the edge (the parent's page lists it) while the unit's own
    # page was never read.
    for node_id, record in evidence.items():
        node = node_map.get(node_id)
        if node is None:
            continue
        actual_parent = parent_map.get(node_id)
        block = record.get("placement") if isinstance(record.get("placement"), dict) else None
        if block and block.get("status") == PLACEMENT_LISTED and str(block.get("parentId") or "") != str(actual_parent or ""):
            # Evidence for an edge the tree no longer has. Never inherited.
            stats["placements_stale_parent"] += 1
        listed = placement_from_record(record, actual_parent)
        if listed and not evidence_names_this_node(str(node.get("name") or ""), listed.get("matchedText")):
            stats["placements_stale_name"] += 1
            listed = None
        if listed and classify_source_url(str(listed.get("url") or "")) == "official_site":
            node["placementVerified"] = True
            node["placementUrl"] = str(listed["url"])
            node["placementVerifiedAt"] = listed.get("checkedAt")
            node["placementParentId"] = actual_parent
            node["placementMatchedText"] = listed.get("matchedText")
            # The claim named, beside the boolean, so the data product says
            # what was tested without needing the UI's wording.
            node["placementMethod"] = PLACEMENT_METHOD
            stats["placements_evidenced"] += 1
        elif block and block.get("status") == PLACEMENT_NOT_LISTED and str(block.get("parentId") or "") == str(actual_parent or ""):
            # Read and not listed. Recorded so it is auditable; claims nothing.
            node["placementVerified"] = False
            node["placementParentId"] = actual_parent
            node["placementVerifiedAt"] = block.get("checkedAt")
            stats["placements_checked_not_listed"] += 1

    # "No evidence recorded" and "could not be checked" are different states.
    # Most organisations sit under a curated grouping ("The Cabinet") that
    # has no page of its own, so their edge is unreachable by this method;
    # saying so keeps the coverage number from reading as a failure to try.
    if sites is not None:
        for node_id, node in node_map.items():
            if node is root or node.get("placementVerified") is not None:
                continue
            if "position" in str(node.get("type") or "").casefold():
                continue
            parent = parent_map.get(node_id)
            if parent and parent not in sites:
                node["placementCheckable"] = False
                stats["placements_not_checkable_no_parent_page"] += 1
    return stats
