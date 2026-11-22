"""
Scheme routes — MGNREGA, JJM, PMAY, etc.
GET /api/v1/schemes
GET /api/v1/schemes/{id}
GET /api/v1/schemes/{id}/history

Every route takes `?view=live|official|combined`. Scheme figures are live only: the CAG accounts are
by department grant, so there is no official figure per scheme yet (todo.md 2.2a). The official view
therefore returns no figures, and the combined view returns the live ones marked provisional.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date

from database.connection import get_db
from database.models import Scheme, SchemeProgress, District, Department
from api.figures import live_label, to_source
from api.schemas import (
    FigureSource, SchemeSummary, SchemeDetail, SchemeDistrictProgress, SchemeHistoryPoint, SchemeVelocity,
)
from processors.combined_view import Figure, View, resolve

router = APIRouter(prefix="/schemes", tags=["Schemes"])

VIEW_QUERY = Query(View.COMBINED, description="live | official | combined (default)")
OFFICIAL_NOTE = "No official figure per scheme: the CAG accounts are by department grant"
OUTLAY_SOURCE = FigureSource(
    source_type=None,
    label="Reference value from database/seeds.py; no source document recorded yet",
    measure="total_outlay",
)


def scheme_sources(
    view: View,
    financial_year: str,
    scheme: Scheme,
    values: dict[str, tuple[float | None, str]],
    source: str | None,
    updated,
) -> tuple[dict[str, float | None], dict[str, FigureSource]]:
    """Resolve each live scheme figure ({field: (value, measure)}) for `view`; returns values + sources."""
    out_values: dict[str, float | None] = {}
    out_sources: dict[str, FigureSource] = {"total_outlay_lakhs": OUTLAY_SOURCE}
    for name, (value, measure) in values.items():
        live = Figure(
            value=value, source_type="live", label=live_label({source}), measure=measure,
            source_url=scheme.source_url, fetched_at=updated,
        ) if value is not None else None
        note = OFFICIAL_NOTE if view is View.OFFICIAL else f"No data collected for {financial_year}"
        resolved = resolve(view, live, None, note=note)
        out_values[name] = resolved.value
        out_sources[name] = to_source(resolved)
    return out_values, out_sources


@router.get("", response_model=list[SchemeSummary])
async def list_schemes(
    financial_year: str = Query("2024-25"),
    scheme_type: str | None = Query(None, description="css | central | ut"),
    department_id: int | None = Query(None),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """All schemes with their aggregate financial progress (2 queries)."""
    query = select(Scheme, Department).join(Department)
    if scheme_type:
        query = query.where(Scheme.scheme_type == scheme_type)
    if department_id:
        query = query.where(Scheme.department_id == department_id)
    query = query.where(Scheme.is_active.is_(True))

    rows = (await db.execute(query)).all()

    # ── Single batch aggregation (fix N+1) ─────────────────────────────────
    agg_rows = (await db.execute(
        select(
            SchemeProgress.scheme_id,
            func.sum(SchemeProgress.funds_allocated).label("allocated"),
            func.sum(SchemeProgress.funds_utilized).label("utilized"),
            func.sum(SchemeProgress.funds_released).label("released"),
            func.avg(SchemeProgress.physical_pct).label("avg_physical"),
            func.max(SchemeProgress.snapshot_date).label("latest_date"),
            func.max(SchemeProgress.source).label("source"),
            func.max(SchemeProgress.created_at).label("updated"),
        ).where(
            SchemeProgress.financial_year == financial_year,
        ).group_by(SchemeProgress.scheme_id)
    )).all()
    agg_map = {row.scheme_id: row for row in agg_rows}

    results = []
    for scheme, dept in rows:
        row = agg_map.get(scheme.id)
        values, sources = scheme_sources(view, financial_year, scheme, {
            "funds_allocated_lakhs": (to_int(row.allocated) if row else None, "allocated"),
            "funds_released_lakhs": (to_int(row.released) if row else None, "released"),
            "funds_utilized_lakhs": (to_int(row.utilized) if row else None, "utilized"),
            "physical_pct": (round(row.avg_physical, 2) if row and row.avg_physical is not None else None,
                             "physical_progress_pct"),
        }, row.source if row else None, row.updated if row else None)
        allocated, utilized = values["funds_allocated_lakhs"], values["funds_utilized_lakhs"]

        results.append(SchemeSummary(
            id=scheme.id,
            name=scheme.name,
            code=scheme.code,
            scheme_type=scheme.scheme_type,
            department_name=dept.name,
            total_outlay_lakhs=scheme.total_outlay,
            funds_allocated_lakhs=allocated,
            funds_released_lakhs=values["funds_released_lakhs"],
            funds_utilized_lakhs=utilized,
            utilization_pct=round(utilized / allocated * 100, 2) if allocated and utilized is not None else None,
            physical_pct=values["physical_pct"],
            last_updated=row.latest_date if row and view is not View.OFFICIAL else None,
            view=view,
            sources=sources,
        ))

    results.sort(key=lambda x: x.total_outlay_lakhs or 0, reverse=True)
    return results


@router.get("/{scheme_id}", response_model=SchemeDetail)
async def get_scheme_detail(
    scheme_id: int,
    financial_year: str = Query("2024-25"),
    view: View = VIEW_QUERY,
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
    latest_date = latest_date_result.scalar() if view is not View.OFFICIAL else None

    # District-wise progress for latest snapshot (live only; none in the official view)
    district_rows = [] if latest_date is None else (await db.execute(
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

    def total(attr: str) -> int | None:
        known = [getattr(d, attr) for d in district_progress if getattr(d, attr) is not None]
        return sum(known) if known else None

    physical = [d.physical_pct for d in district_progress if d.physical_pct is not None]
    snapshots = [sp for sp, _ in district_rows]
    values, sources = scheme_sources(view, financial_year, scheme, {
        "funds_allocated_lakhs": (total("funds_allocated_lakhs"), "allocated"),
        "funds_released_lakhs": (total("funds_released_lakhs"), "released"),
        "funds_utilized_lakhs": (total("funds_utilized_lakhs"), "utilized"),
        "physical_pct": (round(sum(physical) / len(physical), 2) if physical else None, "physical_progress_pct"),
    },
        max((sp.source for sp in snapshots if sp.source), default=None),
        max((sp.created_at for sp in snapshots if sp.created_at), default=None),
    )
    if district_progress:
        sources["district_progress"] = sources["funds_utilized_lakhs"]
    allocated, utilized = values["funds_allocated_lakhs"], values["funds_utilized_lakhs"]

    return SchemeDetail(
        id=scheme.id,
        name=scheme.name,
        code=scheme.code,
        scheme_type=scheme.scheme_type,
        department_name=dept.name,
        total_outlay_lakhs=scheme.total_outlay,
        funds_allocated_lakhs=allocated,
        funds_released_lakhs=values["funds_released_lakhs"],
        funds_utilized_lakhs=utilized,
        utilization_pct=round(utilized / allocated * 100, 2) if allocated and utilized is not None else None,
        physical_pct=values["physical_pct"],
        last_updated=latest_date,
        view=view,
        sources=sources,
        description=scheme.description,
        start_year=scheme.start_year,
        end_year=scheme.end_year,
        source_url=scheme.source_url,
        district_progress=district_progress,
    )


@router.get("/{scheme_id}/history", response_model=SchemeVelocity)
async def get_scheme_velocity(
    scheme_id: int,
    financial_year: str = Query("2024-25"),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """
    Time-series of spending for a scheme + run-rate projection to March 31st.

    Math:
      daily_run_rate = total_utilized_so_far / days_elapsed_in_FY
      projected_utilized = current_utilized + (daily_run_rate * days_remaining)
      on_track = projected_utilized >= total_allocated
    """
    # Fetch scheme
    scheme_row = await db.execute(select(Scheme).where(Scheme.id == scheme_id))
    scheme = scheme_row.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    # Pull all snapshots aggregated by date (sum across districts); live only
    rows = [] if view is View.OFFICIAL else (await db.execute(
        select(
            SchemeProgress.snapshot_date,
            func.sum(SchemeProgress.funds_allocated).label("allocated"),
            func.sum(SchemeProgress.funds_utilized).label("utilized"),
            func.max(SchemeProgress.source).label("source"),
            func.max(SchemeProgress.created_at).label("updated"),
        )
        .where(
            SchemeProgress.scheme_id == scheme_id,
            SchemeProgress.financial_year == financial_year,
        )
        .group_by(SchemeProgress.snapshot_date)
        .order_by(SchemeProgress.snapshot_date.asc())
    )).all()

    history = [
        SchemeHistoryPoint(
            snapshot_date=r.snapshot_date,
            funds_allocated_lakhs=int(r.allocated or 0),
            funds_utilized_lakhs=int(r.utilized or 0),
            utilization_pct=round((r.utilized / r.allocated * 100), 2)
            if r.allocated and r.allocated > 0 else None,
        )
        for r in rows
    ]

    if rows:
        history_source = FigureSource(
            source_type="live",
            label=f"{live_label({r.source for r in rows})} (provisional)",
            measure="utilized",
            source_url=scheme.source_url,
            fetched_at=max((r.updated for r in rows if r.updated), default=None),
            provisional=True,
        )
    else:
        history_source = FigureSource(
            source_type=None,
            label=OFFICIAL_NOTE if view is View.OFFICIAL else f"No data collected for {financial_year}",
        )

    # ── Projection math ────────────────────────────────────────────────────────
    fy_start_year = int(financial_year.split("-")[0])
    fy_start = date(fy_start_year, 4, 1)          # April 1
    fy_end   = date(fy_start_year + 1, 3, 31)     # March 31

    today = date.today()
    days_elapsed  = max((today - fy_start).days, 1)
    days_remaining = max((fy_end - today).days, 0)

    daily_run_rate   = None
    projected        = None
    on_track         = None
    surrender_risk   = None
    verdict          = "NO DATA"

    if history:
        latest = history[-1]
        current_utilized  = latest.funds_utilized_lakhs
        total_allocated   = latest.funds_allocated_lakhs

        if days_elapsed > 0:
            daily_run_rate = current_utilized / days_elapsed

        if daily_run_rate is not None:
            projected = int(current_utilized + (daily_run_rate * days_remaining))
            on_track  = projected >= total_allocated

            if on_track:
                verdict = "ON TRACK"
                surrender_risk = 0
            else:
                shortfall_pct = (total_allocated - projected) / total_allocated * 100 if total_allocated else 0
                surrender_risk = max(0, total_allocated - projected)
                verdict = "CRITICAL" if shortfall_pct > 40 else "AT RISK"
    else:
        total_allocated = None

    return SchemeVelocity(
        scheme_id=scheme_id,
        scheme_name=scheme.name,
        financial_year=financial_year,
        history=history,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        daily_run_rate_lakhs=round(daily_run_rate, 2) if daily_run_rate else None,
        projected_utilized_lakhs=projected,
        total_allocated_lakhs=total_allocated,
        on_track=on_track,
        surrender_risk_lakhs=surrender_risk,
        verdict=verdict,
        view=view,
        sources={"history": history_source},
    )


def to_int(value) -> int | None:
    return int(value) if value is not None else None
