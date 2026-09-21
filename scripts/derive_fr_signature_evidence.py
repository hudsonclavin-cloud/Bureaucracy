"""Derive post evidence from the signature blocks of Federal Register documents.

    python scripts/derive_fr_signature_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_fr_signature_evidence.py             # writes data/verification/fr_signature_evidence.json

Every rule and notice the government publishes ends with a signature block
naming the signing official and that official's own title. This reads the
title. **The signer's name is never read**: the name line is located only so
that the title can be taken from below it, the rule `positions.py` sets for the
PLUM archive's incumbent columns and `whitehouse_pay.py` binds harder still.

The documents are committed verbatim under
`tests/fixtures/federal_register/signatures/` with the API listings that
selected them, and every digest is recomputed from the bytes before a line is
read. The claim is narrow and dated: this post existed, and was filled, on the
day the Register published that document. It says nothing about who holds it
now, and nothing about where it sits -- one document is one observation, so no
placement is claimed from it.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.federal_register_signatures import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    DOCUMENT_DIR,
    INDEX_DIR,
    SOURCE,
    build_records,
    read_documents,
)

REFUSALS = (
    "refused_no_signature_title",
    "refused_agencies_reach_no_organisation",
    "refused_agencies_reach_several_organisations",
    "refused_title_under_two_tokens",
    "refused_organisation_carries_no_post_of_that_name",
    "refused_siblings_share_the_name",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    parser.add_argument("--document-dir", type=Path, default=DOCUMENT_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    documents, read_stats = read_documents(args.index_dir, args.document_dir)
    base = load_base_graph(args.base_graph)
    records, stats = build_records(documents, base)

    print(f"  API listings        : {read_stats['listings']}")
    print(f"  documents listed    : {read_stats['listed_documents']} ({read_stats['listed_twice']} named by two listings)")
    print(f"  documents committed : {read_stats['documents_read']}; "
          f"{read_stats['documents_refused_by_the_host']} refused by the host (it served its "
          f"'Request Access' page until the attempts ran out, and the response was never parsed); "
          f"{read_stats['documents_not_fetched']} never fetched")
    print(f"  signature titles    : {read_stats['titles_extracted']} extracted, "
          f"{stats['distinct_titles']} of them distinct")
    for reason, count in sorted(read_stats.items()):
        if reason.startswith("refused_") and count:
            print(f"    {reason:56s}: {count}")
    print(f"  signatures matched  : {stats['signatures_matched']} across {stats['documents_considered']} documents")
    for reason in REFUSALS:
        print(f"    {reason:56s}: {stats[reason]}")
    print(f"  posts listed        : {stats['posts_listed']}")

    if args.dry_run and records:
        print("\nEach post, with the document that names it (the signer's name is not read):")
        for node_id, record in sorted(records.items(), key=lambda kv: kv[1]["listedTitle"]):
            print(f"  - {record['listedTitle']} [{node_id}]")
            print(f"    {record['documentType']} {record['documentNumber']}, published "
                  f"{record['publicationDate']}: \"{record['documentTitle']}\"")
            print(f"    filed by the Register under {', '.join(record['agenciesListed'])}"
                  f" · {record['occurrences']} committed document(s) carry this title")
    if args.dry_run:
        unmatched = Counter()
        for document in documents:
            if document.get("listedTitle"):
                unmatched[document["listedTitle"]] += 1
        for title in {r["listedTitle"] for r in records.values()}:
            unmatched.pop(title, None)
        print("\nThe titles that reached nothing, most frequent first — most are written")
        print("\"<office>, <organisation>\", and splitting one to reach a node would be")
        print("producing a title rather than selecting one:")
        for title, count in unmatched.most_common(20):
            print(f"  {count:3d}  {title}")

    print("\nA signature is evidence the post existed and was filled on the day the")
    print("Register published the document. It says nothing about who holds it now —")
    print("the signer's name is never read — and nothing about where the post sits:")
    print("one document is one observation, so no placement is claimed. A")
    print("federalregister.gov URL is classified `federal_register` rather than")
    print("`official_site` -- a notice documents an office, it is not the office's own")
    print("site -- so a post confirmed by a signature alone scores 0.4 and publishes")
    print("`unverified` with a source recorded, never `partial` and never `verified`.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    store = {
        "_note": (
            "Derived by scripts/derive_fr_signature_evidence.py from the signature blocks of "
            "Federal Register documents committed verbatim under "
            "tests/fixtures/federal_register/signatures/ with their digests and with the API "
            "listings that selected them. Each record says that the official who signed one "
            "published document stated this title, under an agency the Register's own "
            "`agencies` field reduces to exactly one organisation in this graph. The signer's "
            "name is never read. No placement is claimed: one document is one observation."
        ),
        "source": {"kind": SOURCE, "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "indexDir": str(Path(args.index_dir).relative_to(PROJECT_ROOT)),
                   "documentDir": str(Path(args.document_dir).relative_to(PROJECT_ROOT))},
        "report": {**read_stats, **stats},
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
