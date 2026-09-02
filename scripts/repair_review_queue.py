#!/usr/bin/env python3
"""Repair the served review queue offline, and say what was done.

output/candidate_nodes.json is fetched by the site (behind "Show Candidate
Nodes"). The committed copy is a 2026-03-12 crawl of pre-fix code: 1,855 of its
3,812 records are template-invented positions with a generated:// "source",
about 1,490 duplicate a published node by name, dozens carry the acronym
mangling the normaliser has since fixed, every one claims "Last Verified:
2026-03-12" for a check that never happened, and hundreds are foreign bodies
the Wikidata crawler now filters out.

A crawl needs the network. What can be done without one is to drop records
that could not be produced today and to recompute the fields the site reads.
Each rule is a predicate with a count in the report, so the repair is
reviewable, and the release gate enforces the invariants afterwards.

Usage:
    python scripts/repair_review_queue.py [--input output/candidate_nodes.json] [--output ...] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.discovery.source_discovery import estimate_candidate_confidence  # noqa: E402
from data_pipeline.exporter.build_graph import DEFAULT_GRAPH_OUTPUT, canonical_name_key, walk_tree  # noqa: E402
from data_pipeline.json_io import load_json_file, write_json_file  # noqa: E402
from data_pipeline.processors.normalize_nodes import normalize_name, verify_node_sources  # noqa: E402

DEFAULT_QUEUE = PROJECT_ROOT / "output" / "candidate_nodes.json"

# Tokens that only occur in the names of non-U.S. public bodies. Deliberately
# conservative: "Consulate"/"Embassy" alone are not here because U.S. missions
# abroad carry them too. Everything matched is listed in the report.
FOREIGN_NAME_MARKERS = (
    "Ministry of", "Ministry for", "Ministère", "Parliamentary Under-Secretary", "Parliament of",
    "Oberfinanzdirektion", "Finanzamt", "Bundes", "Landtag", "Bundestag", "Bundesrat",
    "People's Republic", "Her Majesty", "His Majesty", "Government of Canada", "Government of India",
    "Government of Australia", "Australian Government", "New South Wales", "Queensland", "Victoria Government",
    "Government of Japan", "Prefecture", "Republic of France", "Government of France", "of the United Kingdom",
    "Scottish Government", "Welsh Government", "Northern Ireland Executive", "Province of", "Provincial",
    "Cantonal", "Federal Court of Justice of Germany", "Foreign, Commonwealth and Development Office",
    "Department for ",  # UK departments ("Department for Education"); U.S. ones are "Department of"
)
MANGLED_ACRONYM = re.compile(r"\b(SEC|DOE|HUD|DoD|USA|NASA|FDIC|USPS)([a-z]+)\b")
# A record whose "name" is a bare Wikidata item id had no English label.
WIKIDATA_ID_NAME = re.compile(r"^Q\d+$")


def load_published_names(graph_path: Path) -> tuple[set[str], dict[str, str]]:
    graph = load_json_file(graph_path, default_factory=dict)
    names: set[str] = set()
    ids_by_name: dict[str, str] = {}
    ambiguous: set[str] = set()
    for node, _ in walk_tree(graph) if isinstance(graph, dict) else []:
        key = canonical_name_key(node.get("name"))
        if not key:
            continue
        names.add(key)
        if key in ids_by_name:
            ambiguous.add(key)
        else:
            ids_by_name[key] = str(node.get("id") or "")
    for key in ambiguous:
        ids_by_name.pop(key, None)
    return names, ids_by_name


def is_generated(record: dict[str, Any]) -> bool:
    urls = [record.get("sourceUrl"), *(record.get("sourceUrls") or [])]
    return any(str(url or "").startswith("generated://") for url in urls)


def is_foreign(record: dict[str, Any]) -> bool:
    haystack = " ".join(str(record.get(field) or "") for field in ("name", "possibleParent", "desc"))
    return any(marker in haystack for marker in FOREIGN_NAME_MARKERS)


def unmangle_name(name: str) -> str:
    def fix(match: re.Match[str]) -> str:
        return match.group(1).capitalize() + match.group(2)

    return MANGLED_ACRONYM.sub(fix, name)


def repair(records: list[dict[str, Any]], *, published_names: set[str], ids_by_name: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report: dict[str, Any] = {
        "input_records": len(records),
        "dropped": Counter(),
        "dropped_samples": {},
        "renamed": 0,
        "parents_resolved": 0,
        "parents_cleared": 0,
        "rescored": 0,
    }
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def drop(rule: str, record: dict[str, Any]) -> None:
        report["dropped"][rule] += 1
        samples = report["dropped_samples"].setdefault(rule, [])
        if len(samples) < 8:
            samples.append(f"{record.get('name')} ‹ {record.get('possibleParent') or '-'}")

    for raw in records:
        if not isinstance(raw, dict):
            continue
        record = dict(raw)
        if is_generated(record):
            drop("template_generated_source", record)
            continue
        if is_foreign(record):
            drop("non_us_public_body", record)
            continue
        if WIKIDATA_ID_NAME.match(str(record.get("name") or "").strip()):
            drop("unlabelled_wikidata_item", record)
            continue
        name = unmangle_name(normalize_name(record.get("name")))
        if name != record.get("name"):
            report["renamed"] += 1
            record["name"] = name
        key = canonical_name_key(name)
        if key in published_names:
            drop("duplicates_published_node", record)
            continue
        parent_name = str(record.get("possibleParent") or "").strip()
        if parent_name == "Unnamed Node" or not parent_name:
            if parent_name:
                report["parents_cleared"] += 1
            record["possibleParent"] = None
            record["possibleParentId"] = None
        else:
            record["possibleParent"] = unmangle_name(normalize_name(parent_name))
            record["possibleParentId"] = ids_by_name.get(canonical_name_key(record["possibleParent"]))
            if record["possibleParentId"]:
                report["parents_resolved"] += 1
        dedupe_key = (key, canonical_name_key(record.get("possibleParent") or ""))
        if dedupe_key in seen:
            drop("duplicate_name_and_parent", record)
            continue
        seen.add(dedupe_key)
        # Re-score under the current classifier and recompute what a source is.
        source_url = str(record.get("sourceUrl") or (record.get("sourceUrls") or [""])[0] or "")
        method = str(record.get("discoveryMethod") or "")
        if source_url and method:
            estimate = round(estimate_candidate_confidence(source_url, method), 2)
            if estimate != record.get("confidenceEstimate"):
                report["rescored"] += 1
            record["confidenceEstimate"] = estimate
            record["discoveryConfidenceEstimate"] = estimate
        record.pop("lastVerified", None)
        verify_node_sources(record)
        record["confidenceScore"] = record.get("confidenceEstimate", record.get("confidenceScore"))
        kept.append(record)

    report["output_records"] = len(kept)
    report["dropped"] = dict(report["dropped"])
    return kept, report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output", type=Path, default=None, help="defaults to --input")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])

    records = load_json_file(args.input, default_factory=list)
    if not isinstance(records, list):
        print(f"FATAL: {args.input} is not a list of candidates")
        return 2
    published_names, ids_by_name = load_published_names(args.graph)
    kept, report = repair(records, published_names=published_names, ids_by_name=ids_by_name)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.dry_run:
        write_json_file(args.output or args.input, kept)
        print(f"Wrote {len(kept):,} candidates to {args.output or args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
