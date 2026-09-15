"""robots.txt for the verifier.

The verifier points an unattended fetcher at human-facing federal websites.
A project whose deliverable is public trustworthiness does not ignore their
stated crawl rules, and a bot-managed host answers an unknown agent with a
challenge page the verifier would otherwise have to interpret.

Failing open is deliberate and narrow: a robots.txt that cannot be fetched
is not a prohibition, and treating it as one would silently stop the whole
run. A robots.txt that IS fetched and disallows the path is obeyed.

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
401/403 refusal below would have reached the other 64 hosts, but every one
of them refuses the page itself to the same agent, so the relaxation was
measured as worth nearly nothing once this bug was fixed. The conservative
policy stays, on its own merits and without costing coverage.

One case is neither allowed nor disallowed, and must not be reported as
though a rule had been read: a host that answers robots.txt with 401 or
403. No file was served, so no rule exists to quote. We keep the refusal,
as a deliberate conservative choice rather than a requirement: a host that
will not show us its robots.txt is a host we do not have permission from,
and the cost of stopping is now a handful of nodes rather than hundreds.
That is NOT what the current standard mandates. RFC 9309 section 2.3.1.3
puts 4xx under "Unavailable" and permits a crawler to access any resource;
it is 5xx ("Unreachable", section 2.3.1.4) that requires assuming a complete
disallow. Python's parser implements the older pre-RFC convention, in which
401 and 403 alone mean disallow-all. [Likely, from memory: rfc-editor.org
and datatracker.ietf.org are both refused by this environment's proxy, so
the section numbers above remain unverified -- check them before citing
this comment.] If a later run wants the standard's behaviour rather than
ours, that is a deliberate policy change here, not a bug fix.

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
UNFETCHABLE = "unfetchable"     # DNS, TLS, timeout: a fact about the network; allow


@dataclass
class RobotsFile:
    kind: str
    status: int | None = None
    parser: RobotFileParser | None = None


class RobotsPolicy:
    def __init__(self, *, user_agent: str, timeout: int = 30, enabled: bool = True) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.enabled = enabled
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
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = getattr(response, "status", 200) or 200
        except HTTPError as error:
            if error.code in (401, 403):
                return RobotsFile(REFUSED, error.code)
            if 400 <= error.code < 500:
                return RobotsFile(NO_FILE, error.code)
            return RobotsFile(UNREACHABLE, error.code)
        except (URLError, OSError, ValueError):
            # No robots.txt we could reach at all is not a prohibition.
            return RobotsFile(UNFETCHABLE)
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        try:
            parser.parse(raw.decode("utf-8", "replace").splitlines())
        except Exception:  # noqa: BLE001 — an unparseable file states no rule
            return RobotsFile(NO_FILE, status)
        return RobotsFile(RULES, status, parser)

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
        if found.kind == RULES and found.parser is not None:
            if found.parser.can_fetch(self.user_agent, url):
                return True, "allowed by robots.txt"
            return False, f"{host}/robots.txt disallows {urlparse(url).path or '/'}"
        if found.kind == REFUSED:
            # No rule was read, so none may be quoted. Refused by this
            # project's choice, not by the standard.
            return False, (
                f"{host}/robots.txt could not be read ({found.status}); "
                "refused by policy, no rule was seen"
            )
        if found.kind == UNREACHABLE:
            return False, (
                f"{host}/robots.txt could not be fetched (HTTP {found.status}); "
                "refused while the site is failing, no rule was seen"
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
