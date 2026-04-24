"""
District routes — per-district fund absorption analysis.
GET /api/v1/districts
GET /api/v1/districts/heatmap
GET /api/v1/districts/{id}
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.connection import get_db
from database.models import District, SchemeProgress
from api.schemas import DistrictHeatmapItem, DistrictDetail

router = APIRouter(prefix="/districts", tags=["Districts"])


def _absorption_grade(score: float) -> str:
    if score >= 80: return "A"
    if score >= 60: return "B"
    if score >= 40: return "C"
    if score >= 20: return "D"
    return "F"


@router.get("/heatmap", response_model=list[DistrictHeatmapItem])
async def get_district_heatmap(
    financial_year: str = Query("2024-25"),
    scheme_code: str | None = Query(None, description="Filter by specific scheme"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all 20 districts with aggregated fund absorption scores.
    Fixed: was N+1 queries (1 per district); now 2 queries total.
    """
    districts = (await db.execute(select(District))).scalars().all()

    # ── Single aggregation query for all districts ────────────────────────────
    agg_query = select(
        SchemeProgress.district_id,
        func.avg(SchemeProgress.utilization_pct).label("avg_util"),
        func.sum(SchemeProgress.funds_allocated).label("total_alloc"),
        func.sum(SchemeProgress.funds_utilized).label("total_util"),
        func.count(SchemeProgress.scheme_id.distinct()).label("scheme_count"),
    ).where(
        SchemeProgress.financial_year == financial_year,
    ).group_by(SchemeProgress.district_id)

    if scheme_code:
        from database.models import Scheme
        scheme_sq = select(Scheme.id).where(Scheme.code == scheme_code).scalar_subquery()
        agg_query = agg_query.where(SchemeProgress.scheme_id == scheme_sq)

    agg_rows = (await db.execute(agg_query)).all()
    agg_map = {row.district_id: row for row in agg_rows}

    results = []
    for district in districts:
        agg = agg_map.get(district.id)
        avg_util = round(agg.avg_util or 0, 2) if agg else 0.0

        results.append(DistrictHeatmapItem(
            id=district.id,
            name=district.name,
            code=district.code,
            division=district.division,
            population=district.population,
            is_border_district=district.is_border_district,
            avg_utilization_pct=avg_util,
            total_funds_allocated_lakhs=int(agg.total_alloc or 0) if agg else 0,
            total_funds_utilized_lakhs=int(agg.total_util or 0) if agg else 0,
            active_schemes_count=int(agg.scheme_count or 0) if agg else 0,
            absorption_score=avg_util,
            absorption_grade=_absorption_grade(avg_util),
        ))

    results.sort(key=lambda x: x.absorption_score or 0, reverse=True)
    return results


@router.get("/{district_id}", response_model=DistrictDetail)
async def get_district_detail(
    district_id: int,
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """Full district detail: all scheme progress in that district."""
    district = await db.get(District, district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    from database.models import Scheme, Department
    from api.schemas import SchemeDistrictProgress

    # Use a subquery to find the latest snapshot date for each scheme in this district
    subq = (
        select(
            SchemeProgress.scheme_id,
            func.max(SchemeProgress.snapshot_date).label("latest")
        )
        .where(
            SchemeProgress.district_id == district_id,
            SchemeProgress.financial_year == financial_year,
        )
        .group_by(SchemeProgress.scheme_id)
        .subquery()
    )

    # Join the subquery with SchemeProgress and Scheme to get the full row
    sp_rows = (await db.execute(
        select(SchemeProgress, Scheme)
        .join(Scheme, SchemeProgress.scheme_id == Scheme.id)
        .join(
            subq,
            (SchemeProgress.scheme_id == subq.c.scheme_id) &
            (SchemeProgress.snapshot_date == subq.c.latest)
        )
        .where(
            SchemeProgress.district_id == district_id,
            SchemeProgress.financial_year == financial_year,
        )
    )).all()

    scheme_progress_list = []
    for progress, scheme in sp_rows:
            scheme_progress_list.append(SchemeDistrictProgress(
                district_id=district.id,
                district_name=district.name,
                district_code=district.code,
                division=district.division,
                target_physical=progress.target_physical,
                achieved_physical=progress.achieved_physical,
                physical_unit=progress.physical_unit,
                physical_pct=progress.physical_pct,
                funds_allocated_lakhs=progress.funds_allocated,
                funds_released_lakhs=progress.funds_released,
                funds_utilized_lakhs=progress.funds_utilized,
                utilization_pct=progress.utilization_pct,
                release_pct=progress.release_pct,
                snapshot_date=progress.snapshot_date,
                scheme_name=scheme.name,
                scheme_code=scheme.code,
            ))

    total_allocated = sum(s.funds_allocated_lakhs or 0 for s in scheme_progress_list)
    total_utilized = sum(s.funds_utilized_lakhs or 0 for s in scheme_progress_list)
    avg_util = (
        sum(s.utilization_pct or 0 for s in scheme_progress_list) / len(scheme_progress_list)
        if scheme_progress_list else 0
    )

    return DistrictDetail(
        id=district.id,
        name=district.name,
        code=district.code,
        division=district.division,
        population=district.population,
        is_border_district=district.is_border_district,
        avg_utilization_pct=round(avg_util, 2),
        total_funds_allocated_lakhs=total_allocated,
        total_funds_utilized_lakhs=total_utilized,
        active_schemes_count=len(scheme_progress_list),
        absorption_score=round(avg_util, 2),
        absorption_grade=_absorption_grade(avg_util),
        scheme_progress=scheme_progress_list,
    )
