"""Honest User-Agent and robots.txt handling (collectors/http_policy.py, BaseCollector.fetch_url)."""
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from collectors import http_policy
from collectors.base_collector import BaseCollector
from collectors.http_policy import USER_AGENT, RobotsUnreachableError, check_robots, http_headers
from database.models import Base, CollectorStatus, DataSyncLog

ROBOTS = "User-agent: *\nDisallow: /admin/\n\nUser-agent: JKMoneyFlowBot\nDisallow: /private/\n"


@pytest.fixture(autouse=True)
def fresh_cache():
    http_policy.clear_robots_cache()
    yield
    http_policy.clear_robots_cache()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def client_for(routes: dict[str, httpx.Response], seen: list | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return routes.get(request.url.path, httpx.Response(200, text="ok"))

    return httpx.Client(transport=httpx.MockTransport(handler), headers=http_headers())


def test_user_agent_is_honest():
    assert "Mozilla" not in USER_AGENT
    assert USER_AGENT.startswith("JKMoneyFlowBot/")
    assert "+https://" in USER_AGENT


def test_rules_are_applied_to_our_agent():
    client = client_for({"/robots.txt": httpx.Response(200, text=ROBOTS)})
    assert check_robots(client, "https://portal.example/report").allowed
    assert not check_robots(client, "https://portal.example/private/report").allowed
    # Only the group for our agent applies, not the * group (RFC 9309 §2.2.1).
    assert check_robots(client, "https://portal.example/admin/x").allowed


def test_missing_robots_txt_allows_everything():
    client = client_for({"/robots.txt": httpx.Response(404)})
    result = check_robots(client, "https://portal.example/anything")
    assert result.allowed
    assert "404" in result.reason


def test_server_error_on_robots_txt_means_do_not_fetch():
    client = client_for({"/robots.txt": httpx.Response(503)})
    with pytest.raises(RobotsUnreachableError):
        check_robots(client, "https://portal.example/report")


def test_robots_txt_is_fetched_once_per_host():
    seen: list[httpx.Request] = []
    client = client_for({"/robots.txt": httpx.Response(200, text=ROBOTS)}, seen)
    check_robots(client, "https://portal.example/a")
    check_robots(client, "https://portal.example/b")
    assert [r.url.path for r in seen] == ["/robots.txt"]
    assert seen[0].headers["User-Agent"] == USER_AGENT


def run_fetch(db, client, url):
    class _Collector(BaseCollector):
        collector_name = "test_collector"

        def run_collection(self):
            self.fetch_url(client, url)
            self._records_inserted = 1

    _Collector(db).run()
    return db.execute(select(DataSyncLog).order_by(DataSyncLog.id.desc())).scalars().first()


def test_allowed_fetch_records_the_robots_check(db):
    seen: list[httpx.Request] = []
    client = client_for({"/robots.txt": httpx.Response(200, text=ROBOTS)}, seen)
    log = run_fetch(db, client, "https://portal.example/report")
    assert log.status is CollectorStatus.SUCCESS
    record = log.extra_info["robots"]["https://portal.example/report"]
    assert record["allowed"] is True
    assert record["robots_url"] == "https://portal.example/robots.txt"
    assert all(r.headers["User-Agent"] == USER_AGENT for r in seen)


def test_disallowed_url_is_no_source_and_never_fetched(db):
    seen: list[httpx.Request] = []
    client = client_for({"/robots.txt": httpx.Response(200, text=ROBOTS)}, seen)
    log = run_fetch(db, client, "https://portal.example/private/report")
    assert log.status is CollectorStatus.NO_SOURCE
    assert "disallows" in log.error_message
    assert [r.url.path for r in seen] == ["/robots.txt"]


def test_refusing_our_user_agent_is_no_source(db):
    client = client_for({"/robots.txt": httpx.Response(404), "/report": httpx.Response(403)})
    log = run_fetch(db, client, "https://portal.example/report")
    assert log.status is CollectorStatus.NO_SOURCE
    assert "honest User-Agent" in log.error_message


def test_unreachable_robots_txt_fails_the_run(db):
    client = client_for({"/robots.txt": httpx.Response(500)})
    with pytest.raises(RobotsUnreachableError):
        run_fetch(db, client, "https://portal.example/report")
    log = db.execute(select(DataSyncLog)).scalars().one()
    assert log.status is CollectorStatus.FAILED
