"""The fetcher records what happened, including when nothing was served.

A refusal that leaves no trace looks identical to a source nobody thought to
try, and this repository has already been caught once publishing a claim whose
provenance nobody could check. Both directions are pinned here: a fetch that
succeeds writes the bytes and their hash, and a fetch that fails writes the
reason and no fixture at all.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest import mock

from scripts import fetch_fixture

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
BODY = b"<html><body><table><tr><td>Level I</td><td>$253,100</td></tr></table></body></html>"
URL = "https://www.example.gov/salary-tables/EX.aspx"


class _Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return URL

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


class FetchFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"fetch-{uuid.uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.target = self.tmp_path / "table.html"
        self.meta = self.tmp_path / "table.html.meta.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def _read_meta(self) -> dict:
        return json.loads(self.meta.read_text(encoding="utf-8"))

    def test_a_served_file_is_written_verbatim_with_its_hash(self) -> None:
        with mock.patch.object(fetch_fixture, "robots_verdict", return_value=(True, "allows /")), \
                mock.patch.object(fetch_fixture.urllib.request, "urlopen", return_value=_Response(BODY)):
            code = fetch_fixture.fetch(URL, self.target)
        self.assertEqual(code, 0)
        self.assertEqual(self.target.read_bytes(), BODY)
        meta = self._read_meta()
        self.assertEqual(meta["sha256"], hashlib.sha256(BODY).hexdigest())
        self.assertEqual((meta["status"], meta["bytes"], meta["error"]), (200, len(BODY), None))
        self.assertIn("bureaucracy-data-pipeline", meta["user_agent"])

    def test_a_refused_connection_writes_the_reason_and_no_fixture(self) -> None:
        error = urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
        with mock.patch.object(fetch_fixture, "robots_verdict", return_value=(True, "allows /")), \
                mock.patch.object(fetch_fixture.urllib.request, "urlopen", side_effect=error):
            code = fetch_fixture.fetch(URL, self.target)
        self.assertEqual(code, 1)
        self.assertFalse(self.target.exists(), "a fixture was written for a fetch that served nothing")
        meta = self._read_meta()
        self.assertIn("403 Forbidden", meta["error"])
        self.assertIsNone(meta["sha256"])

    def test_a_robots_disallow_is_obeyed_and_recorded(self) -> None:
        with mock.patch.object(fetch_fixture, "robots_verdict", return_value=(False, "disallows /salary-tables/EX.aspx")), \
                mock.patch.object(fetch_fixture.urllib.request, "urlopen", return_value=_Response(BODY)) as opened:
            code = fetch_fixture.fetch(URL, self.target)
        self.assertEqual(code, 1)
        opened.assert_not_called()
        self.assertFalse(self.target.exists())
        self.assertIn("disallows", self._read_meta()["error"])

    def test_a_401_on_robots_is_refused_by_policy_not_by_a_rule(self) -> None:
        # RobotFileParser swallows a 401/403 on robots.txt and sets a blanket
        # disallow with no rules parsed. The path stays refused, but the record
        # must not quote a rule nobody read.
        error = urllib.error.HTTPError(URL, 403, "Forbidden", {}, None)
        with mock.patch.object(fetch_fixture.urllib.request, "urlopen", side_effect=error):
            allowed, verdict = fetch_fixture.robots_verdict(URL, fetch_fixture.DEFAULT_UA)
        self.assertFalse(allowed)
        self.assertIn("refused by policy", verdict)
        self.assertNotIn("disallows", verdict)

    def test_a_404_on_robots_fails_open(self) -> None:
        error = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
        with mock.patch.object(fetch_fixture.urllib.request, "urlopen", side_effect=error):
            allowed, verdict = fetch_fixture.robots_verdict(URL, fetch_fixture.DEFAULT_UA)
        self.assertTrue(allowed)
        self.assertIn("failing open", verdict)

    def test_it_refuses_to_write_outside_the_fixture_tree(self) -> None:
        self.assertEqual(fetch_fixture.main(["fetch_fixture.py", URL, "../../escape.html"]), 2)


class RecordedRefusalTests(unittest.TestCase):
    """The committed record of the Executive Schedule table this session could
    not read. It is evidence, so it must stay a refusal with no data beside
    it — a fixture appearing here later means somebody fetched it, which is
    the point."""

    PAY = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "pay"

    def test_the_blocked_fetch_is_recorded_with_its_reason(self) -> None:
        meta = json.loads((self.PAY / "executive_schedule_2026.html.meta.json").read_text(encoding="utf-8"))
        self.assertIn("opm.gov", meta["url"])
        self.assertIn("403", meta["error"])
        self.assertIsNone(meta["sha256"])

    def test_no_table_was_typed_in_beside_it(self) -> None:
        stray = [p.name for p in self.PAY.iterdir() if p.suffix not in (".json", ".md")]
        self.assertEqual(stray, [], "a pay table appeared without a fetch behind it")


if __name__ == "__main__":
    unittest.main()
