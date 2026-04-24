"""
Alerts routes — sync health, low utilization flags, collector triggers.
GET  /api/v1/alerts/sync-status
GET  /api/v1/alerts/low-utilization
POST /api/v1/alerts/trigger/{collector_name}  (manual run)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone

from database.connection import get_db
from database.models import DataSyncLog, SchemeProgress, Scheme, District, Department, CollectorStatus
from api.schemas import SyncStatusItem, LowUtilizationAlert

router = APIRouter(prefix="/alerts", tags=["Alerts"])

# Map collector name → job function (for manual triggers)
COLLECTOR_MAP = {
    "mgnrega": "scheduler.jobs.run_mgnrega",
    "jjm": "scheduler.jobs.run_jjm",
    "pmay": "scheduler.jobs.run_pmay",
    "dbt": "scheduler.jobs.run_dbt",
    "tenders": "scheduler.jobs.run_tenders",
    "cga": "scheduler.jobs.run_cga",
    "cag": "scheduler.jobs.run_cag_audit",
    "pfms": "scheduler.jobs.run_pfms",
}


@router.get("/sync-status", response_model=list[SyncStatusItem])
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    """
    Health check for all data collectors.
    Shows last run time, status, records updated.
    Drives the SyncStatusPanel on the frontend.
    """
    # Get latest run per collector
    subq = (
        select(
            DataSyncLog.collector_name,
            func.max(DataSyncLog.started_at).label("latest_run"),
        )
        .group_by(DataSyncLog.collector_name)
        .subquery()
    )

    rows = (await db.execute(
        select(DataSyncLog).join(
            subq,
            (DataSyncLog.collector_name == subq.c.collector_name)
            & (DataSyncLog.started_at == subq.c.latest_run),
        )
    )).scalars().all()

    results = []
    for log in rows:
        # Find last successful run
        last_success_result = await db.execute(
            select(func.max(DataSyncLog.finished_at)).where(
                DataSyncLog.collector_name == log.collector_name,
                DataSyncLog.status == CollectorStatus.SUCCESS,
            )
        )
        last_success = last_success_result.scalar()
        is_healthy = log.status == CollectorStatus.SUCCESS

        results.append(SyncStatusItem(
            collector_name=log.collector_name,
            status=log.status,
            last_run=log.started_at,
            last_success=last_success,
            records_last_run=(log.records_inserted or 0) + (log.records_updated or 0),
            next_run="06:00 IST daily",
            is_healthy=is_healthy,
        ))

    return results


@router.get("/low-utilization", response_model=list[LowUtilizationAlert])
async def get_low_utilization_alerts(
    financial_year: str = Query("2024-25"),
    threshold_pct: float = Query(40.0, description="Flag schemes below this utilization %"),
    min_allocation_lakhs: int = Query(5000, description="Only flag if allocation > this"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns scheme-district combinations with dangerously low fund utilization.
    These represent 'dead money' — allocated but not reaching the ground.
    """
    from sqlalchemy import and_
    from datetime import date

    # Get latest snapshot per scheme-district combo
    latest_subq = (
        select(
            SchemeProgress.scheme_id,
            SchemeProgress.district_id,
            func.max(SchemeProgress.snapshot_date).label("latest"),
        )
        .where(SchemeProgress.financial_year == financial_year)
        .group_by(SchemeProgress.scheme_id, SchemeProgress.district_id)
        .subquery()
    )

    rows = (await db.execute(
        select(SchemeProgress, Scheme, District, Department)
        .join(latest_subq, and_(
            SchemeProgress.scheme_id == latest_subq.c.scheme_id,
            SchemeProgress.district_id == latest_subq.c.district_id,
            SchemeProgress.snapshot_date == latest_subq.c.latest,
        ))
        .join(Scheme, SchemeProgress.scheme_id == Scheme.id)
        .join(District, SchemeProgress.district_id == District.id)
        .join(Department, Scheme.department_id == Department.id)
        .where(
            SchemeProgress.financial_year == financial_year,
            SchemeProgress.utilization_pct < threshold_pct,
            SchemeProgress.funds_allocated >= min_allocation_lakhs,
        )
        .order_by(SchemeProgress.utilization_pct.asc())
    )).all()

    results = []
    for sp, scheme, district, dept in rows:
        severity = "critical" if (sp.utilization_pct or 0) < 20 else "warning"
        results.append(LowUtilizationAlert(
            scheme_name=scheme.name,
            scheme_code=scheme.code,
            district_name=district.name,
            department_name=dept.name,
            funds_allocated_lakhs=sp.funds_allocated or 0,
            funds_utilized_lakhs=sp.funds_utilized or 0,
            utilization_pct=sp.utilization_pct or 0,
            severity=severity,
            snapshot_date=sp.snapshot_date,
        ))

    return results


@router.post("/trigger/{collector_name}")
async def trigger_collector(
    collector_name: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a specific collector.
    Useful for testing or forcing a refresh outside the schedule.
    """
    if collector_name not in COLLECTOR_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown collector '{collector_name}'. Valid: {list(COLLECTOR_MAP.keys())}"
        )

    # Import and run in background so API returns immediately
    if collector_name == "mgnrega":
        from scheduler.jobs import run_mgnrega
        background_tasks.add_task(run_mgnrega)
    elif collector_name == "jjm":
        from scheduler.jobs import run_jjm
        background_tasks.add_task(run_jjm)
    elif collector_name == "cga":
        from scheduler.jobs import run_cga
        background_tasks.add_task(run_cga)
    elif collector_name == "cag":
        from scheduler.jobs import run_cag_audit
        background_tasks.add_task(run_cag_audit)
    elif collector_name == "pfms":
        from scheduler.jobs import run_pfms
        background_tasks.add_task(run_pfms)

    return {
        "message": f"Collector '{collector_name}' triggered in background",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/cag-findings")
async def get_cag_findings(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Return CAG audit findings for the feed UI."""
    from database.models import CAGFinding
    from sqlalchemy import desc

    rows = (await db.execute(
        select(CAGFinding)
        .order_by(desc(CAGFinding.report_year), desc(CAGFinding.id))
        .limit(limit)
    )).scalars().all()

    return [
        {
            "id": r.id,
            "report_year": r.report_year,
            "report_title": r.report_title,
            "department_name": r.department_name_raw,
            "finding_summary": r.finding_summary,
            "finding_raw": r.finding_raw,
            "amount_flagged_lakhs": r.amount_flagged,
            "severity": r.severity,
            "paragraph_ref": r.paragraph_ref,
            "source_pdf_url": r.source_pdf_url,
        }
        for r in rows
    ]

