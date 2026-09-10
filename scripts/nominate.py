#!/usr/bin/env python3
"""Nominations: agents propose what to check, the machine decides what is true.

611 of the graph's 788 organisations have no candidate page in
`official_sites.json`, so the verifier has nothing to fetch for them and they
can never earn a source however long it runs. The bottleneck is not fetching;
it is *knowing which URL to fetch*. That is a job an agent can do and a script
cannot, so this harness lets many agents nominate — in parallel, without
colliding — and keeps the adjudication where it belongs.

**A nomination is not a claim.** `official_sites.json` has always said so:
"A URL here is something to check, not evidence." An agent proposing
`https://www.nist.gov/` for NIST is proposing a fetch, and
`scripts/verify_base_graph.py` decides by reading the page and testing
label equality. The worst a wrong nomination can do is waste one request.
That division — agents nominate from what they know, the machine confirms
from what it read — is what makes it safe to run this at the scale of the
whole tree.

    python scripts/nominate.py status --kind source
    python scripts/nominate.py next --kind source --shard 1/8 --count 25 > batch.json
    python scripts/nominate.py record --kind source --file proposals.json --run agent-1
    python scripts/nominate.py report --kind source
    python scripts/nominate.py promote --kind source --dry-run

Parallelism. `--shard k/N` partitions the work deterministically, and each
agent writes its own ledger under `data/audit/nominations/`, so N agents never
touch the same file and git merges their branches without conflict.

`promote` is the only command that writes outside `data/audit/`, and it writes
one file — `official_sites.json`, the fetch queue — recording every promoted
URL in `official_sites_provenance.json` exactly as `seed_official_sites.py`
does. Nothing here ever writes evidence, a cost, or the curated graph.

See docs/SOURCE_NOMINATION_RUNBOOK.md (kind=source) and
docs/COST_NOMINATION_RUNBOOK.md (kind=cost) for the agent's instructions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GRAPH = PROJECT_ROOT / "output" / "graph.json"
EVIDENCE_DIR = PROJECT_ROOT / "data" / "verification"
SITES = EVIDENCE_DIR / "official_sites.json"
PROVENANCE = EVIDENCE_DIR / "official_sites_provenance.json"
LEDGER_DIR = PROJECT_ROOT / "data" / "audit" / "nominations"

# Run as a script, the repository root is not on sys.path.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Imported under a distinct name on purpose. This module already defines its
# own `is_organisation` further down, and the two tests are deliberately
# different: for PAGE nomination a committee is an organisation (the Senate's
# committees have real pages and the repo has nominated them), while for a
# MEASURED COST the release gate refuses a committee outright. Importing the
# stricter one as `is_organisation` silently shadowed it — the guard below
# then ran the looser local test and let a committee through.
from data_pipeline.verification.financial_evidence import (  # noqa: E402
    BASES as FINANCIAL_BASES,
    NON_MONETARY_BASES as FINANCIAL_NON_MONETARY_BASES,
    POSITION_ONLY_BASES as FINANCIAL_POSITION_ONLY_BASES,
    is_organisation as may_carry_a_measured_cost,
)

KINDS = ("source", "cost")

# A page nomination must be somewhere the verifier will agree to fetch and
# that could be an organisation's own site. Dataset hosts are excluded for the
# same reason classify_source_url stopped calling them official sites: a
# FiscalData URL is a record about a unit, never the unit's page.
DATASET_HOSTS = ("fiscaldata.treasury.gov", "api.fiscaldata.treasury.gov", "api.usaspending.gov")
SOURCE_ROLES = ("own_site", "parent_listing", "official_list")

# What a cost nomination may name. Each is a different measurement and the
# graph must never let one stand in for another.
#
# One vocabulary, defined once. This list used to be five names written here
# and a different, longer list written in the evidence module — two spellings
# of one concept, which is how a nomination for a Congressional Justification
# (which reports a budget *request*) became inexpressible while the evidence
# side could record it happily. Nothing is lost by widening it: every one of
# the 5,195 cost nominations on file is a noCandidate carrying no metric at
# all, so there is no stored value to migrate.
COST_METRICS = tuple(sorted(FINANCIAL_BASES))
COST_SYSTEMS = ("treasury_mts", "usaspending_file_ab", "agency_afr", "omb_public_budget", "opm_pay_table")

CONFIDENCES = ("likely", "speculative")
NO_CANDIDATE_REASONS = (
    "not_an_organisation",          # a position, role or accounting line
    "editorial_grouping",           # a curated grouping the government does not name
    "covered_by_parent",            # no page of its own; the parent's page is the right check
    "no_public_page_known",         # a real unit with nothing this agent can name
    "not_on_a_gov_host",            # usps.com, si.edu — real, but the verifier will refuse them
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def walk(node, parent=None):
    yield node, parent
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from walk(child, node)


def load_graph():
    graph = load_json(GRAPH)
    if not graph:
        raise SystemExit(f"{GRAPH} is missing. Run scripts/regenerate_published_graph.py first.")
    order, parents, by_id = [], {}, {}
    for node, parent in walk(graph):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        order.append(node_id)
        by_id[node_id] = node
        parents[node_id] = str((parent or {}).get("id") or "") or None
    return graph, order, parents, by_id


def ledger_paths(kind):
    return sorted(LEDGER_DIR.glob(f"{kind}-*.jsonl"))


def read_ledger(kind) -> dict[str, dict]:
    """Every agent's file, merged. Later records win, which is what makes a
    re-nomination after a failed fetch work."""
    records: dict[str, dict] = {}
    for path in ledger_paths(kind):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("id"):
                records[str(record["id"])] = record
    return records


def is_organisation(node) -> bool:
    type_text = str(node.get("type") or "").casefold()
    return not node.get("synthetic") and not any(
        word in type_text for word in ("position", "role", "caucus", "office holder")
    )


def urls_already_tried(evidence: dict) -> dict[str, str]:
    """Every URL the verifier has already read or failed on, and what happened.

    Re-nominating a URL that 404ed last week wastes the one thing this whole
    exercise is short of, so the harness refuses it and the dossier shows why.
    """
    tried: dict[str, str] = {}
    for record in evidence.values():
        for source in record.get("sources") or []:
            if url := str(source.get("url") or ""):
                tried[url] = "read and the name was found"
        for failure in record.get("failures") or []:
            if url := str(failure.get("url") or ""):
                tried.setdefault(url, str(failure.get("reason") or "failed"))
        placement = record.get("placement") if isinstance(record.get("placement"), dict) else {}
        for url in placement.get("urlsRead") or []:
            tried.setdefault(str(url), "read")
    return tried


# --------------------------------------------------------------------------
# next


def cmd_next(args):
    _, order, parents, by_id = load_graph()
    evidence = load_json(EVIDENCE_DIR / "evidence.json").get("nodes") or {}
    directory = load_json(EVIDENCE_DIR / "directory_evidence.json").get("nodes") or {}
    sites = {k: v for k, v in load_json(SITES).items() if not k.startswith("_")}
    tried = urls_already_tried(evidence)
    done = set(read_ledger(args.kind))

    pending = []
    for node_id in order:
        node = by_id[node_id]
        if node_id in done:
            continue
        if args.kind == "source":
            # Positions and accounting lines have no page of their own, and
            # asking 4,382 times produces 4,382 identical refusals.
            if not is_organisation(node):
                continue
            if node_id in sites and not args.include_covered:
                continue
        pending.append(node_id)

    if args.shard:
        index, total = (int(part) for part in args.shard.split("/"))
        if not 1 <= index <= total:
            raise SystemExit(f"--shard {args.shard} is out of range")
        pending = [node_id for position, node_id in enumerate(pending) if position % total == index - 1]

    batch = pending[: args.count]
    nodes = []
    for node_id in batch:
        node = by_id[node_id]
        chain, current, seen = [], parents.get(node_id), set()
        while current and current not in seen:
            seen.add(current)
            if parent := by_id.get(current):
                chain.append({"id": current, "name": parent.get("name"),
                              "candidatePages": sites.get(current) or []})
            current = parents.get(current)
        entry = {
            "id": node_id,
            "name": node.get("name"),
            "type": node.get("type"),
            "description": node.get("desc"),
            "ancestors": chain,
            "existingCandidatePages": sites.get(node_id) or [],
            "urlsAlreadyTried": {u: why for u, why in tried.items() if u in (sites.get(node_id) or [])},
            "directoryListing": (directory.get(node_id) or {}).get("listedUrl")
            or (directory.get(node_id) or {}).get("url"),
            "verificationState": {
                key: node.get(key) for key in
                ("sourceUrls", "sourceTypes", "verificationMethod", "verificationFailure", "placementCheckable")
                if node.get(key) not in (None, [], "")
            },
        }
        if args.kind == "cost":
            entry["cost"] = {key: node.get(key) for key in
                             ("cost_status", "resolved_total_amount", "treasury_row_name", "cost_basis")}
            entry["positionListing"] = node.get("positionListing")
        nodes.append(entry)

    print(json.dumps({
        "kind": args.kind, "run": args.run, "shard": args.shard, "generated": now(),
        "remaining_in_shard_after_this_batch": max(len(pending) - len(batch), 0),
        "nodes": nodes,
    }, indent=1, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------
# record


class Rejected(Exception):
    pass


def validate_url(url: str) -> None:
    if not url.startswith("https://"):
        raise Rejected(f"a nominated page must be https: {url!r}")
    host = urlparse(url).netloc.lower()
    if not host:
        raise Rejected(f"a nominated page has no host: {url!r}")
    if not (host.endswith(".gov") or host.endswith(".mil")):
        raise Rejected(
            f"the verifier only fetches .gov and .mil hosts, so {host} would be refused: {url!r}. "
            "If that is genuinely the unit's home, say noCandidate with reason not_on_a_gov_host."
        )
    if any(host == dataset or host.endswith("." + dataset) for dataset in DATASET_HOSTS):
        raise Rejected(f"{host} is a data service, not any unit's own page: {url!r}")
    if re.search(r"\s", url):
        raise Rejected(f"a nominated page contains whitespace: {url!r}")


def validate_source(record, node, sites, tried):
    node_id = record["id"]
    if not is_organisation(node):
        raise Rejected(f"{node_id} is a {node.get('type')!r}; pages are nominated for organisations only")
    nominations = record.get("nominations") or []
    if record.get("noCandidate"):
        if nominations:
            raise Rejected(f"{node_id}: noCandidate is set but nominations were given")
        if record.get("reason") not in NO_CANDIDATE_REASONS:
            raise Rejected(f"{node_id}: reason {record.get('reason')!r} is not one of {NO_CANDIDATE_REASONS}")
        return
    if not nominations:
        raise Rejected(f"{node_id}: no nominations and noCandidate is not set")
    seen = set()
    existing = set(sites.get(node_id) or [])
    for nomination in nominations:
        if not isinstance(nomination, dict):
            raise Rejected(f"{node_id}: a nomination is not an object")
        url = str(nomination.get("url") or "")
        validate_url(url)
        if url in seen:
            raise Rejected(f"{node_id}: {url} nominated twice")
        seen.add(url)
        if url in existing:
            raise Rejected(f"{node_id}: {url} is already a candidate for this node")
        if url in tried:
            raise Rejected(
                f"{node_id}: {url} has already been fetched — {tried[url]}. "
                "Nominate a different page rather than the one that failed."
            )
        if nomination.get("role") not in SOURCE_ROLES:
            raise Rejected(f"{node_id}: role {nomination.get('role')!r} is not one of {SOURCE_ROLES}")
        if nomination.get("confidence") not in CONFIDENCES:
            raise Rejected(f"{node_id}: confidence {nomination.get('confidence')!r} is not one of {CONFIDENCES}")
        if not str(nomination.get("basis") or "").strip():
            raise Rejected(f"{node_id}: a nomination has no basis")


def validate_cost(record, node):
    node_id = record["id"]
    if record.get("noCandidate"):
        if record.get("identifiers"):
            raise Rejected(f"{node_id}: noCandidate is set but identifiers were given")
        if not str(record.get("reason") or "").strip():
            raise Rejected(f"{node_id}: noCandidate needs a reason")
        return
    identifiers = record.get("identifiers") or []
    if not identifiers:
        raise Rejected(f"{node_id}: no identifiers and noCandidate is not set")
    if record.get("metric") not in COST_METRICS:
        raise Rejected(f"{node_id}: metric {record.get('metric')!r} is not one of {COST_METRICS}")
    # The same node-kind rule the release gate and the evidence validator both
    # apply. It was missing here before the vocabulary was widened and the
    # widening made it reachable in more ways: a rate of pay is a fact about a
    # post, an organisation's money is not, and a headcount is not a cost at
    # all. A nomination is only a proposal, but proposing to look up a
    # department's "rate of basic pay" wastes the fetch it earns.
    node_is_org = may_carry_a_measured_cost(node)
    metric = record["metric"]
    if metric in FINANCIAL_POSITION_ONLY_BASES and node_is_org:
        raise Rejected(f"{node_id}: {metric!r} is one post's pay and cannot be nominated for an organisation")
    if metric not in FINANCIAL_POSITION_ONLY_BASES and not node_is_org:
        raise Rejected(f"{node_id}: {metric!r} is an organisation's measure and cannot be nominated for a {node.get('type')!r}")
    if metric in FINANCIAL_NON_MONETARY_BASES:
        raise Rejected(
            f"{node_id}: {metric!r} is a headcount, not a cost. It is a valid financial-evidence "
            "basis but not something to nominate as a node's cost identifier."
        )
    for identifier in identifiers:
        if not isinstance(identifier, dict):
            raise Rejected(f"{node_id}: an identifier is not an object")
        if identifier.get("system") not in COST_SYSTEMS:
            raise Rejected(f"{node_id}: system {identifier.get('system')!r} is not one of {COST_SYSTEMS}")
        if not str(identifier.get("key") or "").strip():
            raise Rejected(f"{node_id}: an identifier has no key")
        if not str(identifier.get("basis") or "").strip():
            raise Rejected(f"{node_id}: an identifier has no basis")
        if identifier.get("confidence") not in CONFIDENCES:
            raise Rejected(f"{node_id}: confidence {identifier.get('confidence')!r} is not one of {CONFIDENCES}")


def cmd_record(args):
    _, _, _, by_id = load_graph()
    evidence = load_json(EVIDENCE_DIR / "evidence.json").get("nodes") or {}
    sites = {k: v for k, v in load_json(SITES).items() if not k.startswith("_")}
    tried = urls_already_tried(evidence)
    payload = load_json(Path(args.file))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise SystemExit(f"{args.file} carries no records list")

    validated, problems = [], []
    for raw in records:
        record = dict(raw)
        try:
            node_id = str(record.get("id") or "")
            if node_id not in by_id:
                raise Rejected(f"{node_id!r} is not a node in the published graph")
            if args.kind == "source":
                validate_source(record, by_id[node_id], sites, tried)
            else:
                validate_cost(record, by_id[node_id])
            record["kind"] = args.kind
            record["run"] = args.run
            record["nominatedAt"] = record.get("nominatedAt") or now()
            validated.append(record)
        except Rejected as error:
            problems.append(str(error))

    if problems:
        print(f"REJECTED: {len(problems)} of {len(records)} records failed. Nothing was written.\n")
        for line in problems[:40]:
            print(f"  - {line}")
        if len(problems) > 40:
            print(f"  … and {len(problems) - 40} more")
        return 1

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    # One file per agent run: N agents in parallel never touch the same file,
    # and two branches of this repository merge without a conflict.
    path = LEDGER_DIR / f"{args.kind}-{re.sub(r'[^A-Za-z0-9_.-]', '-', args.run)}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        for record in validated:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"recorded {len(validated)} nodes -> {path.relative_to(PROJECT_ROOT)}")
    print(f"{args.kind} ledger now holds {len(read_ledger(args.kind)):,} nodes across {len(ledger_paths(args.kind))} agent file(s)")
    return 0


# --------------------------------------------------------------------------
# promote / status / report


def cmd_promote(args):
    """Move accepted page nominations into the verifier's fetch queue.

    The queue is a list of things to check. Promoting a URL asserts nothing
    about the unit — only that the verifier should read that page and see.
    """
    if args.kind != "source":
        raise SystemExit("promote applies to page nominations only")
    _, _, _, by_id = load_graph()
    sites = load_json(SITES)
    provenance = load_json(PROVENANCE)
    records = read_ledger("source")
    added, skipped = [], []
    for node_id, record in sorted(records.items()):
        if record.get("noCandidate") or node_id not in by_id:
            continue
        existing = list(sites.get(node_id) or [])
        for nomination in record.get("nominations") or []:
            url = str(nomination.get("url") or "")
            if not url or url in existing:
                skipped.append(url)
                continue
            if args.only_role and nomination.get("role") != args.only_role:
                continue
            existing.append(url)
            added.append((node_id, url, nomination.get("role")))
            provenance.setdefault(node_id, {})
            provenance[node_id] = {
                "url": url,
                "source": "agent_nomination",
                "role": nomination.get("role"),
                "basis": nomination.get("basis"),
                "confidence": nomination.get("confidence"),
                "run": record.get("run"),
                "nominatedAt": record.get("nominatedAt"),
                "note": "A candidate page to fetch. Not evidence: the verifier decides by reading it.",
            }
        if existing:
            sites[node_id] = existing

    print(f"  would add {len(added)} candidate page(s) across {len({n for n, _, _ in added})} node(s)")
    for node_id, url, role in added[: args.limit]:
        print(f"    {node_id} <- {url}  [{role}]")
    if len(added) > args.limit:
        print(f"    … and {len(added) - args.limit} more")
    if args.dry_run:
        print("\n  --dry-run: nothing written")
        return 0
    SITES.write_text(json.dumps(sites, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    PROVENANCE.write_text(json.dumps(provenance, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n  wrote {SITES.relative_to(PROJECT_ROOT)} and {PROVENANCE.relative_to(PROJECT_ROOT)}")
    print("  next: python scripts/verify_base_graph.py   (needs the .gov hosts reachable)")
    return 0


def cmd_status(args):
    _, order, _, by_id = load_graph()
    sites = {k: v for k, v in load_json(SITES).items() if not k.startswith("_")}
    done = read_ledger(args.kind)
    if args.kind == "source":
        eligible = [i for i in order if is_organisation(by_id[i])]
        without = [i for i in eligible if i not in sites]
        print(f"  organisations           : {len(eligible):,}")
        print(f"  already have a page     : {len(eligible) - len(without):,}")
        print(f"  need one nominated      : {len(without):,}")
    else:
        eligible = order
        print(f"  nodes                   : {len(eligible):,}")
    print(f"  nominated so far        : {len(done):,}")
    print(f"  agent files             : {len(ledger_paths(args.kind))}")
    return 0


def cmd_report(args):
    done = read_ledger(args.kind)
    if not done:
        print("nothing nominated yet")
        return 0
    if args.kind == "source":
        roles, confidences, hosts = Counter(), Counter(), Counter()
        no_candidate = Counter()
        pages = 0
        for record in done.values():
            if record.get("noCandidate"):
                no_candidate[record.get("reason")] += 1
                continue
            for nomination in record.get("nominations") or []:
                pages += 1
                roles[nomination.get("role")] += 1
                confidences[nomination.get("confidence")] += 1
                hosts[urlparse(str(nomination.get("url") or "")).netloc.lower()] += 1
        print(f"  nodes nominated     : {len(done):,}")
        print(f"  candidate pages     : {pages:,}")
        print(f"    by role           : {dict(roles.most_common())}")
        print(f"    by confidence     : {dict(confidences.most_common())}")
        print(f"  no candidate        : {sum(no_candidate.values()):,} {dict(no_candidate.most_common())}")
        print(f"  distinct hosts      : {len(hosts):,}")
    else:
        metrics, systems = Counter(), Counter()
        no_candidate = 0
        for record in done.values():
            if record.get("noCandidate"):
                no_candidate += 1
                continue
            metrics[record.get("metric")] += 1
            for identifier in record.get("identifiers") or []:
                systems[identifier.get("system")] += 1
        print(f"  nodes nominated     : {len(done):,}")
        print(f"    by metric         : {dict(metrics.most_common())}")
        print(f"    by system         : {dict(systems.most_common())}")
        print(f"  no candidate        : {no_candidate:,}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Accepted before or after the subcommand. An agent will type it both
    # ways, and a usage error is a batch of work not done.
    parser.add_argument("--kind", choices=KINDS, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_kind(subparser):
        subparser.add_argument("--kind", choices=KINDS, default=None, dest="sub_kind")
        return subparser

    p = add_kind(sub.add_parser("next", help="emit the next batch of nodes needing a nomination"))
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--shard", help="k/N — take every Nth node, so N agents can run without colliding")
    p.add_argument("--include-covered", action="store_true", help="include nodes that already have a candidate page")
    p.add_argument("--run", default=f"run-{datetime.now(timezone.utc):%Y%m%d}")
    p.set_defaults(func=cmd_next)

    p = add_kind(sub.add_parser("record", help="validate nominations and append them to this run's ledger"))
    p.add_argument("--file", required=True)
    p.add_argument("--run", required=True, help="this agent's name; becomes its own ledger file")
    p.set_defaults(func=cmd_record)

    p = add_kind(sub.add_parser("promote", help="move accepted page nominations into the verifier's fetch queue"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only-role", choices=SOURCE_ROLES)
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_promote)

    p = add_kind(sub.add_parser("status", help="how much is nominated"))
    p.set_defaults(func=cmd_status)

    p = add_kind(sub.add_parser("report", help="what has been nominated"))
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.kind = getattr(args, "sub_kind", None) or args.kind or "source"
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
