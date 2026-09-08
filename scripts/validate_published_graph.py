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
        urls_here = node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []
        backed = (
            str(node.get("cost_status") or "") == "official"
            and node.get("rollup_total_amount") is not None
            and "treasury_outlays" in types
            # The type is a label; the URL is the evidence. The evidence module
            # once stripped the FiscalData URL from 26 measured nodes and this
            # check, keyed on the type alone, let the Supreme Court cite a court
            # About page as the source of its outlays.
            and any("fiscaldata.treasury.gov" in str(u) for u in urls_here)
        )
        if not backed:
            illegitimate.append("{} claims a measured cost without a Treasury line and its URL".format(label(node)))
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

    # 5. A part cannot cost more than the whole — less the whole's negative
    #    parts. Since the statement's receipts are carried as explicit
    #    negative lines, a positive child may reach the parent's figure plus
    #    what its negative siblings take back (CMS's $2.3T sits inside HHS's
    #    $1.7T net beside −$749B of Medicare premiums and transfers), and no
    #    further. A line the Treasury files under another section is outside
    #    the parent's total altogether and is checked in the report instead.
    def is_external(node):
        return node.get("treasury_external_section") is True

    over_parent = []
    for parent, _ in pairs:
        parent_amount = amount_of(parent)
        if parent_amount is None:
            continue
        kids = [c for c in (parent.get("children") or []) if isinstance(c, dict) and not is_external(c)]
        negatives = sum(a for a in (amount_of(c) for c in kids) if a is not None and a < 0)
        pool = parent.get("treasury_pool_negative")
        capacity = parent_amount - negatives + (-float(pool) if isinstance(pool, (int, float)) and pool < 0 else 0.0)
        for child in kids:
            child_amount = amount_of(child)
            if child_amount is None or child_amount <= 0:
                continue
            if child_amount > capacity * (1 + 1e-9) + 0.01:
                over_parent.append(
                    "{} = {:,.2f} > parent {} = {:,.2f} less its negative lines {:,.2f}".format(
                        label(child), child_amount, label(parent), parent_amount, negatives
                    )
                )
    gate.check("no child costs more than its parent less the parent's negative lines", over_parent)

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
    #     A negative figure is a different thing: net outlays below zero are
    #     what the Treasury reports for the Mint, the FDIC, the Executive
    #     Office of the President, and for the receipts it nets inside every
    #     section. Those may be negative — a Treasury line, a receipts line
    #     the exporter carries explicitly, or an estimate for a grouping whose
    #     measured members net below zero (stamped measured_net_beneath) —
    #     and nothing else may.
    non_positive = []
    unlabelled_missing = []
    for node in nodes:
        amount = amount_of(node)
        if amount is not None and amount == 0:
            non_positive.append("{} = 0.00".format(label(node)))
        elif amount is not None and amount < 0:
            measured_line = node.get("rollup_total_amount") is not None and str(node.get("treasury_row_name") or "")
            receipts_line = str(node.get("synthetic") or "") == "treasury_receipts"
            net_beneath = node.get("measured_net_beneath")
            negative_grouping = isinstance(net_beneath, (int, float)) and net_beneath < 0 and str(node.get("cost_status") or "") == "allocated"
            if not (measured_line or receipts_line or negative_grouping):
                non_positive.append("{} = {:,.2f} is negative without a Treasury line behind it".format(label(node), amount))
        elif amount is None and str(node.get("cost_status") or "") != "unavailable":
            unlabelled_missing.append("{} has no amount and cost_status {!r}".format(label(node), node.get("cost_status")))
    gate.check("no zero amounts, and no negative amount without a Treasury line behind it", non_positive)
    gate.check("a missing amount is labelled unavailable", unlabelled_missing)
    # A Treasury line is a measured figure; while the root is anchored, every
    # one is published, in full or capped, never as "not available". Six lines
    # under the independent-agencies grouping ($3.08B, the Peace Corps among
    # them) were hidden this way once, and the cap summary never counted them
    # because it counts only scaled_official nodes.
    hidden_lines = []
    if str(graph.get("cost_status") or "") == "root_total" and graph.get("resolved_total_amount") is not None:
        for node in nodes:
            if node is graph:
                continue
            line = node.get("rollup_total_amount")
            if isinstance(line, (int, float)) and line != 0 and str(node.get("cost_status") or "") == "unavailable":
                hidden_lines.append("{} carries a Treasury line of {:,.2f} but is published unavailable".format(label(node), line))
    gate.check("no Treasury line is hidden as unavailable", hidden_lines)

    # 11. Check 6, at every level: the parts of any node must fit inside it —
    #     signed, with two named exceptions the node itself declares. A line
    #     the Treasury files under another section is not part of this
    #     parent's total (treasury_external_section). And a netted unit whose
    #     lines exceed its net total by a negative line the graph has no node
    #     for carries treasury_pool_negative, the exact excess, and its
    #     unlined children publish nothing; the excess is allowed, to the cent.
    over_parent_sums = []
    external_lines = []
    negative_pools = []
    for parent, _ in pairs:
        parent_amount = amount_of(parent)
        if parent_amount is None:
            continue
        children = [c for c in (parent.get("children") or []) if isinstance(c, dict)]
        external_lines.extend(c for c in children if is_external(c))
        child_amounts = [a for a in (amount_of(c) for c in children if not is_external(c)) if a is not None]
        if not child_amounts:
            continue
        total = sum(child_amounts)
        allowance = 0.0
        pool = parent.get("treasury_pool_negative")
        if isinstance(pool, (int, float)) and pool < 0:
            allowance = -float(pool)
            negative_pools.append(parent)
        if total > parent_amount + abs(parent_amount) * CHILD_SUM_TOLERANCE + allowance + 0.01:
            over_parent_sums.append(
                "children of {} sum to {:,.2f} > {:,.2f}{}".format(
                    label(parent), total, parent_amount, " + declared negative pool {:,.2f}".format(allowance) if allowance else ""
                )
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
    # One exception, by design: the government-wide offsetting receipts the
    # Treasury nets against Total Outlays without assigning them to any
    # branch. It is a Treasury accounting line, not a fourth branch, and it
    # is the only thing allowed beside the three.
    receipts_at_root = [
        c for c in top_level
        if isinstance(c, dict) and str(c.get("synthetic") or "") == "treasury_receipts"
        and str(c.get("id") or "") == "treasury-undistributed-offsetting-receipts"
    ]
    actual_top = tuple(str(c.get("id") or "") for c in top_level if c not in receipts_at_root)
    if len(receipts_at_root) > 1:
        actual_top = actual_top + ("treasury-undistributed-offsetting-receipts",) * (len(receipts_at_root) - 1)
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
        region = node.get("verificationMatchedIn")
        if region is not None and str(region) not in ("navigation", "content"):
            unknown_method.append("{} verificationMatchedIn {!r}".format(label(node), region))
    # Placement: evidence for the parent -> child edge. A True claim must carry
    # an official URL and a date, and must name the parent the published tree
    # actually gives the node — evidence for a different edge is not evidence.
    placement_unbacked, placement_wrong_parent = [], []
    parent_of = {}
    stack_p = [(graph, None)]
    while stack_p:
        n, p = stack_p.pop()
        parent_of[str(n.get("id") or "")] = p
        for c in n.get("children", []) or []:
            if isinstance(c, dict):
                stack_p.append((c, str(n.get("id") or "")))
    for node in nodes:
        if node.get("placementVerified") is False:
            # "Read and not listed" is a statement about one parent's page on
            # one date; it must name the parent the tree has and a real date.
            stamp = str(node.get("placementVerifiedAt") or "")
            if not re.match(r"^\d{4}-\d{2}-\d{2}", stamp) or stamp[:10] > today:
                placement_unbacked.append("{} placementVerified false at {!r}".format(label(node), stamp))
            claimed = str(node.get("placementParentId") or "")
            actual = parent_of.get(str(node.get("id") or ""))
            if not claimed or claimed != actual:
                placement_wrong_parent.append("{} not-listed claims parent {!r}, tree has {!r}".format(label(node), claimed, actual))
        if node.get("placementVerified") is not None and node.get("placementCheckable") is False:
            placement_unbacked.append("{} says its placement could not be checked beside a placement result".format(label(node)))
        if node.get("placementVerified") is not True:
            continue
        url = str(node.get("placementUrl") or "")
        host = url.split("/")[2].lower() if url.startswith("http") and url.count("/") >= 2 else ""
        stamp = str(node.get("placementVerifiedAt") or "")
        if not host.endswith((".gov", ".mil")) or not re.match(r"^\d{4}-\d{2}-\d{2}", stamp) or stamp[:10] > today:
            placement_unbacked.append("{} placementUrl {!r} at {!r}".format(label(node), url, stamp))
        if str(node.get("placementMethod") or "") != "name_labelled_on_parent_official_page":
            placement_unbacked.append("{} placementMethod {!r}".format(label(node), node.get("placementMethod")))
        matched = canonical_key(node.get("placementMatchedText"))
        name_key = canonical_key(node.get("name"))
        if matched and name_key and name_key not in matched:
            placement_unbacked.append("{} placement text {!r} does not name it".format(label(node), node.get("placementMatchedText")))
        if node.get("placementMatchedIn") is not None and str(node.get("placementMatchedIn")) not in ("navigation", "content"):
            placement_unbacked.append("{} placementMatchedIn {!r}".format(label(node), node.get("placementMatchedIn")))
        claimed = str(node.get("placementParentId") or "")
        actual = parent_of.get(str(node.get("id") or ""))
        if not claimed or claimed != actual:
            placement_wrong_parent.append("{} claims parent {!r}, tree has {!r}".format(label(node), claimed, actual))
    gate.check("every placement claim has an official URL and a date", placement_unbacked)
    gate.check("every placement claim names the parent the tree actually has", placement_wrong_parent)

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
    org_edges = [n for n in nodes if n is not graph and "position" not in str(n.get("type") or "").lower()]
    placed = sum(1 for n in org_edges if n.get("placementVerified") is True)
    placed_no = sum(1 for n in org_edges if n.get("placementVerified") is False)
    unreachable = sum(1 for n in org_edges if n.get("placementCheckable") is False)
    print("  placement evidenced  : {:,} of {:,} organisation edges ({:.1%}); {:,} checked and not listed; {:,} unreachable (parent has no page)".format(
        placed, len(org_edges), placed / len(org_edges) if org_edges else 0, placed_no, unreachable))
    # A capped Treasury line publishes below the figure the statement reported.
    # Each node says so in the panel; this is the total, which nothing showed.
    # Only the top-most capped node in a branch: a capped department and its
    # capped bureaus are the same dollars, and adding both overstates it ~4x.
    cap_nodes = cap_reported = cap_published = 0
    def walk_capped(node, inside):
        nonlocal cap_nodes, cap_reported, cap_published
        capped = str(node.get("cost_status") or "") == "scaled_official"
        if capped and not inside:
            line = node.get("rollup_total_amount")
            try:
                line = float(line)
            except (TypeError, ValueError):
                line = 0.0
            if line > 0:
                cap_nodes += 1
                cap_reported += line
                cap_published += amount_of(node) or 0.0
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                walk_capped(child, inside or capped)
    walk_capped(graph, False)
    if cap_reported:
        print("  Treasury lines capped: {:,} top-most nodes · ${:,.0f} reported vs ${:,.0f} published · {:.1%} shown, ${:,.0f} withheld".format(
            cap_nodes, cap_reported, cap_published, cap_published / cap_reported, cap_reported - cap_published))
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
