"""
A real 0 stays 0 and an unknown figure stays null, from the scraped cell to the API (todo.md 1.3).
"""
import csv
import io
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import alerts, dbt, export, schemes, tenders
from collectors.jjm_collector import JJMCollector
from collectors.mgnrega_collector import MGNREGACollector
from database.connection import get_db
from database.models import (
    Base, BudgetAllocation, DBTTransfer, Department, District, DivisionType, Scheme, SchemeProgress,
    SchemeType, Tender,
)
from processors.data_cleaner import apportion, clean_amount, parse_int, parse_number, percent
from processors.gap_calculator import last_mile_gap_pct, recalculate_all_gaps

YEAR = "2025-26"


# ── Cleaning helpers ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("cell, expected", [
    ("0", 0.0), ("1,23,456", 123456.0), ("12.5", 12.5), ("-3", -3.0), ("Rs. 5", 5.0),
    ("", None), ("-", None), ("N/A", None), (None, None), (0, 0.0),
])
def test_parse_number(cell, expected):
    assert parse_number(cell) == expected


def test_clean_amount_and_helpers():
    assert clean_amount("1.5 Cr") == 150
    assert clean_amount("₹1234 Lakh") == 1234
    assert clean_amount("0") == 0
    assert clean_amount("") is None and clean_amount(None) is None
    assert parse_int("7.9") == 7
    assert apportion(100, 0.25) == 25 and apportion(None, 0.25) is None and apportion(100, None) is None
    assert percent(0, 100) == 0.0
    assert percent(None, 100) is None and percent(5, None) is None and percent(5, 0) is None
    assert last_mile_gap_pct(100, 100) == 0.0
    assert last_mile_gap_pct(100, None) is None and last_mile_gap_pct(0, 0) is None


# ── Collectors ────────────────────────────────────────────────────────────────

def test_jjm_parser_keeps_missing_counts_unknown():
    collector = JJMCollector.__new__(JJMCollector)
    rows = collector._parse_coverage_response([
        {"districtName": "SRINAGAR", "totalHH": "1,000", "hhWithTap": "0"},
        {"districtName": "BUDGAM", "totalHH": "500"},
    ])
    by_code = {r["district_code"]: r for r in rows}
    assert by_code["SGR"]["hh_with_tap"] == 0          # printed 0 is a real 0
    assert by_code["BDG"]["hh_with_tap"] is None       # absent is unknown
    assert by_code["BDG"]["villages_covered"] is None


def test_mgnrega_fund_table_without_totals_is_unknown():
    collector = MGNREGACollector.__new__(MGNREGACollector)
    assert collector._parse_fund_table("<table><tr><td>nothing</td></tr></table>") == {
        "allocated": None, "released": None, "utilized": None,
    }


@pytest.fixture
def sync_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'c.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        dept = Department(name="Jal Shakti", code="JALSHAKTI", division=DivisionType.CENTRAL)
        db.add(dept)
        db.flush()
        db.add_all([
            Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=dept.id),
            District(name="Srinagar", code="SGR", division=DivisionType.KASHMIR),
            District(name="Budgam", code="BDG", division=DivisionType.KASHMIR),
        ])
        db.commit()
        yield db
    engine.dispose()


def test_jjm_save_stores_unknown_funds_as_null(sync_db):
    collector = JJMCollector(sync_db, financial_year=YEAR)
    scheme = sync_db.execute(select(Scheme)).scalar_one()
    collector._save_progress(
        scheme,
        [
            {"district_code": "SGR", "total_hh": 300, "hh_with_tap": 0},
            {"district_code": "BDG", "total_hh": 100, "hh_with_tap": None},
        ],
        {"allocated": 400, "released": None, "utilized": 0},
    )
    rows = {r.district.code: r for r in sync_db.execute(select(SchemeProgress)).scalars()}
    sgr, bdg = rows["SGR"], rows["BDG"]
    assert (sgr.funds_allocated, sgr.funds_utilized, sgr.funds_released) == (300, 0, None)
    assert sgr.utilization_pct == 0.0 and sgr.release_pct is None
    assert sgr.achieved_physical == 0 and sgr.physical_pct == 0.0
    assert bdg.achieved_physical is None and bdg.physical_pct is None


def test_jjm_save_with_an_unknown_household_count_leaves_funds_unknown(sync_db):
    collector = JJMCollector(sync_db, financial_year=YEAR)
    scheme = sync_db.execute(select(Scheme)).scalar_one()
    collector._save_progress(
        scheme,
        [{"district_code": "SGR", "total_hh": 300}, {"district_code": "BDG", "total_hh": None}],
        {"allocated": 400, "released": 100, "utilized": 50},
    )
    rows = sync_db.execute(select(SchemeProgress)).scalars().all()
    assert {r.funds_allocated for r in rows} == {None}


def test_gap_calculator_does_not_turn_unknown_into_zero(sync_db):
    scheme = sync_db.execute(select(Scheme)).scalar_one()
    sgr = sync_db.execute(select(District).where(District.code == "SGR")).scalar_one()
    row = SchemeProgress(scheme_id=scheme.id, district_id=sgr.id, financial_year=YEAR,
                         funds_allocated=100, funds_released=None, funds_utilized=0,
                         target_physical=None, achieved_physical=5,
                         release_pct=55.0, snapshot_date=date(2025, 10, 1))
    sync_db.add(row)
    sync_db.commit()
    recalculate_all_gaps(sync_db, YEAR)
    sync_db.refresh(row)
    assert row.utilization_pct == 0.0
    assert row.release_pct is None and row.physical_pct is None


# ── API ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    path = tmp_path / "api.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        dept = Department(name="Rural Development", code="RDPR", division=DivisionType.CENTRAL)
        db.add(dept)
        db.flush()
        known = Scheme(name="Known", code="K", scheme_type=SchemeType.CSS, department_id=dept.id)
        unknown = Scheme(name="Unknown", code="U", scheme_type=SchemeType.CSS, department_id=dept.id)
        sgr = District(name="Srinagar", code="SGR", division=DivisionType.KASHMIR)
        db.add_all([known, unknown, sgr])
        db.flush()
        day = date(2025, 10, 1)
        db.add_all([
            DBTTransfer(scheme_id=known.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=day,
                        beneficiaries_enrolled=10, beneficiaries_paid=10, amount_transferred=0,
                        last_mile_gap_pct=0.0),
            DBTTransfer(scheme_id=unknown.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=day),
            SchemeProgress(scheme_id=unknown.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=day,
                           funds_allocated=100, funds_utilized=None),
            SchemeProgress(scheme_id=known.id, district_id=sgr.id, financial_year=YEAR, snapshot_date=day,
                           funds_allocated=100, funds_utilized=0, utilization_pct=0.0),
            Tender(tender_ref="T1", title="No award amount", status="awarded", contractor_name="A"),
            BudgetAllocation(department_id=dept.id, financial_year=YEAR, budget_estimate=500),
        ])
        db.commit()
        ids = {"known": known.id, "unknown": unknown.id}

    sessions = async_sessionmaker(create_async_engine(f"sqlite+aiosqlite:///{path}"), expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    for module in (alerts, dbt, export, schemes, tenders):
        app.include_router(module.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c, ids
    engine.dispose()


def test_dbt_routes(client):
    c, ids = client
    summary = {s["scheme_code"]: s for s in c.get("/api/v1/dbt/schemes", params={"financial_year": YEAR}).json()}
    assert summary["K"]["total_amount_transferred_lakhs"] == 0
    assert summary["K"]["overall_gap_pct"] == 0.0
    assert summary["U"]["total_beneficiaries_enrolled"] is None
    assert summary["U"]["total_amount_transferred_lakhs"] is None
    assert summary["U"]["overall_gap_pct"] is None

    gap = c.get(f"/api/v1/dbt/schemes/{ids['unknown']}/gap", params={"financial_year": YEAR}).json()
    assert gap[0]["beneficiaries_paid"] is None and gap[0]["last_mile_gap_pct"] is None


def test_history_with_unknown_spending_has_no_verdict(client):
    c, ids = client
    unknown = c.get(f"/api/v1/schemes/{ids['unknown']}/history", params={"financial_year": YEAR}).json()
    assert unknown["history"][0]["funds_utilized_lakhs"] is None
    assert unknown["history"][0]["utilization_pct"] is None
    assert unknown["verdict"] == "NO DATA" and unknown["projected_utilized_lakhs"] is None

    known = c.get(f"/api/v1/schemes/{ids['known']}/history", params={"financial_year": YEAR}).json()
    assert known["history"][0]["funds_utilized_lakhs"] == 0
    assert known["verdict"] != "NO DATA"


def test_low_utilization_alert_keeps_real_zero(client):
    c, _ = client
    rows = c.get("/api/v1/alerts/low-utilization", params={"financial_year": YEAR, "min_allocation_lakhs": 0}).json()
    assert [(r["scheme_code"], r["funds_utilized_lakhs"], r["utilization_pct"]) for r in rows] == [("K", 0, 0.0)]


def test_contractor_without_award_amount_is_null(client):
    c, _ = client
    rows = c.get("/api/v1/tenders/contractors").json()
    assert rows == [{"contractor_name": "A", "total_tenders_won": 1, "total_awarded_lakhs": None}]


def test_gap_csv_leaves_unknowns_blank(client):
    c, _ = client
    text = c.get("/api/v1/export/gap-analysis", params={"financial_year": YEAR}).text
    row = next(csv.DictReader(io.StringIO(text)))
    assert row["allocated_lakhs"] == "500"
    assert row["utilized_lakhs"] == ""       # no CGA spending figure
    assert row["released_lakhs"] == ""       # no release figure: not assumed to equal the allocation
    assert row["gap_lakhs"] == ""
    assert row["utilization_pct"] == ""
