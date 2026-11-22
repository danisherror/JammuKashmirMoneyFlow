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

    updated = 0
    for record in records:
        alloc = record.funds_allocated or 0
        released = record.funds_released or 0
        utilized = record.funds_utilized or 0
        target = record.target_physical or 0
        achieved = record.achieved_physical or 0

        if alloc > 0:
            record.utilization_pct = round((utilized / alloc) * 100, 2)
            record.release_pct = round((released / alloc) * 100, 2)
        if target > 0:
            record.physical_pct = round((achieved / target) * 100, 2)

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
        enrolled = record.beneficiaries_enrolled or 0
        paid = record.beneficiaries_paid or 0
        if enrolled > 0:
            gap = ((enrolled - paid) / enrolled) * 100
            record.last_mile_gap_pct = round(gap, 2)


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
