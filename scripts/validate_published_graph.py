#!/usr/bin/env python3
"""Release gate for the published graph.

Reads output/graph.json (or a path given as the first argument) and exits
nonzero if any node asserts more than its evidence supports. This runs over the
real artefact rather than a fixture, which is the only way it could have caught
the three validator failures of this week: each one produced a plausible number
and passed its own unit tests.

The gate never writes. Run it before every push that touches output/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"

EXPECTED_ROOT_ID = "the-constitution-of-the-united-states"
MAX_TOP_LEVEL_CHILDREN = 10
CHILD_SUM_TOLERANCE = 0.005  # 0.5%, for rounding in the apportionment cascade
SAMPLE_LIMIT = 20


def walk(node, parent=None):
    """Yield (node, parent) for every dict node in the tree."""
    yield node, parent
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from walk(child, node)


def amount_of(node):
    value = node.get("resolved_total_amount")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def label(node):
    return "{} ({})".format(node.get("name") or "Unnamed Node", node.get("id") or "no-id")


class Gate:
    def __init__(self):
        self.failures = []

    def check(self, name, violations, detail=""):
        """Record a check. `violations` is a list of human-readable strings."""
        if violations:
            self.failures.append((name, violations))
            print("FAIL  {} — {} violation(s){}".format(name, len(violations), detail))
            for line in violations[:SAMPLE_LIMIT]:
                print("        {}".format(line))
            if len(violations) > SAMPLE_LIMIT:
                print("        … and {} more".format(len(violations) - SAMPLE_LIMIT))
        else:
            print("ok    {}{}".format(name, detail))


def check_review_queue(gate, queue_path, graph, nodes):
    """The review queue is served to the site too. A record the current
    discovery code could not produce must not be there."""
    try:
        records = json.loads(queue_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        gate.check("review queue is readable JSON", ["{}: {}".format(queue_path, error)])
        return
    if not isinstance(records, list):
        gate.check("review queue is a list", ["{} holds a {}".format(queue_path, type(records).__name__)])
        return
    published = {canonical_key(n.get("name")) for n in nodes}
    generated, duplicates, unchecked_dates, bad_parent_ids, duplicate_ids, fragments = [], [], [], [], [], []
    ids = Counter()
    node_ids = {str(n.get("id") or "") for n in nodes}
    for record in records:
        if not isinstance(record, dict):
            continue
        ids[str(record.get("id") or "")] += 1
        urls = [record.get("sourceUrl"), *(record.get("sourceUrls") if isinstance(record.get("sourceUrls"), list) else [])]
        if any(str(u or "").startswith("generated://") for u in urls):
            generated.append(label(record))
        if canonical_key(record.get("name")) in published:
            duplicates.append(label(record))
        elif is_federal_register_only(urls):
            extended = extends_published_name(canonical_key(record.get("name")), published)
            if extended:
                fragments.append("{} extends {!r}".format(label(record), extended))
        if record.get("lastVerified") and not (record.get("sourceUrls") or []):
            unchecked_dates.append(label(record))
        parent_id = record.get("possibleParentId")
        if parent_id and parent_id not in node_ids:
            bad_parent_ids.append("{} names parent id {!r}".format(label(record), parent_id))
    duplicate_ids = ["{} appears {} times".format(i, c) for i, c in ids.items() if c > 1]
    gate.check("review queue has no template-generated records", generated)
    gate.check("review queue has no records duplicating a published node", duplicates)
    gate.check("review queue has no Federal Register fragments extending a published name", fragments)
    gate.check("review queue claims no verification date without a source", unchecked_dates)
    gate.check("review queue parent ids exist in the graph", bad_parent_ids)
    gate.check("review queue has no duplicate ids", duplicate_ids)
    print("  review queue         : {:,} records".format(len(records)))


# A Federal Register notice names the agency it concerns and then goes on:
# "Office of Management and Budget Review", "... (OMB) Circular No". The old
# extractor kept such fragments. A name that is a published node's name plus
# trailing words is one, unless the trailing words open a unit of their own
# ("Department of Energy Office of Science").
ORG_UNIT_LEADING_WORDS = frozenset(
    "office bureau division directorate service administration center centre agency board "
    "commission institute laboratory program programme council corps command department".split()
)


def extends_published_name(name_key, published_keys):
    for published in published_keys:
        if published and name_key.startswith(published + " "):
            remainder = name_key[len(published) + 1 :].split()
            if remainder and remainder[0] not in ORG_UNIT_LEADING_WORDS:
                return published
    return None


def is_federal_register_only(urls):
    hosts = []
    for url in urls:
        text = str(url or "")
        if text.startswith(("http://", "https://")):
            hosts.append(text.split("/")[2].lower())
    return bool(hosts) and all(h.endswith("federalregister.gov") for h in hosts)


def canonical_key(value):
    # Same reduction the exporter uses (kept local so the gate stays stdlib-only).
    import re

    text = str(value or "").casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(r"\bu s(?: a)?\b", "united states", text)
    for prefix in ("the ", "united states "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


def main(argv):
    graph_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_GRAPH
    if not graph_path.exists():
        print("FATAL: no graph at {}".format(graph_path))
        return 2

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = [node for node, _ in walk(graph)]
    pairs = list(walk(graph))
    print("Validating {} ({:,} nodes)\n".format(graph_path, len(nodes)))

    gate = Gate()

    # 1. Root identity.
    root_id = str(graph.get("id") or "")
    gate.check(
        "root id",
        [] if root_id == EXPECTED_ROOT_ID else ["root id is {!r}, expected {!r}".format(root_id, EXPECTED_ROOT_ID)],
    )

    # 2. A measured cost is the Treasury anchor on the root, or a Treasury
    #    outlay line applied to the one node it names (an official rollup with
    #    the FiscalData source on it). Anything else claiming measurement is an
    #    estimate wearing the wrong badge; a root that does not is a missing anchor.
    verified = [n for n in nodes if str(n.get("costVerificationStatus") or "").lower() == "verified"]
    illegitimate = []
    for node in verified:
        if node is graph:
            continue
        types = node.get("sourceTypes") if isinstance(node.get("sourceTypes"), list) else []
        backed = (
            str(node.get("cost_status") or "") == "official"
            and node.get("rollup_total_amount") is not None
            and "treasury_outlays" in types
        )
        if not backed:
            illegitimate.append("{} claims a measured cost without a Treasury line".format(label(node)))
    measured_violations = list(illegitimate)
    if graph not in verified:
        measured_violations.insert(0, "root {} is not measured (no Treasury anchor)".format(label(graph)))
    gate.check(
        "measured costs are the root and Treasury lines only",
        measured_violations,
        " — root + {} Treasury line(s)".format(len(verified) - (1 if graph in verified else 0)) if not measured_violations else "",
    )

    # 3. Every amount carries a provenance label.
    gate.check(
        "every amount has a cost_status",
        [label(n) for n in nodes if amount_of(n) is not None and not n.get("cost_status")],
    )

    # 4. attachToRoot together with parentId asserts a discovered reporting line
    #    to the Constitution.
    gate.check(
        "no attachToRoot with a parentId",
        [label(n) for n in nodes if n.get("attachToRoot") and n.get("parentId")],
    )

    # 5. A part cannot cost more than the whole.
    over_parent = []
    for node, parent in pairs:
        if parent is None:
            continue
        child_amount = amount_of(node)
        parent_amount = amount_of(parent)
        if child_amount is None or parent_amount is None:
            continue
        if child_amount > parent_amount * (1 + 1e-9):
            over_parent.append(
                "{} = {:,.2f} > parent {} = {:,.2f}".format(
                    label(node), child_amount, label(parent), parent_amount
                )
            )
    gate.check("no child costs more than its parent", over_parent)

    # 6. Direct children must not sum past the root total.
    root_amount = amount_of(graph)
    child_sum = sum(a for a in (amount_of(c) for c in (graph.get("children") or []) if isinstance(c, dict)) if a is not None)
    if root_amount is None:
        gate.check("children sum within the root total", ["root has no resolved_total_amount"])
    else:
        delta = child_sum - root_amount
        pct = (delta / root_amount * 100) if root_amount else 0.0
        detail = " — children {:,.2f} vs root {:,.2f} (delta {:+,.2f}, {:+.4f}%)".format(
            child_sum, root_amount, delta, pct
        )
        over = child_sum > root_amount * (1 + CHILD_SUM_TOLERANCE)
        gate.check(
            "children sum within the root total",
            ["children exceed the root total by {:,.2f} ({:.4f}%)".format(delta, pct)] if over else [],
            detail,
        )

    # 7. sourceCount and sourceUrls must never disagree.
    disagreements = []
    for node in nodes:
        try:
            count = int(node.get("sourceCount") or 0)
        except (TypeError, ValueError):
            count = 0
        urls = node.get("sourceUrls")
        urls = urls if isinstance(urls, list) else []
        if count > 0 and not urls:
            disagreements.append("{} claims {} source(s) with an empty sourceUrls".format(label(node), count))
        elif urls and count == 0:
            disagreements.append("{} has {} sourceUrls but sourceCount 0".format(label(node), len(urls)))
    gate.check("sourceCount agrees with sourceUrls", disagreements)

    # 8. Duplicate ids.
    id_counts = Counter(str(n.get("id") or "") for n in nodes)
    gate.check(
        "no duplicate node ids",
        ["{} appears {} times".format(node_id, count) for node_id, count in id_counts.items() if count > 1],
    )

    # 10. An amount of zero (or less) is a claim that the thing is free. A share
    #     the cascade could not resolve must say so with cost_status
    #     'unavailable' and no amount, never with $0.00.
    non_positive = []
    unlabelled_missing = []
    for node in nodes:
        amount = amount_of(node)
        if amount is not None and amount <= 0:
            non_positive.append("{} = {:,.2f}".format(label(node), amount))
        elif amount is None and str(node.get("cost_status") or "") != "unavailable":
            unlabelled_missing.append("{} has no amount and cost_status {!r}".format(label(node), node.get("cost_status")))
    gate.check("no zero or negative amounts", non_positive)
    gate.check("a missing amount is labelled unavailable", unlabelled_missing)

    # 11. Check 6, at every level: the parts of any node must fit inside it.
    over_parent_sums = []
    for parent, _ in pairs:
        parent_amount = amount_of(parent)
        if parent_amount is None:
            continue
        children = [c for c in (parent.get("children") or []) if isinstance(c, dict)]
        child_amounts = [a for a in (amount_of(c) for c in children) if a is not None]
        if not child_amounts:
            continue
        total = sum(child_amounts)
        if total > parent_amount * (1 + CHILD_SUM_TOLERANCE) + 0.01:
            over_parent_sums.append(
                "children of {} sum to {:,.2f} > {:,.2f}".format(label(parent), total, parent_amount)
            )
    gate.check("children sum within every parent's total", over_parent_sums)

    # 12. A cost source count is a claim of evidence for the figure. It needs a
    #     source URL, an official rollup on the node, or — for the root only —
    #     the Treasury summary the graph carries.
    unsupported_cost_sources = []
    for node in nodes:
        try:
            cost_sources = int(node.get("costSourceCount") or 0)
        except (TypeError, ValueError):
            cost_sources = 0
        if cost_sources <= 0:
            continue
        urls = node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []
        has_rollup = node.get("rollup_total_amount") is not None
        is_anchor = node is graph and isinstance(graph.get("__budgetSummary"), dict)
        if not (urls or has_rollup or is_anchor):
            unsupported_cost_sources.append(
                "{} claims {} cost source(s) with no sourceUrls and no rollup".format(label(node), cost_sources)
            )
    gate.check("costSourceCount is backed by evidence", unsupported_cost_sources)

    # 9. Root fan-out. 3,438 top-level children was the symptom that started this.
    top_level = graph.get("children") or []
    # The root's children are the three branches of the federal government.
    # A node published beside them claims to be a fourth. "At most 10" was a
    # size check, not a structural one, and it let one through.
    BRANCH_IDS = ("legislative-branch", "executive-branch", "judicial-branch")
    actual_top = tuple(str(c.get("id") or "") for c in top_level)
    gate.check(
        "root's children are exactly the three branches",
        ["root has {}, expected {}".format(list(actual_top), list(BRANCH_IDS))] if actual_top != BRANCH_IDS else [],
        " — {}".format(len(top_level)),
    )

    # 13. A verification claim is a fetch that happened: a check date must be a
    # real, past ISO date, and a node that says how it was verified must carry
    # the URL it was verified against. The site draws "checked and failed"
    # from a date without a URL, so that pairing is allowed; a method without
    # a URL is not.
    today = datetime.now(timezone.utc).date().isoformat()
    bad_dates, method_without_url = [], []
    for node in nodes:
        stamp = node.get("lastVerified")
        if stamp is not None:
            text = str(stamp).strip()
            iso_ok = bool(re.match(r"^\d{4}-\d{2}-\d{2}", text))
            if not iso_ok or text[:10] > today:
                bad_dates.append("{} lastVerified {!r}".format(label(node), stamp))
        if node.get("verificationMethod") and not (node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []):
            method_without_url.append(label(node))
    gate.check("every lastVerified is a past ISO date", bad_dates)
    gate.check("every verification method is backed by a source URL", method_without_url)

    # A failed existence check and a source are contradictory claims about the
    # same node; the merge order between the evidence pass and the Treasury
    # pass is exactly what could produce both. And a node is only allowed to
    # call a source official when a .gov/.mil URL is actually there.
    KNOWN_METHODS = {"name_labelled_on_own_official_page", "name_labelled_on_parent_official_page"}
    failure_beside_source, unofficial_official, unknown_method = [], [], []
    for node in nodes:
        urls = [str(u) for u in (node.get("sourceUrls") or []) if str(u).startswith(("http://", "https://"))]
        official = [u for u in urls if urlparse(u).netloc.lower().endswith((".gov", ".mil"))]
        if node.get("verificationFailure") and urls:
            failure_beside_source.append("{} claims {!r} beside {} source(s)".format(label(node), node["verificationFailure"], len(urls)))
        if "official_site" in (node.get("sourceTypes") or []) and not official:
            unofficial_official.append("{} claims an official source with no .gov/.mil URL".format(label(node)))
        method = node.get("verificationMethod")
        if method and str(method) not in KNOWN_METHODS:
            unknown_method.append("{} verificationMethod {!r}".format(label(node), method))
    gate.check("no node claims a failed check beside a source", failure_beside_source)
    gate.check("an official source type has a .gov/.mil URL behind it", unofficial_official)
    gate.check("every verification method is one this pipeline can produce", unknown_method)

    # 14. The review queue beside the graph, when there is one.
    queue_path = graph_path.parent / "candidate_nodes.json"
    if queue_path.exists():
        check_review_queue(gate, queue_path, graph, nodes)

    # Reported, never fatal.
    verification = Counter(str(n.get("verificationStatus") or "none") for n in nodes)
    cost_status = Counter(str(n.get("cost_status") or "none") for n in nodes)
    no_source = sum(
        1
        for n in nodes
        if not (n.get("sourceUrls") if isinstance(n.get("sourceUrls"), list) else []) and not n.get("lastVerified")
    )
    print("\n--- reported, not enforced ---")
    print("  nodes                : {:,}".format(len(nodes)))
    print("  with a cost          : {:,}".format(sum(1 for n in nodes if amount_of(n) is not None)))
    print("  verification         : {}".format(dict(verification.most_common())))
    print("  cost_status          : {}".format(dict(cost_status.most_common())))
    print("  no source recorded   : {:,}".format(no_source))
    official = sum(
        1 for n in nodes
        if any(
            urlparse(str(u)).netloc.lower().endswith((".gov", ".mil"))
            for u in (n.get("sourceUrls") or [])
            if str(u).startswith(("http://", "https://"))
        )
    )
    methods = Counter(str(n.get("verificationMethod")) for n in nodes if n.get("verificationMethod"))
    checked_failed = sum(1 for n in nodes if n.get("verificationFailure"))
    print("  official source      : {:,} of {:,} ({:.1%})".format(official, len(nodes), official / len(nodes) if nodes else 0))
    print("  verified by          : {}".format(dict(methods) or "nothing yet"))
    print("  checked, not found   : {:,}".format(checked_failed))
    summary = graph.get("__budgetSummary") if isinstance(graph.get("__budgetSummary"), dict) else {}
    print("  anchor               : {} {}".format(
        summary.get("label") or "none",
        "(reused from a previous build)" if summary.get("reused_from_previous_build") else "",
    ).rstrip())

    print()
    if gate.failures:
        total = sum(len(v) for _, v in gate.failures)
        print("FAILED: {} check(s), {} violation(s) total".format(len(gate.failures), total))
        return 1
    print("PASSED: all checks clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
