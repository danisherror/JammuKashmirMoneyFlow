"""
Budget routes — department allocations and expenditure data.
GET /api/v1/budget/overview
GET /api/v1/budget/departments
GET /api/v1/budget/departments/{id}
GET /api/v1/budget/gap-analysis
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from loguru import logger

from database.connection import get_db
from database.models import Department, BudgetAllocation, Expenditure
from api.schemas import BudgetOverview, DepartmentSummary, DepartmentDetail, GapAnalysisItem

router = APIRouter(prefix="/budget", tags=["Budget"])


@router.get("/overview", response_model=BudgetOverview)
async def get_budget_overview(
    financial_year: str = Query("2024-25", description="Financial year e.g. 2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """
    Top-level J&K budget summary for the given financial year.
    Returns total allocation, capital vs revenue split.
    """
    # Sum all allocations for the year
    result = await db.execute(
        select(
            func.sum(BudgetAllocation.budget_estimate).label("total"),
            func.sum(BudgetAllocation.budget_estimate).filter(BudgetAllocation.is_capital == True).label("capital"),
            func.sum(BudgetAllocation.budget_estimate).filter(BudgetAllocation.is_capital == False).label("revenue"),
            func.count(BudgetAllocation.department_id.distinct()).label("dept_count"),
        ).where(BudgetAllocation.financial_year == financial_year)
    )
    row = result.one()

    total = row.total or 0
    capital = row.capital or 0
    revenue = row.revenue or 0

    return BudgetOverview(
        financial_year=financial_year,
        total_budget_lakhs=total,
        total_capital_lakhs=capital,
        total_revenue_lakhs=revenue,
        capital_pct=round((capital / total * 100) if total > 0 else 0, 1),
        revenue_pct=round((revenue / total * 100) if total > 0 else 0, 1),
        total_departments=row.dept_count or 0,
        data_as_of=None,
    )


@router.get("/departments", response_model=list[DepartmentSummary])
async def list_departments(
    financial_year: str = Query("2024-25"),
    division: str | None = Query(None, description="Filter by division: jammu/kashmir/central"),
    sort_by: str = Query("budget_estimate", description="Sort by: budget_estimate | utilization_pct"),
    db: AsyncSession = Depends(get_db),
):
    """
    All departments with their budget allocation and utilization for the year.
    """
    query = (
        select(Department, BudgetAllocation)
        .join(BudgetAllocation, and_(
            BudgetAllocation.department_id == Department.id,
            BudgetAllocation.financial_year == financial_year,
        ))
        .where(Department.is_active == True)
    )

    if division:
        query = query.where(Department.division == division)

    rows = (await db.execute(query)).all()

    results = []
    for dept, alloc in rows:
        # Get latest total expenditure for this dept
        exp_result = await db.execute(
            select(func.sum(Expenditure.utilized_amount)).where(
                and_(
                    Expenditure.department_id == dept.id,
                    Expenditure.financial_year == financial_year,
                )
            )
        )
        utilized = exp_result.scalar() or 0
        budget = alloc.budget_estimate or 0
        util_pct = round((utilized / budget * 100), 2) if budget > 0 else None

        results.append(DepartmentSummary(
            id=dept.id,
            name=dept.name,
            code=dept.code,
            division=dept.division,
            financial_year=financial_year,
            budget_estimate_lakhs=alloc.budget_estimate,
            revised_estimate_lakhs=alloc.revised_estimate,
            utilized_lakhs=utilized,
            utilization_pct=util_pct,
            is_capital=alloc.is_capital,
            data_as_of=None,
        ))

    # Sort
    if sort_by == "utilization_pct":
        results.sort(key=lambda x: x.utilization_pct or 0, reverse=True)
    else:
        results.sort(key=lambda x: x.budget_estimate_lakhs, reverse=True)

    return results


@router.get("/departments/{dept_id}", response_model=DepartmentDetail)
async def get_department_detail(
    dept_id: int,
    financial_year: str = Query("2024-25"),
    db: AsyncSession = Depends(get_db),
):
    """
    Single department deep dive: monthly expenditure trend + linked schemes.
    """
    dept = await db.get(Department, dept_id)
    if not dept:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Department not found")

    alloc_result = await db.execute(
        select(BudgetAllocation).where(
            BudgetAllocation.department_id == dept_id,
            BudgetAllocation.financial_year == financial_year,
        )
    )
    alloc = alloc_result.scalar_one_or_none()

    # Monthly expenditure breakdown
    monthly_result = await db.execute(
        select(Expenditure.month, func.sum(Expenditure.utilized_amount).label("amount"))
        .where(
            Expenditure.department_id == dept_id,
            Expenditure.financial_year == financial_year,
        )
        .group_by(Expenditure.month)
        .order_by(Expenditure.month)
    )
    monthly = [{"month": row.month, "amount_lakhs": row.amount or 0} for row in monthly_result]

    total_utilized = sum(m["amount_lakhs"] for m in monthly)
    budget = alloc.budget_estimate if alloc else 0

    return DepartmentDetail(
        id=dept.id,
        name=dept.name,
        code=dept.code,
        division=dept.division,
        financial_year=financial_year,
        budget_estimate_lakhs=budget,
        revised_estimate_lakhs=alloc.revised_estimate if alloc else None,
        utilized_lakhs=total_utilized,
        utilization_pct=round((total_utilized / budget * 100), 2) if budget > 0 else None,
        is_capital=alloc.is_capital if alloc else False,
        data_as_of=None,
        monthly_expenditure=monthly,
    )


@router.get("/gap-analysis", response_model=list[GapAnalysisItem])
async def get_gap_analysis(
    financial_year: str = Query("2024-25"),
    min_allocation_lakhs: int = Query(10000, description="Minimum allocation to include (in lakhs)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Departments ranked by their unspent budget gap.
    Highlights where allocated money is NOT being spent.
    """
    rows = (await db.execute(
        select(Department, BudgetAllocation)
        .join(BudgetAllocation, and_(
            BudgetAllocation.department_id == Department.id,
            BudgetAllocation.financial_year == financial_year,
        ))
        .where(
            Department.is_active == True,
            BudgetAllocation.budget_estimate >= min_allocation_lakhs,
        )
    )).all()

    results = []
    for dept, alloc in rows:
        exp_result = await db.execute(
            select(func.sum(Expenditure.utilized_amount)).where(
                and_(
                    Expenditure.department_id == dept.id,
                    Expenditure.financial_year == financial_year,
                )
            )
        )
        utilized = exp_result.scalar() or 0
        budget = alloc.budget_estimate
        gap = budget - utilized
        util_pct = round((utilized / budget * 100), 2) if budget > 0 else 0

        flag = "on_track"
        if util_pct < 20:
            flag = "critical"
        elif util_pct < 40:
            flag = "warning"

        results.append(GapAnalysisItem(
            department_id=dept.id,
            department_name=dept.name,
            department_code=dept.code,
            allocated_lakhs=budget,
            utilized_lakhs=utilized,
            gap_lakhs=gap,
            utilization_pct=util_pct,
            gap_flag=flag,
        ))

    results.sort(key=lambda x: x.gap_lakhs, reverse=True)
    return results
