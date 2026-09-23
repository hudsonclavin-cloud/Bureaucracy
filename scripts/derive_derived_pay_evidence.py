#!/usr/bin/env python
"""Derive pay evidence for the Article I courts from a statutory parity
provision joined to the U.S. Courts' own Judicial Compensation table.

    python scripts/derive_derived_pay_evidence.py --dry-run
    python scripts/derive_derived_pay_evidence.py    # writes data/verification/derived_pay_evidence.json

Reads five committed files and fetches nothing: four U.S. Code sections
(26 U.S.C. 7443, 28 U.S.C. 172, 10 U.S.C. 942, 38 U.S.C. 7253), each of which
states which tier of Article III judge that court's judges are paid at, and
the Judicial Compensation table, which states what each tier pays.

**Neither document states the figure.** This is the only source in the project
whose record is a derivation rather than a quotation, and every record says so:
it carries both documents, the count, and the percentage this project's own
source arithmetic gives for that count, beside an explicit
`documentsStatingTheFigure: 0`.

A quote is checked against its section's OPERATIVE text -- everything above
the publisher's notes -- and never against the whole page. uscode.house.gov
prints a section's repealed text beneath the law, and a research pass this was
built from read 38 U.S.C. 7253's repealed subsection as though it were current.
See `data_pipeline/verification/derived_pay.py`.

Every record is validated against its own node by
`financial_evidence.validate_record` before it is written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification import financial_evidence as fe  # noqa: E402
from data_pipeline.verification.derived_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    STRENGTH_SCALE,
    Unreadable,
    build_records,
    document_strength_percent,
)
from data_pipeline.verification.judicial_pay import (  # noqa: E402
    DEFAULT_TABLE_HTML,
    load_judicial_compensation,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE_HTML,
                        help="verbatim uscourts.gov Judicial Compensation page")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_judicial_compensation(args.table)
    except Exception as error:  # the judicial module raises its own Unreadable
        print(f"refused: {error}")
        return 1
    table = loaded["table"]
    year = sorted(table["years"], reverse=True)[0]
    compensation = dict(table["years"][year])

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    try:
        records, report = build_records(
            node_map,
            compensation,
            table_url=loaded["url"],
            table_sha256=loaded["sha256"],
            table_retrieved_at=loaded["fetched_at"],
        )
    except Unreadable as error:
        print(f"refused: {error}")
        return 1

    validated: dict[str, dict] = {}
    rejected: list[str] = []
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            rejected.append(f"{node_id}: not in the base graph")
            continue
        try:
            out = fe.validate_record(record, node)
        except fe.Rejected as error:
            rejected.append(str(error))
            continue
        state = fe.classify(out)
        if state != "partial":
            rejected.append(
                f"{node_id}: classified {state!r}; no document here states this figure, so nothing "
                "from this source may be more than a proxy"
            )
            continue
        out["financialEvidenceStatus"] = state
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"Judicial Compensation {year}, fetched {loaded['fetched_at']}")
    for tier, values in sorted(compensation["tiers"].items()):
        print(f"    {values['rateText']:>10s}  {tier}")
    print(f"considered {report['considered']}  priced {report['priced']}  validated {report['validated']}")
    for node_id, record in sorted(records.items()):
        print(f"    PRICED   {node_id}")
        print(f"             {record['derivation']}")
    for node_id, reason in report["refused"].items():
        print(f"    refused: {node_id} — {reason}")
    for node_id, reason in report["notPriced"].items():
        print(f"    not priced: {node_id} — {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print(
        f"Every record rests on {report['documentsPerRecord']} official documents "
        f"({document_strength_percent(report['documentsPerRecord'])}% on {STRENGTH_SCALE}); "
        f"{report['documentsStatingTheFigure']} of them state the figure."
    )
    print("Every record is scoped 'proxy'. Basic pay is not the node's cost, and nothing here writes a source URL onto a node.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_derived_pay_evidence.py from two kinds of document, NEITHER of which "
            "states the figure it publishes. Four parity provisions — 26 U.S.C. 7443(c)(1) (Tax Court), "
            "28 U.S.C. 172(b) (Court of Federal Claims), 10 U.S.C. 942(d) (Court of Appeals for the Armed "
            "Forces) and 38 U.S.C. 7253(e) (Court of Appeals for Veterans Claims) — each state which tier of "
            "Article III judge that court's judges are paid at; the Administrative Office's own Judicial "
            "Compensation table states what that tier pays. Each record carries both documents, the count, and "
            "the percentage this project's own source arithmetic gives for that count, beside an explicit "
            "documentsStatingTheFigure: 0. Every quote is re-checked on every run against its section's "
            "OPERATIVE text — everything above the publisher's notes — because uscode.house.gov prints a "
            "section's repealed text beneath the law, and 38 U.S.C. 7253's repealed subsection (e)(1) puts the "
            "CAVC's chief judge at the circuit rate where the current subsection (e) puts every judge of that "
            "court at the district rate. The Court of International Trade is not priced: 28 U.S.C. 252 states "
            "no parity. Only single-post chief-judge nodes are priced; every 'Judge (xN)' node states a "
            "multiplicity and is refused. Basic pay is not the node's cost. Regenerate by re-running the "
            "script; never edit by hand."
        ),
        "source": {
            "kind": "statutory_parity_derived_pay",
            "sections": report["sections"],
            "table": {
                "url": loaded["url"],
                "fetched_at": loaded["fetched_at"],
                "sha256": loaded["sha256"],
                "file": _relative(Path(args.table)),
            },
            "year": year,
            "documentsPerRecord": report["documentsPerRecord"],
            "documentsStatingTheFigure": report["documentsStatingTheFigure"],
            "documentStrengthPercent": report["documentStrengthPercent"],
            "strengthScale": STRENGTH_SCALE,
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {_relative(args.out)}  ({len(validated)} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
