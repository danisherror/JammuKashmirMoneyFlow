"""/alerts/sync-status reports APScheduler's real next fire time per collector."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import alerts
from database.connection import get_db
from database.models import Base, CollectorStatus, DataSyncLog
from scheduler import jobs


@pytest.fixture
def scheduler(monkeypatch):
    monkeypatch.setattr(jobs.settings, "scheduler_enabled", True)
    sched = jobs.create_scheduler()
    sched.start(paused=True)   # computes next_run_time without firing anything
    yield sched
    sched.shutdown(wait=False)


def test_job_ids_match_the_mapping(scheduler):
    assert {job.id for job in scheduler.get_jobs()} == set(jobs.JOB_COLLECTORS)


def test_next_run_times_take_the_earliest_job(scheduler):
    weekly = scheduler.get_job(jobs.WEEKLY_JOB_ID).next_run_time
    monthly = scheduler.get_job(jobs.MONTHLY_CGA_JOB_ID).next_run_time
    times = jobs.next_run_times(scheduler)

    assert set(times) == {c.collector_name for c in jobs.ALL_COLLECTORS}
    assert times["jjm_collector"] == weekly
    assert times["cga_collector"] == min(weekly, monthly)


def test_no_scheduler_means_no_next_run():
    assert jobs.next_run_times(None) == {}


def _sync_status(tmp_path, scheduler, logs):
    path = tmp_path / "db.sqlite"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)
    with Session(sync_engine) as db:
        db.add_all(logs)
        db.commit()

    sessions = async_sessionmaker(create_async_engine(f"sqlite+aiosqlite:///{path}"), expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(alerts.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.state.scheduler = scheduler
    with TestClient(app) as client:
        items = client.get("/api/v1/alerts/sync-status").json()
    sync_engine.dispose()
    return {i["collector_name"]: i for i in items}


def test_sync_status_route_uses_the_scheduler(tmp_path, scheduler):
    items = _sync_status(tmp_path, scheduler, [
        DataSyncLog(collector_name="jjm_collector", status=CollectorStatus.SUCCESS,
                    started_at=datetime(2026, 11, 22, tzinfo=timezone.utc), records_inserted=3),
    ])
    expected = scheduler.get_job(jobs.WEEKLY_JOB_ID).next_run_time
    assert datetime.fromisoformat(items["jjm_collector"]["next_run"]) == expected


def test_sync_status_lists_every_collector_with_its_source(tmp_path, scheduler):
    items = _sync_status(tmp_path, scheduler, [
        DataSyncLog(collector_name="tenders_collector", status=CollectorStatus.NO_SOURCE,
                    started_at=datetime(2026, 11, 22, tzinfo=timezone.utc),
                    error_message="CAPTCHA on the search page"),
    ])
    assert list(items) == [c.collector_name for c in jobs.ALL_COLLECTORS]

    tenders = items["tenders_collector"]
    assert tenders["status"] == "no_source"
    assert tenders["error_message"] == "CAPTCHA on the search page"
    assert tenders["source_name"] == "jktenders.gov.in"
    assert tenders["source_url"].startswith("https://jktenders.gov.in/")
    assert tenders["label"] == "Tenders"

    never = items["dbt_collector"]
    assert never["status"] == "never_run"
    assert never["last_run"] is None and never["last_success"] is None
    assert never["is_healthy"] is False and never["records_last_run"] == 0

    # A collector without a known source says so instead of linking somewhere.
    assert items["cga_collector"]["source_url"] is None
