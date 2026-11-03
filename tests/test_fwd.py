"""OPM Federal Workforce Data: the stream aggregator refuses what it cannot count honestly, the committed
documents print the words a record quotes, and the derived aggregate is checked against its own digest."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from data_pipeline.verification import fwd  # noqa: E402

HEADER = ["agency", "agency_code", "agency_subelement", "agency_subelement_code", "annualized_adjusted_basic_pay",
          "count", "snapshot_yyyymm", "grade"]


def stream(rows, header=None):
    header = header or HEADER
    lines = ["|".join(header)] + ["|".join(r) for r in rows]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def row(agency="DEPARTMENT OF ENERGY", code="DN", sub="FEDERAL ENERGY REGULATORY COMMISSION", sub_code="DNFE",
        pay="REDACTED", count="1", snap="202608", grade="15"):
    return [agency, code, sub, sub_code, pay, count, snap, grade]


def chunked(data: bytes, size: int):
    for i in range(0, len(data), size):
        yield data[i:i + size]


class AggregatorTests(unittest.TestCase):
    def test_it_counts_records_per_agency_and_sub_element_across_chunk_boundaries(self):
        data = stream([row(), row(), row(sub="DEPARTMENT OF ENERGY", sub_code="DN00"), row(code="VA", agency="DEPARTMENT OF VETERANS AFFAIRS",
                                                                                          sub="VETERANS HEALTH ADMINISTRATION", sub_code="VATA")])
        for size in (1, 7, 64, 1 << 20):
            result = fwd.aggregate_stream(chunked(data, size))
            self.assertEqual(result["records"], 4)
            self.assertEqual(result["snapshot"], "202608")
            self.assertEqual(result["bytes"], len(data))
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual([(r["agency_code"], r["subelement_code"], r["records"]) for r in result["rows"]],
                             [("DN", "DN00", 1), ("DN", "DNFE", 2), ("VA", "VATA", 1)])

    def test_nothing_but_the_six_columns_leaves_the_aggregator(self):
        data = stream([row(pay="SENTINEL-PAY", grade="SENTINEL-GRADE")])
        text = json.dumps(fwd.aggregate_stream(chunked(data, 1024)))
        self.assertNotIn("SENTINEL", text)
        self.assertEqual(set(fwd.READ_COLUMNS), {"agency_code", "agency", "agency_subelement_code", "agency_subelement",
                                                 "count", "snapshot_yyyymm"})

    def test_it_refuses_rather_than_repairs(self):
        cases = {
            "a count that is not the integer 1": stream([row(count="2")]),
            "a count that is not a number": stream([row(count="x")]),
            "two snapshots": stream([row(), row(snap="202607")]),
            "a short row": stream([row()[:5]]),
            "a code with two names": stream([row(), row(sub="SOMETHING ELSE")]),
            "no records": stream([]),
            "an empty agency code": stream([row(code="")]),
            "an empty sub-element code": stream([row(sub_code="  ")]),
            "a header naming a read column twice": stream([row() + ["1"]], header=HEADER + ["count"]),
            "a line with no newline longer than the cap": b"|".join([b"x" * 200] * 400),
        }
        for label, data in cases.items():
            with self.subTest(label), self.assertRaises(fwd.Unreadable):
                fwd.aggregate_stream(chunked(data, 100))

    def test_a_header_without_the_snapshot_column_is_refused(self):
        header = [h for h in HEADER if h != "snapshot_yyyymm"]
        data = stream([[v for i, v in enumerate(row()) if HEADER[i] != "snapshot_yyyymm"]], header=header)
        with self.assertRaises(fwd.Unreadable):
            fwd.aggregate_stream([data])


class DocumentTests(unittest.TestCase):
    def test_the_committed_documents_print_the_words_a_record_quotes(self):
        fwd.check_documents()

    def test_the_coverage_sentence_is_not_fedscopes(self):
        from data_pipeline.verification import headcounts

        self.assertNotEqual(fwd.COVERAGE_STATEMENT, headcounts.COVERAGE_STATEMENT)
        self.assertIn("pay or non-pay status", fwd.COVERAGE_STATEMENT)
        self.assertNotIn("active pay status", fwd.COVERAGE_STATEMENT)

    def test_a_page_without_the_sentence_or_the_list_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("fwd_data_sources.html", "fwd_data_dictionary.xlsx"):
                shutil.copy(fwd.FWD_FIXTURE_DIR / name, Path(tmp) / name)
                shutil.copy(fwd.FWD_FIXTURE_DIR / (name + ".meta.json"), Path(tmp) / (name + ".meta.json"))
            page = Path(tmp) / "fwd_data_sources.html"
            dictionary = Path(tmp) / "fwd_data_dictionary.xlsx"
            fwd.check_documents(dictionary, page)
            for old in ("in either a pay or non-pay status", "Defense Intelligence Agency"):
                original = page.read_text(encoding="utf-8")
                page.write_text(original.replace(old, "REMOVED"), encoding="utf-8")
                meta = page.with_name(page.name + ".meta.json")
                data = json.loads(meta.read_text())
                data["sha256"] = hashlib.sha256(page.read_bytes()).hexdigest()
                meta.write_text(json.dumps(data))
                with self.subTest(old), self.assertRaises(fwd.Unreadable):
                    fwd.check_documents(dictionary, page)
                page.write_text(original, encoding="utf-8")
                data["sha256"] = hashlib.sha256(page.read_bytes()).hexdigest()
                meta.write_text(json.dumps(data))

    def test_a_document_whose_bytes_changed_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("fwd_data_sources.html", "fwd_data_dictionary.xlsx"):
                shutil.copy(fwd.FWD_FIXTURE_DIR / name, Path(tmp) / name)
                shutil.copy(fwd.FWD_FIXTURE_DIR / (name + ".meta.json"), Path(tmp) / (name + ".meta.json"))
            (Path(tmp) / "fwd_data_sources.html").write_text("tampered", encoding="utf-8")
            with self.assertRaises(fwd.Unreadable):
                fwd.check_documents(Path(tmp) / "fwd_data_dictionary.xlsx", Path(tmp) / "fwd_data_sources.html")

    def test_the_listing_names_the_newest_edition_and_the_download_address(self):
        listing = json.loads(fwd.FWD_LISTING_FIXTURE.read_text(encoding="utf-8"))
        entry = fwd.select_latest(listing)
        self.assertEqual((entry["year"], entry["month"]), ("2026", "08"))
        self.assertEqual(fwd.download_url(entry), "https://data.opm.gov/data/blob/download/chunked/employment_202608_1.txt"
                                                  "?customFileName=employment_202608_1.txt&fileType=application/json")
        self.assertEqual(fwd.parquet_url(entry), "https://data.opm.gov/api/v1/files/employment/2026/08/1/download")
        with self.assertRaises(fwd.Unreadable):
            fwd.select_latest([])

    def test_a_listing_entry_that_is_not_an_employment_edition_is_never_selected(self):
        good = {"filename": "employment_202608_1", "year": "2026", "month": "08", "version": 1, "current": True}
        bad = [
            dict(good, month="13", filename="employment_202613_1"),
            dict(good, month="0", filename="employment_202600_1"),
            dict(good, version="x"),
            dict(good, filename="dynamics_202609_1", month="09"),
            dict(good, current=False, month="09", filename="employment_202609_1"),
        ]
        self.assertEqual(fwd.select_latest(bad + [good])["filename"], "employment_202608_1")
        with self.assertRaises(fwd.Unreadable):
            fwd.select_latest(bad)


def write_aggregate(directory: Path, payload: dict) -> Path:
    path = directory / "agg.json"
    body = (json.dumps(payload, indent=1) + "\n").encode("utf-8")
    path.write_bytes(body)
    path.with_name("agg.json.meta.json").write_text(json.dumps({"sha256": hashlib.sha256(body).hexdigest(), "fetched_at": "2026-11-03T00:00:00Z"}))
    return path


def sample_payload():
    return {
        "kind": fwd.AGGREGATE_KIND, "derived": True,
        "stream": {"url": "https://data.opm.gov/x", "records": 3, "snapshot": "202608", "bytes": 10, "sha256": "ab"},
        "rows": [
            {"agency_code": "DN", "agency_name": "DEPARTMENT OF ENERGY", "subelement_code": "DN00", "subelement_name": "DEPARTMENT OF ENERGY", "records": 2},
            {"agency_code": "DN", "agency_name": "DEPARTMENT OF ENERGY", "subelement_code": "DNFE",
             "subelement_name": "FEDERAL ENERGY REGULATORY COMMISSION", "records": 1},
        ],
    }


class AggregateFixtureTests(unittest.TestCase):
    def test_a_good_aggregate_reads_as_headcount_rows_for_its_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = fwd.load_aggregate(write_aggregate(Path(tmp), sample_payload()))
            periods = fwd.periods_from_aggregate(payload)
            self.assertEqual(list(periods), ["2026-08"])
            self.assertEqual(periods["2026-08"][1], {
                "datecode": "202608", "agency_code": "DN", "agency_name": "DEPARTMENT OF ENERGY", "subagency_code": "DNFE",
                "subagency_name": "FEDERAL ENERGY REGULATORY COMMISSION", "employees": 1})

    def test_each_way_an_aggregate_can_be_wrong_is_refused(self):
        def tampered(mutate):
            payload = sample_payload()
            mutate(payload)
            return payload

        cases = {
            "rows that do not sum to the stream's records": tampered(lambda p: p["stream"].update(records=4)),
            "not marked derived": tampered(lambda p: p.update(derived=False)),
            "the wrong kind": tampered(lambda p: p.update(kind="other")),
            "no rows": tampered(lambda p: p.update(rows=[])),
            "no stream record": tampered(lambda p: p.pop("stream")),
        }
        for label, payload in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp, self.assertRaises(fwd.Unreadable):
                fwd.load_aggregate(write_aggregate(Path(tmp), payload))

    def test_a_changed_byte_fails_the_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_aggregate(Path(tmp), sample_payload())
            path.write_bytes(path.read_bytes().replace(b'"records": 2', b'"records": 9'))
            with self.assertRaises(fwd.Unreadable):
                fwd.load_aggregate(path)

    def test_a_snapshot_that_is_not_a_month_is_refused(self):
        with self.assertRaises(fwd.Unreadable):
            fwd.period_of("2026")


def committed_aggregates():
    return sorted(p for p in fwd.FWD_FIXTURE_DIR.glob("fwd_employment_agency_subelement_*.json") if not p.name.endswith(".meta.json"))


@unittest.skipUnless(committed_aggregates(), "no committed aggregate yet")
class CommittedAggregateTests(unittest.TestCase):
    def setUp(self):
        self.path = committed_aggregates()[-1]
        self.payload = fwd.load_aggregate(self.path)

    def test_the_committed_aggregate_is_the_listing_s_newest_edition_and_says_it_is_derived(self):
        stream_record = self.payload["stream"]
        self.assertTrue(self.payload["derived"])
        self.assertEqual(stream_record["listing_filename"], "employment_202608_1")
        self.assertEqual(stream_record["url"], fwd.download_url({"filename": "employment_202608_1"}))
        self.assertEqual(stream_record["columns_read"], list(fwd.READ_COLUMNS))
        self.assertEqual(sum(r["records"] for r in self.payload["rows"]), stream_record["records"])
        self.assertTrue(fwd.period_of(stream_record["snapshot"]) == "2026-08")

    def test_the_committed_aggregate_matches_the_headcount_matcher_s_row_shape(self):
        periods = fwd.periods_from_aggregate(self.payload)
        rows = periods["2026-08"]
        self.assertGreater(len(rows), 400)
        self.assertTrue(all(r["employees"] > 0 for r in rows))
        self.assertEqual(sum(r["employees"] for r in rows), self.payload["stream"]["records"])


if __name__ == "__main__":
    unittest.main()
