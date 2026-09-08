#!/usr/bin/env python
"""Group the verifier's candidate hosts by why they could not be read.

    python scripts/report_unreachable_hosts.py

An unreachable page is not a flaw in the evidence — the record says
`fetch_failed` and applies nothing — but the reason matters, because one
cause is the environment's network policy (fixable by widening an
allowlist), one is this project's own robots.txt conduct rule (deliberate,
and not to be relaxed to raise a coverage number), and one is simply that
the planner never tried. docs/NETWORK_ACCESS.md is this report, written out.
Read-only: reads data/verification/official_sites.json and evidence.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITES = PROJECT_ROOT / "data" / "verification" / "official_sites.json"
DEFAULT_EVIDENCE = PROJECT_ROOT / "data" / "verification" / "evidence.json"

PROXY_DENIED = "denied by the environment's network policy (CONNECT 403)"
ROBOTS_REFUSED = "refused by this project's robots.txt policy (401/403 on robots.txt)"
NOT_ATTEMPTED = "never attempted (its node was already confirmed elsewhere)"
REACHED = "reached: a page was read"


def classify(reason: str) -> str:
    text = str(reason or "")
    if "robots" in text.lower():
        return ROBOTS_REFUSED
    if "Tunnel connection failed" in text or "CONNECT" in text:
        return PROXY_DENIED
    if "404" in text:
        return "HTTP 404"
    if "no_readable_text" in text:
        return "200 with no readable body (a JS shell or a bot challenge)"
    if "name_not_labelled_on_page" in text:
        return REACHED
    return "other: " + text[:60]


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv
    sites_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_SITES
    evidence_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_EVIDENCE
    sites = {k: v for k, v in json.loads(sites_path.read_text(encoding="utf-8")).items() if not str(k).startswith("_")}
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")).get("nodes", {})

    hosts: dict[str, set[str]] = defaultdict(set)
    for node_id, urls in sites.items():
        for url in urls if isinstance(urls, list) else [urls]:
            hosts[urlparse(str(url)).netloc.lower()].add(node_id)

    reached: set[str] = set()
    cause: dict[str, str] = {}
    for record in evidence.values():
        for source in record.get("sources") or []:
            reached.add(urlparse(str(source.get("url", ""))).netloc.lower())
        for url in (record.get("placement") or {}).get("urlsRead") or []:
            reached.add(urlparse(str(url)).netloc.lower())
        for failure in record.get("failures") or []:
            host = urlparse(str(failure.get("url", ""))).netloc.lower()
            cause.setdefault(host, classify(failure.get("reason")))

    groups: dict[str, list[str]] = defaultdict(list)
    for host in hosts:
        groups[REACHED if host in reached else cause.get(host, NOT_ATTEMPTED)].append(host)

    print(f"{len(hosts)} candidate hosts in {sites_path.name}\n")
    for group in sorted(groups, key=lambda g: -len(groups[g])):
        members = sorted(groups[group])
        nodes = sum(len(hosts[h]) for h in members)
        print(f"== {group}: {len(members)} host(s), {nodes} node(s)")
        if group != REACHED:
            for line_start in range(0, len(members), 4):
                print("   " + "  ".join(f"{h:<30}" for h in members[line_start:line_start + 4]).rstrip())
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
