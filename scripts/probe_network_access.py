#!/usr/bin/env python
"""Which hosts this project needs are reachable from THIS session, right now.

    python scripts/probe_network_access.py                # probe and report
    python scripts/probe_network_access.py --allowlist    # hosts blocked RIGHT NOW
    python scripts/probe_network_access.py --all-hosts    # every host this repo could ever need
    python scripts/probe_network_access.py --domains      # the same, as registrable domains
    python scripts/probe_network_access.py --data-only    # just the API hosts

**`--allowlist` is reactive and `--all-hosts` is not.** The first emits the
hosts the proxy refuses on this run, which is what to paste when something is
broken today. It goes stale the moment a nomination is promoted or a curator
adds a page: the verifier reaches 238 hosts across 162 registrable domains
today, 26 of them under house.gov and 23 under senate.gov, and every new
committee arrives as one more subdomain. `--all-hosts` emits the union of
every host the repository currently knows about from any source — the data
APIs, `official_sites.json`, the provenance file, every nomination ledger
under `data/audit/nominations/`, and every URL `evidence.json` has recorded a
fetch against — so an allowlist built from it survives the next promotion.

**The genuinely future-proof answer is `*.gov` and `*.mil`, and it grants
nothing.** `classify_source_url` returns `official_site` only for those two
suffixes, `verify_node` and `verify_placement` refuse any URL that is not
`official_site`, `nominate.py` refuses a nomination on any other host, and
the release gate refuses an `official_site` claim without a `.gov`/`.mil`
URL behind it. The code is already the allowlist. A network allowlist
narrower than `*.gov`/`*.mil` therefore adds no safety — it only adds a
second list that has to be maintained in step with the first, and the
2026-09-09 incident in `docs/NETWORK_ACCESS.md` §0 is what that costs.

`scripts/report_unreachable_hosts.py` answers a different question: it groups
the hosts the verifier *recorded* a failure for, from evidence written in a
past run. This one asks the live question — can we get out to them now — and
it exists because of a specific, expensive confusion.

`docs/NETWORK_ACCESS.md` §0 records four `.gov` hosts that returned 200 on
2026-09-08 and were refused at the proxy on 2026-09-09 with nothing in the
repository changed. An allowlist is a property of the cloud environment the
session runs in, and this repository is reachable from two of them. So when a
fetch fails there are three quite different causes that look identical from
inside a crawler:

  * the environment's allowlist does not carry the host;
  * the allowlist was widened, but on the wrong environment;
  * the host itself is refusing us (a 403 from the server, robots.txt, a 404).

The third is a fact about the host and the first two are facts about the
sandbox, and the discriminator is where the 403 comes from. A refusal at the
CONNECT — before a byte reaches the host — raises URLError carrying "Tunnel
connection failed"; a refusal by the host arrives as an HTTPError with a
status, which means we got through. This script reports that difference
rather than collapsing both into "failed", and prints the environment it is
running in so a widened allowlist can be checked against the right one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITES = PROJECT_ROOT / "data" / "verification" / "official_sites.json"

USER_AGENT = os.environ.get(
    "BUREAUCRACY_PIPELINE_UA",
    "BureaucracyNetworkProbe/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)",
)

#: Hosts the pipeline's own crawlers and fixtures need, which are NOT in
#: official_sites.json because they serve records about units rather than a
#: unit's own page. Each is written as the code actually addresses it — the
#: Treasury anchor comes from api.fiscaldata.treasury.gov (see
#: data_pipeline/crawler/treasury_outlays.py), and allowlisting the bare
#: fiscaldata.treasury.gov instead would look like it worked and silently
#: leave the anchor unreachable.
DATA_HOSTS = {
    "api.fiscaldata.treasury.gov": "Monthly Treasury Statement — the cost cascade's anchor",
    "api.usaspending.gov": "account- and bureau-level outlays; no API key needed",
    "www.opm.gov": "FedScope headcounts, the PLUM archive, the Executive Schedule pay table",
    "www.federalregister.gov": "the agency directory",
    "api.federalregister.gov": "the agency directory, as an API",
    "www.senate.gov": "the Senate's own committee list",
    "clerk.house.gov": "the House Clerk's committee list — no House placement evidence without it",
    "escs.opm.gov": "OPM's current PLUM export",
    "www.govinfo.gov": "the printed Plum Book, the Budget Appendix",
    "api.sam.gov": "SAM.gov Federal Hierarchy (also needs a SAM.gov key)",
}

TIMEOUT = 12


def candidate_hosts() -> dict[str, str]:
    """Every host the verifier has a candidate page on."""
    try:
        sites = json.loads(SITES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    hosts: dict[str, str] = {}
    for node_id, urls in sites.items():
        if node_id.startswith("_"):
            continue
        for url in urls or []:
            host = urlparse(str(url)).hostname
            if host:
                hosts.setdefault(host.lower(), f"candidate page for {node_id}")
    return hosts


#: Everywhere a host this project might need to reach can be written down.
#: Each is read defensively: a missing or malformed file contributes nothing
#: rather than failing the run, because this command's whole job is to be
#: runnable when things are already broken.
NOMINATION_LEDGERS = PROJECT_ROOT / "data" / "audit" / "nominations"
PROVENANCE = PROJECT_ROOT / "data" / "verification" / "official_sites_provenance.json"
EVIDENCE = PROJECT_ROOT / "data" / "verification" / "evidence.json"
#: Documents this project cites a rule from but cannot currently read. RFC
#: 9309 is the one CLAUDE.md marks "[likely; unverified from this
#: environment]" — the robots.txt 4xx rule the verifier's politeness policy
#: turns on — and it is unverified precisely because these hosts are refused.
STANDARDS_HOSTS = {
    "www.rfc-editor.org": "RFC 9309, the robots.txt standard this project's politeness policy cites",
    "datatracker.ietf.org": "the same RFC, as IETF serves it",
}


def _hosts_from(urls) -> set[str]:
    found = set()
    for url in urls or []:
        host = urlparse(str(url or "")).hostname
        if host:
            found.add(host.lower())
    return found


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def every_known_host() -> dict[str, str]:
    """Every host any part of this repository has ever addressed.

    The superset `--all-hosts` emits. Deliberately includes hosts that are
    only *proposed* (a nomination nobody has promoted) and hosts that only
    ever failed: an allowlist that carries just today's working set has to be
    edited again the moment the queue moves, which is the maintenance cost
    this command exists to remove.
    """
    hosts: dict[str, str] = {}

    def add(found, why):
        for host in found:
            hosts.setdefault(host, why)

    add(DATA_HOSTS, "")
    for host, why in DATA_HOSTS.items():
        hosts[host] = why
    for host, why in STANDARDS_HOSTS.items():
        hosts.setdefault(host, why)
    for host, why in candidate_hosts().items():
        hosts.setdefault(host, why)

    provenance = _load_json(PROVENANCE)
    if isinstance(provenance, dict):
        for key, value in provenance.items():
            if key.startswith("_"):
                continue
            for record in (value if isinstance(value, list) else [value]):
                if isinstance(record, dict):
                    add(_hosts_from([record.get("url"), record.get("listedUrl")]),
                        f"a page nominated or seeded for {key}")

    if NOMINATION_LEDGERS.is_dir():
        for ledger in sorted(NOMINATION_LEDGERS.glob("*.jsonl")):
            try:
                lines = ledger.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                for nomination in (record.get("nominations") or []):
                    if isinstance(nomination, dict):
                        add(_hosts_from([nomination.get("url")]),
                            f"nominated in {ledger.name}, not yet promoted")

    evidence = _load_json(EVIDENCE)
    nodes = evidence.get("nodes") if isinstance(evidence, dict) else None
    if isinstance(nodes, dict):
        for record in nodes.values():
            if not isinstance(record, dict):
                continue
            for source in (record.get("sources") or []):
                if isinstance(source, dict):
                    add(_hosts_from([source.get("url")]), "a page that has confirmed a node")
            for failure in (record.get("failures") or []):
                if isinstance(failure, dict):
                    add(_hosts_from([failure.get("url")]), "a page the verifier has tried")
    return hosts


def registrable_domain(host: str) -> str:
    """The last two labels. Crude on purpose and correct for this input: every
    host here is under .gov or .mil, neither of which has a public second
    level the way .co.uk does, so "energy.gov" and "af.mil" are right and
    there is no list to keep current."""
    parts = str(host or "").strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def probe(host: str) -> tuple[str, str]:
    """Classify one host. Returns (verdict, detail).

    robots.txt is the right thing to ask for: it is what the verifier fetches
    first, it is small, and every one of these hosts serves one or answers
    for it.
    """
    request = urllib.request.Request(
        f"https://{host}/robots.txt", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return "reachable", f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        # The host answered. Its status is the host's business, not the proxy's.
        return "reachable", f"HTTP {error.code} from the host"
    except urllib.error.URLError as error:
        reason = str(error.reason)
        if "tunnel connection failed" in reason.lower() or "forbidden" in reason.lower():
            return "proxy_refused", reason
        return "unreachable", reason
    except Exception as error:  # pragma: no cover - defensive
        return "unreachable", f"{type(error).__name__}: {error}"


def environment_note() -> str:
    """Which sandbox this is, since an allowlist belongs to one."""
    for key in ("CLAUDE_ENVIRONMENT_ID", "CCR_ENVIRONMENT_ID", "ENVIRONMENT_ID"):
        if os.environ.get(key):
            return f"{key}={os.environ[key]}"
    return (
        "not in the environment. Ask the session itself — the claude-code-remote "
        "get_session tool reports environment_id — and widen THAT environment's "
        "allowlist, not one with a more fitting name."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-hosts", action="store_true",
                        help="every host this repository could need, from every source; fetches nothing")
    parser.add_argument("--domains", action="store_true",
                        help="the same superset collapsed to registrable domains, for a wildcard allowlist")
    parser.add_argument("--allowlist", action="store_true",
                        help="print only the blocked hosts, one per line, ready to paste")
    parser.add_argument("--data-only", action="store_true",
                        help="probe only the API/data hosts, not every candidate page")
    args = parser.parse_args(argv)

    # Both of these answer "what should the allowlist contain", which is a
    # question about the repository and not about the network, so neither
    # probes anything. That also makes them work when egress is entirely
    # blocked, which is exactly when the list is needed.
    if args.all_hosts or args.domains:
        known = every_known_host()
        if args.domains:
            for domain in sorted({registrable_domain(h) for h in known}):
                print(domain)
        else:
            for host in sorted(known):
                print(host)
        return 0

    targets = dict(DATA_HOSTS)
    if not args.data_only:
        for host, why in candidate_hosts().items():
            targets.setdefault(host, why)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = dict(zip(targets, pool.map(probe, targets)))

    blocked = sorted(h for h, (verdict, _) in results.items() if verdict == "proxy_refused")

    if args.allowlist:
        for host in blocked:
            print(host)
        return 0

    print(f"environment: {environment_note()}")
    print(f"probed {len(targets)} hosts\n")

    by_verdict: dict[str, list[str]] = {}
    for host, (verdict, detail) in sorted(results.items()):
        by_verdict.setdefault(verdict, []).append(f"{host}  ({detail})")

    for verdict in ("reachable", "proxy_refused", "unreachable"):
        rows = by_verdict.get(verdict) or []
        print(f"{verdict}: {len(rows)}")
        for row in rows[:60]:
            print(f"    {row}")
        if len(rows) > 60:
            print(f"    … and {len(rows) - 60} more")
        print()

    print("the data hosts specifically — these gate whole lines of evidence:")
    for host, why in sorted(DATA_HOSTS.items()):
        verdict, detail = results[host]
        mark = "ok  " if verdict == "reachable" else "BLOCKED"
        print(f"    {mark}  {host:<34} {why}")

    if blocked:
        print(f"\n{len(blocked)} host(s) refused at the proxy. To get the paste-ready list:")
        print("    python scripts/probe_network_access.py --allowlist")
        return 1
    print("\nnothing refused at the proxy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
