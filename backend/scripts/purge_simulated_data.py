"""
One-off cleanup: delete rows the old random-data fallbacks saved as if real.

Until commit 64c776b, six collectors invented figures when their (never
implemented) live path failed. This removes what they left behind:

| Table              | Written by                | How it is recognised                               |
|--------------------|---------------------------|----------------------------------------------------|
| scheme_progress    | pmay_collector            | source contains "simulated", or raw_data.note ==   |
|                    |                           | "simulated fallback" -> row deleted                |
| scheme_progress    | pfms_collector            | overwrote funds_released on existing rows ->       |
|                    |                           | funds_released and release_pct set to NULL (below) |
| dbt_transfers      | dbt_collector             | source contains "simulated"                        |
| expenditures       | cga_collector             | source contains "simulation"                       |
| tenders            | tenders_collector         | tender_ref "NIT/<dept>/<year>/<4 digits>" from     |
|                    |                           | jktenders.gov.in/nicgep/app                        |
| cag_findings       | cag_collector             | the five invented MOCK_FINDINGS paragraphs         |
| data_sync_log      | the six collectors above  | old "success" runs relabelled "failed", since they |
|                    |                           | saved simulated data, not real data                |

PFMS: the collector set raw_data["pfms_note"] = "simulated fallback", but it
mutated the JSON dict in place, which SQLAlchemy doesn't track unless the
column was empty before, so the marker is unreliable. If PFMS ever logged
updated rows, funds_released/release_pct are cleared on every central or
centrally sponsored scheme row dated on or before its last such run. Re-running
the JJM/MGNREGA collectors restores any real value that was overwritten.

Dry run by default; pass --apply to delete.

    docker compose exec api python -m scripts.purge_simulated_data           # counts only
    docker compose exec api python -m scripts.purge_simulated_data --apply
"""
import argparse
import re
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import (
    CAGFinding,
    CollectorStatus,
    DataSyncLog,
    DBTTransfer,
    Expenditure,
    Scheme,
    SchemeProgress,
    SchemeType,
    Tender,
)

SIMULATED_COLLECTORS = (
    "pmay_collector",
    "pfms_collector",
    "tenders_collector",
    "dbt_collector",
    "cga_collector",
    "cag_collector",
)

FAKE_TENDERS_URL = "https://jktenders.gov.in/nicgep/app"
FAKE_TENDER_REF = re.compile(r"^NIT/[A-Z0-9_&-]+/\d{4}/\d{4}$")

FAKE_CAG_PDF_URL = "https://cag.gov.in/en/audit-report?tags=Jammu+%26+Kashmir"
FAKE_CAG_TITLE = "Report of the CAG on General & Social Sector — Government of J&K 2023-24"
FAKE_CAG_PARAS = {"Para 3.2", "Para 5.1", "Para 6.3", "Para 4.7", "Para 7.2"}


def _is_simulated_note(raw_data) -> bool:
    return isinstance(raw_data, dict) and raw_data.get("note") == "simulated fallback"


def purge(db: Session, apply: bool = False, today: date | None = None) -> dict[str, int]:
    """Delete (or with apply=False, count) simulated rows. Returns counts per action."""
    counts: dict[str, int] = {}

    # scheme_progress rows invented by PMAY
    progress_rows = db.execute(select(SchemeProgress)).scalars().all()
    fake_progress = [
        r for r in progress_rows
        if (r.source and "simulat" in r.source.lower()) or _is_simulated_note(r.raw_data)
    ]
    counts["scheme_progress deleted"] = len(fake_progress)

    # funds_released overwritten by PFMS
    last_pfms_update = db.execute(
        select(func.max(DataSyncLog.started_at)).where(
            DataSyncLog.collector_name == "pfms_collector",
            DataSyncLog.records_updated > 0,
        )
    ).scalar()
    fake_ids = {r.id for r in fake_progress}
    pfms_rows = [
        r for r in progress_rows
        if r.id not in fake_ids
        and isinstance(r.raw_data, dict) and "pfms_note" in r.raw_data
    ]
    if last_pfms_update is not None:
        central = select(Scheme.id).where(Scheme.scheme_type.in_([SchemeType.CSS, SchemeType.CENTRAL]))
        cutoff = last_pfms_update.date()
        pfms_rows += [
            r for r in db.execute(
                select(SchemeProgress).where(
                    SchemeProgress.scheme_id.in_(central),
                    SchemeProgress.snapshot_date <= cutoff,
                    SchemeProgress.funds_released.is_not(None),
                )
            ).scalars()
            if r.id not in fake_ids and r not in pfms_rows
        ]
    counts["scheme_progress funds_released cleared"] = len(pfms_rows)

    fake_dbt = db.execute(
        select(DBTTransfer).where(func.lower(DBTTransfer.source).contains("simulat"))
    ).scalars().all()
    counts["dbt_transfers deleted"] = len(fake_dbt)

    fake_exp = db.execute(
        select(Expenditure).where(func.lower(Expenditure.source).contains("simulation"))
    ).scalars().all()
    counts["expenditures deleted"] = len(fake_exp)

    fake_tenders = [
        t for t in db.execute(
            select(Tender).where(or_(Tender.source_url == FAKE_TENDERS_URL, Tender.source_url.is_(None)))
        ).scalars()
        if FAKE_TENDER_REF.match(t.tender_ref or "")
    ]
    counts["tenders deleted"] = len(fake_tenders)

    fake_cag = db.execute(
        select(CAGFinding).where(
            CAGFinding.source_pdf_url == FAKE_CAG_PDF_URL,
            CAGFinding.report_title == FAKE_CAG_TITLE,
            CAGFinding.paragraph_ref.in_(FAKE_CAG_PARAS),
        )
    ).scalars().all()
    counts["cag_findings deleted"] = len(fake_cag)

    old_successes = db.execute(
        select(DataSyncLog).where(
            DataSyncLog.collector_name.in_(SIMULATED_COLLECTORS),
            DataSyncLog.status == CollectorStatus.SUCCESS,
        )
    ).scalars().all()
    counts["data_sync_log runs relabelled failed"] = len(old_successes)

    if not apply:
        db.rollback()
        return counts

    stamp = (today or date.today()).isoformat()
    for row in fake_progress + fake_dbt + fake_exp + fake_tenders + fake_cag:
        db.delete(row)
    for row in pfms_rows:
        row.funds_released = None
        row.release_pct = None
        if isinstance(row.raw_data, dict) and "pfms_note" in row.raw_data:
            row.raw_data = {k: v for k, v in row.raw_data.items() if k != "pfms_note"}
    for log in old_successes:
        log.status = CollectorStatus.FAILED
        log.error_message = (
            f"Saved simulated data, not real data. Rows removed by "
            f"scripts.purge_simulated_data on {stamp}."
        )
    db.commit()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="delete the rows (default: count only)")
    args = parser.parse_args()

    from database.connection import SyncSessionLocal

    with SyncSessionLocal() as db:
        counts = purge(db, apply=args.apply)
    verb = "Done" if args.apply else "Dry run (pass --apply to delete)"
    print(verb)
    for action, n in counts.items():
        print(f"  {action}: {n}")


if __name__ == "__main__":
    main()
