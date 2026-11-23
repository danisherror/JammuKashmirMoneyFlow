"""
Routes built on the grant pages and Appendix II of the CAG Appropriation Accounts, end to end: the
real 2023-24 fixture pages (grants 1, 2, 24, 31, 36 and the whole Appendix II) are loaded into
SQLite with the loader, then read through the API. Expected figures are the hand-checked ones in
test_appropriation_details.py / test_appropriation_recoveries.py, converted to ₹ lakhs.
"""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import alerts, budget
from database.connection import get_db
from database.models import Base, Department, DivisionType, GrantDepartmentMap, SourceSnapshot
from loaders.appropriation_accounts import load_appropriation_accounts
from tests.pdf_fixtures import accounts_pdf

URL = "https://cag.gov.in/example-2023-24.pdf"
FETCHED = datetime(2026, 11, 23, tzinfo=timezone.utc)
YEAR = "2023-24"


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("official")
    path = tmp_path / "test.db"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as db:
        load_appropriation_accounts(
            db, accounts_pdf(YEAR), URL, tmp_path / "snapshots", fetched_at=FETCHED, partial_details=True
        )
        gad = Department(name="General Administration", code="GAD", division=DivisionType.CENTRAL)
        coop = Department(name="Cooperatives", code="COOP", division=DivisionType.CENTRAL)
        unmapped = Department(name="Urban Local Bodies", code="ULB", division=DivisionType.CENTRAL)
        db.add_all([gad, coop, unmapped])
        db.flush()
        db.add_all([
            GrantDepartmentMap(financial_year=YEAR, grant_no=1, department_id=gad.id),
            GrantDepartmentMap(financial_year=YEAR, grant_no=36, department_id=coop.id),
        ])
        db.commit()
        ids = {"GAD": gad.id, "COOP": coop.id, "ULB": unmapped.id}
        snapshot_id = db.scalar(select(SourceSnapshot.id))

    async_engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(budget.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, ids, snapshot_id
    sync_engine.dispose()


def get(client, path, status=200, **params):
    response = client.get(f"/api/v1{path}", params=params)
    assert response.status_code == status, response.text
    return response.json()


# ── Official chain (original → final grant → spent → net) ─────────────────────

def test_department_chain_sums_all_section_blocks(setup):
    client, ids, snapshot_id = setup
    chain = get(client, f"/budget/departments/{ids['GAD']}", financial_year=YEAR, view="official")["official_chain"]
    assert chain["grants"] == [1]
    # Revenue voted + revenue charged + capital voted, page 19 of the fixture.
    assert chain["original_lakhs"] == 72427.70
    assert chain["supplementary_lakhs"] == 0
    assert chain["final_grant_lakhs"] == 72427.70
    assert chain["gross_expenditure_lakhs"] == 49732.29
    assert chain["saving_lakhs"] == 22695.41
    assert chain["excess_lakhs"] == 0
    # Appendix II: 2,95 thousand recovered under grant 1 (revenue).
    assert chain["recoveries_lakhs"] == 2.95
    assert chain["recoveries_estimate_lakhs"] == 0
    assert chain["net_expenditure_lakhs"] == 49729.34

    source = chain["sources"]["original_lakhs"]
    assert source["source_type"] == "official"
    assert source["measure"] == "original_grant"
    assert source["snapshot_id"] == snapshot_id
    assert "grant pages" in source["label"]
    assert chain["sources"]["recoveries_lakhs"]["measure"] == "recoveries"
    assert "Appendix II" in chain["sources"]["recoveries_lakhs"]["label"]


def test_department_chain_with_supplementary_and_excess(setup):
    client, ids, _ = setup
    chain = get(client, f"/budget/departments/{ids['COOP']}", financial_year=YEAR)["official_chain"]
    # Revenue voted (O 7,11,969 + S 40,534; excess 23,987) + capital voted (2,50,000).
    assert chain["original_lakhs"] == 9619.69
    assert chain["supplementary_lakhs"] == 405.34
    assert chain["final_grant_lakhs"] == 10025.03
    assert chain["gross_expenditure_lakhs"] == 8233.02
    assert chain["excess_lakhs"] == 239.87
    assert chain["saving_lakhs"] == 2031.88
    assert chain["recoveries_lakhs"] == 0.13
    assert round(chain["final_grant_lakhs"] - chain["gross_expenditure_lakhs"], 2) == round(
        chain["saving_lakhs"] - chain["excess_lakhs"], 2
    )


def test_no_chain_in_live_view_or_without_a_mapped_grant(setup):
    client, ids, _ = setup
    assert get(client, f"/budget/departments/{ids['GAD']}", financial_year=YEAR, view="live")["official_chain"] is None
    assert get(client, f"/budget/departments/{ids['ULB']}", financial_year=YEAR)["official_chain"] is None
    assert get(client, f"/budget/departments/{ids['GAD']}", financial_year="2024-25")["official_chain"] is None


def test_overview_chain_covers_every_loaded_grant(setup):
    client, _, _ = setup
    chain = get(client, "/budget/overview", financial_year=YEAR, view="official")["official_chain"]
    assert chain["grants"] == [1, 2, 24, 31, 36]
    # Appendix II covers every grant, so the UT-wide recoveries are the Appendix II total.
    assert chain["recoveries_lakhs"] == 54120.20
    assert get(client, "/budget/overview", financial_year=YEAR, view="live")["official_chain"] is None
