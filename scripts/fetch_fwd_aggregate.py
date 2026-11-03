#!/usr/bin/env python
"""Stream OPM's Federal Workforce Data status file once and commit its aggregate.

    python scripts/fetch_fwd_aggregate.py --plan                 # what would be fetched; no download
    python scripts/fetch_fwd_aggregate.py                        # the newest edition the listing names
    python scripts/fetch_fwd_aggregate.py --year 2026 --month 08 --version 1

The status file is about 1.66 GB of pipe-delimited text with no Range support,
too large to commit and not something a reviewer re-reads. This script streams
it once, keeps one row per (agency code, sub-element code) with the number of
records (`data_pipeline/verification/fwd.py`, which also says why this derived
aggregate is an explicit exception to the verbatim-fixture rule), and writes
tests/fixtures/opm/fwd/fwd_employment_agency_subelement_<YYYY-MM>.json beside
its `.meta.json`. The stream's own URL, byte count, sha256 and record count are
recorded in the aggregate; a reviewer can re-stream the URL and compare.

robots.txt is asked first (data.opm.gov answers it with a 404, so nothing is
published to obey). A response that is not the file (a different media type, a
filename that is not employment_<YYYYMM>_<version>.txt) is refused, not parsed.
Nothing is written when the stream fails; the failure is printed and the exit
code is 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import fetch_fixture  # noqa: E402
from data_pipeline.verification import fwd  # noqa: E402

CHUNK = 1 << 20
READ_TIMEOUT = 300


def fixture_path(period: str) -> Path:
    return fwd.FWD_FIXTURE_DIR / f"fwd_employment_agency_subelement_{period}.json"


def read_listing() -> list[dict]:
    request = urllib.request.Request(fwd.FWD_LISTING_URL, headers={"User-Agent": fetch_fixture.DEFAULT_UA})
    with urllib.request.urlopen(request, timeout=fetch_fixture.TIMEOUT) as response:
        body = response.read()
    listing = json.loads(body.decode("utf-8"))
    if not isinstance(listing, list):
        raise fwd.Unreadable("the listing is not a list")
    return listing


def chunks_of(response):
    while True:
        block = response.read(CHUNK)
        if not block:
            return
        yield block


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year")
    ap.add_argument("--month")
    ap.add_argument("--version")
    ap.add_argument("--plan", action="store_true", help="print the edition and URL; download nothing")
    args = ap.parse_args(argv)

    listing = read_listing()
    if args.year and args.month and args.version:
        entry = next((e for e in listing if str(e.get("year")) == args.year and str(e.get("month")).zfill(2) == args.month.zfill(2)
                      and str(e.get("version")) == str(args.version)), None)
        if entry is None:
            print(f"the listing names no edition {args.year}-{args.month} version {args.version}")
            return 1
    else:
        entry = fwd.select_latest(listing)
    url = fwd.download_url(entry)
    period = f"{entry['year']}-{str(entry['month']).zfill(2)}"
    print(f"edition {entry['filename']} (published {entry.get('publishDate')}) -> {url}")
    if args.plan:
        return 0

    allowed, verdict = fetch_fixture.robots_verdict(url, fetch_fixture.DEFAULT_UA)
    if not allowed:
        print(f"refused: robots.txt {verdict}")
        return 1
    request = urllib.request.Request(url, headers={"User-Agent": fetch_fixture.DEFAULT_UA})
    fetched_at = fetch_fixture.now()
    try:
        with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as response:
            status = response.status
            content_type = response.headers.get("Content-Type") or ""
            disposition = response.headers.get("Content-Disposition") or ""
            final_url = response.geturl()
            if not re.search(rf'filename="?{re.escape(entry["filename"])}\.txt', disposition):
                print(f"refused: the response names {disposition!r}, not {entry['filename']}.txt")
                return 1
            if "octet-stream" not in content_type and "text" not in content_type:
                print(f"refused: the response is {content_type!r}, not the text stream")
                return 1
            aggregate = fwd.aggregate_stream(chunks_of(response))
    except Exception as error:  # noqa: BLE001 - the reason is the record
        print(f"failed: {type(error).__name__}: {error}")
        return 1

    if fwd.period_of(aggregate["snapshot"]) != period:
        print(f"refused: the stream's snapshot {aggregate['snapshot']} is not the edition's {period}")
        return 1
    payload = {
        "kind": fwd.AGGREGATE_KIND,
        "derived": True,
        "note": (
            "Derived by scripts/fetch_fwd_aggregate.py from OPM's Federal Workforce Data status file as it was served: "
            "one row per (agency code, sub-element code) with the number of records, `count` being the integer 1 per "
            "record in the data dictionary. The stream is about 1.66 GB and is not committed; its URL, bytes, sha256 "
            "and record count are recorded here so a reviewer can re-stream it and compare. This is an explicit "
            "exception to the rule that fixtures are the publisher's own bytes. No other column of any record is kept."
        ),
        "stream": {
            "url": url, "parquet_url": fwd.parquet_url(entry), "final_url": final_url, "status": status, "content_type": content_type,
            "content_disposition": disposition, "listing_url": fwd.FWD_LISTING_URL, "listing_filename": entry["filename"],
            "listing_publish_date": entry.get("publishDate"), "version": entry.get("version"),
            "bytes": aggregate["bytes"], "sha256": aggregate["sha256"], "records": aggregate["records"],
            "columns": aggregate["columns"], "snapshot": aggregate["snapshot"], "columns_read": list(fwd.READ_COLUMNS),
            "robots": verdict,
        },
        "rows": aggregate["rows"],
    }
    target = fixture_path(period)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    target.write_bytes(body)
    meta = {
        "fetched_at": fetched_at, "url": url, "status": status, "final_url": final_url, "content_type": "application/json",
        "user_agent": fetch_fixture.DEFAULT_UA, "robots": verdict, "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(), "error": None,
        "derived": True, "derived_from": {"url": url, "bytes": aggregate["bytes"], "sha256": aggregate["sha256"]},
    }
    target.with_name(target.name + ".meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"streamed {aggregate['bytes']:,} bytes, {aggregate['records']:,} records, {len(aggregate['rows'])} rows, "
          f"stream sha256 {aggregate['sha256']}\nwrote {target.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
