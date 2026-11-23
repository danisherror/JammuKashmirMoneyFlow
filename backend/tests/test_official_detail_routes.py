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


# ── Breakdown (head tree, notes, section blocks) ──────────────────────────────

def find_node(nodes, head_code):
    for node in nodes:
        if node["head_code"] == head_code:
            return node
        found = find_node(node["children"], head_code)
        if found:
            return found
    return None


def all_rows(nodes):
    for node in nodes:
        yield from node["rows"]
        yield from all_rows(node["children"])


def test_department_breakdown_tree(setup):
    client, ids, snapshot_id = setup
    data = get(client, f"/budget/departments/{ids['GAD']}/breakdown", financial_year=YEAR)
    assert data["department_id"] == ids["GAD"]
    assert [(g["grant_no"], g["department_id"]) for g in data["grants"]] == [(1, ids["GAD"])]
    assert {(b["section"], b["kind"]) for b in data["section_blocks"]} == {
        ("revenue", "voted"), ("revenue", "charged"), ("capital", "voted")
    }

    major = find_node(data["tree"], "2052")
    assert major["level"] == "major" and major["rows"] == []
    leaf = find_node(data["tree"], "2052.090.0099.0518")
    assert [n["level"] for n in leaf["rows"][0]["head_path"]] == ["major", "minor", "sub_head", "detailed"]
    (row,) = leaf["rows"]
    assert (row["original_lakhs"], row["supplementary_lakhs"], row["reappropriation_lakhs"]) == (6390.50, 0, -177.15)
    assert (row["final_grant_lakhs"], row["expenditure_lakhs"], row["saving_lakhs"]) == (6213.35, 4252.59, 1960.76)
    assert row["category"] == "saving" and row["reasons_not_communicated"] is True
    assert row["remark"].startswith("Less expenditure against the provision mainly in respect of Salary")
    assert row["source"]["snapshot_id"] == snapshot_id
    assert row["source"]["page"] >= 1 and row["source"]["label"].endswith(f"p.{row['source']['page']}")


def test_unprinted_amounts_stay_null(setup):
    client, ids, _ = setup
    data = get(client, f"/budget/departments/{ids['GAD']}/breakdown", financial_year=YEAR)
    (row,) = find_node(data["tree"], "2013.101.0099.0431")["rows"]
    assert row["category"] == "unutilised"
    assert (row["final_grant_lakhs"], row["expenditure_lakhs"], row["saving_lakhs"]) == (650.00, None, None)


def test_breakdown_notes_are_verbatim(setup):
    client, ids, _ = setup
    data = get(client, f"/budget/departments/{ids['COOP']}/breakdown", financial_year=YEAR)
    assert [(n["number"], n["category"]) for n in data["notes"]] == [
        (1, "comment"), (2, "excess"), (3, "saving"), (4, "unutilised_supplementary"),
        (5, "without_provision"), (6, "comment"), (7, "saving"),
    ]
    rows = list(all_rows(data["tree"]))
    without = [r for r in rows if r["category"] == "without_provision"]
    assert [(r["head_code"], r["expenditure_lakhs"], r["final_grant_lakhs"]) for r in without] == [
        ("2425.107.0099.6028", 148.43, None),
        ("2425.108.0031.6059", 26.25, None),
        ("2425.108.0099.6059", 5.25, None),
    ]


def test_unmapped_grant_breakdown_and_issues(setup):
    client, _, _ = setup
    data = get(client, "/budget/grants/24/breakdown", financial_year=YEAR)
    assert data["department_id"] is None
    assert data["grants"][0]["grant_no"] == 24
    assert [(i["grant_no"], i["kind"]) for i in data["issues"]] == [(24, "headerless_table")]
    row = next(r for r in all_rows(data["tree"]) if r["head_code"] == "4059.60.800.0011.0464")
    assert (row["final_grant_lakhs"], row["expenditure_lakhs"], row["excess_lakhs"]) == (2850.00, 2906.20, 56.20)


def test_grant_list_includes_unmapped_grants(setup):
    client, ids, _ = setup
    grants = {g["grant_no"]: g for g in get(client, "/budget/grants", financial_year=YEAR)}
    assert len(grants) == 36  # every grant in the summary table
    assert grants[1]["department_id"] == ids["GAD"]
    assert grants[24]["department_id"] is None
    assert grants[1]["final_grant_lakhs"] == 72427.70


def test_breakdown_defaults_to_the_latest_loaded_year(setup):
    client, ids, _ = setup
    assert get(client, f"/budget/departments/{ids['GAD']}/breakdown")["financial_year"] == YEAR


def test_breakdown_empty_and_missing_cases(setup):
    client, ids, _ = setup
    data = get(client, f"/budget/departments/{ids['ULB']}/breakdown", financial_year=YEAR)
    assert data["grants"] == [] and data["tree"] == []
    assert "No CAG grant is mapped" in data["note"]
    get(client, "/budget/departments/9999/breakdown", status=404)
    get(client, "/budget/grants/99/breakdown", status=404, financial_year=YEAR)
    # Grant 7 is in the summary but its pages aren't in the fixture.
    data = get(client, "/budget/grants/7/breakdown", financial_year=YEAR)
    assert data["tree"] == [] and "No grant pages" in data["note"]
