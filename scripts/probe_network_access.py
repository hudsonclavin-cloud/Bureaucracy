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
#: Hosts that only ever appear as the far end of a redirect. They are in no
#: candidate-page list, so an allowlist built from `official_sites.json`
#: silently omits them — and that is precisely why the 2026-09-15 widening
#: moved no coverage number: six of the hosts it opened redirect to six it
#: did not. `trade.gov/robots.txt` answered 200 while `trade.gov/` answered
#: "Tunnel connection failed: 403", because the page 301s to www.trade.gov.
#: Measured by requesting all 454 candidate URLs with redirects disabled and
#: reading the Location header; `--redirect-targets` re-derives them live.
REDIRECT_TARGETS = {
    "chinaselectcommittee.house.gov": "301 from selectcommitteeontheccp.house.gov",
    "financialresearch.gov": "301 from www.treasury.gov",
    "highways.dot.gov": "307 from www.fhwa.dot.gov",
    "ncua.gov": "301 from www.ncua.gov",
    "ofac.treasury.gov": "302 from www.treasury.gov",
    "www.arts.gov": "301 from arts.gov",
    "www.bep.gov": "302 from www.moneyfactory.gov",
    "www.dea.gov": "301 from www.justice.gov",
    "www.fna.usda.gov": "301 from www.fns.usda.gov",
    "www.trade.gov": "301 from trade.gov",
}

#: Documents this project cites a rule from. RFC 9309 backs the verifier's
#: robots.txt policy and was unreadable from every session before
#: 2026-09-15, which is why politeness.py carried "[likely; unverified]" for
#: so long; it is now committed at tests/fixtures/standards/rfc9309.txt.
#: Kept here so the citation stays checkable from a fresh environment.
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
    for host, why in REDIRECT_TARGETS.items():
        hosts.setdefault(host, f"redirect target, {why}")
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


def discover_redirect_targets() -> dict[str, str]:
    """Re-derive REDIRECT_TARGETS live, by asking where each candidate page
    sends us. Redirects are followed by every other fetch in this project, so
    the far end has to be allowlisted too — and nothing else in the repo
    writes that host down."""
    from urllib.parse import urljoin

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise urllib.error.HTTPError(req.full_url, code, f"->{newurl}", headers, fp)

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        sites = json.loads(SITES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    urls = [str(u) for k, v in sites.items() if not k.startswith("_") for u in (v or [])]
    known = {(urlparse(u).hostname or "").lower() for u in urls}
    found: dict[str, str] = {}
    for url in sorted(set(urls)):
        try:
            opener.open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT)
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400 and str(error.reason).startswith("->"):
                host = (urlparse(urljoin(url, str(error.reason)[2:])).hostname or "").lower()
                if host and host not in known:
                    found.setdefault(host, f"{error.code} from {urlparse(url).hostname}")
        except Exception:  # noqa: BLE001 — a host we cannot reach proposes nothing
            pass
    return found


def registrable_domain(host: str) -> str:
    """The last two labels. Crude on purpose and correct for this input: every
    host here is under .gov or .mil, neither of which has a public second
    level the way .co.uk does, so "energy.gov" and "af.mil" are right and
    there is no list to keep current."""
    parts = str(host or "").strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def probe(host: str) -> tuple[str, str]:
    """Classify one host. Returns (verdict, detail).

    robots.txt is asked for because it is what the verifier fetches first and
    it is small. **It is not a sufficient test on its own**, and saying so
    here because this command reported "reachable: 233" on 2026-09-15 for a
    set that included hosts whose pages the proxy was refusing outright.
    `trade.gov/robots.txt` answered 200 while `trade.gov/` answered
    `Tunnel connection failed: 403`, because the page 301s to
    `www.trade.gov` and the redirect TARGET is a different host that the
    allowlist did not carry. robots.txt did not redirect, so it sailed
    through and the probe called the host reachable.

    A host is only as reachable as the last hop of its redirect chain. See
    REDIRECT_TARGETS and `--redirect-targets`.
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
    parser.add_argument("--redirect-targets", action="store_true",
                        help="re-derive REDIRECT_TARGETS by following every candidate page's redirects")
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
    if args.redirect_targets:
        found = discover_redirect_targets()
        stale = sorted(set(REDIRECT_TARGETS) - set(found))
        fresh = sorted(set(found) - set(REDIRECT_TARGETS))
        for host in sorted(found):
            print(f"{host}  ({found[host]})")
        if fresh:
            print(f"\nNOT in REDIRECT_TARGETS -- add them: {', '.join(fresh)}")
        if stale:
            print(f"\nin REDIRECT_TARGETS but no longer redirected to: {', '.join(stale)}")
        if not fresh and not stale:
            print("\nREDIRECT_TARGETS is current.")
        return 0

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
