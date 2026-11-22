"""Loader tests: real fixture PDFs into an in-memory SQLite database."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from database.models import (
    AppropriationAccountLine,
    Base,
    Department,
    DivisionType,
    GrantDepartmentMap,
    SourceSnapshot,
)
from loaders.appropriation_accounts import load_appropriation_accounts
from parsers.appropriation_accounts import AppropriationAccountsError

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"
URL = "https://cag.gov.in/example.pdf"
FETCHED = datetime(2026, 11, 22, tzinfo=timezone.utc)


def pdf(year: str) -> bytes:
    return (FIXTURES / f"jk-appropriation-{year}-summary.pdf").read_bytes()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_load_inserts_rows_and_saves_snapshot(db, tmp_path):
    content = pdf("2022-23")
    result = load_appropriation_accounts(db, content, URL, tmp_path, fetched_at=FETCHED)

    sha = hashlib.sha256(content).hexdigest()
    assert (result.financial_year, result.status, result.rows, result.sha256) == ("2022-23", "inserted", 75, sha)
    assert (tmp_path / "appropriation_accounts" / f"{sha}.pdf").read_bytes() == content

    snapshot = db.scalars(select(SourceSnapshot)).one()
    assert (snapshot.source_url, snapshot.sha256, snapshot.byte_size) == (URL, sha, len(content))
    assert count(db, AppropriationAccountLine) == 75

    pwd = db.scalars(
        select(AppropriationAccountLine).where(
            AppropriationAccountLine.grant_no == 16,
            AppropriationAccountLine.section == "revenue",
        )
    ).one()
    assert (pwd.final_grant_thousand, pwd.gross_expenditure_thousand, pwd.excess_thousand) == (
        12027563,
        13603361,
        1575798,
    )
    assert pwd.snapshot_id == snapshot.id
    assert pwd.page == 2


def test_reloading_the_same_pdf_is_a_no_op(db, tmp_path):
    load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    again = load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    assert again.status == "unchanged"
    assert count(db, AppropriationAccountLine) == 75
    assert count(db, SourceSnapshot) == 1


def test_years_are_stored_side_by_side(db, tmp_path):
    for year in ("2021-22", "2022-23", "2023-24"):
        load_appropriation_accounts(db, pdf(year), URL, tmp_path)
    assert count(db, AppropriationAccountLine) == 73 + 75 + 77
    assert count(db, SourceSnapshot) == 3


def test_a_new_file_for_the_same_year_replaces_rows(db, tmp_path):
    load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    reissued = pdf("2022-23") + b"\n% reissued\n"  # same content, different bytes
    result = load_appropriation_accounts(db, reissued, URL, tmp_path)
    assert result.status == "replaced"
    assert count(db, AppropriationAccountLine) == 75
    assert count(db, SourceSnapshot) == 2
    assert set(db.scalars(select(AppropriationAccountLine.snapshot_id))) == {result.snapshot_id}


def test_wrong_year_is_rejected_without_writing(db, tmp_path):
    with pytest.raises(ValueError, match="expected the 2023-24 accounts"):
        load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path, expected_year="2023-24")
    assert count(db, SourceSnapshot) == 0
    assert not any(tmp_path.iterdir())


def test_unparseable_pdf_is_rejected_without_writing(db, tmp_path):
    import pypdfium2 as pdfium

    blank = tmp_path / "blank.pdf"
    doc = pdfium.PdfDocument.new()
    doc.new_page(595, 842)
    doc.save(blank)
    with pytest.raises(AppropriationAccountsError):
        load_appropriation_accounts(db, blank.read_bytes(), URL, tmp_path / "snapshots")
    assert count(db, SourceSnapshot) == 0
    assert count(db, AppropriationAccountLine) == 0
    assert not (tmp_path / "snapshots").exists()


def test_department_comes_from_the_mapping(db, tmp_path):
    load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    pwd = Department(name="Public Works Department", code="PWD", division=DivisionType.CENTRAL)
    db.add(pwd)
    db.flush()
    db.add(GrantDepartmentMap(financial_year="2022-23", grant_no=16, department_id=pwd.id))
    db.commit()

    rows = db.execute(
        select(Department.code, func.sum(AppropriationAccountLine.gross_expenditure_thousand))
        .join(
            GrantDepartmentMap,
            (GrantDepartmentMap.financial_year == AppropriationAccountLine.financial_year)
            & (GrantDepartmentMap.grant_no == AppropriationAccountLine.grant_no),
        )
        .join(Department, Department.id == GrantDepartmentMap.department_id)
        .group_by(Department.code)
    ).all()
    assert rows == [("PWD", 13603361 + 27614436)]
