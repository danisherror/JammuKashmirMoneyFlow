"""
Tenders API Routes
GET /api/v1/tenders
GET /api/v1/tenders/contractors
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from database.connection import get_db
from database.models import Tender
from api.provenance import load_snapshots, snapshot_source
from api.schemas import TenderSummary, ContractorLeaderboardItem

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.get("", response_model=list[TenderSummary])
async def list_tenders(
    limit: int | None = Query(None),
    department_id: int | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get recent tenders, optionally filtered by department or status."""
    query = select(Tender).options(selectinload(Tender.snapshot)).order_by(desc(Tender.published_date))
    
    if department_id:
        query = query.where(Tender.department_id == department_id)
    if status:
        query = query.where(Tender.status == status)
        
    if limit:
        query = query.limit(limit)
    rows = (await db.execute(query)).scalars().all()
    
    return [
        TenderSummary(
            id=t.id,
            tender_ref=t.tender_ref,
            title=t.title,
            department_name=t.department_name_raw or "Unknown",
            estimated_cost_lakhs=t.estimated_cost,
            awarded_cost_lakhs=t.awarded_cost,
            contractor_name=t.contractor_name,
            status=t.status,
            published_date=t.published_date,
            award_date=t.award_date,
            source=snapshot_source(t.snapshot),
        )
        for t in rows
    ]


@router.get("/contractors", response_model=list[ContractorLeaderboardItem])
async def contractor_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the top contractors by total awarded value."""
    # Group by contractor_name, count won tenders, sum awarded_cost
    query = (
        select(
            Tender.contractor_name,
            func.count(Tender.id).label("tenders_won"),
            func.sum(Tender.awarded_cost).label("total_awarded"),
            func.max(Tender.snapshot_id).label("snapshot_id"),
            func.count(Tender.snapshot_id.distinct()).label("snapshot_count"),
        )
        .where(Tender.status == "awarded")
        .where(Tender.contractor_name.isnot(None))
        .group_by(Tender.contractor_name)
        .order_by(func.sum(Tender.awarded_cost).is_(None), desc("total_awarded"))
        .limit(limit)
    )
    
    rows = (await db.execute(query)).all()
    snapshots = await load_snapshots(db, (row.snapshot_id for row in rows))

    return [
        ContractorLeaderboardItem(
            contractor_name=row.contractor_name,
            total_tenders_won=row.tenders_won,
            total_awarded_lakhs=int(row.total_awarded) if row.total_awarded is not None else None,
            source=snapshot_source(snapshots.get(row.snapshot_id), combined=row.snapshot_count),
        )
        for row in rows
    ]
