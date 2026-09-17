"""robots.txt for the verifier.

The verifier points an unattended fetcher at human-facing federal websites.
A project whose deliverable is public trustworthiness does not ignore their
stated crawl rules, and a bot-managed host answers an unknown agent with a
challenge page the verifier would otherwise have to interpret.

A robots.txt that IS fetched and disallows the path is obeyed. A path no
rule covers is fetched. The interesting cases are the ones where no rule
was read at all, and each is decided by RFC 9309, which this repository can
now quote rather than recall: the standard was unreachable from every
earlier session and is committed verbatim at
`tests/fixtures/standards/rfc9309.txt` (fetched 2026-09-15, digest in its
`.meta.json`), with `tests/test_politeness.py` asserting the sentences below
are really in it.

    2.3.1.3.  "Unavailable" Status
       ... such status codes are in the 400-499 range.
       If a server status code indicates that the robots.txt file is
       unavailable to the crawler, then the crawler MAY access any
       resources on the server.

    2.3.1.4.  "Unreachable" Status
       If the robots.txt file is unreachable due to server or network
       errors, this means the robots.txt file is undefined and the crawler
       MUST assume complete disallow. ... server errors are identified by
       status codes in the 500-599 range.

So: 4xx permits access and 5xx requires refusal, exactly as this file used
to guess. Two consequences, and one of them corrects a deviation that ran
the other way.

**A network error is a refusal now (since 2026-09-15).** DNS failure, a TLS
error, a timeout, a reset: this module used to allow the fetch, on the
reasoning that "a robots.txt that cannot be fetched is not a prohibition".
The standard says the opposite in as many words — unreachable "due to
server **or network** errors" is undefined, and undefined MUST be treated
as complete disallow — and it was the one place this project was laxer than
the rule it cited. Measured before changing it: 8 hosts and 11 curated
nodes, every one of which would fail the page fetch on the same fault, so
conforming costs approximately nothing and removes an inconsistency.

**The file is fetched with this project's own User-Agent (since
2026-09-15), and that was a bug, not a policy.** `RobotFileParser.read()`
calls `urllib.request.urlopen` with no headers, so every robots.txt was
requested as `Python-urllib/3.x` while every *page* was requested as the
project's self-identifying agent. Federal hosts behind bot management
routinely refuse the first and serve the second, so the verifier was being
turned away at the door it never needed to knock on, and then recording
"refused by policy" about a site that would have handed over its rules.
Re-probed across the 86 hosts that had refused: with the project's agent,
**19 serve robots.txt (182 recorded failures), 3 answer 404 (78), and 64
still refuse (636)** — so the correct agent recovers 260 fetches, and it
does so by making the verifier MORE obedient, not less. Those 19 hosts'
rules were never read before; now they are read and followed.

That also settles a question this file used to leave open. Relaxing the
401/403 refusal below would have reached the other 64 hosts, but almost every
one of them refuses the page itself to the same agent, so the relaxation was
measured as worth nearly nothing once this bug was fixed. The conservative
policy stays, on its own merits and without costing coverage.

Re-measured on 2026-09-16 against all 64, "almost every one" is the honest
quantifier and "every one" was wrong: `www.nga.mil` (8 nodes) and
`www.army.mil` (12 nodes) serve the page 200 to this agent while refusing
robots.txt, so the relaxation is worth 20 nodes rather than nothing. That
does not change the conclusion. The same pass settled the remaining
hypothesis: this agent and `Python-urllib` draw identical statuses on all 64,
so the fix above is fully spent; a browser agent string would recover 7 hosts
and is refused as a lie told to a government server; and 55 hosts refuse the
page to every agent tried, including a full browser header set over HTTP/2 on
a different TLS stack, which no client-side change reaches.

What that pass did find is that `www.justice.gov` -- 67 nodes, the largest
single refusal here -- is not refusing us at all. It is probabilistic: 4 of 12
to this agent, 2 of 12 to a browser one, and its robots.txt eventually answers
200 with 2,651 bytes of real `text/plain` whose rules permit `/about` and
carry no crawl-delay. Those 67 nodes are refused on a rule the Department of
Justice never published. A bounded, backed-off retry would read and follow the
real file, which is the same shape of fix as the one above and makes this
module more obedient rather than less.

**Implemented 2026-09-17.** `RobotsPolicy` asks again, `retries` more times
(default 2), waiting `backoff` seconds times the attempt number between
knocks, and only on 401, 403 and 5xx: a 404 is an answer, and a DNS or TLS
failure will not heal in seconds while each attempt would cost a timeout.
The verdict records how many attempts it took, and `allows()` says so --
"read on attempt 3", or "could not be read (403) on each of 3 attempts" --
so the evidence never presents a third-try success as a first-try one. The
verifier applies the same rule to the page itself (`fetch_with_retries` in
`scripts/verify_base_graph.py`, `--retries`, `--retry-backoff`), since
justice.gov answers the page the same way it answers robots.txt. The two
cautions in `docs/NETWORK_ACCESS.md` section 7 stand: the backoff is not
decoration, because that host's success rate fell across a session of
sustained probing; and a 200 is trusted exactly as it always was, so a
challenge page served with the wrong status still parses to no rule and
allows -- a limitation this change neither adds nor removes.

One case is neither allowed nor disallowed, and must not be reported as
though a rule had been read: a host that answers robots.txt with 401 or
403. No file was served, so no rule exists to quote. We keep the refusal,
as a deliberate conservative choice rather than a requirement: a host that
will not show us its robots.txt is a host we do not have permission from,
and the cost of stopping is now a handful of nodes rather than hundreds.
That is NOT what the standard mandates, and that is now quoted above rather
than remembered: 401 and 403 are 4xx, so RFC 9309 would permit the fetch.
Python's parser implements the older pre-RFC convention in which those two
alone mean disallow-all, and this module keeps the refusal on purpose. It is
the one place we are deliberately stricter than the rule we cite, and it is
cheap: after the User-Agent fix below, it costs a handful of nodes. If a
later run wants the standard's behaviour instead, that is a deliberate
policy change here, not a bug fix.

**A 5xx now says what actually happened.** It is refused, which matches the
standard, but the old code reported it as `robots.txt disallows <path>` --
asserting a published rule when the file had never been read, which is the
one thing this module exists to avoid. `RobotFileParser` left both of its
flags clear on a 5xx and `can_fetch` returned False off an unset
`last_checked`, so the refusal was right for a reason the message got
wrong. Statuses are classified here now rather than inferred from another
object's private state.
"""

from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

#: What the fetch of robots.txt itself concluded. Kept separate from the
#: parsed rules because "the rules say no" and "there were no rules" are
#: different facts and the verifier records which one it acted on.
RULES = "rules"                 # 2xx: a file was read; its rules decide
NO_FILE = "no_file"             # 404/410/other 4xx: nothing published; allow
REFUSED = "refused"             # 401/403: served nothing and would not say why
UNREACHABLE = "unreachable"     # 5xx: the site is failing; refuse until it is not
UNFETCHABLE = "unfetchable"     # DNS, TLS, timeout: RFC 9309 2.3.1.4, refuse


@dataclass
class RobotsFile:
    kind: str
    status: int | None = None
    parser: RobotFileParser | None = None
    detail: str = ""      # the network error's class, when there was one
    attempts: int = 1     # how many requests it took to reach this verdict


class RobotsPolicy:
    def __init__(self, *, user_agent: str, timeout: int = 30, enabled: bool = True,
                 retries: int = 2, backoff: float = 2.0, sleep=time.sleep) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.enabled = enabled
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.sleep = sleep
        self._files: dict[str, RobotsFile] = {}

    def _fetch(self, origin: str) -> RobotsFile:
        """Fetch and classify one origin's robots.txt, as this project's agent.

        Deliberately not `RobotFileParser.read()`: that method sends no
        User-Agent, and the whole point is to knock on the door as the same
        caller that will ask for the page.
        """
        request = urllib.request.Request(
            f"{origin}/robots.txt", headers={"User-Agent": self.user_agent}
        )
        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    status = getattr(response, "status", 200) or 200
                break
            except HTTPError as error:
                retryable = error.code in (401, 403) or error.code >= 500
                if retryable and attempts <= self.retries:
                    # A host that would not serve the file this time is asked
                    # again, gently: measured on www.justice.gov, which answers
                    # 401 about two times in three and a real file the third.
                    self.sleep(self.backoff * attempts)
                    continue
                if error.code in (401, 403):
                    return RobotsFile(REFUSED, error.code, attempts=attempts)
                if 400 <= error.code < 500:
                    return RobotsFile(NO_FILE, error.code, attempts=attempts)
                return RobotsFile(UNREACHABLE, error.code, attempts=attempts)
            except (URLError, OSError, ValueError) as error:
                # RFC 9309 2.3.1.4: unreachable "due to server or network errors"
                # is undefined, and undefined MUST be read as complete disallow.
                # Not retried: DNS and TLS do not heal in seconds, and each
                # attempt would cost a full timeout.
                return RobotsFile(UNFETCHABLE, detail=f"{error.__class__.__name__}", attempts=attempts)
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.parse(raw.decode("utf-8", "replace").splitlines())
        except Exception:  # noqa: BLE001 — an unparseable file states no rule
            return RobotsFile(NO_FILE, status, attempts=attempts)
        return RobotsFile(RULES, status, parser, attempts=attempts)

    def _file(self, url: str) -> RobotsFile:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._files:
            self._files[origin] = self._fetch(origin)
        return self._files[origin]

    def allows(self, url: str) -> tuple[bool, str]:
        if not self.enabled:
            return True, "robots checks disabled"
        found = self._file(url)
        host = urlparse(url).netloc
        read_on = f" (read on attempt {found.attempts})" if found.attempts > 1 else ""
        each_of = f" on each of {found.attempts} attempts" if found.attempts > 1 else ""
        if found.kind == RULES and found.parser is not None:
            if found.parser.can_fetch(self.user_agent, url):
                return True, "allowed by robots.txt" + read_on
            return False, f"{host}/robots.txt disallows {urlparse(url).path or '/'}" + read_on
        if found.kind == REFUSED:
            # No rule was read, so none may be quoted. Refused by this
            # project's choice, not by the standard.
            return False, (
                f"{host}/robots.txt could not be read ({found.status}){each_of}; "
                "refused by policy, no rule was seen"
            )
        if found.kind == UNREACHABLE:
            return False, (
                f"{host}/robots.txt could not be fetched (HTTP {found.status}){each_of}; "
                "refused while the site is failing, no rule was seen"
            )
        if found.kind == UNFETCHABLE:
            return False, (
                f"{host}/robots.txt could not be reached ({found.detail}); "
                "refused: an undefined robots.txt is a complete disallow"
            )
        return True, "no readable robots.txt"

    def crawl_delay(self, url: str) -> float:
        found = self._file(url)
        if found.kind != RULES or found.parser is None:
            return 0.0
        try:
            delay = found.parser.crawl_delay(self.user_agent)
        except Exception:  # noqa: BLE001
            return 0.0
        return float(delay) if delay else 0.0
