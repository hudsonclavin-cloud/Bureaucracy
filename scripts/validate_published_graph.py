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

# OPM's Salary Table No. 2026-EX, mirrored so the gate can check a published
# rate against the figure the table actually prints. The gate is stdlib-only
# and reads one file — it cannot parse the fixture — and without a mirror it
# could not tell $209,600 from $290,600 on any node. The mirror is pinned to
# the fetched page by tests/test_pay_tables.py, which parses
# tests/fixtures/opm/pay/executive_schedule_2026.html and asserts equality, so
# the two cannot drift apart silently. Same precedent as `position_title_keys`.
EXECUTIVE_SCHEDULE_TABLE = "Salary Table No. 2026-EX"
EXECUTIVE_SCHEDULE_RATES = {
    "I": 253_100.0,
    "II": 228_000.0,
    "III": 209_600.0,
    "IV": 197_200.0,
    "V": 184_900.0,
}
EXECUTIVE_SCHEDULE_PAY_PLAN = "EX"
EXECUTIVE_SCHEDULE_EFFECTIVE = "2026-01-01"
EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT = "Effective January 2026"
# The page's own notes, mirrored for the same reason the rates are. The panel
# prints these inside quotation marks as "the table's own note", so an
# unchecked footnote list is a channel for a fabricated quotation attributed
# to OPM — a red team published "no pay freeze applies", the reverse of what
# the page says, and every other check passed.
EXECUTIVE_SCHEDULE_FOOTNOTES = (
    "Under a provision in the Continuing Appropriations Act, 2026 (November 12, 2025), the freeze "
    "on the payable pay rates for the Vice President and certain senior political appointees "
    "continues through January 30, 2026. Future Congressional action will determine whether these "
    "frozen rates continue beyond that date.",
)
# The weights the cascade may divide a share by. A pay rate appearing here
# would mean a rate of basic pay had become an apportionment basis.
KNOWN_COST_BASES = {
    "annual_budget_weight", "budget_weight", "direct_outlay_weight",
    "implied_budget_weight", "employee_weight", "implied_employee_weight",
    "subtree_weight",
}


def table_pay_violations(node, pay, listing, today, label):
    """Everything that must be true of a rate looked up from the salary table.

    The claim being checked is a join of two documents — *the archive reports
    this post at Level II; the January 2026 table pays Level II $228,000* — and
    every rule here exists to stop one half being published as if it were the
    other, or as if either were this unit's cost.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionPayRate {!r} is not a record".format(pay))
        return out

    # Whose figure it is. A rate of basic pay is one post's rate; on an
    # organisation it would read as what the unit costs. This is the dual of
    # the gate's existing "a measured cost sits only on an organisation".
    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    # A node standing for many posts has no single holder for a rate to be of,
    # and its own panel sentence says any figure shown is the group's.
    if node.get("representsPosts"):
        say("carries one post's rate but stands for several posts")

    # The level half. It must still be the level the archive publishes on this
    # very node: if positions.py withdrew or changed the listing, the rate is a
    # figure for a rank nothing now says this post holds.
    level = str(pay.get("payLevel") or "")
    plan = str(pay.get("payPlan") or "")
    if level not in EXECUTIVE_SCHEDULE_RATES:
        say("prices level {!r}, which the Executive Schedule does not have".format(level))
    if plan != EXECUTIVE_SCHEDULE_PAY_PLAN:
        # The archive carries Roman numerals on pay plans that are not the
        # Executive Schedule at all ("THE SECRETARY" on AD, "BOARD MEMBER -
        # CHAIR" on WC). Those are ranks in other systems and this table does
        # not price them.
        say("prices pay plan {!r}; only {!r} is the Executive Schedule".format(plan, EXECUTIVE_SCHEDULE_PAY_PLAN))
    if not isinstance(listing, dict):
        say("claims a table rate with no position listing beneath it to say what level the post is")
    else:
        if str(listing.get("payLevel") or "") != level:
            say("prices level {!r} but its listing reports {!r}".format(level, listing.get("payLevel")))
        if str(listing.get("payPlan") or "") != plan:
            say("prices pay plan {!r} but its listing reports {!r}".format(plan, listing.get("payPlan")))
        if listing.get("reportedPay") is not None:
            say("carries a table rate beside a rate the archive states; two rates for one post")

    # The rate half. The mirrored table is the only thing that can catch a
    # figure that is simply wrong, and the printed text must agree with it too
    # — the panel prints the text and the JSON carries the number.
    amount = pay.get("amount")
    expected = EXECUTIVE_SCHEDULE_RATES.get(level)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a rate of basic pay".format(amount))
    elif expected is not None and abs(float(amount) - expected) > 0.005:
        say("publishes {:,.2f} for level {}, which the table pays {:,.2f}".format(float(amount), level, expected))
    # Everything below is a field the PANEL PRINTS VERBATIM. Checking the
    # machine-readable amount and leaving these free text would mean the gate
    # vouched for a figure while the sentence beside it said something else —
    # "pays $197,200 per month", "effective January 2031", "for Level I".
    if expected is not None:
        printed = "${:,.0f}".format(expected)
        if str(pay.get("rateText") or "") != printed:
            # Not a digit comparison: digits alone let arbitrary text ride
            # along into the money figure the reader sees.
            say("prints the rate as {!r}; the table prints {!r}".format(pay.get("rateText"), printed))
        scope = str(pay.get("amountScope") or "")
        if scope.casefold() != "level {}".format(level).casefold():
            # amountScope is the only field saying which level the printed
            # rate is for, and the panel prints it at the end of the sentence.
            say("prints the rate as being for {!r} while pricing level {!r}".format(scope, level))
    if str(pay.get("table") or "") != EXECUTIVE_SCHEDULE_TABLE:
        say("cites table {!r}, not {!r}".format(pay.get("table"), EXECUTIVE_SCHEDULE_TABLE))

    # Both dates, because the two-sourced claim is only auditable when a reader
    # can see that one source is older than the other. The table's effective
    # date is deliberately NOT required to be past: a table may be published
    # ahead of the date it takes effect.
    if str(pay.get("effective") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE:
        say("dates the table {!r}, not {!r}".format(pay.get("effective"), EXECUTIVE_SCHEDULE_EFFECTIVE))
    if str(pay.get("effectiveText") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT:
        # The heading is what the panel prints; the ISO date is what the gate
        # would otherwise be checking. Both, or a reader and the machine are
        # being told different things.
        say("prints the effective heading as {!r}; the page prints {!r}".format(
            pay.get("effectiveText"), EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a table rate without a past retrieval date ({!r})".format(checked))
    url = str(pay.get("url") or "")
    host = url.split("/")[2].lower() if url.startswith("http") and url.count("/") >= 2 else ""
    if not host.endswith((".gov", ".mil")):
        say("claims a table rate with no .gov/.mil document behind it")
    source = pay.get("levelSource") if isinstance(pay.get("levelSource"), dict) else {}
    if not str(source.get("edition") or "").strip():
        say("does not say which edition of the archive reported the level")
    src_url = str(source.get("url") or "")
    src_host = src_url.split("/")[2].lower() if src_url.startswith("http") and src_url.count("/") >= 2 else ""
    if not src_host.endswith((".gov", ".mil")):
        say("does not say which document reported the level")

    # The footnote. A pay freeze for the Vice President and certain senior
    # political appointees is the difference between the table's rate and what
    # was payable, so dropping it publishes a rate that may not have been paid.
    footnotes = pay.get("footnotes")
    if not isinstance(footnotes, list) or not any(str(f).strip() for f in footnotes):
        say("carries a table rate without the notes the table prints beside it")
    elif tuple(str(f).strip() for f in footnotes) != EXECUTIVE_SCHEDULE_FOOTNOTES:
        # The panel prints these in quotation marks as the table's own words,
        # so anything but the page's actual notes is a fabricated quotation.
        say("quotes notes the table does not carry")

    # It is not a cost, and it is not evidence that the post exists.
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a table rate and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a table rate and claims a verified cost")
    basis = str(node.get("cost_basis") or "")
    if basis and basis not in KNOWN_COST_BASES:
        say("carries a table rate and an unknown cost basis {!r}".format(basis))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a salary table that names no post")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a salary table that names no post")
    return out


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


def _within(curated, official, tolerance):
    """Is the curated string within `tolerance` of the official count? The
    same first-number-with-magnitudes reading the cascade uses, kept local so
    the gate stays stdlib-only; a wildly different figure is the finding, not
    a violation, so this only feeds the report."""
    import re as _re

    text = str(curated or "").replace(",", "")
    match = _re.search(r"(\d+(?:\.\d+)?)\s*(million|thousand|k|m)?", text, _re.I)
    if not match or not official:
        return True
    value = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    value *= {"million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(suffix, 1)
    if not value:
        return True
    return abs(value - official) <= tolerance * max(value, official)


def parent_name_of(node, parent_of, by_id):
    parent = by_id.get(parent_of.get(str(node.get("id") or "")))
    return (parent or {}).get("name")


def position_title_keys(name, parent_name):
    """The keys a curated position name answers to: itself, itself without a
    trailing qualifier that is the parent's own name or acronym, and each
    slash-separated alternative. The same reduction
    data_pipeline/verification/positions.py makes, mirrored here so the gate
    stays stdlib-only; tests/test_positions.py pins the two together."""
    text = str(name or "").strip()
    parent_keys = set()
    parent_text = str(parent_name or "").strip()
    if parent_text:
        parent_keys.add(canonical_key(parent_text))
        acronyms = re.findall(r"\(([^)]+)\)", parent_text)
        parent_keys.update(canonical_key(a) for a in acronyms)
        without = canonical_key(re.sub(r"\([^)]*\)", " ", parent_text))
        if without:
            parent_keys.add(without)
    core = text
    if "," in text:
        for index, char in enumerate(text):
            if char != ",":
                continue
            head, tail = text[:index].strip(), text[index + 1:].strip()
            if head and tail and canonical_key(tail) in parent_keys:
                core = head
                break
    keys = set()
    for candidate in (text, core):
        key = canonical_key(candidate)
        if key:
            keys.add(key)
        for part in str(candidate).split("/"):
            part_key = canonical_key(part)
            if part_key:
                keys.add(part_key)
    return keys or {canonical_key(text)}


def directory_name_keys(value):
    """The Federal Register's agency directory writes the head noun last
    ("Prisons Bureau", "Energy Department", "Inspector General Office, Energy
    Department"); the curated file writes "Bureau of Prisons". The same
    rewrite data_pipeline/verification/directories.py matches by, mirrored
    here so the gate stays stdlib-only; tests pin the two together."""
    text = str(value or "")
    if "," in text:
        core, _, tail = text.rpartition(",")
        # A qualifier ("…, Energy Department") is a scope, not part of the name.
        if tail.strip().endswith(("Department", "President", "Congress", "Agency", "Administration", "Commission")):
            text = core
    key = canonical_key(text)
    if not key:
        return set()
    keys = {key}
    tokens = key.split()
    heads = ("department", "office", "bureau", "administration", "agency", "service", "commission", "board",
             "corporation", "council", "institute", "center", "division", "foundation", "authority", "committee")
    if len(tokens) > 1 and tokens[-1] in heads:
        head, rest = tokens[-1], " ".join(tokens[:-1])
        for prep in ("of", "of the", "for", "on"):
            keys.add("{} {} {}".format(head, prep, rest))
    for k in list(keys):
        if k.startswith("united states "):
            keys.add(k[len("united states "):])
        else:
            keys.add("united states " + k)
    return keys


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
    KNOWN_METHODS = {
        "name_labelled_on_own_official_page",
        "name_labelled_on_parent_official_page",
        "listed_in_federal_register_agency_directory",
        "listed_in_senate_committee_list",
        "listed_in_opm_plum_archive",
    }
    KNOWN_FAILURES = {"not_found", "not_in_official_list"}
    failure_beside_source, unofficial_official, unknown_method = [], [], []
    # Kept apart from unknown_method deliberately: a pay defect printed under
    # "every verification method is one this pipeline can produce" would be
    # reported as the wrong kind of fault.
    bad_table_pay = []
    for node in nodes:
        urls = [str(u) for u in (node.get("sourceUrls") or []) if str(u).startswith(("http://", "https://"))]
        official = [u for u in urls if urlparse(u).netloc.lower().endswith((".gov", ".mil"))]
        if node.get("verificationFailure") and urls:
            failure_beside_source.append("{} claims {!r} beside {} source(s)".format(label(node), node["verificationFailure"], len(urls)))
        if node.get("verificationFailure") and str(node.get("verificationFailure")) not in KNOWN_FAILURES:
            unknown_method.append("{} verificationFailure {!r}".format(label(node), node.get("verificationFailure")))
        # A negative must be as auditable as a positive: it names the page or
        # the list it was checked against, and when. The panel prints that URL.
        failure_kind = str(node.get("verificationFailure") or "")
        if failure_kind:
            src = node.get("verificationFailureSource") if isinstance(node.get("verificationFailureSource"), dict) else {}
            src_url = str(src.get("url") or "")
            src_host = src_url.split("/")[2].lower() if src_url.startswith("http") and src_url.count("/") >= 2 else ""
            src_date = str(src.get("checkedAt") or "")
            if failure_kind == "not_in_official_list" and not src_url.startswith("https://www.senate.gov/"):
                unknown_method.append("{} claims not_in_official_list without the list's URL".format(label(node)))
            elif failure_kind == "not_found" and not src_host.endswith((".gov", ".mil")):
                unknown_method.append("{} claims its own page did not name it, without naming the page".format(label(node)))
            if not re.match(r"^\d{4}-\d{2}-\d{2}", src_date) or src_date[:10] > today:
                unknown_method.append("{} claims a failed check without a past date ({!r})".format(label(node), src_date))
        # An official headcount is a sourced number beside an uncited one; it
        # needs the file, the period and a past date, or it is just another
        # uncited number with a better name. The coverage sentence is
        # required too: the population is what makes it comparable at all.
        official_headcount = node.get("employeesOfficial")
        if official_headcount is not None:
            src = node.get("employeesOfficialSource") if isinstance(node.get("employeesOfficialSource"), dict) else {}
            src_url = str(src.get("url") or "")
            src_host = src_url.split("/")[2].lower() if src_url.startswith("http") and src_url.count("/") >= 2 else ""
            src_date = str(src.get("checkedAt") or "")
            if not isinstance(official_headcount, int) or official_headcount < 0:
                unknown_method.append("{} employeesOfficial {!r}".format(label(node), official_headcount))
            if not src_host.endswith((".gov", ".mil")) or not src.get("period") or not src.get("coverage"):
                unknown_method.append("{} claims an official headcount without a .gov file, a period and its coverage".format(label(node)))
            if not re.match(r"^\d{4}-\d{2}-\d{2}", src_date) or src_date[:10] > today:
                unknown_method.append("{} claims an official headcount without a past date ({!r})".format(label(node), src_date))
        # A position listing is a record of the archive's period, never of now.
        listing = node.get("positionListing")
        if listing is not None:
            if not isinstance(listing, dict):
                unknown_method.append("{} positionListing {!r}".format(label(node), listing))
            else:
                l_url = str(listing.get("url") or "")
                l_host = l_url.split("/")[2].lower() if l_url.startswith("http") and l_url.count("/") >= 2 else ""
                l_date = str(listing.get("checkedAt") or "")
                if not l_host.endswith((".gov", ".mil")) or not listing.get("edition"):
                    unknown_method.append("{} claims a position listing without a .gov file and the edition it came from".format(label(node)))
                if not re.match(r"^\d{4}-\d{2}-\d{2}", l_date) or l_date[:10] > today:
                    unknown_method.append("{} claims a position listing without a past date ({!r})".format(label(node), l_date))
                # The archive's LevelGradePay column is a rank for some rows
                # and a rate of basic pay for others. Once split, neither may
                # hold the other's kind of value: a rank that is a dollar
                # figure was the wrong claim about the right number, and a
                # rate that is not a positive number is not a rate at all.
                pay_level = listing.get("payLevel")
                if pay_level is not None and (not isinstance(pay_level, str) or "$" in pay_level):
                    unknown_method.append("{} publishes {!r} as a pay level".format(label(node), pay_level))
                reported_pay = listing.get("reportedPay")
                if reported_pay is not None:
                    if isinstance(reported_pay, bool) or not isinstance(reported_pay, (int, float)) or reported_pay <= 0:
                        unknown_method.append("{} publishes {!r} as a reported rate of pay".format(label(node), reported_pay))
                    elif "$" not in str(listing.get("reportedPayText") or ""):
                        unknown_method.append("{} reports pay without the text the archive prints".format(label(node)))
        # A rate looked up from the salary table for the level the archive
        # reports. Two documents, neither of which says what this post pays: the
        # checks below are what keep the join from being read as one source.
        pay = node.get("positionPayRate")
        if pay is not None:
            bad_table_pay.extend(table_pay_violations(node, pay, listing, today, label))
        # The same, for a page read that did not name the node and stands
        # beside a directory listing that did.
        read_not_named = node.get("pageReadNotNamed")
        if read_not_named is not None:
            if not isinstance(read_not_named, dict):
                unknown_method.append("{} pageReadNotNamed {!r}".format(label(node), read_not_named))
            else:
                rn_url = str(read_not_named.get("url") or "")
                rn_host = rn_url.split("/")[2].lower() if rn_url.startswith("http") and rn_url.count("/") >= 2 else ""
                rn_date = str(read_not_named.get("checkedAt") or "")
                if not rn_host.endswith((".gov", ".mil")) or not re.match(r"^\d{4}-\d{2}-\d{2}", rn_date) or rn_date[:10] > today:
                    unknown_method.append("{} records a page read that did not name it, without a .gov URL and a past date".format(label(node)))
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
    by_id = {}
    stack_p = [(graph, None)]
    while stack_p:
        n, p = stack_p.pop()
        parent_of[str(n.get("id") or "")] = p
        by_id[str(n.get("id") or "")] = n
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
        if str(node.get("placementMethod") or "") not in (
            "name_labelled_on_parent_official_page",
            "listed_under_parent_in_federal_register_agency_directory",
            "listed_under_committee_in_senate_committee_list",
            "listed_under_organization_in_opm_plum_archive",
        ):
            placement_unbacked.append("{} placementMethod {!r}".format(label(node), node.get("placementMethod")))
        matched = canonical_key(node.get("placementMatchedText"))
        name_key = canonical_key(node.get("name"))
        if str(node.get("placementMethod") or "") == "listed_under_committee_in_senate_committee_list":
            matched = re.sub(r"^subcommittee on (the )?", "", matched)
            name_key = re.sub(r"^subcommittee on (the )?", "", name_key)
        if str(node.get("placementMethod") or "") == "listed_under_organization_in_opm_plum_archive":
            # A curated position name legitimately carries the parent's own
            # name or acronym ("Director, AHRQ" under AHRQ), and may offer
            # alternatives ("Director / Administrator / Chair"). The plain
            # substring test would refuse 25 of the 91 real matches, so the
            # gate mirrors the module's rule; a test pins the two together.
            name_key = min(position_title_keys(node.get("name"), parent_name_of(node, parent_of, by_id)), key=len, default=name_key)
        if matched and name_key and name_key not in matched and name_key not in directory_name_keys(node.get("placementMatchedText")):
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
    gate.check("a salary-table rate names a level the archive still reports and the rate that table prints", bad_table_pay)

    # A published disagreement is a claim like any other: it must name both
    # figures, sit on the estimate it actually affected, and be a real
    # disagreement. An empty or self-agreeing dispute block would read as a
    # caveat where there is none.
    bad_dispute = []
    for node in nodes:
        dispute = node.get("cost_weight_dispute")
        if dispute is None:
            continue
        if not isinstance(dispute, dict):
            bad_dispute.append("{} cost_weight_dispute is a {}".format(label(node), type(dispute).__name__))
            continue
        curated = dispute.get("curatedEmployeesParsed")
        official = dispute.get("officialEmployees")
        if not isinstance(curated, (int, float)) or isinstance(curated, bool) or curated <= 0:
            bad_dispute.append("{} dispute has no curated figure".format(label(node)))
            continue
        if not isinstance(official, (int, float)) or isinstance(official, bool) or official <= 0:
            bad_dispute.append("{} dispute has no official figure".format(label(node)))
            continue
        if official != node.get("employeesOfficial"):
            bad_dispute.append("{} dispute cites {!r}, the node carries {!r}".format(
                label(node), official, node.get("employeesOfficial")))
        if abs(curated - official) / official <= 0.10:
            bad_dispute.append("{} dispute between {} and {} is within 10%".format(label(node), curated, official))
        if str(node.get("cost_status") or "") != "allocated" or str(node.get("cost_basis") or "") != "employee_weight":
            bad_dispute.append("{} dispute on a {!r} cost with basis {!r}".format(
                label(node), node.get("cost_status"), node.get("cost_basis")))
        if not str(dispute.get("url") or "").startswith("https://"):
            bad_dispute.append("{} dispute has no source URL".format(label(node)))
    gate.check("every published weight dispute names both figures and is one", bad_dispute)

    # A measured cost belongs to an organisation. An outside review of an
    # older checkout of this project reported $463.2M of the Comptroller of
    # the Currency's outlays published on a node typed Position; that is not
    # true on this graph — apply_treasury_outlay_rows has excluded position,
    # committee, role and caucus types from name matching, and none of the
    # measured nodes is one — but nothing here forbade it, so a re-fed payload
    # or a future change could reintroduce exactly that. A Treasury line names
    # an organisation's outlays; publishing one as a post's cost would be a
    # measured figure about the wrong kind of thing.
    non_org_measured = []
    for node in nodes:
        if str(node.get("cost_status") or "") not in ("official", "scaled_official"):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in ("position", "role", "committee", "caucus", "office holder")):
            non_org_measured.append("{} is a {!r} carrying a measured cost".format(label(node), node.get("type")))
    gate.check("a measured cost sits only on an organisation", non_org_measured)

    # A name that states how many things it stands for, against what the
    # graph carries. The claim is only ever "the name says N, we carry M";
    # it must be arithmetic, and it must not appear where it is not true.
    bad_counts = []
    for node, parent in walk(graph):
        stated, carried = node.get("statedChildCount"), node.get("carriedChildCount")
        if stated is None and carried is None and not node.get("childrenIncomplete"):
            continue
        if not isinstance(stated, int) or not isinstance(carried, int) or stated < 0 or carried < 0:
            bad_counts.append("{} states {!r} and carries {!r}".format(label(node), stated, carried))
            continue
        real = sum(1 for c in (node.get("children") or []) if isinstance(c, dict) and not c.get("synthetic"))
        if carried != real:
            bad_counts.append("{} says it carries {} children, the tree has {}".format(label(node), carried, real))
        if bool(node.get("childrenIncomplete")) != (carried < stated):
            bad_counts.append("{} flags incomplete={!r} with {} of {}".format(
                label(node), node.get("childrenIncomplete"), carried, stated))
        if str(stated) not in str(node.get("name") or ""):
            bad_counts.append("{} claims a stated count its name does not carry".format(label(node)))
    gate.check("a stated child count is the name's and the tree's", bad_counts)

    # A position standing for several posts. Where the name gives no number,
    # none may be published: an invented count is a figure nobody wrote.
    bad_multiplicity = []
    for node in nodes:
        represents = node.get("representsPosts")
        if represents is None:
            continue
        if not isinstance(represents, dict) or represents.get("kind") not in ("exact", "range", "unstated"):
            bad_multiplicity.append("{} representsPosts {!r}".format(label(node), represents))
            continue
        kind = represents["kind"]
        if kind == "exact" and not (isinstance(represents.get("count"), int) and represents["count"] > 1):
            bad_multiplicity.append("{} states {!r} posts".format(label(node), represents.get("count")))
        if kind == "range":
            low, high = represents.get("low"), represents.get("high")
            if not (isinstance(low, int) and isinstance(high, int) and 0 < low <= high):
                bad_multiplicity.append("{} states a range {!r}-{!r}".format(label(node), low, high))
        if kind == "unstated" and any(k in represents for k in ("count", "low", "high")):
            bad_multiplicity.append("{} invents a number for an unstated multiplicity".format(label(node)))
        if str(represents.get("text") or "") not in str(node.get("name") or ""):
            bad_multiplicity.append("{} quotes {!r}, which is not in its name".format(label(node), represents.get("text")))
    gate.check("a multiplicity is read from the name and never invented", bad_multiplicity)

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
    # "with a cost" is not "with a known cost". A record naming the node is
    # the only thing that makes a figure that node's own; everything else is
    # its share of an ancestor's total, divided by a weight. Reported as
    # nodes and as dollars, because the two say different things: a handful
    # of measured nodes can cover most of the money, and usually do.
    exact = [n for n in nodes if str(n.get("cost_status") or "") in ("official", "root_total")]
    estimated = [n for n in nodes if str(n.get("cost_status") or "") in ("allocated", "scaled_official")]
    anchor_total = amount_of(graph) or 0.0
    top_exact, seen_exact = [], set()

    def collect_exact(node, inside):
        node_id = str(node.get("id") or "")
        measured = str(node.get("cost_status") or "") == "official"
        if measured and not inside and node_id not in seen_exact:
            seen_exact.add(node_id)
            top_exact.append(node)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                collect_exact(child, inside or measured)

    for branch in graph.get("children") or []:
        if isinstance(branch, dict):
            collect_exact(branch, False)
    # Signed: the government-wide offsetting receipts are a measured, negative
    # top-most line, and taking its magnitude would count $343B of receipts as
    # $343B of covered spending and push the coverage past 100%.
    exact_dollars = sum(amount_of(n) or 0.0 for n in top_exact)
    print("  cost identified for the node itself: {:,} of {:,} nodes ({:.1%}); {:,} are a share of an ancestor's total".format(
        len(exact), len(nodes), len(exact) / len(nodes) if nodes else 0, len(estimated)))
    print("  the measured nodes cover {:.1%} of the anchor ({:,.0f} of {:,.0f}), counting each only once".format(
        exact_dollars / anchor_total if anchor_total else 0, exact_dollars, anchor_total))
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
    directory_listed = sum(1 for n in nodes if isinstance(n.get("directoryListing"), dict) and n["directoryListing"].get("source") != "senate_committee_list")
    directory_placed = sum(1 for n in org_edges if str(n.get("placementMethod") or "") == "listed_under_parent_in_federal_register_agency_directory")
    directory_disagree = sum(1 for n in nodes if isinstance(n.get("placementDirectoryDisagreement"), dict))
    directory_ancestor = sum(1 for n in nodes if isinstance(n.get("placementDirectoryAncestor"), dict))
    print("  directory-listed     : {:,} in the Federal Register's agency directory; {:,} placements from it; {:,} filed under an ancestor here; {:,} filed elsewhere by it".format(
        directory_listed, directory_placed, directory_ancestor, directory_disagree))
    senate_listed = sum(1 for n in nodes if isinstance(n.get("directoryListing"), dict) and n["directoryListing"].get("source") == "senate_committee_list")
    senate_placed = sum(1 for n in org_edges if str(n.get("placementMethod") or "") == "listed_under_committee_in_senate_committee_list")
    senate_missing = sum(1 for n in nodes if str(n.get("verificationFailure") or "") == "not_in_official_list")
    official_counts = [n for n in nodes if n.get("employeesOfficial") is not None]
    disagree = sum(
        1 for n in official_counts
        if str(n.get("employees") or "").strip() and not _within(n.get("employees"), n["employeesOfficial"], 0.10)
    )
    listings = [n for n in nodes if isinstance(n.get("positionListing"), dict)]
    disputed = [n for n in nodes if isinstance(n.get("cost_weight_dispute"), dict)]
    print("  OPM headcounts       : {:,} nodes carry one; {:,} differ from the curated figure by more than 10%".format(
        len(official_counts), disagree))
    print("  weights disputed     : {:,} allocated shares were apportioned by a headcount OPM's file contradicts".format(
        len(disputed)))
    with_rate = sum(1 for n in listings if isinstance(n["positionListing"].get("reportedPay"), (int, float)))
    with_level = sum(1 for n in listings if n["positionListing"].get("payLevel"))
    print("  archive pay          : {:,} positions carry a rate of basic pay the archive reports; {:,} carry a level or grade only".format(
        with_rate, with_level))
    table_paid = [n for n in nodes if isinstance(n.get("positionPayRate"), dict)]
    by_level = {}
    for n in table_paid:
        key = str(n["positionPayRate"].get("payLevel") or "?")
        by_level[key] = by_level.get(key, 0) + 1
    print("  salary table         : {:,} positions priced from {} for the level the archive reports ({}); "
          "{:,} not priced (a level on another pay plan)".format(
              len(table_paid), EXECUTIVE_SCHEDULE_TABLE,
              ", ".join("{} {}".format(k, by_level[k]) for k in sorted(by_level, key=len)) or "none",
              with_level - len(table_paid)))
    print("  PLUM archive         : {:,} positions listed in the previous administration's archive; {:,} placements from it".format(
        len(listings), sum(1 for n in nodes if str(n.get("placementMethod") or "") == "listed_under_organization_in_opm_plum_archive")))
    print("  Senate list          : {:,} committees and subcommittees listed; {:,} placements from it; {:,} curated names the list does not carry".format(
        senate_listed, senate_placed, senate_missing))
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
