"""
Scheme routes — MGNREGA, JJM, PMAY, etc.
GET /api/v1/schemes
GET /api/v1/schemes/{id}
GET /api/v1/schemes/{id}/districts
GET /api/v1/schemes/category/{type}
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from database.connection import get_db
from database.models import Scheme, SchemeProgress, District, Department
from api.schemas import SchemeSummary, SchemeDetail, SchemeDistrictProgress

router = APIRouter(prefix="/schemes", tags=["Schemes"])


@router.get("", response_model=list[SchemeSummary])
async def list_schemes(
    financial_year: str = Query("2024-25"),
    scheme_type: str | None = Query(None, description="css | central | ut"),
    department_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """All schemes with their aggregate financial progress."""
    query = select(Scheme, Department).join(Department)
    if scheme_type:
        query = query.where(Scheme.scheme_type == scheme_type)
    if department_id:
        query = query.where(Scheme.department_id == department_id)
    query = query.where(Scheme.is_active == True)

    rows = (await db.execute(query)).all()
    results = []

    for scheme, dept in rows:
        # Aggregate progress across all districts for latest snapshot
        agg = await db.execute(
            select(
                func.sum(SchemeProgress.funds_allocated).label("allocated"),
                func.sum(SchemeProgress.funds_utilized).label("utilized"),
                func.avg(SchemeProgress.physical_pct).label("avg_physical"),
                func.max(SchemeProgress.snapshot_date).label("latest_date"),
            ).where(
                SchemeProgress.scheme_id == scheme.id,
                SchemeProgress.financial_year == financial_year,
            )
        )
        row = agg.one()

        allocated = row.allocated or 0
        utilized = row.utilized or 0
        util_pct = round((utilized / allocated * 100), 2) if allocated > 0 else None

        results.append(SchemeSummary(
            id=scheme.id,
            name=scheme.name,
            code=scheme.code,
            scheme_type=scheme.scheme_type,
            department_name=dept.name,
            total_outlay_lakhs=scheme.total_outlay,
            funds_allocated_lakhs=allocated,
            funds_utilized_lakhs=utilized,
            utilization_pct=util_pct,
            physical_pct=round(row.avg_physical, 2) if row.avg_physical else None,
            last_updated=row.latest_date,
        ))

    results.sort(key=lambda x: x.total_outlay_lakhs or 0, reverse=True)
    return results


@router.get("/{scheme_id}", response_model=SchemeDetail)
async def get_scheme_detail(
    scheme_id: int,
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Full scheme detail with district-wise breakdown."""
    result = await db.execute(
        select(Scheme, Department)
        .join(Department)
        .where(Scheme.id == scheme_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Scheme not found")

    scheme, dept = row

    # Get latest snapshot date for this scheme
    latest_date_result = await db.execute(
        select(func.max(SchemeProgress.snapshot_date)).where(
            SchemeProgress.scheme_id == scheme_id,
            SchemeProgress.financial_year == financial_year,
        )
    )
    latest_date = latest_date_result.scalar()

    # District-wise progress for latest snapshot
    district_rows = (await db.execute(
        select(SchemeProgress, District)
        .join(District, SchemeProgress.district_id == District.id)
        .where(
            SchemeProgress.scheme_id == scheme_id,
            SchemeProgress.financial_year == financial_year,
            SchemeProgress.snapshot_date == latest_date,
        )
        .order_by(SchemeProgress.utilization_pct.desc())
    )).all()

    district_progress = [
        SchemeDistrictProgress(
            district_id=district.id,
            district_name=district.name,
            district_code=district.code,
            division=district.division,
            target_physical=sp.target_physical,
            achieved_physical=sp.achieved_physical,
            physical_unit=sp.physical_unit,
            physical_pct=sp.physical_pct,
            funds_allocated_lakhs=sp.funds_allocated,
            funds_released_lakhs=sp.funds_released,
            funds_utilized_lakhs=sp.funds_utilized,
            utilization_pct=sp.utilization_pct,
            release_pct=sp.release_pct,
            snapshot_date=sp.snapshot_date,
        )
        for sp, district in district_rows
    ]

    total_allocated = sum(d.funds_allocated_lakhs or 0 for d in district_progress)
    total_utilized = sum(d.funds_utilized_lakhs or 0 for d in district_progress)
    avg_physical = (
        sum(d.physical_pct or 0 for d in district_progress) / len(district_progress)
        if district_progress else None
    )

    return SchemeDetail(
        id=scheme.id,
        name=scheme.name,
        code=scheme.code,
        scheme_type=scheme.scheme_type,
        department_name=dept.name,
        total_outlay_lakhs=scheme.total_outlay,
        funds_allocated_lakhs=total_allocated,
        funds_utilized_lakhs=total_utilized,
        utilization_pct=round((total_utilized / total_allocated * 100), 2) if total_allocated else None,
        physical_pct=round(avg_physical, 2) if avg_physical else None,
        last_updated=latest_date,
        description=scheme.description,
        start_year=scheme.start_year,
        end_year=scheme.end_year,
        source_url=scheme.source_url,
        district_progress=district_progress,
    )
