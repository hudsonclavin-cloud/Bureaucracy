"""The fetch script's refusals, hermetically: a fake listing and a fake stream stand in for data.opm.gov, and the
fixture directory is a temporary one. Every refusal leaves nothing behind; the one success writes an aggregate whose
own digest verifies and whose stream record is the fake stream's."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import fetch_fixture  # noqa: E402
import fetch_fwd_aggregate as script  # noqa: E402
from data_pipeline.verification import fwd  # noqa: E402

HEADER = "agency|agency_code|agency_subelement|agency_subelement_code|annualized_adjusted_basic_pay|count|snapshot_yyyymm"
LISTING = [{"filename": "employment_202608_1", "publishDate": "2026-10-04T03:54:31Z", "version": 1, "current": True, "month": "08", "year": "2026"}]
DOWNLOAD = fwd.download_url(LISTING[0])


def stream_bytes(snapshot="202608", rows=3):
    lines = [HEADER] + [f"DEPARTMENT OF ENERGY|DN|FERC|DNFE|REDACTED|1|{snapshot}" for _ in range(rows)]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


class FakeResponse:
    def __init__(self, body: bytes, headers: dict, url: str, fail_after: int | None = None):
        self._body, self._pos, self.headers, self._url, self.status = body, 0, headers, url, 200
        self._fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self._url

    def read(self, n=-1):
        if self._fail_after is not None and self._pos >= self._fail_after:
            raise OSError("connection reset by peer")
        n = len(self._body) - self._pos if n is None or n < 0 else n
        if self._fail_after is not None:
            n = min(n, self._fail_after - self._pos)
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk


def run(*, body=None, disposition='attachment; filename="employment_202608_1.txt"', content_type="application/octet-stream",
        robots=(True, "allows /"), fail_after=None, argv=()):
    body = stream_bytes() if body is None else body
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)

        def fake_urlopen(request, timeout=None):
            url = request.full_url
            if url == fwd.FWD_LISTING_URL:
                return FakeResponse(json.dumps(LISTING).encode(), {}, url)
            return FakeResponse(body, {"Content-Disposition": disposition, "Content-Type": content_type}, url, fail_after)

        out = io.StringIO()
        with mock.patch.object(fwd, "FWD_FIXTURE_DIR", directory), \
                mock.patch.object(script.urllib.request, "urlopen", fake_urlopen), \
                mock.patch.object(fetch_fixture, "robots_verdict", lambda url, ua, cache=None: robots), \
                contextlib.redirect_stdout(out):
            code = script.main(list(argv))
        return code, out.getvalue(), sorted(p.name for p in directory.iterdir()), directory


class FetchTests(unittest.TestCase):
    def test_a_good_stream_writes_an_aggregate_whose_digest_verifies(self):
        body = stream_bytes()
        code, text, files, _ = run(body=body)
        self.assertEqual(code, 0, text)
        self.assertEqual(files, ["fwd_employment_agency_subelement_2026-08.json", "fwd_employment_agency_subelement_2026-08.json.meta.json"])

    def test_the_aggregate_records_the_stream_it_was_made_from(self):
        body = stream_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            def fake_urlopen(request, timeout=None):
                if request.full_url == fwd.FWD_LISTING_URL:
                    return FakeResponse(json.dumps(LISTING).encode(), {}, request.full_url)
                return FakeResponse(body, {"Content-Disposition": 'attachment; filename="employment_202608_1.txt"', "Content-Type": "application/octet-stream"}, request.full_url)

            with mock.patch.object(fwd, "FWD_FIXTURE_DIR", directory), mock.patch.object(script.urllib.request, "urlopen", fake_urlopen), \
                    mock.patch.object(fetch_fixture, "robots_verdict", lambda url, ua, cache=None: (True, "allows /")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(script.main([]), 0)
                payload = fwd.load_aggregate(directory / "fwd_employment_agency_subelement_2026-08.json")
        self.assertTrue(payload["derived"])
        self.assertEqual(payload["stream"]["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual((payload["stream"]["bytes"], payload["stream"]["records"], payload["stream"]["snapshot"]), (len(body), 3, "202608"))
        self.assertEqual(payload["stream"]["url"], DOWNLOAD)
        self.assertEqual(payload["rows"][0]["records"], 3)

    def test_each_refusal_writes_nothing_and_exits_one(self):
        cases = {
            "a different file's disposition": dict(disposition='attachment; filename="employment_202607_1.txt"'),
            "a longer filename that merely starts with the edition's": dict(disposition='attachment; filename="employment_202608_1.txt.bak"'),
            "a parquet where the text was asked": dict(disposition='attachment; filename="employment_202608_1.parquet"'),
            "an HTML page": dict(content_type="text/html; charset=utf-8", disposition='attachment; filename="employment_202608_1.txt"'),
            "a stream of another snapshot": dict(body=stream_bytes(snapshot="202607")),
            "a stream that is not the file": dict(body=b"<html>Request Access</html>"),
            "robots.txt disallowing the path": dict(robots=(False, "disallows /data/blob")),
            "a stream that dies half way": dict(fail_after=120),
            "a stream with a count that is not 1": dict(body=stream_bytes().replace(b"|1|202608", b"|2|202608", 1)),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                code, text, files, _ = run(**kwargs)
                self.assertEqual(code, 1, text)
                self.assertEqual(files, [], f"{label} left {files}")

    def test_the_listing_is_read_only_after_robots_is_asked_about_it(self):
        asked = []

        def robots(url, ua, cache=None):
            asked.append(url)
            return False, "disallows /api"

        code, text, files, _ = run(robots=(False, "x"), argv=["--plan"])
        self.assertEqual(code, 1)
        self.assertEqual(files, [])
        with mock.patch.object(fetch_fixture, "robots_verdict", robots), mock.patch.object(script.urllib.request, "urlopen", side_effect=AssertionError("fetched")):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(script.main(["--plan"]), 1)
        self.assertEqual(asked, [fwd.FWD_LISTING_URL])

    def test_plan_downloads_nothing(self):
        code, text, files, _ = run(argv=["--plan"])
        self.assertEqual(code, 0)
        self.assertIn(DOWNLOAD, text)
        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()
