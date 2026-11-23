"""
Load the J&K Appropriation Accounts (CAG) into the database.

Tables filled from one PDF: `appropriation_account_lines` (summary table); from the grant
pages, `appropriation_major_heads`, `appropriation_section_blocks`, `appropriation_notes`,
`appropriation_head_lines` and `appropriation_document_issues`; and from Appendix II,
`appropriation_recoveries`.

Steps, all-or-nothing per document:
  1. download the PDF (or read a local copy),
  2. parse and validate it (parsers.appropriation_accounts for the summary, then
     parsers.appropriation_details for the grant pages, parsers.appropriation_recoveries for
     Appendix II) — a document that fails is never stored,
  3. save the bytes to <raw_snapshot_dir>/appropriation_accounts/<sha256>.pdf,
  4. in one transaction, record the snapshot and replace that year's rows in every table.

Re-loading the same file is a no-op. Loading a different file for a year already loaded (e.g. a
reissued PDF) replaces that year's rows and keeps the old snapshot row for the record.

Usage (from backend/):
    python -m loaders.appropriation_accounts --all
    python -m loaders.appropriation_accounts --year 2022-23
    python -m loaders.appropriation_accounts --file saved.pdf --url https://cag.gov.in/...
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import (
    AppropriationAccountLine,
    AppropriationDocumentIssue,
    AppropriationHeadLine,
    AppropriationMajorHead,
    AppropriationNote,
    AppropriationRecovery,
    AppropriationSectionBlock,
    SourceSnapshot,
)
from parsers.appropriation_accounts import parse_appropriation_summary
from parsers.appropriation_details import AppropriationDetails, parse_appropriation_details
from parsers.appropriation_recoveries import AppropriationRecoveries, parse_appropriation_recoveries

SOURCE_TYPE = "appropriation_accounts"

# Official PDFs, checked 2026-11-22 (see tests/fixtures/appropriation_accounts/SOURCES.md).
KNOWN_DOCUMENTS = {
    "2021-22": "https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2021-22-English-08-12-2022-063aa89a8638765-77820288.pdf",
    "2022-23": "https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2022-23-J-K-English-28-02-2024-066bf1b4e8f88f3-67986467.pdf",
    "2023-24": "https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2023-24-UT-JK-English-28-03-2025-069d791c2d23943-29281571.pdf",
}

# Identify ourselves honestly; no personal details.
USER_AGENT = "JKPublicMoneyFlowTracker/0.1 (open-source public-finance research)"


@dataclass(frozen=True)
class LoadResult:
    financial_year: str
    snapshot_id: int
    sha256: str
    status: str  # "inserted" | "replaced" | "unchanged"
    rows: int  # summary rows
    head_rows: int = 0  # note-table rows from the grant pages


# Every table holding rows derived from one year's document; all are replaced together.
YEAR_TABLES = (
    AppropriationAccountLine,
    AppropriationMajorHead,
    AppropriationSectionBlock,
    AppropriationNote,
    AppropriationHeadLine,
    AppropriationDocumentIssue,
    AppropriationRecovery,
)


def fetch_pdf(url: str, timeout: float = 120.0) -> bytes:
    import httpx

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        raise ValueError(f"{url} did not return a PDF (content-type {response.headers.get('content-type')!r})")
    return content


def load_appropriation_accounts(
    db: Session,
    pdf_bytes: bytes,
    source_url: str,
    snapshot_dir: Path,
    fetched_at: datetime | None = None,
    expected_year: str | None = None,
    partial_details: bool = False,
) -> LoadResult:
    """Parse, snapshot and store one Appropriation Accounts PDF. Commits on success, rolls back on error.

    `partial_details=True` accepts grant pages for only some grants; it exists for test fixtures,
    which are cut down from the full PDFs. Real documents must contain every grant.
    """
    summary = parse_appropriation_summary(io.BytesIO(pdf_bytes))  # raises before anything is written
    year = summary.financial_year
    if expected_year and year != expected_year:
        raise ValueError(f"expected the {expected_year} accounts, but the PDF is for {year}")
    details = parse_appropriation_details(io.BytesIO(pdf_bytes), summary=summary, partial=partial_details)
    recoveries = parse_appropriation_recoveries(io.BytesIO(pdf_bytes), summary=summary)

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    relative_path = Path(SOURCE_TYPE) / f"{sha256}.pdf"
    target = snapshot_dir / relative_path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        tmp.write_bytes(pdf_bytes)
        tmp.replace(target)

    try:
        snapshot = db.execute(select(SourceSnapshot).where(SourceSnapshot.sha256 == sha256)).scalar_one_or_none()
        if snapshot is None:
            snapshot = SourceSnapshot(
                source_type=SOURCE_TYPE,
                title=f"Appropriation Accounts {year}, Union Territory of Jammu and Kashmir",
                source_url=source_url,
                sha256=sha256,
                storage_path=relative_path.as_posix(),
                content_type="application/pdf",
                byte_size=len(pdf_bytes),
                fetched_at=fetched_at or datetime.now(timezone.utc),
            )
            db.add(snapshot)
            db.flush()

        # Per table, which snapshots this year's rows come from. A table that should have rows but has
        # none (e.g. a database loaded before the grant-page tables existed) forces a reload.
        existing = {
            table: set(db.execute(select(table.snapshot_id).where(table.financial_year == year)).scalars())
            for table in YEAR_TABLES
        }
        expected_tables = {
            AppropriationAccountLine,
            AppropriationMajorHead,
            AppropriationSectionBlock,
            AppropriationRecovery,
        }
        if details.notes:
            expected_tables.add(AppropriationNote)
        if details.heads:
            expected_tables.add(AppropriationHeadLine)
        if all(existing[t] == {snapshot.id} for t in expected_tables) and all(
            existing[t] <= {snapshot.id} for t in YEAR_TABLES
        ):
            db.commit()
            return LoadResult(year, snapshot.id, sha256, "unchanged", len(summary.lines), len(details.heads))

        status = "replaced" if existing[AppropriationAccountLine] else "inserted"
        for table in YEAR_TABLES:
            db.execute(delete(table).where(table.financial_year == year))
        db.add_all(
            AppropriationAccountLine(
                snapshot_id=snapshot.id,
                financial_year=year,
                grant_no=line.grant_no,
                grant_name_raw=line.grant_name,
                section=line.section,
                kind=line.kind,
                final_grant_thousand=line.grant_amount,
                gross_expenditure_thousand=line.expenditure,
                saving_thousand=line.saving,
                excess_thousand=line.excess,
                page=line.page,
            )
            for line in summary.lines
        )
        db.add_all(_detail_rows(details, snapshot.id))
        db.add_all(_recovery_rows(recoveries, snapshot.id))
        db.commit()
        return LoadResult(year, snapshot.id, sha256, status, len(summary.lines), len(details.heads))
    except Exception:
        db.rollback()
        raise


def _recovery_rows(recoveries: AppropriationRecoveries, snapshot_id: int) -> list[AppropriationRecovery]:
    return [
        AppropriationRecovery(
            snapshot_id=snapshot_id,
            financial_year=recoveries.financial_year,
            grant_no=line.grant_no,
            grant_name_raw=line.grant_name,
            section=line.section,
            budget_estimate_thousand=line.budget_estimate,
            actual_thousand=line.actual,
            page=line.page,
            actuals_page=line.actuals_page,
        )
        for line in recoveries.lines
    ]


def _detail_rows(details: AppropriationDetails, snapshot_id: int) -> list:
    year = details.financial_year
    rows: list = [
        AppropriationMajorHead(
            snapshot_id=snapshot_id,
            financial_year=year,
            grant_no=m.grant_no,
            section=m.section,
            code=m.code,
            name=m.name,
            page=m.page,
        )
        for m in details.major_heads
    ]
    rows += [
        AppropriationSectionBlock(
            snapshot_id=snapshot_id,
            financial_year=year,
            grant_no=t.grant_no,
            section=t.section,
            kind=t.kind,
            original_thousand=t.original,
            supplementary_thousand=t.supplementary,
            reappropriation_thousand=t.reappropriation,
            final_grant_thousand=t.final_grant,
            expenditure_thousand=t.expenditure,
            saving_thousand=t.saving,
            excess_thousand=t.excess,
            surrendered_thousand=t.surrendered,
            page=t.page,
        )
        for t in details.section_totals
    ]
    rows += [
        AppropriationNote(
            snapshot_id=snapshot_id,
            financial_year=year,
            grant_no=n.grant_no,
            section=n.section,
            kind=n.kind,
            number=n.number,
            text=n.text,
            category=n.category,
            reasons_not_communicated=n.reasons_not_communicated,
            page=n.page,
        )
        for n in details.notes
    ]
    rows += [
        AppropriationHeadLine(
            snapshot_id=snapshot_id,
            financial_year=year,
            grant_no=h.grant_no,
            section=h.section,
            kind=h.kind,
            note_number=h.note_number,
            category=h.category,
            reasons_not_communicated=h.reasons_not_communicated,
            head_code=h.head_code,
            major_head_code=h.path[0].code,
            head_name=h.head_name,
            head_path=[{"level": p.level, "code": p.code, "name": p.name} for p in h.path],
            original_thousand=h.original,
            supplementary_thousand=h.supplementary,
            reappropriation_thousand=h.reappropriation,
            final_grant_thousand=h.final_grant,
            expenditure_thousand=h.expenditure,
            saving_thousand=h.saving,
            excess_thousand=h.excess,
            remark=h.remark,
            printed_error=h.printed_error,
            page=h.page,
        )
        for h in details.heads
    ]
    for kind, texts in (
        ("skipped_table", details.skipped_tables),
        ("misfiled", details.misfiled),
        ("footnote", details.footnotes),
        ("headerless_table", details.headerless_tables),
    ):
        rows += [
            AppropriationDocumentIssue(snapshot_id=snapshot_id, financial_year=year, kind=kind, text=text)
            for text in texts
        ]
    return rows


def _main(argv: list[str] | None = None) -> int:
    import argparse

    from loguru import logger

    from config import get_settings
    from database.connection import SyncSessionLocal, sync_engine
    from database.models import Base

    parser = argparse.ArgumentParser(description="Load J&K Appropriation Accounts PDFs into the database.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="load every year in KNOWN_DOCUMENTS")
    group.add_argument("--year", choices=sorted(KNOWN_DOCUMENTS))
    group.add_argument("--file", type=Path, help="a local copy of the PDF (also pass --url)")
    parser.add_argument("--url", help="where --file was downloaded from (stored as its source)")
    args = parser.parse_args(argv)

    if args.file and not args.url:
        parser.error("--file needs --url, so the stored rows can be traced to their source")

    Base.metadata.create_all(sync_engine)  # creates only missing tables
    snapshot_dir = Path(get_settings().raw_snapshot_dir)

    jobs: list[tuple[str | None, str, bytes | None]] = []
    if args.file:
        jobs.append((None, args.url, args.file.read_bytes()))
    else:
        years = sorted(KNOWN_DOCUMENTS) if args.all else [args.year]
        jobs.extend((year, KNOWN_DOCUMENTS[year], None) for year in years)

    failures = 0
    for year, url, content in jobs:
        try:
            pdf_bytes = content if content is not None else fetch_pdf(url)
            with SyncSessionLocal() as db:
                result = load_appropriation_accounts(db, pdf_bytes, url, snapshot_dir, expected_year=year)
            logger.info(
                f"{result.financial_year}: {result.status}, {result.rows} summary rows, "
                f"{result.head_rows} head rows, sha256 {result.sha256[:12]}"
            )
        except Exception as exc:  # report every year, then exit non-zero
            failures += 1
            logger.error(f"{year or url}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
