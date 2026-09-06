"""robots.txt for the verifier.

The verifier points an unattended fetcher at human-facing federal websites.
A project whose deliverable is public trustworthiness does not ignore their
stated crawl rules, and a bot-managed host answers an unknown agent with a
challenge page the verifier would otherwise have to interpret.

Failing open is deliberate and narrow: a robots.txt that cannot be fetched
is not a prohibition, and treating it as one would silently stop the whole
run. A robots.txt that IS fetched and disallows the path is obeyed.

One case is neither, and it must not be reported as though it were the
second: a host that answers robots.txt itself with 401 or 403.
`RobotFileParser.read()` swallows that error and sets `disallow_all` with no
rules parsed, so the path is refused -- but the file was never read, and
saying "the site's robots.txt disallows this path" asserts a published rule
nobody has seen.

We keep the refusal, as a deliberate conservative choice rather than a
requirement: a host that will not show us its robots.txt is a host we do not
have permission from, and the cost of stopping is a few unchecked nodes.
That is NOT what the current standard mandates. RFC 9309 section 2.3.1.3
puts 4xx under "Unavailable" and permits a crawler to access any resource;
it is 5xx ("Unreachable", section 2.3.1.4) that requires assuming a complete
disallow. Python's parser implements the older pre-RFC convention, in which
401 and 403 alone mean disallow-all. [Likely, from memory: rfc-editor.org is
not reachable from the environment this was written in, so the section
numbers above are unverified -- check them before citing this comment.] If a
later run wants the standard's behaviour rather than ours, that is a
deliberate policy change here, not a bug fix.
"""

from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsPolicy:
    def __init__(self, *, user_agent: str, timeout: int = 30, enabled: bool = True) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.enabled = enabled
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _parser(self, url: str) -> RobotFileParser | None:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._parsers:
            parser = RobotFileParser()
            parser.set_url(f"{origin}/robots.txt")
            try:
                parser.read()
            except (HTTPError, URLError, OSError, ValueError):
                # No readable robots.txt is not a prohibition.
                self._parsers[origin] = None
            else:
                self._parsers[origin] = parser
        return self._parsers[origin]

    def allows(self, url: str) -> tuple[bool, str]:
        if not self.enabled:
            return True, "robots checks disabled"
        parser = self._parser(url)
        if parser is None:
            return True, "no readable robots.txt"
        if parser.can_fetch(self.user_agent, url):
            return True, "allowed by robots.txt"
        host = urlparse(url).netloc
        if self._refused_robots(parser):
            # 401/403 on robots.txt itself: no rule was read, so none may be
            # quoted. Refused by this project's choice, not by the standard.
            return False, f"{host}/robots.txt could not be read (401/403); refused by policy, no rule was seen"
        return False, f"{host}/robots.txt disallows {urlparse(url).path or '/'}"

    @staticmethod
    def _refused_robots(parser: RobotFileParser) -> bool:
        """True when the blanket disallow came from an unreadable robots.txt
        rather than from a rule in one."""
        if not getattr(parser, "disallow_all", False):
            return False
        return not getattr(parser, "entries", None) and getattr(parser, "default_entry", None) is None

    def crawl_delay(self, url: str) -> float:
        parser = self._parser(url)
        if parser is None:
            return 0.0
        try:
            delay = parser.crawl_delay(self.user_agent)
        except Exception:  # noqa: BLE001
            return 0.0
        return float(delay) if delay else 0.0
