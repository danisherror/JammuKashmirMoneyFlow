"""
How the tracker identifies itself and decides whether it may fetch a URL.

- One honest User-Agent naming the project and where to find it. No browser
  impersonation: if a portal refuses this UA, the collector reports `no_source`
  instead of spoofing (todo.md 1.6).
- robots.txt is checked before every fetch, following RFC 9309
  (https://www.rfc-editor.org/rfc/rfc9309):
  * the rules are matched with Python's urllib.robotparser;
  * 4xx on robots.txt means "unavailable": no rules, any path may be fetched
    (§2.3.1.3);
  * 5xx or a network error means "unreachable": complete disallow (§2.3.1.4).
    We don't fetch, and report it as a failure of that run rather than as
    `no_source`, since the site is down rather than closed to us;
  * a parsed robots.txt is cached for at most 24 hours (§2.4).
"""
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "JKMoneyFlowBot/1.0 (+https://github.com/danisherror/JammuKashmirMoneyFlow)"

ROBOTS_CACHE_SECONDS = 24 * 3600


class RobotsUnreachableError(RuntimeError):
    """robots.txt returned 5xx or couldn't be fetched: treat as complete disallow (RFC 9309 §2.3.1.4)."""


@dataclass(frozen=True)
class RobotsResult:
    url: str
    robots_url: str
    allowed: bool
    reason: str                 # "rules allow", "rules disallow", "no robots.txt (HTTP 404)"
    checked_at: datetime

    def as_record(self) -> dict:
        return {
            "robots_url": self.robots_url,
            "allowed": self.allowed,
            "reason": self.reason,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class _Entry:
    parser: RobotFileParser | None      # None = no robots.txt (4xx): everything allowed
    reason: str
    checked_at: datetime
    fetched_monotonic: float = field(default_factory=time.monotonic)


_cache: dict[str, _Entry] = {}


def robots_url_for(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def http_headers(accept: str = "application/json, text/html, */*") -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-IN,en;q=0.9"}


def _load(client: httpx.Client, robots_url: str) -> _Entry:
    now = datetime.now(timezone.utc)
    try:
        response = client.get(robots_url, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as e:
        raise RobotsUnreachableError(f"{robots_url} unreachable ({e.__class__.__name__}: {e})") from e
    if response.status_code >= 500:
        raise RobotsUnreachableError(f"{robots_url} returned HTTP {response.status_code}")
    if response.status_code >= 400:
        return _Entry(parser=None, reason=f"no robots.txt (HTTP {response.status_code})", checked_at=now)
    parser = RobotFileParser(robots_url)
    parser.parse(response.text.splitlines())
    return _Entry(parser=parser, reason="robots.txt rules", checked_at=now)


def check_robots(client: httpx.Client, url: str) -> RobotsResult:
    """
    May USER_AGENT fetch `url`? Raises RobotsUnreachableError when robots.txt
    can't be read (5xx / network), in which case nothing may be fetched.
    """
    robots_url = robots_url_for(url)
    entry = _cache.get(robots_url)
    if entry is None or time.monotonic() - entry.fetched_monotonic > ROBOTS_CACHE_SECONDS:
        entry = _load(client, robots_url)
        _cache[robots_url] = entry

    if entry.parser is None:
        return RobotsResult(url, robots_url, True, entry.reason, entry.checked_at)
    allowed = entry.parser.can_fetch(USER_AGENT, url)
    reason = "robots.txt rules allow" if allowed else "robots.txt rules disallow"
    return RobotsResult(url, robots_url, allowed, reason, entry.checked_at)


def clear_robots_cache():
    _cache.clear()
