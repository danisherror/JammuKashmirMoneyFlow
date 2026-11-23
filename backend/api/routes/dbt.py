"""
DBT API Routes
GET /api/v1/dbt/schemes
GET /api/v1/dbt/schemes/{id}/gap
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from database.connection import get_db
from database.models import DBTTransfer, Scheme, District
from api.schemas import DBTSchemeSummary, DBTDistrictGap
from processors.gap_calculator import last_mile_gap_pct
from api.provenance import load_snapshots, snapshot_source

router = APIRouter(prefix="/dbt", tags=["DBT"])


@router.get("/schemes", response_model=list[DBTSchemeSummary])
async def list_dbt_schemes(
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate DBT data per scheme (sum across all districts)."""
    # First, subquery to get the latest snapshot date per scheme-district combo
    latest_subq = (
        select(
            DBTTransfer.scheme_id,
            DBTTransfer.district_id,
            func.max(DBTTransfer.snapshot_date).label("latest"),
        )
        .where(DBTTransfer.financial_year == financial_year)
        .group_by(DBTTransfer.scheme_id, DBTTransfer.district_id)
        .subquery()
    )

    # Now aggregate across districts for the latest snapshot
    query = (
        select(
            Scheme.id,
            Scheme.name,
            Scheme.code,
            func.sum(DBTTransfer.beneficiaries_enrolled).label("total_enrolled"),
            func.sum(DBTTransfer.beneficiaries_paid).label("total_paid"),
            func.sum(DBTTransfer.amount_transferred).label("total_amount"),
            func.max(DBTTransfer.snapshot_id).label("snapshot_id"),
            func.count(DBTTransfer.snapshot_id.distinct()).label("snapshot_count"),
        )
        .join(latest_subq, (DBTTransfer.scheme_id == latest_subq.c.scheme_id) & (DBTTransfer.district_id == latest_subq.c.district_id) & (DBTTransfer.snapshot_date == latest_subq.c.latest))
        .join(Scheme, DBTTransfer.scheme_id == Scheme.id)
        .group_by(Scheme.id, Scheme.name, Scheme.code)
    )

    rows = (await db.execute(query)).all()
    snapshots = await load_snapshots(db, (r.snapshot_id for r in rows))
    results = []

    # SUM skips NULLs and is NULL when every district's figure is unknown: unknown stays null, not 0.
    for r in rows:
        enrolled = to_int(r.total_enrolled)
        paid = to_int(r.total_paid)
        results.append(DBTSchemeSummary(
            scheme_id=r.id,
            scheme_name=r.name,
            scheme_code=r.code,
            financial_year=financial_year,
            total_beneficiaries_enrolled=enrolled,
            total_beneficiaries_paid=paid,
            total_amount_transferred_lakhs=to_int(r.total_amount),
            overall_gap_pct=last_mile_gap_pct(enrolled, paid),
            source=snapshot_source(snapshots.get(r.snapshot_id), combined=r.snapshot_count),
        ))

    # Most enrolled first; unknown enrolment last.
    return sorted(
        results,
        key=lambda x: (x.total_beneficiaries_enrolled is not None, x.total_beneficiaries_enrolled or 0),
        reverse=True,
    )


@router.get("/schemes/{scheme_id}/gap", response_model=list[DBTDistrictGap])
async def dbt_scheme_gap(
    scheme_id: int,
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Get district-wise last-mile gap for a specific DBT scheme."""
    # Subquery for latest snapshot
    latest_subq = (
        select(
            DBTTransfer.district_id,
            func.max(DBTTransfer.snapshot_date).label("latest"),
        )
        .where(
            DBTTransfer.scheme_id == scheme_id,
            DBTTransfer.financial_year == financial_year
        )
        .group_by(DBTTransfer.district_id)
        .subquery()
    )

    query = (
        select(DBTTransfer, District)
        .options(selectinload(DBTTransfer.snapshot))
        .join(latest_subq, (DBTTransfer.district_id == latest_subq.c.district_id) & (DBTTransfer.snapshot_date == latest_subq.c.latest))
        .join(District, DBTTransfer.district_id == District.id)
        .where(
            DBTTransfer.scheme_id == scheme_id,
            DBTTransfer.financial_year == financial_year
        )
        .order_by(DBTTransfer.last_mile_gap_pct.is_(None), desc(DBTTransfer.last_mile_gap_pct))
    )

    rows = (await db.execute(query)).all()

    return [
        DBTDistrictGap(
            district_id=district.id,
            district_name=district.name,
            district_code=district.code,
            beneficiaries_enrolled=dbt.beneficiaries_enrolled,
            beneficiaries_paid=dbt.beneficiaries_paid,
            amount_transferred_lakhs=dbt.amount_transferred,
            last_mile_gap_pct=round(dbt.last_mile_gap_pct, 2) if dbt.last_mile_gap_pct is not None else None,
            source=snapshot_source(dbt.snapshot),
        )
        for dbt, district in rows
    ]


def to_int(value) -> int | None:
    return int(value) if value is not None else None
