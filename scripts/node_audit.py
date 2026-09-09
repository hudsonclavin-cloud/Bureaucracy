#!/usr/bin/env python3
"""The node-by-node audit harness.

Every node in the published graph gets looked at once, by an agent, against
the evidence this repository actually holds. This script is the mechanical
half of that: it decides which nodes come next, hands over everything the
repository already knows about each one, and — the part that matters —
**refuses to record a finding whose evidence does not check out.**

Why the refusal is the point. An agent asked to examine 5,195 nodes will,
somewhere around the four-hundredth, begin pattern-matching instead of
reading, and will write down a quotation that is not on the page. This
repository's own history is a list of validators that "ran happily and were
wrong". So `record` re-reads every file an agent cites and fails the whole
batch if a quoted string is not in it. Whitespace is normalised, because
these files are hard-wrapped and an honest sentence-length quote crosses a
newline; nothing else is. An agent cannot talk its way past that, and
neither can a tired one.

    python scripts/node_audit.py status
    python scripts/node_audit.py next --count 25 > /tmp/batch.json
    python scripts/node_audit.py record --file /tmp/findings.json
    python scripts/node_audit.py verify
    python scripts/node_audit.py report

The ledger (`data/audit/node_audit.jsonl`) is append-only and is the audit's
only output. **Nothing here ever edits the curated graph, the published
graph, or any evidence file.** A finding is a proposal for a curator, not a
change; that separation is what makes it safe to let an agent loose on every
node in the tree.

See docs/NODE_AUDIT_RUNBOOK.md for the instructions the agent follows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GRAPH = PROJECT_ROOT / "output" / "graph.json"
BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
LEDGER = PROJECT_ROOT / "data" / "audit" / "node_audit.jsonl"
EVIDENCE_DIR = PROJECT_ROOT / "data" / "verification"

# The audit may cite these and nothing else on disk. A finding that rests on
# a file outside this list is resting on something the repository does not
# publish, which is not evidence the site can stand behind.
CITABLE_ROOTS = ("data/", "tests/fixtures/", "output/", "docs/", "CLAUDE.md", "CURATION.md")

CHECKS = {
    # Is this a real unit of the federal government, under this name?
    "existence": (
        "confirmed_by_repo_evidence",     # an evidence file names it
        "no_evidence_in_repo",            # nothing here says either way
        "contradicted_by_repo_evidence",  # an official list that should carry it does not
        "not_checkable_offline",          # needs a fetch this session cannot make
    ),
    # Is the parent the published tree gives it the right one?
    "placement": (
        "confirmed_by_repo_evidence",
        "no_evidence_in_repo",
        "contradicted_by_repo_evidence",
        "not_checkable_offline",
    ),
    # Is the name the one the government uses now?
    "name_currency": (
        "current_per_repo_evidence",
        "no_evidence_in_repo",
        "stale_per_repo_evidence",
        "not_checkable_offline",
    ),
    # Does `type` describe what this is?
    "node_type": ("fits", "wrong", "unclear"),
    # Does the uncited prose assert anything the repo's evidence contradicts?
    # "It has no citation" is NOT a finding — that is true of all 5,170 and is
    # already labelled on every panel. Only a contradiction counts.
    "description": ("no_contradiction_found", "contradicted", "no_description"),
    # Is the cost the right kind of number, from the right source? The values
    # map onto cost_status, because the first draft's "sound" and
    # "no_cost_published" left no way to say "this is an apportioned estimate,
    # which is the expected state" — and that is 4,885 of the 5,195 nodes.
    "cost": (
        "measured_and_sound",  # official or root_total, from the right record
        "estimate_only",       # allocated or scaled_official: a share of an ancestor's total
        "wrong_source",        # measured, but that record is not this node's
        "wrong_kind",          # the wrong kind of number (a salary as a unit's cost)
        "unavailable",         # no figure published at all
    ),
    # Is this node the same unit as another node?
    "duplication": ("distinct", "duplicates_another_node", "unclear"),
}

FINDING_KINDS = (
    "stale_name", "wrong_parent", "duplicate", "wrong_type",
    "description_contradicted", "cost_source_mismatch", "not_a_real_unit",
    "missing_from_official_list", "count_mismatch", "other",
)
SEVERITIES = ("blocking", "correction", "note")
CONFIDENCES = ("certain", "likely", "speculative")


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
        raise SystemExit(f"{GRAPH} is missing or unreadable. Run scripts/regenerate_published_graph.py first.")
    order, parents, by_id = [], {}, {}
    for node, parent in walk(graph):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        order.append(node_id)
        by_id[node_id] = node
        parents[node_id] = str((parent or {}).get("id") or "") or None
    return graph, order, parents, by_id


def load_evidence():
    out = {}
    for name in ("evidence", "directory_evidence", "headcount_evidence", "position_evidence"):
        payload = load_json(EVIDENCE_DIR / f"{name}.json")
        out[name] = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else {}
    return out


def read_ledger() -> dict[str, dict]:
    records: dict[str, dict] = {}
    if not LEDGER.exists():
        return records
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
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


# --------------------------------------------------------------------------
# next — the dossier


def ancestors_of(node_id, parents, by_id):
    chain, seen = [], set()
    current = parents.get(node_id)
    while current and current not in seen:
        seen.add(current)
        node = by_id.get(current)
        if node:
            chain.append({"id": current, "name": node.get("name"), "type": node.get("type")})
        current = parents.get(current)
    return chain


def source_context(node_id, node, parents, by_id, sites, tried):
    """What phase 1b needs to nominate a page, added to the same dossier.

    Reading a node's evidence and then reading it again in a separate pass to
    ask "and which page should we fetch for it?" is 5,195 dossiers read twice
    for nothing. The agent that has just formed a view of what this unit is is
    the cheapest one to ask where its page would be.
    """
    chain, current, seen = [], parents.get(node_id), set()
    while current and current not in seen:
        seen.add(current)
        if parent := by_id.get(current):
            chain.append({"id": current, "name": parent.get("name"), "candidatePages": sites.get(current) or []})
        current = parents.get(current)
    existing = sites.get(node_id) or []
    return {
        "eligible": is_organisation(node) and not existing,
        "existingCandidatePages": existing,
        "ancestorCandidatePages": chain,
        "urlsAlreadyTried": {url: why for url, why in tried.items() if url in existing},
    }


def is_organisation(node) -> bool:
    type_text = str(node.get("type") or "").casefold()
    return not node.get("synthetic") and not any(
        word in type_text for word in ("position", "role", "caucus", "office holder")
    )


def dossier(node_id, order, parents, by_id, evidence, name_index, sources=None):
    node = by_id[node_id]
    children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
    same_name = [i for i in name_index.get(str(node.get("name") or "").casefold(), []) if i != node_id]
    entry = {
        "id": node_id,
        "name": node.get("name"),
        "type": node.get("type"),
        "description": node.get("desc"),
        "descriptionSource": node.get("descriptionSource"),
        "ancestors": ancestors_of(node_id, parents, by_id),
        "childCount": len(children),
        "childNames": [c.get("name") for c in children[:25]],
        "siblingNames": [
            c.get("name")
            for c in (by_id.get(parents.get(node_id) or "", {}).get("children") or [])
            if isinstance(c, dict) and str(c.get("id")) != node_id
        ][:25],
        "otherNodesWithThisName": same_name[:10],
        "cost": {
            "cost_status": node.get("cost_status"),
            "resolved_total_amount": node.get("resolved_total_amount"),
            "cost_basis": node.get("cost_basis"),
            "cost_validation": node.get("cost_validation"),
            "treasury_row_name": node.get("treasury_row_name"),
            "costVerificationStatus": node.get("costVerificationStatus"),
        },
        "published_claims": {
            key: node.get(key)
            for key in (
                "sourceUrls", "sourceTypes", "lastVerified", "verificationMethod",
                "verificationFailure", "verificationFailureSource", "verificationMatchedIn",
                "placementVerified", "placementMethod", "placementUrl", "placementParentId",
                "placementMatchedText", "placementCheckable", "placementDirectoryDisagreement",
                "directoryListing", "employeesOfficial", "employeesOfficialSource",
                "positionListing", "employees", "budget", "statedChildCount",
                "carriedChildCount", "childrenIncomplete", "representsPosts",
                "cost_weight_dispute",
            )
            if node.get(key) is not None
        },
        "evidence_records": {
            source: record for source, records in evidence.items()
            if (record := records.get(node_id)) is not None
        },
    }
    if sources is not None:
        entry["source_nomination"] = source_context(node_id, node, parents, by_id, *sources)
    return entry


def cmd_next(args):
    _, order, parents, by_id = load_graph()
    evidence = load_evidence()
    done = set(read_ledger())
    sources = None
    if getattr(args, "with_sources", False):
        # Run as a script, the repository root is not on sys.path.
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.nominate import urls_already_tried

        sites = {k: v for k, v in load_json(EVIDENCE_DIR / "official_sites.json").items() if not k.startswith("_")}
        sources = (sites, urls_already_tried(evidence["evidence"]))
    name_index: dict[str, list[str]] = {}
    for node_id in order:
        name_index.setdefault(str(by_id[node_id].get("name") or "").casefold(), []).append(node_id)

    pending = [i for i in order if i not in done]
    if args.branch:
        pending = [
            i for i in pending
            if any(a["id"] == args.branch for a in ancestors_of(i, parents, by_id)) or i == args.branch
        ]
    if getattr(args, "shard", None):
        index, total = (int(part) for part in args.shard.split("/"))
        if not 1 <= index <= total:
            raise SystemExit(f"--shard {args.shard} is out of range")
        pending = [node_id for position, node_id in enumerate(pending) if position % total == index - 1]
    batch = pending[: args.count]
    print(json.dumps({
        "run": args.run,
        "generated": now(),
        "remaining_after_this_batch": max(len(pending) - len(batch), 0),
        "nodes": [dossier(i, order, parents, by_id, evidence, name_index, sources) for i in batch],
    }, indent=1, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------
# record — validation with teeth


class Rejected(Exception):
    pass


def check_quote(source: str, quote: str, cache: dict[str, str]) -> None:
    """The anti-confabulation gate: a quoted string must really be in the file.

    Cheap to run, impossible to argue with, and the only reason this audit's
    output can be trusted after the agent has stopped reading carefully.
    """
    if source.startswith(("http://", "https://")):
        host = source.split("/")[2].lower() if source.count("/") >= 2 else ""
        if not host.endswith((".gov", ".mil")):
            raise Rejected(f"cited URL is not a .gov/.mil source: {source}")
        return  # a live page cannot be re-read here; the URL is the audit trail
    if not any(source.startswith(root) for root in CITABLE_ROOTS):
        raise Rejected(f"cited path is outside the repository's citable files: {source}")
    path = PROJECT_ROOT / source
    if not path.is_file():
        raise Rejected(f"cited file does not exist: {source}")
    if source not in cache:
        try:
            # Whitespace-normalised, because these files are hard-wrapped and a
            # sentence quoted from one spans a line break. Comparing raw would
            # fail every honest multi-line quotation, which teaches an agent to
            # quote three words at a time or to fight the tool — and neither
            # makes the citation more truthful. The words must still all be
            # there, in order: normalising space cannot let an invented
            # sentence through.
            cache[source] = " ".join(path.read_text(encoding="utf-8", errors="replace").split())
        except OSError as error:
            raise Rejected(f"cited file could not be read: {source} ({error})") from error
    needle = " ".join(quote.split())
    if needle and needle not in cache[source]:
        raise Rejected(f"quoted text is not in {source}: {quote[:120]!r}")


def validate_record(record, by_id, done, cache, force):
    node_id = str(record.get("id") or "")
    if node_id not in by_id:
        raise Rejected(f"{node_id!r} is not a node in the published graph")
    if node_id in done and not force:
        raise Rejected(f"{node_id} is already in the ledger (pass --force to re-audit)")

    checks = record.get("checks")
    if not isinstance(checks, dict):
        raise Rejected(f"{node_id}: no checks block")
    for name, allowed in CHECKS.items():
        value = checks.get(name)
        if value not in allowed:
            raise Rejected(f"{node_id}: check {name}={value!r}, expected one of {allowed}")

    findings = record.get("findings")
    if not isinstance(findings, list):
        raise Rejected(f"{node_id}: findings must be a list (use [] for a clean node)")
    for finding in findings:
        if not isinstance(finding, dict):
            raise Rejected(f"{node_id}: a finding is not an object")
        if finding.get("kind") not in FINDING_KINDS:
            raise Rejected(f"{node_id}: finding kind {finding.get('kind')!r} is not one of {FINDING_KINDS}")
        if finding.get("severity") not in SEVERITIES:
            raise Rejected(f"{node_id}: severity {finding.get('severity')!r} is not one of {SEVERITIES}")
        if finding.get("confidence") not in CONFIDENCES:
            raise Rejected(f"{node_id}: confidence {finding.get('confidence')!r} is not one of {CONFIDENCES}")
        if not str(finding.get("claim") or "").strip():
            raise Rejected(f"{node_id}: a finding has no claim")
        evidence = finding.get("evidence")
        if finding["confidence"] in ("certain", "likely"):
            if not isinstance(evidence, list) or not evidence:
                raise Rejected(
                    f"{node_id}: a {finding['confidence']} finding carries no evidence. "
                    "Lower it to 'speculative' or cite something."
                )
        for item in evidence or []:
            if not isinstance(item, dict):
                raise Rejected(f"{node_id}: an evidence entry is not an object")
            source = str(item.get("source") or "")
            if not source:
                raise Rejected(f"{node_id}: an evidence entry has no source")
            check_quote(source, str(item.get("quote") or ""), cache)

    record["auditedAt"] = record.get("auditedAt") or now()
    return record


def cmd_record(args):
    _, _, _, by_id = load_graph()
    done = set(read_ledger())
    payload = load_json(Path(args.file))
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise SystemExit(f"{args.file} carries no records list")

    cache: dict[str, str] = {}
    validated, problems = [], []
    for record in records:
        try:
            validated.append(validate_record(dict(record), by_id, done, cache, args.force))
        except Rejected as error:
            problems.append(str(error))

    if problems:
        # All or nothing. A batch that is half-fabricated is not half-usable,
        # and letting the good half through teaches the agent that some of its
        # invented citations survive.
        print(f"REJECTED: {len(problems)} of {len(records)} records failed validation. Nothing was written.\n")
        for line in problems[:40]:
            print(f"  - {line}")
        if len(problems) > 40:
            print(f"  … and {len(problems) - 40} more")
        return 1

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        for record in validated:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    total = len(read_ledger())
    print(f"recorded {len(validated)} nodes; ledger now holds {total:,}")
    return 0


# --------------------------------------------------------------------------
# status / verify / report


def cmd_status(args):
    _, order, parents, by_id = load_graph()
    done = read_ledger()
    print(f"  nodes in the graph : {len(order):,}")
    print(f"  audited            : {len(done):,} ({len(done) / len(order):.1%})")
    print(f"  remaining          : {len(order) - len(done):,}")
    by_branch = Counter()
    for node_id in order:
        chain = ancestors_of(node_id, parents, by_id)
        branch = chain[-2]["name"] if len(chain) >= 2 else (by_id[node_id].get("name") or "root")
        if node_id not in done:
            by_branch[branch] += 1
    if by_branch:
        print("\n  remaining by branch:")
        for branch, count in by_branch.most_common(10):
            print(f"    {count:>6,}  {branch}")
    return 0


def cmd_verify(args):
    """Re-check every recorded citation from scratch.

    `record` already refused anything that did not check out, but a file can
    change after a finding was written, and a finding that no longer matches
    its source is a claim with nothing behind it.
    """
    _, _, _, by_id = load_graph()
    done = read_ledger()
    cache: dict[str, str] = {}
    stale, unknown = [], []
    for node_id, record in done.items():
        if node_id not in by_id:
            unknown.append(f"{node_id} is in the ledger but no longer in the graph")
        for finding in record.get("findings") or []:
            for item in finding.get("evidence") or []:
                try:
                    check_quote(str(item.get("source") or ""), str(item.get("quote") or ""), cache)
                except Rejected as error:
                    stale.append(f"{node_id}: {error}")
    print(f"  ledger records     : {len(done):,}")
    print(f"  citations re-checked and still exact: {'yes' if not stale else 'NO'}")
    for line in stale[:20]:
        print(f"    - {line}")
    for line in unknown[:20]:
        print(f"    - {line}")
    if stale:
        print(f"\n  {len(stale)} citation(s) no longer match their source.")
    return 1 if stale else 0


def cmd_report(args):
    done = read_ledger()
    if not done:
        print("nothing audited yet")
        return 0
    kinds, severities, confidences, checks = Counter(), Counter(), Counter(), {k: Counter() for k in CHECKS}
    findings = []
    for record in done.values():
        for name in CHECKS:
            checks[name][str((record.get("checks") or {}).get(name))] += 1
        for finding in record.get("findings") or []:
            kinds[finding.get("kind")] += 1
            severities[finding.get("severity")] += 1
            confidences[finding.get("confidence")] += 1
            findings.append((finding.get("severity"), record.get("id"), finding.get("kind"), finding.get("claim")))
    clean = sum(1 for r in done.values() if not (r.get("findings") or []))
    print(f"  audited            : {len(done):,}  ({clean:,} with nothing to report)")
    print(f"  findings           : {sum(kinds.values()):,}")
    print(f"    by kind          : {dict(kinds.most_common())}")
    print(f"    by severity      : {dict(severities.most_common())}")
    print(f"    by confidence    : {dict(confidences.most_common())}")
    for name in CHECKS:
        print(f"  {name:<18} : {dict(checks[name].most_common())}")
    blocking = [f for f in findings if f[0] == "blocking"]
    if blocking:
        print(f"\n  blocking findings ({len(blocking)}):")
        for _, node_id, kind, claim in blocking[: args.limit]:
            print(f"    [{kind}] {node_id}: {claim}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("next", help="emit the next batch of unaudited nodes, with their evidence")
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--branch", help="only nodes beneath this node id")
    p.add_argument("--shard", help="k/N — take every Nth node, so N agents can run without colliding")
    p.add_argument("--with-sources", action="store_true",
                   help="also carry what phase 1b needs to nominate a page, so each dossier is read once")
    p.add_argument("--run", default=f"audit-{datetime.now(timezone.utc):%Y-%m-%d}")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("record", help="validate a batch of findings and append them to the ledger")
    p.add_argument("--file", required=True)
    p.add_argument("--force", action="store_true", help="allow re-auditing a node already in the ledger")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("status", help="how much of the graph has been audited")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("verify", help="re-check every recorded citation against its source")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("report", help="what the audit has found so far")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `node_audit.py next | head` is the normal way to look at a batch,
        # and an agent that sees a traceback for it will start working around
        # a problem that does not exist.
        try:
            sys.stdout.close()
        finally:
            sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
