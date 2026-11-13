"""OPM's Federal Workforce Data (FWD), the successor to FedScope, read for headcounts.

data.opm.gov publishes the Enterprise Human Resources Integration (EHRI)
"Status" dataset monthly: one record per active federal civilian employee,
with the agency and agency sub-element each belongs to and a `count` column the
data dictionary defines as "The integer value 1, used for counting or
aggregating values over the data set." The August 2026 edition is 2,024,832
records and 1,657,827,332 bytes of pipe-delimited text (57 MB as Parquet, which
this repository's standard-library readers cannot open). A headcount for an
agency or sub-agency is the sum of `count` over its records, which is the same
quantity FedScope's `EMPCOUNT` was, from the same agency and sub-agency codes.

**What is committed, and why it is an exception to the verbatim-fixture rule.**
Every fixture in this repository is the publisher's own bytes. A 1.66 GB text
file cannot be committed, and a file this size is not something a reviewer
re-reads. So the committed fixture is a DERIVED AGGREGATE: one row per
(agency code, sub-element code) with the number of records, written by
`scripts/fetch_fwd_aggregate.py` from the stream as it was served, with the
stream's URL, byte count, sha256 and record count recorded beside it. The
fixture says it is derived. Its own digest is recomputed here before a row is
read (the refusal every fixture reader makes); the stream's digest cannot be
recomputed offline, and the record says so. A reader who doubts a row can
re-stream the same URL and compare the stream digest, which the script prints.

**No person is in the file.** The status file carries no name column, and the
aggregator takes by header index exactly the six columns in `READ_COLUMNS`,
keeping nothing else from any record.

**Two documents say what the numbers count.** The data dictionary
(`FWD Data Dictionary.xlsx`) defines `count`; the Data Sources page prints the
coverage sentence ("Status data files include all active employees (in either a
pay or non-pay status) ...") and the list of what EHRI excludes. Both are
committed verbatim beside the aggregate, and the coverage sentence a record
quotes is re-found in the committed page. That sentence differs from FedScope's
("an active pay status"), so a node never carries one population's sentence
under the other's count.

**Pay is not read.** The file's `annualized_adjusted_basic_pay` column is 47%
REDACTED (Defense entirely), and a sum over the rest would describe a different
population from the headcount beside it. Payroll stays on FedScope's printed
averages, with their own period (`fedscope_payroll.py`).
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FWD_SOURCE = "opm_fwd_employment"
FWD_LISTING_URL = "https://data.opm.gov/api/v1/files/employment?current=true"
#: The text stream the site's "Download .TXT" button serves, chunked. The API's `/download` address
#: (`/api/v1/files/employment/{year}/{month}/{version}/download`) serves the Parquet file instead.
FWD_DOWNLOAD_URL = (
    "https://data.opm.gov/data/blob/download/chunked/{filename}.txt?customFileName={filename}.txt&fileType=application/json"
)
FWD_PARQUET_URL = "https://data.opm.gov/api/v1/files/employment/{year}/{month}/{version}/download"
FWD_DATA_SOURCES_URL = "https://data.opm.gov/resources/data-sources"
FWD_DICTIONARY_URL = "https://data.opm.gov/FWD%20Data%20Dictionary.xlsx"
FWD_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "opm" / "fwd"
FWD_DATA_SOURCES_FIXTURE = FWD_FIXTURE_DIR / "fwd_data_sources.html"
FWD_DICTIONARY_FIXTURE = FWD_FIXTURE_DIR / "fwd_data_dictionary.xlsx"
FWD_LISTING_FIXTURE = FWD_FIXTURE_DIR / "fwd_employment_listing.json"
AGGREGATE_KIND = "opm_fwd_employment_aggregate"
DELIMITER = "|"
#: A line longer than this is not a record of this file (the longest real one is a few hundred bytes); a stream with no
#: newline would otherwise grow without bound.
MAX_LINE_BYTES = 1 << 16

#: The only columns taken off a record, by header name. Anything else in the stream is read past and dropped.
READ_COLUMNS = (
    "agency_code", "agency", "agency_subelement_code", "agency_subelement", "count", "snapshot_yyyymm",
)

#: The publisher's own words, pinned against the committed copies by tests and by the gate's mirror.
COUNT_DEFINITION = "The integer value 1, used for counting or aggregating values over the data set."
COVERAGE_STATEMENT = (
    "Status data files include all active employees (in either a pay or non-pay status) for each "
    "agency’s workforce as of the last day of each month."
)
COVERAGE_SOURCE = "OPM, Federal Workforce Data, Data Sources page, Status dataset"
#: Names the Data Sources page's exclusion list must carry for the panel's pointer to be true.
EXCLUSION_LIST_MARKERS = ("U.S. Postal Service", "Central Intelligence Agency", "Defense Intelligence Agency")


#: Organisations OUTSIDE the Executive Branch that the Data Sources page lists as INCLUDED in the dataset ("EHRI
#: generally does not include employees of the Legislative branch. However, the following organizations are
#: included"; likewise the Judicial branch). A reviewed identification, node id -> the label the page prints,
#: re-checked on every run against the committed page: a record for one of these is not "outside the covered
#: branch", whatever the Executive-Branch rule says. The Government Publishing Office is the page's
#: "Government Printing Office" under the name the FWD file itself prints for it, which is why this is a table of
#: reviewed identifications and not a name match.
INCLUDED_OUTSIDE_EXECUTIVE = {
    "leg-support-gpo": "Government Printing Office",
    "leg-support-uscc": "U.S. \u2013 China Economic and Security Review Commission",
    "jud-specialized-tax": "U.S. Tax Court",
}


class Unreadable(ValueError):
    """The aggregate or a document it rests on is not what it claims to be."""


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def period_of(snapshot: str) -> str:
    text = str(snapshot or "").strip()
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:]}"
    raise Unreadable(f"snapshot {snapshot!r} is not YYYYMM")


def aggregate_stream(chunks: Iterable[bytes]) -> dict[str, Any]:
    """Aggregate the pipe-delimited status stream once, in memory of one line.

    Refuses rather than repairs: a row whose field count differs from the
    header's, a `count` that is not an integer or is not 1 (the dictionary
    says it is the integer 1, and the aggregate relies on it), a stream with
    two snapshots, a code printed with two names, and a header missing a
    column in READ_COLUMNS. Returns the stream's byte count, sha256 and record
    count with the per-(agency, sub-element) rows.
    """
    digest = hashlib.sha256()
    total_bytes = 0
    header: list[str] | None = None
    index: dict[str, int] = {}
    wanted: tuple[int, ...] = ()
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    records = 0
    snapshot: str | None = None
    pending = b""

    def take(line: bytes) -> None:
        nonlocal header, index, wanted, records, snapshot
        text = line.rstrip(b"\r").decode("utf-8")
        if header is None:
            header = text.split(DELIMITER)
            index = {name: i for i, name in enumerate(header)}
            missing = [c for c in READ_COLUMNS if c not in index]
            if missing:
                raise Unreadable(f"the stream's header lacks {missing}")
            repeated = [c for c in READ_COLUMNS if header.count(c) != 1]
            if repeated:
                raise Unreadable(f"the stream's header names {repeated} more than once")
            wanted = tuple(index[c] for c in READ_COLUMNS)
            return
        if not text:
            return
        parts = text.split(DELIMITER)
        if len(parts) != len(header):
            raise Unreadable(f"record {records + 1} has {len(parts)} fields against a header of {len(header)}")
        agency_code, agency, sub_code, sub_name, count, snap = (parts[i] for i in wanted)
        if not agency_code.strip() or not sub_code.strip():
            raise Unreadable(f"record {records + 1} has an empty agency or sub-element code")
        if count != "1":
            raise Unreadable(f"record {records + 1}: count {count!r} is not the integer 1 the dictionary defines")
        if snapshot is None:
            snapshot = snap
        elif snap != snapshot:
            raise Unreadable(f"the stream carries two snapshots, {snapshot} and {snap}")
        records += 1
        key = (agency_code, sub_code)
        group = groups.get(key)
        if group is None:
            groups[key] = {"agency_code": agency_code, "agency_name": agency, "subelement_code": sub_code,
                           "subelement_name": sub_name, "records": 1}
        else:
            if group["agency_name"] != agency or group["subelement_name"] != sub_name:
                raise Unreadable(f"code {key} is printed with two names")
            group["records"] += 1

    for chunk in chunks:
        digest.update(chunk)
        total_bytes += len(chunk)
        pending += chunk
        lines = pending.split(b"\n")
        pending = lines.pop()
        if len(pending) > MAX_LINE_BYTES:
            raise Unreadable(f"a line of more than {MAX_LINE_BYTES} bytes with no newline is not a record of this file")
        for line in lines:
            take(line)
    if pending.strip():
        take(pending)
    if header is None or snapshot is None or not records:
        raise Unreadable("the stream carried no records")
    rows = sorted(groups.values(), key=lambda g: (g["agency_code"], g["subelement_code"]))
    return {
        "bytes": total_bytes, "sha256": digest.hexdigest(), "records": records, "snapshot": snapshot,
        "columns": len(header), "rows": rows,
    }


def load_aggregate(path: str | Path) -> dict[str, Any]:
    """The committed aggregate, after its own digest is recomputed against the fetch record."""
    path = Path(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    meta_path = path.with_name(path.name + ".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unreadable(f"{meta_path.name} is unreadable: {error}") from error
    if meta.get("sha256") != digest:
        raise Unreadable(f"{path.name}: digest {digest} is not the fetch record's {meta.get('sha256')}")
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("kind") != AGGREGATE_KIND or payload.get("derived") is not True:
        raise Unreadable(f"{path.name} is not a derived FWD aggregate")
    rows = payload.get("rows")
    stream = payload.get("stream")
    if not isinstance(rows, list) or not rows or not isinstance(stream, dict):
        raise Unreadable(f"{path.name} carries no rows or no stream record")
    if sum(int(r["records"]) for r in rows) != int(stream.get("records") or -1):
        raise Unreadable(f"{path.name}: the rows do not sum to the stream's record count")
    payload["_meta"] = meta
    payload["_sha256"] = digest
    return payload


def periods_from_aggregate(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """The aggregate in the row shape `headcounts.match_fedscope` reads, keyed by period."""
    period = period_of(payload["stream"]["snapshot"])
    return {period: [
        {
            "datecode": str(payload["stream"]["snapshot"]),
            "agency_code": str(r["agency_code"]),
            "agency_name": str(r["agency_name"]),
            "subagency_code": str(r["subelement_code"]),
            "subagency_name": str(r["subelement_name"]),
            "employees": int(r["records"]),
        }
        for r in payload["rows"]
    ]}


def load_fwd_meta(path: str | Path) -> dict[str, Any]:
    """url, fetched_at, sha256 and file of the aggregate, plus the stream block, for a record."""
    payload = load_aggregate(path)
    stream = payload["stream"]
    return {
        "url": stream.get("url"), "fetched_at": payload["_meta"].get("fetched_at"), "sha256": payload["_sha256"],
        "file": Path(path).name, "stream": stream,
    }


def dictionary_strings(path: str | Path = FWD_DICTIONARY_FIXTURE) -> list[str]:
    """The text cells of the committed data dictionary, read with the standard library."""
    with zipfile.ZipFile(io.BytesIO(Path(path).read_bytes())) as archive:
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
    return [html.unescape(s) for s in re.findall(r"<t[^>]*>([^<]*)</t>", shared)]


def page_text(path: str | Path = FWD_DATA_SOURCES_FIXTURE) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))


def included_outside_executive_labels(page: str | Path = FWD_DATA_SOURCES_FIXTURE) -> list[str]:
    """The organisations the page lists as included from the Legislative and Judicial branches, as printed."""
    text = Path(page).read_text(encoding="utf-8")
    start = text.find("Legislative branch")
    end = text.find("EHRI datasets", start)
    if start < 0 or end < 0:
        raise Unreadable("the committed Data Sources page has no Legislative/Judicial inclusion lists")
    items = re.findall(r"<li[^>]*>(.*?)</li>", text[start:end], flags=re.S)
    return [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", item))).strip() for item in items]


def check_documents(
    dictionary: str | Path = FWD_DICTIONARY_FIXTURE, page: str | Path = FWD_DATA_SOURCES_FIXTURE,
) -> None:
    """Raise unless the committed documents print the words a record quotes."""
    for path in (dictionary, page):
        meta = json.loads(Path(path).with_name(Path(path).name + ".meta.json").read_text(encoding="utf-8"))
        if meta.get("sha256") != file_sha256(path):
            raise Unreadable(f"{Path(path).name}: digest is not the fetch record's")
    if COUNT_DEFINITION not in dictionary_strings(dictionary):
        raise Unreadable("the committed dictionary does not define `count` as the integer 1")
    text = re.sub(r"\s+", " ", page_text(page))
    if re.sub(r"\s+", " ", COVERAGE_STATEMENT) not in text:
        raise Unreadable("the committed Data Sources page does not print the coverage sentence")
    for marker in EXCLUSION_LIST_MARKERS:
        if marker not in text:
            raise Unreadable(f"the committed Data Sources page's exclusion list does not carry {marker!r}")
    listed = included_outside_executive_labels(page)
    for node_id, wanted in INCLUDED_OUTSIDE_EXECUTIVE.items():
        if wanted not in listed:
            raise Unreadable(f"the committed Data Sources page does not list {wanted!r} (for {node_id}) among the included bodies")


def select_latest(listing: list[dict[str, Any]]) -> dict[str, Any]:
    """The newest (year, month) entry of the listing, highest version of that month."""
    entries = [e for e in listing if isinstance(e, dict) and e.get("current") and str(e.get("year", "")).isdigit()
               and str(e.get("month", "")).isdigit() and 1 <= int(e["month"]) <= 12 and str(e.get("version", "")).isdigit()
               and str(e.get("filename") or "").startswith("employment_")]
    if not entries:
        raise Unreadable("the listing carries no current employment file")
    return max(entries, key=lambda e: (int(e["year"]), int(e["month"]), int(e.get("version") or 0)))


def download_url(entry: dict[str, Any]) -> str:
    return FWD_DOWNLOAD_URL.format(filename=entry["filename"])


def parquet_url(entry: dict[str, Any]) -> str:
    return FWD_PARQUET_URL.format(year=entry["year"], month=entry["month"], version=entry["version"])
