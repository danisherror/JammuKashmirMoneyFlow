"""
Budget routes — department allocations and expenditure data.
GET /api/v1/budget/overview
GET /api/v1/budget/departments
GET /api/v1/budget/departments/{id}
GET /api/v1/budget/gap-analysis
GET /api/v1/budget/departments/{id}/breakdown
GET /api/v1/budget/grants
GET /api/v1/budget/grants/{grant_no}/breakdown

Every route takes `?view=live|official|combined` (default combined; see processors.combined_view)
and returns a `sources` map saying where each figure comes from. Official figures are the CAG
Appropriation Accounts: "budget" is the final grant (original + supplementary) and "utilized" is
gross expenditure, as stated in each source's `measure`.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.figures import (
    as_of,
    department_figures,
    live_label,
    load_live_allocations,
    load_official_year,
    pct,
    to_source,
)
from api.provenance import load_snapshots, newest_id, snapshot_source
from api.official import department_grants, grant_breakdown, latest_detail_year, list_grants, official_chain
from api.schemas import (
    BudgetOverview,
    DepartmentDetail,
    DepartmentSummary,
    FigureSource,
    GapAnalysisItem,
    GrantBreakdown,
    GrantInfo,
)
from database.connection import get_db
from database.models import Department, Expenditure, Scheme, SchemeProgress
from processors.combined_view import Figure, View, resolve

router = APIRouter(prefix="/budget", tags=["Budget"])

VIEW_QUERY = Query(View.COMBINED, description="live | official | combined (default)")


@router.get("/overview", response_model=BudgetOverview)
async def get_budget_overview(
    financial_year: str = Query("2024-25", description="Financial year e.g. 2024-25"),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """
    Top-level J&K budget summary for the given financial year: total, capital and revenue.
    Live and official totals are never compared here: the budget table lists only some departments,
    the CAG accounts all grants.
    """
    live = await load_live_allocations(db, financial_year)
    official = (await load_official_year(db, financial_year)).total

    def live_total(attr: str, measure: str) -> Figure | None:
        if not live:
            return None
        return Figure(
            value=float(sum(getattr(a, attr) for a in live.values())),
            source_type="live",
            label=live_label(set().union(*(a.sources for a in live.values()))),
            measure=measure,
            fetched_at=max((a.updated for a in live.values() if a.updated), default=None),
        )

    note = f"No budget figure for {financial_year}"
    total = resolve(view, live_total("budget_estimate", "budget_estimate"),
                    official.figure(official.final_grant, "final_grant") if official else None,
                    comparable=False, note=note)
    capital = resolve(view, live_total("capital", "budget_estimate"),
                      official.figure(official.capital_final_grant, "final_grant") if official else None,
                      comparable=False, note=note)
    revenue = resolve(view, live_total("revenue", "budget_estimate"),
                      official.figure(official.revenue_final_grant, "final_grant") if official else None,
                      comparable=False, note=note)

    if total.figure is None:
        departments = 0
    elif total.figure.source_type == "official":
        departments = len(official.grants)
    else:
        departments = len(live)

    return BudgetOverview(
        financial_year=financial_year,
        total_budget_lakhs=total.value,
        total_capital_lakhs=capital.value,
        total_revenue_lakhs=revenue.value,
        capital_pct=pct(capital.value, total.value),
        revenue_pct=pct(revenue.value, total.value),
        total_departments=departments,
        data_as_of=as_of(total, capital, revenue),
        official_chain=await official_chain(db, financial_year) if view is not View.LIVE else None,
        view=view,
        sources={
            "total_budget_lakhs": to_source(total),
            "total_capital_lakhs": to_source(capital),
            "total_revenue_lakhs": to_source(revenue),
        },
    )


@router.get("/departments", response_model=list[DepartmentSummary])
async def list_departments(
    financial_year: str = Query("2024-25"),
    division: str | None = Query(None, description="Filter by division: jammu/kashmir/central"),
    sort_by: str = Query("budget_estimate", description="Sort by: budget_estimate | utilization_pct"),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """
    Departments with an allocation or spending figure for the year in the chosen view.
    Official view: only the grants mapped to a tracker department (grant_department_map).
    """
    figures = await department_figures(db, financial_year, view)
    if not figures:
        return []

    query = select(Department).where(Department.id.in_(list(figures)), Department.is_active.is_(True))
    if division:
        query = query.where(Department.division == division)
    departments = (await db.execute(query)).scalars().all()

    results = [summary(dept, financial_year, view, figures[dept.id]) for dept in departments]
    if sort_by == "utilization_pct":
        results.sort(key=lambda x: (x.utilization_pct is not None, x.utilization_pct or 0), reverse=True)
    else:
        results.sort(key=lambda x: (x.budget_estimate_lakhs is not None, x.budget_estimate_lakhs or 0), reverse=True)
    return results


def summary(dept: Department, financial_year: str, view: View, fig) -> DepartmentSummary:
    return DepartmentSummary(
        id=dept.id,
        name=dept.name,
        code=dept.code,
        division=dept.division,
        financial_year=financial_year,
        budget_estimate_lakhs=fig.allocated.value,
        revised_estimate_lakhs=fig.revised.value,
        utilized_lakhs=fig.utilized.value,
        utilization_pct=fig.utilization_pct,
        is_capital=fig.is_capital,
        data_as_of=as_of(fig.allocated, fig.utilized),
        view=view,
        sources=fig.sources(),
    )


@router.get("/departments/{dept_id}", response_model=DepartmentDetail)
async def get_department_detail(
    dept_id: int,
    financial_year: str = Query("2024-25"),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """
    Single department: totals in the chosen view, the live monthly expenditure trend, and (official
    and combined views) the audited original → final grant → spent chain of its mapped grants.
    """
    dept = await db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    fig = (await department_figures(db, financial_year, view, [dept_id]))[dept_id]
    base = summary(dept, financial_year, view, fig)

    # Monthly figures exist only on the live side; the CAG accounts are annual.
    monthly: list[dict] = []
    monthly_source = FigureSource(source_type=None, label="The CAG accounts have no monthly figures")
    if view is not View.OFFICIAL:
        rows = (await db.execute(
            select(
                Expenditure.month,
                func.sum(Expenditure.utilized_amount).label("amount"),
                func.max(Expenditure.source).label("source"),
                func.max(Expenditure.created_at).label("updated"),
                func.max(Expenditure.snapshot_id).label("snapshot_id"),
            )
            .where(Expenditure.department_id == dept_id, Expenditure.financial_year == financial_year)
            .group_by(Expenditure.month)
            .order_by(Expenditure.month)
        )).all()
        snapshots = await load_snapshots(db, (r.snapshot_id for r in rows))
        monthly = [
            {"month": r.month, "amount_lakhs": r.amount,
             "source": snapshot_source(snapshots.get(r.snapshot_id), measure="utilized")}
            for r in rows
        ]
        if rows:
            newest = snapshots.get(newest_id(r.snapshot_id for r in rows))
            monthly_source = FigureSource(
                source_type="live",
                label=f"{live_label({r.source for r in rows})} (provisional)",
                measure="utilized",
                source_url=newest.source_url if newest else None,
                snapshot_id=newest.id if newest else None,
                fetched_at=newest.fetched_at if newest else max((r.updated for r in rows if r.updated), default=None),
                provisional=True,
            )
        else:
            monthly_source = FigureSource(source_type=None, label=f"No monthly spending figure for {financial_year}")

    chain = None
    if view is not View.LIVE:
        grants = await department_grants(db, financial_year, dept_id)
        chain = await official_chain(db, financial_year, grants) if grants else None

    return DepartmentDetail(
        **base.model_dump(exclude={"sources"}),
        sources={**base.sources, "monthly_expenditure": monthly_source},
        monthly_expenditure=monthly,
        official_chain=chain,
    )


@router.get("/gap-analysis", response_model=list[GapAnalysisItem])
async def get_gap_analysis(
    financial_year: str = Query("2024-25"),
    min_allocation_lakhs: int = Query(10000, description="Minimum allocation to include (in lakhs)"),
    view: View = VIEW_QUERY,
    db: AsyncSession = Depends(get_db),
):
    """
    Departments ranked by their unspent budget gap: (PFMS release, or the allocation when no release
    figure exists) − utilised. Departments with no spending figure get gap_flag "no_data", not 0%.
    """
    figures = await department_figures(db, financial_year, view)
    figures = {
        d: f for d, f in figures.items()
        if f.allocated.value is not None and f.allocated.value >= min_allocation_lakhs
    }
    if not figures:
        return []

    departments = (await db.execute(
        select(Department).where(Department.id.in_(list(figures)), Department.is_active.is_(True))
    )).scalars().all()

    # PFMS central releases (live only) per department
    pfms_rows = (await db.execute(
        select(
            Scheme.department_id,
            func.sum(SchemeProgress.funds_released).label("total"),
            func.max(SchemeProgress.source).label("source"),
            func.max(SchemeProgress.created_at).label("updated"),
            func.max(SchemeProgress.snapshot_id).label("snapshot_id"),
        )
        .join(SchemeProgress, SchemeProgress.scheme_id == Scheme.id)
        .where(SchemeProgress.financial_year == financial_year, Scheme.department_id.in_(list(figures)))
        .group_by(Scheme.department_id)
    )).all()
    pfms = {r.department_id: r for r in pfms_rows if r.total is not None}   # a real 0 release is kept
    release_snapshots = await load_snapshots(db, (r.snapshot_id for r in pfms.values()))

    results = []
    for dept in departments:
        fig = figures[dept.id]
        allocated = fig.allocated.value
        utilized = fig.utilized.value
        # PFMS releases are live figures; don't mix them with audited totals.
        release_row = pfms.get(dept.id) if fig.allocated.figure.source_type == "live" else None
        released = float(release_row.total) if release_row else None

        base = released if released is not None else allocated
        gap = round(base - utilized, 2) if utilized is not None else None
        util_pct = fig.utilization_pct

        if util_pct is None:
            flag = "no_data"
        elif util_pct < 20:
            flag = "critical"
        elif util_pct < 40:
            flag = "warning"
        else:
            flag = "on_track"

        sources = {
            "allocated_lakhs": to_source(fig.allocated),
            "utilized_lakhs": to_source(fig.utilized),
            "released_lakhs": (
                snapshot_source(release_snapshots.get(release_row.snapshot_id), measure="released",
                                label=f"{live_label({release_row.source})} (provisional)")
                or FigureSource(source_type="live", label=f"{live_label({release_row.source})} (provisional)",
                                measure="released", fetched_at=release_row.updated, provisional=True)
            ) if release_row else FigureSource(source_type=None, label="No live PFMS release figure; gap uses the allocation"),
        }
        results.append(GapAnalysisItem(
            department_id=dept.id,
            department_name=dept.name,
            department_code=dept.code,
            allocated_lakhs=allocated,
            released_lakhs=released,
            utilized_lakhs=utilized,
            gap_lakhs=gap,
            utilization_pct=util_pct,
            gap_flag=flag,
            view=view,
            sources=sources,
        ))

    results.sort(key=lambda x: (x.gap_lakhs is not None, x.gap_lakhs or 0), reverse=True)
    return results


# ── Grant breakdown (CAG Appropriation Accounts grant pages) ──────────────────

BREAKDOWN_YEAR = Query(
    None, description="Financial year, e.g. 2023-24. Default: the latest year with CAG grant pages loaded"
)


async def _breakdown_year(db: AsyncSession, financial_year: str | None) -> str:
    year = financial_year or await latest_detail_year(db)
    if year is None:
        raise HTTPException(status_code=404, detail="No CAG Appropriation Accounts grant pages are loaded")
    return year


@router.get("/grants", response_model=list[GrantInfo])
async def get_grants(financial_year: str | None = BREAKDOWN_YEAR, db: AsyncSession = Depends(get_db)):
    """Every grant in the year's CAG accounts, including those not mapped to a tracker department."""
    return await list_grants(db, await _breakdown_year(db, financial_year))


@router.get("/departments/{dept_id}/breakdown", response_model=GrantBreakdown)
async def get_department_breakdown(
    dept_id: int, financial_year: str | None = BREAKDOWN_YEAR, db: AsyncSession = Depends(get_db)
):
    """
    Where a department's audited grant went: section blocks, the head tree from the Notes and
    Comments (amounts, verbatim remark, PDF page) and the notes themselves. Official figures only,
    so there is no `view` parameter. The head rows are the heads the CAG chose to comment on; they
    don't add up to the grant total.
    """
    if not await db.get(Department, dept_id):
        raise HTTPException(status_code=404, detail="Department not found")
    year = await _breakdown_year(db, financial_year)
    return await grant_breakdown(db, year, await department_grants(db, year, dept_id), department_id=dept_id)


@router.get("/grants/{grant_no}/breakdown", response_model=GrantBreakdown)
async def get_grant_breakdown(
    grant_no: int, financial_year: str | None = BREAKDOWN_YEAR, db: AsyncSession = Depends(get_db)
):
    """The same breakdown for one grant number, mapped to a tracker department or not."""
    year = await _breakdown_year(db, financial_year)
    result = await grant_breakdown(db, year, [grant_no])
    if not result.grants:
        raise HTTPException(status_code=404, detail=f"Grant {grant_no} is not in the {year} accounts")
    mapped = result.grants[0].department_id
    return result.model_copy(update={"department_id": mapped})
