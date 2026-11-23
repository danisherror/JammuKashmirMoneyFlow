"""
Gap Calculator Processor
Runs after each collector to compute utilization gaps across all schemes/departments.
These computed fields drive the dashboard's "money gap" analysis.
"""
from datetime import date
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import (
    SchemeProgress, DBTTransfer
)
from processors.data_cleaner import percent


def recalculate_all_gaps(db: Session, financial_year: str = "2024-25"):
    """
    Master function called by scheduler after collectors run.
    Recomputes all utilization percentages and gap flags.
    """
    logger.info("[gap_calculator] Starting gap recalculation...")
    _recalculate_scheme_gaps(db, financial_year)
    _recalculate_dbt_gaps(db, financial_year)
    _flag_low_utilization(db, financial_year)
    db.commit()
    logger.info("[gap_calculator] Gap recalculation complete.")


def _recalculate_scheme_gaps(db: Session, financial_year: str):
    """
    For each SchemeProgress record, recompute utilization_pct, release_pct,
    physical_pct from raw figures.
    """
    records = db.execute(
        select(SchemeProgress).where(
            SchemeProgress.financial_year == financial_year,
            SchemeProgress.funds_allocated > 0,
        )
    ).scalars().all()

    # An unknown (NULL) figure gives an unknown percentage, never 0% (todo.md 1.3).
    updated = 0
    for record in records:
        record.utilization_pct = percent(record.funds_utilized, record.funds_allocated)
        record.release_pct = percent(record.funds_released, record.funds_allocated)
        record.physical_pct = percent(record.achieved_physical, record.target_physical)
        updated += 1

    logger.info(f"[gap_calculator] Recalculated gaps for {updated} scheme progress records")


def _recalculate_dbt_gaps(db: Session, financial_year: str):
    """Recalculate last_mile_gap_pct for DBT transfers."""
    records = db.execute(
        select(DBTTransfer).where(
            DBTTransfer.financial_year == financial_year,
            DBTTransfer.beneficiaries_enrolled > 0,
        )
    ).scalars().all()

    for record in records:
        record.last_mile_gap_pct = last_mile_gap_pct(record.beneficiaries_enrolled, record.beneficiaries_paid)


def last_mile_gap_pct(enrolled: int | None, paid: int | None) -> float | None:
    """(enrolled − paid) / enrolled × 100; None when either count is unknown or nobody is enrolled."""
    if enrolled is None or paid is None or enrolled <= 0:
        return None
    return round((enrolled - paid) / enrolled * 100, 2)


def _flag_low_utilization(db: Session, financial_year: str):
    """
    Identify schemes with <40% utilization in the second half of FY.
    These are candidates for budget cuts or investigation.
    Log them for the alerts API.
    """
    today = date.today()
    # Indian FY: April=month 1, March=month 12
    # Q3 = October (month 7) onwards
    current_month = (today.month - 3) % 12 or 12   # convert to FY month

    if current_month < 7:
        # Before Q3, low utilization is expected — don't flag
        return

    low_util = db.execute(
        select(SchemeProgress).where(
            SchemeProgress.financial_year == financial_year,
            SchemeProgress.utilization_pct < 40,
            SchemeProgress.funds_allocated > 10000,     # only flag if >₹100 Cr allocated
            SchemeProgress.snapshot_date == date.today(),
        )
    ).scalars().all()

    if low_util:
        logger.warning(
            f"[gap_calculator] {len(low_util)} scheme-district combinations "
            f"have <40% utilization in Q{current_month // 3 + 1} of FY{financial_year}. "
            f"These will appear in /alerts/low-utilization endpoint."
        )
