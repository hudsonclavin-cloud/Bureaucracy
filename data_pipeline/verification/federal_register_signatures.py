"""Posts, as the officials who sign the government's own documents state them.

`CLAUDE.md` records where the page method for posts ran out. An agency's
website is not obliged to name its officers, and the Government Manual's
leadership tables carry what the Office of the Federal Register chose to
print. Counted on the published graph the day this module landed: 4,280 of the
4,591 positions carry no verification method at all, and 1,922 of those sit
under an organisation whose own page WAS read -- it named the organisation, or
was recorded as not naming it -- and simply does not name the post. Both of
those sources are documents ABOUT an agency, and both are as complete as
somebody decided to make them.

A Federal Register document is a different kind of thing. Every rule and every
notice the government publishes ends with a signature block, and the block
names the signing official and the official's own title:

    R.N. Macon,
    Captain, U.S. Coast Guard, Captain of the Port, Lake Michigan.
    [FR Doc. 2026-19270 Filed 9-18-26; 8:45 am]

That is not a roster somebody compiled. It is an act of government carried out
by a named officer, published by the Office of the Federal Register, and the
title is there because the document has no legal force without somebody
competent to sign it. So it is evidence of something the other sources cannot
give: that the post existed AND was filled on the day the document was signed.

**The signer's name is never read.** The block's shape is `<name>,` on one line
and `<title>.` on the next, so the name line is matched in order to be
EXCLUDED -- the rule `whitehouse_pay.classify_row` follows for its NAME column
and `positions.py` follows for the PLUM archive's incumbent columns. Here it is
structural rather than a promise: `signature_title` finds the name line's
index and returns only what is BELOW it, so no published string can be the
name line, and `tests/test_federal_register_signatures.py` asserts over every
committed document that nothing this module returns is a name the document
prints. A title outlives its holder; a holder is nobody's business here.

**Scoping is the API's, not the text's.** The signature says "U.S. Coast
Guard" in its own words, and reading that would be exactly the assembly this
project refuses everywhere else. What scopes a document is the Federal
Register's own `agencies` field, resolved by the same canonical-key rule
`directories.py` uses for the agency directory -- and only when the WHOLE
agency list reduces to exactly one organisation here. A rule the Coast Guard
signs is filed by the Register under both "Homeland Security Department" and
"Coast Guard"; both are nodes in this graph, so which of the two the document
belongs to is not something the API settles, and the document is refused. That
refusal is the single largest cost of this module and it is measured below
rather than argued around.

**Equality, never containment.** The title must equal exactly one direct post
child of that organisation under `canonical_name_key`, with a floor of two
tokens. No fold, no split, no containment: `Press Secretary` sits inside
`ASSISTANT PRESS SECRETARY` and `Office of Science` inside `Office of Science
and Technology Policy`, and this project has published both mistakes once
already. Most signature titles are written `<office>, <organisation>` --
"Administrator, Agricultural Marketing Service" -- and splitting that to reach
a node named `Administrator` would be producing a title rather than selecting
one. It is refused, and counted.

**It claims no placement.** One document was read and it yields one
observation; publishing existence and placement from it would present a single
finding as two corroborating ones. That is the rule the Manual's post route
already follows, and the gate refuses a placement method naming this source.

**What a confirmation is worth, which is less than it first looks.**
`classify_source_url` files a `federalregister.gov` URL as `federal_register`
and deliberately NOT as `official_site` -- "the Register is a .gov host, but a
notice is documentation of an office, not the office's own site" -- so a
signature URL scores the bare 0.4 that any source scores and misses the 0.3 an
official site adds. A post confirmed here ALONE therefore publishes
`unverified` with a source recorded, not `partial`: the site shows what was
read and does not call it a verification. That is the existing arithmetic
applied honestly rather than a rule this module introduces, and it is left
exactly where it is. A post that already carries a page or Manual claim keeps
it, gains this beside it, and the second source adds 0.1 -- which is how one of
these can reach `verified`. Nothing here writes a cost field: a signature is
not money.

**The fixtures, and the responses that are not documents.**
`www.federalregister.gov` answers `robots.txt` 200 and allows both paths read
here. The API listings and the documents are committed verbatim under
`tests/fixtures/federal_register/signatures/` with their `.meta.json`, and
every digest is recomputed from the bytes before a line is read. The host
answers a document's `raw_text_url` with an HTML "Request Access" page on
roughly three requests in five, at random and under HTTP 200 -- the same URL
serves the document on the next attempt, and the rate moves with neither the
request headers nor the delay -- so a response whose media type is not
`text/plain` is not the document. It is refused outright rather than having
markup parsed out of it, the fetch retries up to twelve times, and after the
last attempt the meta record says so and no fixture is written
(`docs/NETWORK_ACCESS.md` section 13).
The plain-text rendering the Publishing Office serves carries a fixed
`<html><head>…<pre>` envelope of its own and, on some documents, a Cloudflare
e-mail-obfuscation span in the body; nothing here parses either. The signature
block is located by the document's own `[FR Doc. <number> Filed …]` line, whose
number must be the number the API gives, and a tag or an HTML entity inside
the block refuses it. A bare ampersand does not: this graph names units
"Health & Human Services", and `AF/A1 (Manpower & Personnel)` is a curated
post a blunter rule could never confirm.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node
from data_pipeline.verification.directories import federal_register_name_keys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "federal_register" / "signatures"
INDEX_DIR = FIXTURE_DIR / "index"
DOCUMENT_DIR = FIXTURE_DIR / "documents"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "fr_signature_evidence.json"

SOURCE = "federal_register_signature"
SOURCE_TYPE = "federal_register_signature"
METHOD = "signed_a_federal_register_document"
DOCUMENT_URL = "https://www.federalregister.gov/d/{}"

#: The media type the document path publishes. Anything else is the host's
#: "Request Access" page, which is not the document and is never parsed.
DOCUMENT_MEDIA_TYPE = "text/plain"

#: A post's canonical key must carry at least this many tokens -- the floor
#: `evidence.uncheckable_reason` and `govman.MIN_POST_TOKENS` already apply,
#: and for the same reason: scoping to one agency supplies the context a
#: qualified title lacks and supplies nothing at all to a single common noun.
MIN_POST_TOKENS = 2

#: How far above the `[FR Doc. …]` line the signature block may reach. The
#: block is two printed lines and a hard-wrapped title takes at most a few
#: more; a window is what keeps a search that finds no name line from walking
#: up into the body of the document and finding a sentence that looks like one.
MAX_BLOCK_LINES = 8

#: A signer's name as the Federal Register prints it: `R.N. Macon,`,
#: `Alice M. Kottmyer,`, `Erin Morris,`. Capitalised tokens only, ending in a
#: comma, no digits. It is matched ONLY so that the line can be excluded --
#: nothing derived from it is returned, stored or printed.
NAME_LINE = re.compile(r"^(?:[A-Z][A-Za-z'’.\-]*\.?)(?:\s+[A-Z][A-Za-z'’.\-]*\.?){0,4},$")

WHITESPACE = re.compile(r"\s+")
#: Markup, as it can appear inside the body the publisher serves. The
#: plain-text rendering is wrapped in a fixed HTML envelope of its own, and a
#: few documents carry a Cloudflare e-mail-obfuscation `<a><span>` with an
#: `&#160;` inside it. A signature block containing either is refused rather
#: than cleaned. An ampersand ON ITS OWN is not markup and is not refused:
#: this graph names units "Health & Human Services", and the curated post
#: `AF/A1 (Manpower & Personnel)` is one a blunter rule could never confirm.
MARKUP_CHARACTERS = "<>"
HTML_ENTITY = re.compile(r"&[#A-Za-z][A-Za-z0-9]*;")


class Unreadable(RuntimeError):
    """A committed fixture cannot be read as what it claims to be."""


def normalise(value: Any) -> str:
    return WHITESPACE.sub(" ", str(value or "")).strip()


def load_fixture(path: Path | str) -> dict[str, Any]:
    """A committed fixture's bytes, after the digest is recomputed from them.

    The refusal `pay_tables`, `gs_pay`, `govman` and `net_cost` all make: a
    hand-written file under a `federalregister.gov` URL would read on the site
    exactly like a fetched one, and only the digest tells them apart.
    """
    path = Path(path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
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
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the document")
    return {"bytes": raw, "sha256": digest, "url": str(meta.get("url") or ""),
            "fetchedAt": str(meta.get("fetched_at") or ""),
            "contentType": str(meta.get("content_type") or "").split(";")[0].strip()}


def read_index(index_dir: Path | str = INDEX_DIR) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Every document the committed API listings name, keyed by its number.

    The listings are what selected the fixture set, so they are committed with
    the documents: a reader can see which documents the API returned, not only
    which ones this module found something in.
    """
    index_dir = Path(index_dir)
    documents: dict[str, dict[str, Any]] = {}
    stats = {"listings": 0, "listed_documents": 0, "listed_twice": 0}
    for path in sorted(index_dir.glob("*.json")):
        if path.name.endswith(".meta.json"):
            continue
        loaded = load_fixture(path)
        payload = json.loads(loaded["bytes"].decode("utf-8"))
        stats["listings"] += 1
        for row in payload.get("results") or []:
            number = str((row or {}).get("document_number") or "").strip()
            if not number:
                continue
            if number in documents:
                stats["listed_twice"] += 1
                continue
            documents[number] = {
                "documentNumber": number,
                "documentTitle": normalise(row.get("title")),
                "documentType": normalise(row.get("type")),
                "agenciesListed": [normalise((a or {}).get("name") or (a or {}).get("raw_name"))
                                   for a in (row.get("agencies") or [])
                                   if normalise((a or {}).get("name") or (a or {}).get("raw_name"))],
                "signingDate": (row.get("signing_date") or None),
                "publicationDate": (row.get("publication_date") or None),
                "rawTextUrl": str(row.get("raw_text_url") or ""),
                "listedIn": path.name,
            }
            stats["listed_documents"] += 1
    return documents, stats


def signature_title(text: str, document_number: str) -> tuple[str | None, str]:
    """The title the signature block prints, or None and the reason.

    The block is `<name>,` then the title, then the Register's own
    `[FR Doc. <number> Filed …]` line. The name line is located so that the
    title can be taken from BELOW it: the returned string is built from
    `lines[name_index + 1 : fr_doc_index]` and can therefore never be, or
    contain, the name. Nothing else in this module reads that line.
    """
    marker = f"[FR Doc. {document_number} Filed"
    lines = text.split("\n")
    fr_doc_at = None
    for i, line in enumerate(lines):
        if line.strip().startswith(marker):
            fr_doc_at = i
            break
    if fr_doc_at is None:
        return None, "document_prints_no_fr_doc_line_for_this_number"
    name_at = None
    for j in range(fr_doc_at - 1, max(-1, fr_doc_at - 1 - MAX_BLOCK_LINES), -1):
        stripped = lines[j].strip()
        if not stripped:
            break
        if NAME_LINE.match(stripped):
            name_at = j
            break
    if name_at is None:
        return None, "no_signature_block_above_the_fr_doc_line"
    title = normalise(" ".join(lines[name_at + 1:fr_doc_at]))
    if not title:
        return None, "the_signature_block_carries_no_title_line"
    if any(character in title for character in MARKUP_CHARACTERS) or HTML_ENTITY.search(title):
        return None, "markup_inside_the_signature_block"
    if not title.endswith("."):
        return None, "the_title_does_not_end_in_a_full_stop"
    title = title[:-1].strip()
    if not title:
        return None, "the_signature_block_carries_no_title_line"
    return title, "ok"


def read_documents(
    index_dir: Path | str = INDEX_DIR,
    document_dir: Path | str = DOCUMENT_DIR,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Every committed document, with the title its signature block prints.

    A document the listings name but whose bytes are not committed is counted,
    not silently dropped: the host serves an HTML "Request Access" page for
    this path at random and the fetch refused it rather than parsing markup.
    """
    listed, stats = read_index(index_dir)
    document_dir = Path(document_dir)
    stats.update({"documents_read": 0, "documents_refused_by_the_host": 0,
                  "documents_not_fetched": 0, "titles_extracted": 0})
    out: list[dict[str, Any]] = []
    for number, row in sorted(listed.items()):
        path = document_dir / f"{number}.txt"
        if not path.exists():
            # Two different facts, counted apart: a `.meta.json` with no
            # document beside it is a fetch the host answered with its
            # "Request Access" page until the attempts ran out, and no
            # record at all is a document nothing ever asked for.
            if path.with_name(path.name + ".meta.json").exists():
                stats["documents_refused_by_the_host"] += 1
            else:
                stats["documents_not_fetched"] += 1
            continue
        loaded = load_fixture(path)
        if loaded["contentType"] != DOCUMENT_MEDIA_TYPE:
            # Belt and braces: the fetch already refuses these, and a fixture
            # that slipped through would be markup, not a document.
            stats["documents_refused_by_the_host"] += 1
            continue
        stats["documents_read"] += 1
        title, why = signature_title(loaded["bytes"].decode("utf-8", "replace"), number)
        if title:
            stats["titles_extracted"] += 1
        else:
            stats["refused_" + why] = stats.get("refused_" + why, 0) + 1
        record = dict(row)
        record.update({"listedTitle": title, "refusal": None if title else why,
                       "documentSha256": loaded["sha256"], "url": loaded["url"],
                       "fetchedAt": loaded["fetchedAt"],
                       "documentUrl": DOCUMENT_URL.format(number)})
        out.append(record)
    return out, stats


def resolve_agencies(agency_names: list[str], org_by_key: dict[str, list[str]]) -> set[str]:
    """The organisation nodes the Register's own agency list reaches.

    The name rule is `directories.federal_register_name_keys` -- the directory
    writes "Energy Department" where the curated file writes "Department of
    Energy" -- shared with the agency-directory module so the two can never
    disagree about which agency is which node.
    """
    hits: set[str] = set()
    for name in agency_names:
        for key in federal_register_name_keys(name):
            hits.update(org_by_key.get(key, []))
    return hits


def build_records(
    documents: list[dict[str, Any]],
    root: dict[str, Any],
    *,
    index_tree=None,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """One record per post a committed document's signature names.

    Both sides must be unambiguous: the document's whole agency list must
    reduce to exactly one organisation here, and that organisation must carry
    exactly one direct post child whose name equals the title.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    org_by_key: dict[str, list[str]] = {}
    children: dict[str, list[dict[str, Any]]] = {}
    for node_id, node in node_map.items():
        parent_id = parent_map.get(node_id)
        if parent_id:
            children.setdefault(parent_id, []).append(node)
        # An organisation, as `directories._is_organisation` reads it: not a
        # post, and not one of the accounting lines the exporter creates.
        if not is_post_node(node) and not node.get("synthetic"):
            key = canonical_name_key(node.get("name"))
            if key:
                org_by_key.setdefault(key, []).append(node_id)

    stats = {
        "documents_considered": 0, "signatures_matched": 0,
        "distinct_titles": 0, "posts_listed": 0,
        "refused_no_signature_title": 0,
        "refused_agencies_reach_no_organisation": 0,
        "refused_agencies_reach_several_organisations": 0,
        "refused_title_under_two_tokens": 0,
        "refused_organisation_carries_no_post_of_that_name": 0,
        "refused_siblings_share_the_name": 0,
    }
    titles: set[str] = set()
    # node id -> every committed document whose signature names it, so the
    # record can say how many there are and cite one deterministically.
    hits: dict[str, list[dict[str, Any]]] = {}
    for document in documents:
        stats["documents_considered"] += 1
        title = document.get("listedTitle")
        if not title:
            stats["refused_no_signature_title"] += 1
            continue
        titles.add(title)
        reached = resolve_agencies(document.get("agenciesListed") or [], org_by_key)
        if not reached:
            stats["refused_agencies_reach_no_organisation"] += 1
            continue
        if len(reached) > 1:
            stats["refused_agencies_reach_several_organisations"] += 1
            continue
        org_id = next(iter(reached))
        key = canonical_name_key(title)
        if len(key.split()) < MIN_POST_TOKENS:
            stats["refused_title_under_two_tokens"] += 1
            continue
        named = [c for c in children.get(org_id, [])
                 if is_post_node(c) and c.get("id") and canonical_name_key(c.get("name")) == key]
        if not named:
            stats["refused_organisation_carries_no_post_of_that_name"] += 1
            continue
        if len(named) > 1:
            stats["refused_siblings_share_the_name"] += 1
            continue
        stats["signatures_matched"] += 1
        hits.setdefault(named[0]["id"], []).append(dict(document, organisationId=org_id))
    stats["distinct_titles"] = len(titles)

    records: dict[str, dict[str, Any]] = {}
    for node_id, found in hits.items():
        # The most recent document wins, by the date the Register published
        # it and then by document number, so the citation does not depend on
        # the order the fixtures happened to be read in.
        chosen = sorted(found, key=lambda d: (str(d.get("publicationDate") or ""), d["documentNumber"]))[-1]
        records[node_id] = {
            "source": SOURCE,
            "nodeName": node_map[node_id].get("name"),
            "listedTitle": chosen["listedTitle"],
            "documentNumber": chosen["documentNumber"],
            "documentTitle": chosen["documentTitle"],
            "documentType": chosen["documentType"],
            "agenciesListed": list(chosen["agenciesListed"]),
            "signingDate": chosen.get("signingDate"),
            "publicationDate": chosen.get("publicationDate"),
            "organisationId": chosen["organisationId"],
            "url": chosen["url"],
            "documentUrl": chosen["documentUrl"],
            "documentSha256": chosen["documentSha256"],
            "occurrences": len(found),
        }
        stats["posts_listed"] += 1
    return records, stats


def apply_signature_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp a signature onto the post it names.

    Runs after `apply_evidence_to_tree`, which has already withdrawn every
    field this module owns, so a record dropped since the last build stops
    being published even though the previous graph is re-fed as a payload.
    A page or Manual claim on the same node is kept and this is added beside
    it, never over it. No placement is written, ever.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    from data_pipeline.processors.normalize_nodes import verify_node_sources

    node_map, parent_map = index_tree(root)
    stats = {"listed": 0, "unknown_node": 0, "not_a_post": 0, "stale_name": 0,
             "reparented": 0, "urls_added": 0, "method_set": 0, "method_kept": 0,
             "failed_checks_withdrawn": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_post_node(node):
            stats["not_a_post"] += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("listedTitle")):
            stats["stale_name"] += 1
            continue
        if parent_map.get(node_id) != record.get("organisationId"):
            # The scope IS the claim: the title was read off a document the
            # Register files under one agency, and a post moved to another
            # parent was never scoped to that agency at all.
            stats["reparented"] += 1
            continue
        url = str(record.get("url") or "")
        if not url:
            continue
        if node.get("verificationFailure"):
            # A checked negative is published only where nothing gives the
            # node a source, and this signature is about to.
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
        node["federalRegisterSignature"] = {
            "source": SOURCE,
            "listedTitle": record.get("listedTitle"),
            "documentNumber": record.get("documentNumber"),
            "documentTitle": record.get("documentTitle"),
            "documentType": record.get("documentType"),
            "agenciesListed": list(record.get("agenciesListed") or []),
            "signingDate": record.get("signingDate"),
            "publicationDate": record.get("publicationDate"),
            "url": url,
            "documentUrl": record.get("documentUrl"),
            "documentSha256": record.get("documentSha256"),
            "occurrences": int(record.get("occurrences") or 1),
        }
        if node.get("verificationMethod"):
            # A page read this post's own organisation and labelled it, or
            # the Manual's entry listed it. Either is its own claim and it
            # stays; this is a second source beside it, which the confidence
            # arithmetic rewards without relabelling what was read.
            stats["method_kept"] += 1
        else:
            node["verificationMethod"] = METHOD
            stats["method_set"] += 1
        # The observation's own date: the day the Register published the
        # document that carries the signature.
        when = str(record.get("publicationDate") or "")
        if when:
            node["lastVerified"] = when
            node["evidenceVerifiedAt"] = when
        verify_node_sources(node)
        stats["listed"] += 1
    return stats


def load_signature_evidence(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """The derived records, or nothing when the file is absent."""
    resolved = Path(path or DEFAULT_EVIDENCE_PATH)
    if not resolved.exists():
        return {}
    store = json.loads(resolved.read_text(encoding="utf-8")) or {}
    nodes = store.get("nodes")
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}
