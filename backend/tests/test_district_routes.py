"""District routes report missing figures as null (no data), never 0% / grade F (todo.md 1.3)."""
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import districts
from database.connection import get_db
from database.models import (
    Base, Department, District, DivisionType, Scheme, SchemeProgress, SchemeType,
)

YEAR = "2025-26"


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "db.sqlite"
    sync_engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(sync_engine)
    with Session(sync_engine) as db:
        dept = Department(name="Jal Shakti (PHE)", code="JALSHAKTI", division=DivisionType.CENTRAL)
        db.add(dept)
        db.flush()
        jjm = Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=dept.id)
        with_data = District(name="Srinagar", code="SGR", division=DivisionType.KASHMIR)
        with_null_util = District(name="Budgam", code="BDG", division=DivisionType.KASHMIR)
        empty = District(name="Kupwara", code="KPW", division=DivisionType.KASHMIR)
        db.add_all([jjm, with_data, with_null_util, empty])
        db.flush()
        db.add_all([
            SchemeProgress(scheme_id=jjm.id, district_id=with_data.id, financial_year=YEAR,
                           funds_allocated=100, funds_utilized=0, utilization_pct=0.0,
                           snapshot_date=date(2025, 10, 1)),
            SchemeProgress(scheme_id=jjm.id, district_id=with_null_util.id, financial_year=YEAR,
                           funds_allocated=None, funds_utilized=None, utilization_pct=None,
                           snapshot_date=date(2025, 10, 1)),
        ])
        db.commit()
        ids = {"SGR": with_data.id, "BDG": with_null_util.id, "KPW": empty.id}

    sessions = async_sessionmaker(create_async_engine(f"sqlite+aiosqlite:///{path}"), expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(districts.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c, ids
    sync_engine.dispose()


def test_heatmap_keeps_a_real_zero_apart_from_no_data(client):
    c, _ = client
    items = c.get("/api/v1/districts/heatmap", params={"financial_year": YEAR}).json()
    by_code = {i["code"]: i for i in items}

    # A real 0% is a real F.
    assert by_code["SGR"]["avg_utilization_pct"] == 0.0
    assert by_code["SGR"]["absorption_grade"] == "F"
    assert by_code["SGR"]["total_funds_utilized_lakhs"] == 0

    # Rows without figures, or no rows at all, are unknown.
    for code in ("BDG", "KPW"):
        d = by_code[code]
        assert d["avg_utilization_pct"] is None and d["absorption_score"] is None
        assert d["absorption_grade"] is None
        assert d["total_funds_allocated_lakhs"] is None and d["total_funds_utilized_lakhs"] is None
    assert by_code["KPW"]["active_schemes_count"] == 0

    # Districts with data sort before districts without.
    assert items[0]["code"] == "SGR"


def test_detail_without_rows_is_null_not_zero(client):
    c, ids = client
    d = c.get(f"/api/v1/districts/{ids['KPW']}", params={"financial_year": YEAR}).json()
    assert d["scheme_progress"] == []
    assert d["avg_utilization_pct"] is None and d["absorption_grade"] is None
    assert d["total_funds_allocated_lakhs"] is None and d["total_funds_utilized_lakhs"] is None

    d = c.get(f"/api/v1/districts/{ids['SGR']}", params={"financial_year": YEAR}).json()
    assert d["avg_utilization_pct"] == 0.0 and d["absorption_grade"] == "F"
    assert d["total_funds_allocated_lakhs"] == 100
