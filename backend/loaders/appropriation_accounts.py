"""
Load the J&K Appropriation Accounts (CAG) into `appropriation_account_lines`.

Steps, all-or-nothing per document:
  1. download the PDF (or read a local copy),
  2. parse and validate it (parsers.appropriation_accounts) — a document that fails is never stored,
  3. save the bytes to <raw_snapshot_dir>/appropriation_accounts/<sha256>.pdf,
  4. in one transaction, record the snapshot and replace that year's rows.

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

from database.models import AppropriationAccountLine, SourceSnapshot
from parsers.appropriation_accounts import parse_appropriation_summary

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
    rows: int


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
) -> LoadResult:
    """Parse, snapshot and store one Appropriation Accounts PDF. Commits on success, rolls back on error."""
    summary = parse_appropriation_summary(io.BytesIO(pdf_bytes))  # raises before anything is written
    year = summary.financial_year
    if expected_year and year != expected_year:
        raise ValueError(f"expected the {expected_year} accounts, but the PDF is for {year}")

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

        existing_snapshots = set(
            db.execute(
                select(AppropriationAccountLine.snapshot_id).where(AppropriationAccountLine.financial_year == year)
            ).scalars()
        )
        if existing_snapshots == {snapshot.id}:
            db.commit()
            return LoadResult(year, snapshot.id, sha256, "unchanged", len(summary.lines))

        status = "replaced" if existing_snapshots else "inserted"
        db.execute(delete(AppropriationAccountLine).where(AppropriationAccountLine.financial_year == year))
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
        db.commit()
        return LoadResult(year, snapshot.id, sha256, status, len(summary.lines))
    except Exception:
        db.rollback()
        raise


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
            logger.info(f"{result.financial_year}: {result.status}, {result.rows} rows, sha256 {result.sha256[:12]}")
        except Exception as exc:  # report every year, then exit non-zero
            failures += 1
            logger.error(f"{year or url}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
