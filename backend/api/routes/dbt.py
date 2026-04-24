"""
DBT API Routes
GET /api/v1/dbt/schemes
GET /api/v1/dbt/schemes/{id}/gap
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from database.connection import get_db
from database.models import DBTTransfer, Scheme, District
from api.schemas import DBTSchemeSummary, DBTDistrictGap

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
        )
        .join(latest_subq, (DBTTransfer.scheme_id == latest_subq.c.scheme_id) & (DBTTransfer.district_id == latest_subq.c.district_id) & (DBTTransfer.snapshot_date == latest_subq.c.latest))
        .join(Scheme, DBTTransfer.scheme_id == Scheme.id)
        .group_by(Scheme.id, Scheme.name, Scheme.code)
    )

    rows = (await db.execute(query)).all()
    results = []

    for r in rows:
        enrolled = r.total_enrolled or 0
        paid = r.total_paid or 0
        gap_pct = ((enrolled - paid) / enrolled * 100) if enrolled > 0 else 0.0

        results.append(DBTSchemeSummary(
            scheme_id=r.id,
            scheme_name=r.name,
            scheme_code=r.code,
            financial_year=financial_year,
            total_beneficiaries_enrolled=enrolled,
            total_beneficiaries_paid=paid,
            total_amount_transferred_lakhs=int(r.total_amount or 0),
            overall_gap_pct=round(gap_pct, 2),
        ))

    return sorted(results, key=lambda x: x.total_beneficiaries_enrolled, reverse=True)


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
        .join(latest_subq, (DBTTransfer.district_id == latest_subq.c.district_id) & (DBTTransfer.snapshot_date == latest_subq.c.latest))
        .join(District, DBTTransfer.district_id == District.id)
        .where(
            DBTTransfer.scheme_id == scheme_id,
            DBTTransfer.financial_year == financial_year
        )
        .order_by(desc(DBTTransfer.last_mile_gap_pct))
    )

    rows = (await db.execute(query)).all()

    return [
        DBTDistrictGap(
            district_id=district.id,
            district_name=district.name,
            district_code=district.code,
            beneficiaries_enrolled=dbt.beneficiaries_enrolled or 0,
            beneficiaries_paid=dbt.beneficiaries_paid or 0,
            amount_transferred_lakhs=dbt.amount_transferred or 0,
            last_mile_gap_pct=round(dbt.last_mile_gap_pct or 0.0, 2),
        )
        for dbt, district in rows
    ]
