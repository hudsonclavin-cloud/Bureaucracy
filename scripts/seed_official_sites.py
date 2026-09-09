#!/usr/bin/env python
"""Seed candidate official pages from an official directory.

    python scripts/seed_official_sites.py --dry-run                   # what would be added, and what is skipped why
    python scripts/seed_official_sites.py                             # writes official_sites.json + official_sites_provenance.json
    python scripts/seed_official_sites.py --source federal-register   # the only source so far

data/verification/official_sites.json is the verifier's list of pages to
fetch, keyed by base-graph node id. A URL there is a candidate, never
evidence: the node earns a source only when scripts/verify_base_graph.py
reads the page and finds the node's name on it as a label (CLAUDE.md,
"Existence evidence"). This script fills in candidates the file lacks from
a directory the government publishes about itself. The first source is the
Federal Register's agency directory as already derived into
data/verification/directory_evidence.json: every record from it carries the
agency's own site as the directory lists it (`agencyUrl`).

A candidate is added only when all of these hold, and every refusal is
reported by category:

- the node has no entry in the sites file yet (`has_entry`) — a curated
  candidate is never displaced, and a node is seeded once, so a proposal
  listing several pages for one node adds the first admissible one
  (`one_candidate_per_node`);
- the URL is https (`not_https`) — the Federal Register lists most sites as
  http://, and this script rewrites nothing: an http candidate is refused
  and listed, not upgraded on the directory's behalf;
- the host ends in .gov or .mil (`host_not_gov_or_mil`), the standard the
  evidence module counts as official and the verifier agrees to fetch;
- the URL is not already in the file under any node
  (`url_already_present`; compared after stripping whitespace and one
  trailing "/", which is the only normalisation anywhere here).

Every URL added is recorded in data/verification/official_sites_provenance.json
— node id, URL, the source, the name the directory listed, the directory's
fetch time — so a seeded candidate can always be told from a curated one.
Nothing here fetches; nothing here touches evidence.json or
directory_evidence.json.

Another source is added by writing a loader that returns proposals shaped
{node_id: [url, ...]} and registering it in SOURCES; apply_proposals() does
the rest and is importable.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.json_io import load_json_file, write_json_file  # noqa: E402
from data_pipeline.verification.directories import (  # noqa: E402
    DEFAULT_DIRECTORY_EVIDENCE_PATH,
    FR_SOURCE,
    load_directory_evidence,
)
from data_pipeline.verification.evidence import DEFAULT_SITES_PATH  # noqa: E402

DEFAULT_PROVENANCE_PATH = PROJECT_ROOT / "data" / "verification" / "official_sites_provenance.json"
OFFICIAL_HOST_SUFFIXES = (".gov", ".mil")
PROVENANCE_NOTE_SENTENCE = (
    "Candidates seeded from the Federal Register agency directory by scripts/seed_official_sites.py "
    "are marked in data/verification/official_sites_provenance.json."
)

SKIP_HAS_ENTRY = "has_entry"
SKIP_ONE_PER_NODE = "one_candidate_per_node"
SKIP_MALFORMED = "malformed_url"
SKIP_NOT_HTTPS = "not_https"
SKIP_HOST = "host_not_gov_or_mil"
SKIP_PRESENT = "url_already_present"
SKIP_CATEGORIES = (SKIP_HAS_ENTRY, SKIP_ONE_PER_NODE, SKIP_MALFORMED, SKIP_NOT_HTTPS, SKIP_HOST, SKIP_PRESENT)


def dedup_key(url: Any) -> str:
    """The only normalisation here, and only for the duplicate check: whitespace
    and one trailing slash. What is written is the URL with whitespace stripped."""
    return str(url or "").strip().rstrip("/")


def upgrade_scheme(url: Any) -> tuple[str, bool]:
    """An http:// URL on a .gov or .mil host becomes https://; the directory
    lists 92 of its 102 sites as http, and every .gov domain is HSTS-preloaded
    by mandate, so the scheme is transport, not a claim — the verifier still
    has to fetch the page and find the label. Returns (url, upgraded). Any
    other host is left alone and refused below."""
    text = str(url or "").strip() if isinstance(url, str) else ""
    parts = urlparse(text)
    host = (parts.hostname or "").casefold()
    if parts.scheme == "http" and host.endswith(OFFICIAL_HOST_SUFFIXES):
        return "https://" + text[len("http://"):], True
    return text, False


def refusal(url: Any) -> str | None:
    """Why a URL cannot be a candidate, or None when it can."""
    text = str(url or "").strip() if isinstance(url, str) else ""
    if not text:
        return SKIP_MALFORMED
    parts = urlparse(text)
    host = (parts.hostname or "").casefold()
    if not host:
        return SKIP_MALFORMED
    if parts.scheme != "https":
        return SKIP_NOT_HTTPS
    if not host.endswith(OFFICIAL_HOST_SUFFIXES):
        return SKIP_HOST
    return None


def load_sites_file(path: str | Path) -> dict[str, Any]:
    """The file as it is, `_note` and order included; the evidence module's
    loader drops the note and cleans the lists, and this script must write
    back what it read plus the additions."""
    payload = load_json_file(path, default_factory=dict)
    return payload if isinstance(payload, dict) else {}


def load_provenance(path: str | Path) -> dict[str, dict[str, Any]]:
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    return {str(k): v for k, v in payload.items() if isinstance(v, dict) and not str(k).startswith("_")}


def apply_proposals(
    sites: dict[str, Any],
    proposals: dict[str, list[str]],
    *,
    source: str,
    provenance: dict[str, dict[str, Any]],
    fetched_at: str | None,
    listed_names: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add the admissible proposals to `sites` and record each in `provenance`,
    both in place. Returns {"added": [(node_id, url)], "skipped": {category:
    [(node_id, url)]}}. `sites` is the file as loaded (`_note` and all);
    `proposals` is {node_id: [url, ...]}; `listed_names` is the name each
    directory listed the node under, for the provenance record."""
    listed_names = listed_names or {}
    present: set[str] = set()
    for key, value in sites.items():
        if str(key).startswith("_"):
            continue
        urls = value if isinstance(value, list) else [value]
        present.update(dedup_key(u) for u in urls if isinstance(u, str) and dedup_key(u))
    added: list[tuple[str, str]] = []
    skipped: dict[str, list[tuple[str, str]]] = {category: [] for category in SKIP_CATEGORIES}
    for node_id in sorted(proposals, key=str):
        urls = proposals[node_id]
        urls = urls if isinstance(urls, list) else [urls]
        node_id = str(node_id)
        # Judged against the file as loaded: a node seeded by this very run
        # is reported under one_candidate_per_node, not has_entry.
        had_entry = node_id in sites
        seeded = False
        for raw in urls:
            listed_url = str(raw or "").strip() if isinstance(raw, str) else ""
            url, upgraded = upgrade_scheme(listed_url)
            shown = url or repr(raw)
            if had_entry:
                skipped[SKIP_HAS_ENTRY].append((node_id, shown))
                continue
            if seeded:
                skipped[SKIP_ONE_PER_NODE].append((node_id, shown))
                continue
            why = refusal(url)
            if why:
                skipped[why].append((node_id, shown))
                continue
            if dedup_key(url) in present:
                skipped[SKIP_PRESENT].append((node_id, url))
                continue
            sites[node_id] = [url]
            present.add(dedup_key(url))
            provenance[node_id] = {
                "url": url,
                "source": source,
                "listedName": listed_names.get(node_id),
                "directoryFetchedAt": fetched_at,
            }
            if upgraded:
                # The URL exactly as the directory lists it, beside the one used.
                provenance[node_id]["listedUrl"] = listed_url
                provenance[node_id]["schemeUpgraded"] = True
            added.append((node_id, url))
            seeded = True
    return {"added": added, "skipped": skipped}


def note_with_provenance_sentence(note: Any) -> str:
    text = str(note or "").strip()
    if PROVENANCE_NOTE_SENTENCE in text:
        return text
    return f"{text} {PROVENANCE_NOTE_SENTENCE}".strip()


# ---- sources ---------------------------------------------------------------

def federal_register_proposals(evidence_path: Path) -> dict[str, Any]:
    """Proposals from the Federal Register records in directory_evidence.json:
    each node the directory matched, with the site the directory lists for
    it. The directory's fetch time is the records' checkedAt, which every
    record of one derivation shares."""
    records = load_directory_evidence(evidence_path)
    mine = {
        node_id: record
        for node_id, record in records.items()
        if record.get("source") == FR_SOURCE and record.get("agencyUrl")
    }
    proposals = {node_id: [record["agencyUrl"]] for node_id, record in mine.items()}
    listed_names = {node_id: record.get("listedName") for node_id, record in mine.items()}
    dates = {str(record.get("checkedAt")) for record in mine.values() if record.get("checkedAt")}
    return {
        "source": FR_SOURCE,
        "proposals": proposals,
        "listed_names": listed_names,
        "fetched_at": max(dates) if dates else None,
        "records": len(records),
        "origin": str(evidence_path),
    }


def congress_proposals(house_html: Path, senate_html: Path, base_graph: Path) -> dict[str, Any]:
    """Proposals from the House's and the Senate's own committee pages
    (verbatim fixtures): each committee's site as the chamber links it. The
    Senate prints its links as http; upgrade_scheme handles that, so the
    loader is asked not to refuse them."""
    from data_pipeline.exporter.build_graph import index_tree, load_base_graph
    from data_pipeline.verification.congress_sites import load_congress_site_proposals

    node_map, _ = index_tree(load_base_graph(base_graph))
    proposals, report = load_congress_site_proposals(house_html, senate_html, node_map, require_https=False)
    listed_names: dict[str, str] = {}
    for chamber in ("house", "senate"):
        for match in report.get(chamber, {}).get("matches") or []:
            listed_names[str(match["node_id"])] = f"{match['name']} ({chamber.capitalize()} committee page)"
    dates = [report.get(c, {}).get("fetched_at") for c in ("house", "senate")]
    return {
        "source": "congress_committee_pages",
        "proposals": proposals,
        "listed_names": listed_names,
        "fetched_at": max((d for d in dates if d), default=None),
        "records": len(proposals),
        "origin": f"{house_html}, {senate_html}",
        "report": report,
    }


SOURCES: dict[str, Callable[[argparse.Namespace], dict[str, Any]]] = {
    "federal-register": lambda args: federal_register_proposals(args.directory_evidence),
    "congress": lambda args: congress_proposals(args.house_html, args.senate_html, args.base_graph),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES_PATH)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE_PATH)
    parser.add_argument("--directory-evidence", type=Path, default=DEFAULT_DIRECTORY_EVIDENCE_PATH,
                        help="records derived by scripts/derive_directory_evidence.py")
    parser.add_argument("--source", choices=sorted(SOURCES), default="federal-register")
    fixtures = PROJECT_ROOT / "tests" / "fixtures" / "directories"
    parser.add_argument("--house-html", type=Path, default=fixtures / "house_gov_committees.html")
    parser.add_argument("--senate-html", type=Path, default=fixtures / "senate" / "senate_committees_page.html")
    parser.add_argument("--base-graph", type=Path, default=PROJECT_ROOT / "data" / "federal_gov_complete_1.json")
    parser.add_argument("--dry-run", action="store_true", help="print what would be added; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    sites = load_sites_file(args.sites)
    if not sites:
        print(f"no sites file at {args.sites}; nothing to seed into", file=sys.stderr)
        return 1
    provenance = load_provenance(args.provenance)
    loaded = SOURCES[args.source](args)
    proposals = loaded["proposals"]
    print(f"source {args.source}: {len(proposals)} proposals from {loaded['origin']}  (directory fetched {loaded['fetched_at']})")

    outcome = apply_proposals(
        sites, proposals, source=loaded["source"], provenance=provenance,
        fetched_at=loaded["fetched_at"], listed_names=loaded["listed_names"],
    )
    counts = Counter({category: len(items) for category, items in outcome["skipped"].items()})
    print(f"added {len(outcome['added'])}  skipped {sum(counts.values())}: " + ", ".join(f"{c} {counts[c]}" for c in SKIP_CATEGORIES))
    for node_id, url in outcome["added"]:
        print(f"  + {node_id}  {url}  ({loaded['listed_names'].get(node_id)})")
    for category in (SKIP_HOST, SKIP_NOT_HTTPS, SKIP_PRESENT, SKIP_MALFORMED, SKIP_ONE_PER_NODE):
        items = outcome["skipped"][category]
        if items:
            print(f"  {category} ({len(items)}):")
            for node_id, url in items:
                print(f"    - {node_id}  {url}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    if not outcome["added"]:
        print("nothing to add; files unchanged")
        return 0
    sites["_note"] = note_with_provenance_sentence(sites.get("_note"))
    ordered = {"_note": sites.pop("_note")}
    ordered.update(sites)
    write_json_file(args.sites, ordered)
    write_json_file(args.provenance, dict(sorted(provenance.items())))
    print(f"wrote {len(outcome['added'])} candidates -> {args.sites}; {len(provenance)} provenance records -> {args.provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
