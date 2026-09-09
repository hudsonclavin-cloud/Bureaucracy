#!/usr/bin/env python3
"""Fetch a file verbatim into tests/fixtures/ and record what happened.

Every fixture in this repository is the publisher's own bytes, refreshed only
by re-fetching and never edited by hand; each one has a sibling
`<file>.meta.json` saying where it came from, when, under what User-Agent, what
robots.txt said, and the sha256 of what was served. Until now that was done by
hand for each source, which is how a fetch either gets recorded inconsistently
or gets "helped along" when a host refuses.

A refusal is a result, not a failure to work around: when nothing is served the
fixture is not written at all and the meta file records the error verbatim, so
the repository carries the fact that the source could not be read from here.
That is the same treatment `clerk.house.gov`, `escs.opm.gov` and `govinfo.gov`
already have.

    python scripts/fetch_fixture.py <url> <path under tests/fixtures>

Exits 0 when the file was written, 1 when it was not — in both cases the meta
file is written.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_UA = "bureaucracy-data-pipeline/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)"
TIMEOUT = int(os.environ.get("PIPELINE_HTTP_TIMEOUT", "30"))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def robots_verdict(url: str, user_agent: str) -> tuple[bool, str]:
    """Ask robots.txt, and say which answer this is.

    A host that answers robots.txt itself with 401 or 403 is refused by this
    project's choice, not by the standard: RobotFileParser swallows that status
    and sets a blanket disallow with no rules parsed, so the record must not
    quote a rule nobody read. The distinction is the same one
    verify_base_graph.py makes.
    """
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        request = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
        parser.parse(body.splitlines())
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"robots.txt could not be read ({error.code}); refused by policy"
        return True, f"no readable robots.txt (HTTP {error.code}); failing open"
    except Exception as error:  # noqa: BLE001 - the reason is the record
        return True, f"no readable robots.txt ({type(error).__name__}); failing open"
    allowed = parser.can_fetch(user_agent, url)
    return allowed, ("allows " if allowed else "disallows ") + urlparse(url).path


def fetch(url: str, target: Path, user_agent: str = DEFAULT_UA) -> int:
    meta: dict[str, object] = {
        "fetched_at": now(),
        "url": url,
        "status": None,
        "final_url": None,
        "content_type": None,
        "user_agent": user_agent,
        "robots": None,
        "bytes": None,
        "sha256": None,
        "error": None,
    }
    allowed, verdict = robots_verdict(url, user_agent)
    meta["robots"] = verdict
    target.parent.mkdir(parents=True, exist_ok=True)
    meta_path = target.with_name(target.name + ".meta.json")

    if not allowed:
        meta["error"] = "not fetched: robots.txt " + verdict
        meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print(f"refused  {url}\n         {verdict}")
        return 1

    try:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            meta["status"] = response.status
            meta["final_url"] = response.geturl()
            meta["content_type"] = response.headers.get("Content-Type")
    except Exception as error:  # noqa: BLE001 - the reason is the record
        meta["error"] = f"{type(error).__name__}: {error}"
        meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print(f"failed   {url}\n         {meta['error']}\n         recorded in {meta_path.relative_to(PROJECT_ROOT)}")
        return 1

    meta["bytes"] = len(body)
    meta["sha256"] = hashlib.sha256(body).hexdigest()
    target.write_bytes(body)
    meta_path.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(f"fetched  {url}\n         {len(body):,} bytes -> {target.relative_to(PROJECT_ROOT)}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    url, relative = argv[1], argv[2]
    target = (FIXTURE_ROOT / relative).resolve()
    if FIXTURE_ROOT.resolve() not in target.parents:
        print(f"refusing to write outside tests/fixtures: {relative}")
        return 2
    return fetch(url, target)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
