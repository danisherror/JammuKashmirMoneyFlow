"""scripts.purge_simulated_data removes only what the old simulators wrote."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import (
    Base,
    CAGFinding,
    CollectorStatus,
    DataSyncLog,
    DBTTransfer,
    Department,
    District,
    DivisionType,
    Expenditure,
    Scheme,
    SchemeProgress,
    SchemeType,
    Tender,
)
from scripts.purge_simulated_data import FAKE_CAG_PDF_URL, FAKE_CAG_TITLE, FAKE_TENDERS_URL, purge

DAY = date(2026, 11, 1)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        dept = Department(name="Jal Shakti", code="JAL", division=DivisionType.CENTRAL)
        dist = District(name="Jammu", code="JMU", division=DivisionType.JAMMU)
        session.add_all([dept, dist])
        session.flush()
        session.add_all([
            Scheme(name="Jal Jeevan Mission", code="JJM", scheme_type=SchemeType.CSS, department_id=dept.id),
            Scheme(name="PMAY-G", code="PMAY_G", scheme_type=SchemeType.CSS, department_id=dept.id),
            Scheme(name="UT scheme", code="UT1", scheme_type=SchemeType.UT, department_id=dept.id),
        ])
        session.commit()
        yield session


def ids(db):
    schemes = {s.code: s.id for s in db.execute(select(Scheme)).scalars()}
    district = db.execute(select(District)).scalar_one().id
    dept = db.execute(select(Department)).scalar_one().id
    return schemes, district, dept


def progress(scheme_id, district_id, **kw):
    return SchemeProgress(
        scheme_id=scheme_id, district_id=district_id,
        financial_year=kw.pop("financial_year", "2024-25"),
        snapshot_date=kw.pop("snapshot_date", DAY), **kw,
    )


def seed(db):
    schemes, district, dept = ids(db)
    db.add_all([
        # PMAY simulation (both markers), a real JJM row, and a UT-scheme row PFMS never touched
        progress(schemes["PMAY_G"], district, source="pmayg.nic.in (simulated)",
                 raw_data={"note": "simulated fallback"}, funds_released=10),
        progress(schemes["JJM"], district, source="ejalshakti.gov.in", funds_allocated=100,
                 funds_released=80, release_pct=80.0, raw_data={"pfms_note": "simulated fallback"}),
        progress(schemes["UT1"], district, source="real", funds_released=5, financial_year="2023-24"),
        DBTTransfer(scheme_id=schemes["JJM"], district_id=district, financial_year="2024-25",
                    snapshot_date=DAY, source="dbtbharat.gov.in (simulated)"),
        Expenditure(department_id=dept, financial_year="2024-25", month=3,
                    snapshot_date=DAY, source="CGA Simulation"),
        Expenditure(department_id=dept, financial_year="2024-25", month=4,
                    snapshot_date=DAY, source="cga.nic.in"),
        Tender(tender_ref="NIT/JAL/2026/1234", title="Fake", source_url=FAKE_TENDERS_URL,
               contractor_name="M/S Sharma Constructions"),
        Tender(tender_ref="e-NIT 12 of 2026-27", title="Looks real", source_url=FAKE_TENDERS_URL),
        CAGFinding(report_year=2024, report_title=FAKE_CAG_TITLE, finding_raw="invented",
                   paragraph_ref="Para 3.2", source_pdf_url=FAKE_CAG_PDF_URL),
        CAGFinding(report_year=2024, report_title="A real report", finding_raw="real",
                   paragraph_ref="Para 3.2", source_pdf_url="https://cag.gov.in/real.pdf"),
        DataSyncLog(collector_name="pfms_collector", status=CollectorStatus.SUCCESS,
                    started_at=datetime(2026, 11, 2, tzinfo=timezone.utc), records_updated=1),
        DataSyncLog(collector_name="jjm_collector", status=CollectorStatus.SUCCESS,
                    started_at=datetime(2026, 11, 2, tzinfo=timezone.utc), records_inserted=1),
    ])
    db.commit()


EXPECTED = {
    "scheme_progress deleted": 1,
    "scheme_progress funds_released cleared": 1,
    "dbt_transfers deleted": 1,
    "expenditures deleted": 1,
    "tenders deleted": 1,
    "cag_findings deleted": 1,
    "data_sync_log runs relabelled failed": 1,
}


def test_dry_run_counts_without_changing_anything(db):
    seed(db)
    assert purge(db, apply=False) == EXPECTED
    assert len(db.execute(select(SchemeProgress)).all()) == 3
    assert len(db.execute(select(Tender)).all()) == 2


def test_apply_removes_only_simulated_rows(db):
    seed(db)
    assert purge(db, apply=True, today=date(2026, 11, 23)) == EXPECTED

    rows = db.execute(select(SchemeProgress)).scalars().all()
    assert {r.source for r in rows} == {"ejalshakti.gov.in", "real"}
    jjm = next(r for r in rows if r.source == "ejalshakti.gov.in")
    assert jjm.funds_released is None and jjm.release_pct is None
    assert jjm.funds_allocated == 100
    assert "pfms_note" not in (jjm.raw_data or {})
    ut = next(r for r in rows if r.source == "real")
    assert ut.funds_released == 5   # UT scheme: not a PFMS target

    assert db.execute(select(DBTTransfer)).first() is None
    assert [e.source for e in db.execute(select(Expenditure)).scalars()] == ["cga.nic.in"]
    assert [t.tender_ref for t in db.execute(select(Tender)).scalars()] == ["e-NIT 12 of 2026-27"]
    assert [c.report_title for c in db.execute(select(CAGFinding)).scalars()] == ["A real report"]

    logs = {log.collector_name: log for log in db.execute(select(DataSyncLog)).scalars()}
    assert logs["pfms_collector"].status is CollectorStatus.FAILED
    assert "2026-11-23" in logs["pfms_collector"].error_message
    assert logs["jjm_collector"].status is CollectorStatus.SUCCESS

    # A second run finds nothing left to do.
    assert set(purge(db, apply=True).values()) == {0}
