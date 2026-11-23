"""
`?view=live|official|combined` on the budget and scheme routes, end to end: the real 2022-23
Appropriation Accounts fixture is loaded into SQLite, with hand-made live rows beside it.
"""
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import budget, schemes
from database.connection import get_db
from database.models import (
    AppropriationAccountLine,
    Base,
    BudgetAllocation,
    Department,
    District,
    DivisionType,
    Expenditure,
    GrantDepartmentMap,
    Scheme,
    SchemeProgress,
    SchemeType,
    SourceSnapshot,
)
from loaders.appropriation_accounts import load_appropriation_accounts
from tests.pdf_fixtures import accounts_pdf
from tests.provenance_helpers import make_snapshot

URL = "https://cag.gov.in/example-2022-23.pdf"
FETCHED = datetime(2026, 11, 22, tzinfo=timezone.utc)
YEAR = "2022-23"


def official_lakhs(db: Session, column, grant_no: int | None = None, section: str | None = None) -> float:
    query = select(func.sum(column)).where(AppropriationAccountLine.financial_year == YEAR)
    if grant_no is not None:
        query = query.where(AppropriationAccountLine.grant_no == grant_no)
    if section is not None:
        query = query.where(AppropriationAccountLine.section == section)
    return round(db.scalar(query) / 100, 2)


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "test.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as db:
        load_appropriation_accounts(
            db, accounts_pdf(YEAR), URL, tmp_path / "snapshots", fetched_at=FETCHED, partial_details=True
        )

        pwd = Department(name="Public Works", code="PWD", division=DivisionType.CENTRAL)
        health = Department(name="Health", code="HEALTH", division=DivisionType.CENTRAL)
        ulb = Department(name="Urban Local Bodies", code="ULB", division=DivisionType.CENTRAL)
        db.add_all([pwd, health, ulb])
        db.flush()
        live = make_snapshot(db, "live_budget")
        db.add_all([
            GrantDepartmentMap(financial_year=YEAR, grant_no=16, department_id=pwd.id),
            GrantDepartmentMap(financial_year=YEAR, grant_no=17, department_id=health.id),
        ])

        pwd_grant = official_lakhs(db, AppropriationAccountLine.final_grant_thousand, 16)
        pwd_spent = official_lakhs(db, AppropriationAccountLine.gross_expenditure_thousand, 16)
        db.add_all([
            # within 2% of the audited final grant -> no flag
            BudgetAllocation(department_id=pwd.id, financial_year=YEAR, budget_estimate=int(pwd_grant * 1.01),
                             is_capital=True, source="jkfinance.nic.in", snapshot_id=live.id),
            # far from the audited figure -> flag
            BudgetAllocation(department_id=health.id, financial_year=YEAR, budget_estimate=1000,
                             is_capital=False, source="jkfinance.nic.in", snapshot_id=live.id),
            # no grant mapped -> live only
            BudgetAllocation(department_id=ulb.id, financial_year=YEAR, budget_estimate=50000,
                             is_capital=True, source="jkfinance.nic.in", snapshot_id=live.id),
            # a year the CAG hasn't published
            BudgetAllocation(department_id=pwd.id, financial_year="2024-25", budget_estimate=400000,
                             is_capital=True, source="jkfinance.nic.in", snapshot_id=live.id),
            Expenditure(department_id=pwd.id, financial_year=YEAR, month=1, utilized_amount=int(pwd_spent / 2),
                        source="cga.nic.in", snapshot_date=date(2022, 5, 1), snapshot_id=live.id),
        ])

        district = District(name="Jammu", code="JMU", division=DivisionType.JAMMU)
        db.add(district)
        db.flush()
        jjm = Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=health.id,
                     source_url="https://ejalshakti.gov.in/")
        db.add(jjm)
        db.flush()
        db.add(SchemeProgress(scheme_id=jjm.id, district_id=district.id, financial_year=YEAR,
                              funds_allocated=200, funds_utilized=50, funds_released=None,
                              snapshot_date=date(2023, 1, 1), source="ejalshakti.gov.in",
                              snapshot_id=live.id))
        db.commit()
        ids = {"PWD": pwd.id, "HEALTH": health.id, "ULB": ulb.id, "JJM": jjm.id}
        expected = {
            "pwd_grant": pwd_grant,
            "pwd_spent": pwd_spent,
            "health_grant": official_lakhs(db, AppropriationAccountLine.final_grant_thousand, 17),
            "total": official_lakhs(db, AppropriationAccountLine.final_grant_thousand),
            "capital": official_lakhs(db, AppropriationAccountLine.final_grant_thousand, section="capital"),
            "snapshot_id": db.scalar(select(SourceSnapshot.id).where(SourceSnapshot.source_type == "appropriation_accounts")),
            "live_snapshot_id": live.id,
            "grants": db.scalar(select(func.count(AppropriationAccountLine.grant_no.distinct()))),
            "pwd_page": db.scalar(select(func.min(AppropriationAccountLine.page))
                                  .where(AppropriationAccountLine.grant_no == 16)),
        }

    async_engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(budget.router, prefix="/api/v1")
    app.include_router(schemes.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, ids, expected
    sync_engine.dispose()


def get(client, path, **params):
    response = client.get(f"/api/v1{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def by_code(rows):
    return {row["code"]: row for row in rows}


# ── overview ──────────────────────────────────────────────────────────────────

def test_overview_combined_uses_the_audited_total(setup):
    client, _, expected = setup
    body = get(client, "/budget/overview", financial_year=YEAR)
    assert body["view"] == "combined"
    assert body["total_budget_lakhs"] == expected["total"]
    assert body["total_capital_lakhs"] == expected["capital"]
    src = body["sources"]["total_budget_lakhs"]
    assert src["source_type"] == "official"
    assert src["measure"] == "final_grant"
    assert src["snapshot_id"] == expected["snapshot_id"]
    assert src["source_url"] == URL
    assert src["label"].startswith(f"Official · Appropriation Accounts {YEAR}, p")
    assert src["mismatch"] is None             # totals are never compared
    assert body["total_departments"] == expected["grants"]   # official view counts grants


def test_overview_live_and_missing_year(setup):
    client, _, expected = setup
    live = get(client, "/budget/overview", financial_year=YEAR, view="live")
    assert live["total_budget_lakhs"] == int(expected["pwd_grant"] * 1.01) + 1000 + 50000
    assert live["sources"]["total_budget_lakhs"]["provisional"] is True
    assert live["total_departments"] == 3

    missing = get(client, "/budget/overview", financial_year="2019-20")
    assert missing["total_budget_lakhs"] is None
    assert missing["capital_pct"] is None
    assert missing["sources"]["total_budget_lakhs"] == {
        "source_type": None, "label": "No budget figure for 2019-20", "measure": None, "source_url": None,
        "snapshot_id": None, "page": None, "fetched_at": None, "provisional": False, "mismatch": None,
        "download_url": None,
    }


# ── departments ───────────────────────────────────────────────────────────────

def test_departments_combined_applies_all_rules(setup):
    client, _, expected = setup
    rows = by_code(get(client, "/budget/departments", financial_year=YEAR))
    assert set(rows) == {"PWD", "HEALTH", "ULB"}

    pwd = rows["PWD"]
    assert pwd["budget_estimate_lakhs"] == expected["pwd_grant"]
    assert pwd["utilized_lakhs"] == expected["pwd_spent"]
    assert pwd["is_capital"] is None
    budget_src = pwd["sources"]["budget_estimate_lakhs"]
    assert (budget_src["source_type"], budget_src["mismatch"]) == ("official", None)
    assert budget_src["page"] == expected["pwd_page"]
    # live spending is half the audited figure -> flagged
    spent_mismatch = pwd["sources"]["utilized_lakhs"]["mismatch"]
    assert spent_mismatch["official"] == expected["pwd_spent"]
    assert spent_mismatch["diff_pct"] == pytest.approx(-50, abs=0.1)

    health = rows["HEALTH"]
    assert health["budget_estimate_lakhs"] == expected["health_grant"]
    mismatch = health["sources"]["budget_estimate_lakhs"]["mismatch"]
    assert (mismatch["live"], mismatch["official"]) == (1000, expected["health_grant"])

    ulb = rows["ULB"]
    assert ulb["budget_estimate_lakhs"] == 50000
    assert ulb["is_capital"] is True
    assert ulb["sources"]["budget_estimate_lakhs"]["provisional"] is True
    assert ulb["sources"]["budget_estimate_lakhs"]["label"] == "Live · jkfinance.nic.in (provisional)"
    assert ulb["utilized_lakhs"] is None       # no spending figure: null, not 0
    assert ulb["utilization_pct"] is None


def test_departments_official_lists_only_mapped_grants(setup):
    client, _, _ = setup
    rows = by_code(get(client, "/budget/departments", financial_year=YEAR, view="official"))
    assert set(rows) == {"PWD", "HEALTH"}
    assert rows["HEALTH"]["revised_estimate_lakhs"] is None
    assert all(r["sources"]["budget_estimate_lakhs"]["mismatch"] is None for r in rows.values())


def test_departments_live(setup):
    client, _, expected = setup
    rows = by_code(get(client, "/budget/departments", financial_year=YEAR, view="live"))
    assert rows["PWD"]["budget_estimate_lakhs"] == int(expected["pwd_grant"] * 1.01)
    assert rows["PWD"]["sources"]["budget_estimate_lakhs"]["measure"] == "budget_estimate"


def test_unpublished_year_falls_back_to_live(setup):
    client, _, _ = setup
    rows = by_code(get(client, "/budget/departments", financial_year="2024-25"))
    assert rows["PWD"]["budget_estimate_lakhs"] == 400000
    assert rows["PWD"]["sources"]["budget_estimate_lakhs"]["provisional"] is True
    assert get(client, "/budget/departments", financial_year="2024-25", view="official") == []


def test_department_detail_monthly_is_live_only(setup):
    client, ids, _ = setup
    official = get(client, f"/budget/departments/{ids['PWD']}", financial_year=YEAR, view="official")
    assert official["monthly_expenditure"] == []
    assert official["sources"]["monthly_expenditure"]["label"] == "The CAG accounts have no monthly figures"

    combined = get(client, f"/budget/departments/{ids['PWD']}", financial_year=YEAR)
    assert len(combined["monthly_expenditure"]) == 1
    assert combined["sources"]["monthly_expenditure"]["source_type"] == "live"

    assert client.get("/api/v1/budget/departments/9999").status_code == 404


def test_gap_analysis_no_data_flag(setup):
    client, _, _ = setup
    rows = {r["department_code"]: r for r in get(client, "/budget/gap-analysis", financial_year=YEAR,
                                                    min_allocation_lakhs=0)}
    assert rows["ULB"]["gap_flag"] == "no_data"
    assert rows["ULB"]["gap_lakhs"] is None
    assert rows["PWD"]["released_lakhs"] is None


def test_unknown_view_is_rejected(setup):
    client, _, _ = setup
    assert client.get("/api/v1/budget/overview", params={"view": "audited"}).status_code == 422


# ── schemes ───────────────────────────────────────────────────────────────────

def test_schemes_are_live_only(setup):
    client, ids, expected = setup
    combined = get(client, "/schemes", financial_year=YEAR)[0]
    assert combined["funds_allocated_lakhs"] == 200
    assert combined["funds_released_lakhs"] is None
    src = combined["sources"]["funds_utilized_lakhs"]
    assert (src["source_type"], src["provisional"]) == ("live", True)
    # the live figure points at the saved document it was read from (todo.md 1.4)
    assert src["snapshot_id"] == expected["live_snapshot_id"]
    assert src["source_url"] == "https://example.gov.in/live_budget"
    assert src["download_url"] == f"/api/v1/snapshots/{expected['live_snapshot_id']}"

    official = get(client, "/schemes", financial_year=YEAR, view="official")[0]
    assert official["funds_allocated_lakhs"] is None
    assert official["utilization_pct"] is None
    assert official["sources"]["funds_allocated_lakhs"]["label"].startswith("No official figure per scheme")

    detail = get(client, f"/schemes/{ids['JJM']}", financial_year=YEAR, view="official")
    assert detail["district_progress"] == []
    history = get(client, f"/schemes/{ids['JJM']}/history", financial_year=YEAR, view="official")
    assert (history["history"], history["verdict"]) == ([], "NO DATA")

    detail = get(client, f"/schemes/{ids['JJM']}", financial_year=YEAR)
    assert detail["funds_utilized_lakhs"] == 50
    assert detail["sources"]["district_progress"]["source_type"] == "live"
