"""Loader tests: real fixture PDFs into an in-memory SQLite database."""
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from database.models import (
    AppropriationAccountLine,
    AppropriationDocumentIssue,
    AppropriationHeadLine,
    AppropriationMajorHead,
    AppropriationNote,
    AppropriationSectionBlock,
    Base,
    Department,
    DivisionType,
    GrantDepartmentMap,
    SourceSnapshot,
)
from loaders import appropriation_accounts as loader_module
from parsers.appropriation_accounts import AppropriationAccountsError
from tests.pdf_fixtures import FIXTURES
from tests.pdf_fixtures import accounts_pdf as pdf

URL = "https://cag.gov.in/example.pdf"
FETCHED = datetime(2026, 11, 22, tzinfo=timezone.utc)


def load_appropriation_accounts(*args, **kwargs):
    """The fixtures hold only some grants' pages."""
    return loader_module.load_appropriation_accounts(*args, partial_details=True, **kwargs)


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


def test_load_stores_the_grant_pages(db, tmp_path):
    result = load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    assert result.head_rows == 90
    assert count(db, AppropriationHeadLine) == 90
    assert count(db, AppropriationSectionBlock) == 8
    assert count(db, AppropriationNote) == 22
    assert count(db, AppropriationMajorHead) == 19
    for model in (AppropriationHeadLine, AppropriationSectionBlock, AppropriationNote, AppropriationMajorHead):
        assert set(db.scalars(select(model.snapshot_id))) == {result.snapshot_id}
        assert set(db.scalars(select(model.financial_year))) == {"2022-23"}

    # The printed arithmetic error in grant 32 is stored as printed, with its flag.
    flagged = db.scalars(select(AppropriationHeadLine).where(AppropriationHeadLine.printed_error.is_not(None))).one()
    assert (flagged.grant_no, flagged.head_code) == (32, "4401.800.0011.0222")
    assert flagged.head_path[0] == {"level": "major", "code": "4401", "name": flagged.head_path[0]["name"]}
    assert flagged.major_head_code == "4401"
    assert flagged.head_name == flagged.head_path[-1]["name"]


def test_amounts_not_printed_stay_null(db, tmp_path):
    load_appropriation_accounts(db, pdf("2023-24"), URL, tmp_path)
    unutilised = db.scalars(
        select(AppropriationHeadLine).where(AppropriationHeadLine.category == "unutilised")
    ).first()
    assert unutilised.final_grant_thousand is not None
    assert unutilised.expenditure_thousand is None


def test_parser_side_notes_are_kept(db, tmp_path):
    load_appropriation_accounts(db, pdf("2021-22"), URL, tmp_path)
    kinds = set(db.scalars(select(AppropriationDocumentIssue.kind)))
    assert {"skipped_table", "footnote"} <= kinds


def test_summary_only_rows_are_completed_on_reload(db, tmp_path):
    """A database loaded before the grant-page tables existed gets them on the next run."""
    load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    for model in (AppropriationHeadLine, AppropriationSectionBlock, AppropriationNote, AppropriationMajorHead):
        db.execute(model.__table__.delete())
    db.commit()
    again = load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    assert again.status == "replaced"
    assert count(db, AppropriationHeadLine) == 90
    assert count(db, AppropriationAccountLine) == 75
    assert count(db, SourceSnapshot) == 1


def test_reloading_the_same_pdf_is_a_no_op(db, tmp_path):
    load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    again = load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path)
    assert again.status == "unchanged"
    assert count(db, AppropriationAccountLine) == 75
    assert count(db, AppropriationHeadLine) == 90
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
    assert set(db.scalars(select(AppropriationHeadLine.snapshot_id))) == {result.snapshot_id}
    assert count(db, AppropriationHeadLine) == 90


def test_wrong_year_is_rejected_without_writing(db, tmp_path):
    with pytest.raises(ValueError, match="expected the 2023-24 accounts"):
        load_appropriation_accounts(db, pdf("2022-23"), URL, tmp_path, expected_year="2023-24")
    assert count(db, SourceSnapshot) == 0
    assert not any(tmp_path.iterdir())


def test_grant_pages_that_fail_validation_reject_the_document(db, tmp_path):
    summary_only = (FIXTURES / "jk-appropriation-2022-23-summary.pdf").read_bytes()
    with pytest.raises(AppropriationAccountsError, match="no grant pages"):
        load_appropriation_accounts(db, summary_only, URL, tmp_path)
    assert count(db, SourceSnapshot) == 0
    assert count(db, AppropriationAccountLine) == 0
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
