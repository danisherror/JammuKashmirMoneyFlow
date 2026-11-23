"""
Every fact row has a snapshot (todo.md 1.4): the database refuses a row without one, collectors
link what they write to the responses they saved, and the API reports each row's source.
"""
import hashlib
import json
from datetime import date

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import alerts, dbt, districts, tenders
from collectors import http_policy
from collectors.jjm_collector import COVERAGE_API, FUND_API, JJMCollector
from database.connection import get_db
from database.models import (
    Base, BudgetAllocation, CAGFinding, CollectorStatus, DataSyncLog, DBTTransfer, Department, District,
    DivisionType, Expenditure, Scheme, SchemeProgress, SchemeType, SourceSnapshot, Tender,
)
from database.snapshots import snapshot_file
from tests.provenance_helpers import make_snapshot

YEAR = "2025-26"
DAY = date(2025, 10, 1)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dept = Department(name="Jal Shakti", code="JALSHAKTI", division=DivisionType.CENTRAL)
        session.add(dept)
        session.flush()
        session.add_all([
            Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=dept.id),
            District(name="Srinagar", code="SGR", division=DivisionType.KASHMIR),
            District(name="Budgam", code="BDG", division=DivisionType.KASHMIR),
        ])
        session.commit()
        yield session


def fact_rows(scheme_id, district_id, dept_id):
    return [
        BudgetAllocation(department_id=dept_id, financial_year=YEAR, budget_estimate=1),
        Expenditure(department_id=dept_id, financial_year=YEAR, month=1, snapshot_date=DAY),
        SchemeProgress(scheme_id=scheme_id, district_id=district_id, financial_year=YEAR, snapshot_date=DAY),
        Tender(tender_ref="T-1", title="t"),
        DBTTransfer(scheme_id=scheme_id, district_id=district_id, financial_year=YEAR, snapshot_date=DAY),
        CAGFinding(report_year=2024, finding_raw="para"),
    ]


def test_no_fact_row_without_a_snapshot(db):
    scheme = db.execute(select(Scheme)).scalar_one()
    district = db.execute(select(District)).scalars().first()
    for row in fact_rows(scheme.id, district.id, scheme.department_id):
        db.add(row)
        with pytest.raises(IntegrityError, match="snapshot_id"):
            db.flush()
        db.rollback()


def test_jjm_run_links_rows_to_the_saved_responses(db, tmp_path, monkeypatch):
    coverage = json.dumps([
        {"districtName": "SRINAGAR", "totalHH": 300, "hhWithTap": 150},
        {"districtName": "BUDGAM", "totalHH": 100, "hhWithTap": 100},
    ]).encode()
    funds = json.dumps({"totalAllocation": 400, "fundsReleased": 200, "fundsUtilized": 100}).encode()

    def portal(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        body = coverage if url.startswith(COVERAGE_API) else funds if url.startswith(FUND_API) else None
        if body is None:
            return httpx.Response(500)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    monkeypatch.setattr(http_policy, "_cache", {})
    monkeypatch.setattr(JJMCollector, "request_delay", 0)
    monkeypatch.setattr(
        JJMCollector, "get_http_client",
        lambda self: httpx.Client(transport=httpx.MockTransport(portal), headers=http_policy.http_headers()),
    )
    collector = JJMCollector(db, financial_year=YEAR)
    collector.snapshot_dir = str(tmp_path)
    collector.run()

    log = db.execute(select(DataSyncLog)).scalar_one()
    assert log.status is CollectorStatus.SUCCESS, log.error_message
    snapshots = {s.title: s for s in db.execute(select(SourceSnapshot)).scalars()}
    cov, fund = snapshots["JJM district coverage, J&K"], snapshots["JJM fund utilisation, J&K"]
    assert snapshot_file(cov, tmp_path).read_bytes() == coverage
    assert cov.sha256 == hashlib.sha256(coverage).hexdigest()
    assert cov.source_url.startswith(COVERAGE_API) and cov.collector_name == "jjm_collector"
    assert sorted(log.extra_info["snapshot_ids"]) == sorted([cov.id, fund.id])

    rows = db.execute(select(SchemeProgress)).scalars().all()
    assert len(rows) == 2
    assert {(r.snapshot_id, r.funds_snapshot_id) for r in rows} == {(cov.id, fund.id)}


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dept = Department(name="Jal Shakti", code="JALSHAKTI", division=DivisionType.CENTRAL)
        session.add(dept)
        session.flush()
        scheme = Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=dept.id)
        sgr = District(name="Srinagar", code="SGR", division=DivisionType.KASHMIR)
        session.add_all([scheme, sgr])
        session.flush()
        coverage = make_snapshot(session, "jjm_coverage")
        funds = make_snapshot(session, "jjm_funds")
        older = make_snapshot(session, "jjm_older")
        cag = make_snapshot(session, "cag_report", url="https://cag.gov.in/report.pdf")
        session.add_all([
            SchemeProgress(scheme_id=scheme.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=DAY,
                           funds_allocated=100, funds_utilized=10, utilization_pct=10.0,
                           snapshot_id=coverage.id, funds_snapshot_id=funds.id),
            SchemeProgress(scheme_id=scheme.id, district_id=sgr.id, financial_year=YEAR,
                           snapshot_date=date(2025, 9, 1), funds_allocated=100, snapshot_id=older.id),
            Tender(tender_ref="T-1", title="Road", snapshot_id=coverage.id),
            DBTTransfer(scheme_id=scheme.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=DAY,
                        beneficiaries_enrolled=5, beneficiaries_paid=4, snapshot_id=coverage.id),
            CAGFinding(report_year=2024, finding_raw="para", snapshot_id=cag.id),
        ])
        session.commit()
        ids = {"coverage": coverage.id, "funds": funds.id, "older": older.id, "cag": cag.id,
               "district": sgr.id, "scheme": scheme.id}

    sessions = async_sessionmaker(create_async_engine(f"sqlite+aiosqlite:///{path}"), expire_on_commit=False)

    async def override_db():
        async with sessions() as s:
            yield s

    app = FastAPI()
    for module in (alerts, dbt, districts, tenders):
        app.include_router(module.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c, ids
    engine.dispose()


def assert_points_at(source, snapshot_id, url=None):
    assert source["snapshot_id"] == snapshot_id
    assert source["download_url"] == f"/api/v1/snapshots/{snapshot_id}"
    assert source["fetched_at"].startswith("2026-11-22")
    if url:
        assert source["source_url"] == url


def test_api_rows_carry_their_snapshot(client):
    c, ids = client
    detail = c.get(f"/api/v1/districts/{ids['district']}", params={"financial_year": YEAR}).json()
    row = detail["scheme_progress"][0]
    assert_points_at(row["source"], ids["coverage"], "https://example.gov.in/jjm_coverage")
    assert_points_at(row["funds_source"], ids["funds"])

    heatmap = c.get("/api/v1/districts/heatmap", params={"financial_year": YEAR}).json()
    source = heatmap[0]["source"]
    assert source["snapshot_id"] == ids["older"]   # saved last, so the highest id
    assert "most recently saved of 2 snapshots" in source["label"]

    alert = c.get("/api/v1/alerts/low-utilization", params={"financial_year": YEAR, "min_allocation_lakhs": 0}).json()
    assert_points_at(alert[0]["source"], ids["coverage"])

    finding = c.get("/api/v1/alerts/cag-findings").json()[0]
    assert_points_at(finding["source"], ids["cag"], "https://cag.gov.in/report.pdf")
    assert finding["source"]["source_type"] == "official"

    assert_points_at(c.get("/api/v1/tenders").json()[0]["source"], ids["coverage"])

    gap = c.get(f"/api/v1/dbt/schemes/{ids['scheme']}/gap", params={"financial_year": YEAR}).json()
    assert_points_at(gap[0]["source"], ids["coverage"])
    summary = c.get("/api/v1/dbt/schemes", params={"financial_year": YEAR}).json()
    assert_points_at(summary[0]["source"], ids["coverage"])
