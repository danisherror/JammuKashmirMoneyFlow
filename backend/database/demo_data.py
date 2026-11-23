"""
Made-up budget allocations for local development. NOT REAL.

These were the old seed figures: the 2024-25 ones were never cited and the 2023-24 ones were
"scaled down by ~10% for demonstration" (todo.md 1.1, 2.2). They load only with DEMO_MODE=true,
are stored with is_demo=true and the label below, and are deleted on startup when demo mode is
off. config.Settings refuses DEMO_MODE=true with APP_ENV=production.

Amounts are in ₹ lakhs.
"""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import BudgetAllocation, Department

DEMO_SOURCE = "DEMO DATA — NOT REAL"

# Labelled "from J&K Budget documents" when they were seed data, but never cited (todo.md 2.2).
BUDGET_2024_25 = {
    "PWD":        {"budget_estimate": 450000, "is_capital": True},
    "HEALTH":     {"budget_estimate": 285000, "is_capital": False},
    "SCHOOLEDU":  {"budget_estimate": 320000, "is_capital": False},
    "HIGHEREDU":  {"budget_estimate": 95000,  "is_capital": False},
    "JALSHAKTI":  {"budget_estimate": 380000, "is_capital": True},
    "PDD":        {"budget_estimate": 295000, "is_capital": True},
    "AGRI":       {"budget_estimate": 125000, "is_capital": False},
    "HORTI":      {"budget_estimate": 98000,  "is_capital": False},
    "RDPR":       {"budget_estimate": 210000, "is_capital": False},
    "ULB":        {"budget_estimate": 145000, "is_capital": True},
    "SOCIALWEL":  {"budget_estimate": 87000,  "is_capital": False},
    "POLICE":     {"budget_estimate": 420000, "is_capital": False},
    "REVENUE":    {"budget_estimate": 68000,  "is_capital": False},
    "INDUSTRIES": {"budget_estimate": 55000,  "is_capital": False},
    "TOURISM":    {"budget_estimate": 42000,  "is_capital": True},
    "FOREST":     {"budget_estimate": 38000,  "is_capital": False},
    "FINANCE":    {"budget_estimate": 890000, "is_capital": False},   # includes pension, debt
    "GAD":        {"budget_estimate": 72000,  "is_capital": False},
    "LABOUR":     {"budget_estimate": 31000,  "is_capital": False},
    "ANIMAL":     {"budget_estimate": 44000,  "is_capital": False},
}

# Estimated budget allocations FY2023-24 (in lakhs) — scaled down by ~10% for demonstration
BUDGET_2023_24 = {
    "PWD":        {"budget_estimate": 405000, "is_capital": True},
    "HEALTH":     {"budget_estimate": 256500, "is_capital": False},
    "SCHOOLEDU":  {"budget_estimate": 288000, "is_capital": False},
    "HIGHEREDU":  {"budget_estimate": 85500,  "is_capital": False},
    "JALSHAKTI":  {"budget_estimate": 342000, "is_capital": True},
    "PDD":        {"budget_estimate": 265500, "is_capital": True},
    "AGRI":       {"budget_estimate": 112500, "is_capital": False},
    "HORTI":      {"budget_estimate": 88200,  "is_capital": False},
    "RDPR":       {"budget_estimate": 189000, "is_capital": False},
    "ULB":        {"budget_estimate": 130500, "is_capital": True},
    "SOCIALWEL":  {"budget_estimate": 78300,  "is_capital": False},
    "POLICE":     {"budget_estimate": 378000, "is_capital": False},
    "REVENUE":    {"budget_estimate": 61200,  "is_capital": False},
    "INDUSTRIES": {"budget_estimate": 49500,  "is_capital": False},
    "TOURISM":    {"budget_estimate": 37800,  "is_capital": True},
    "FOREST":     {"budget_estimate": 34200,  "is_capital": False},
    "FINANCE":    {"budget_estimate": 801000, "is_capital": False},
    "GAD":        {"budget_estimate": 64800,  "is_capital": False},
    "LABOUR":     {"budget_estimate": 27900,  "is_capital": False},
    "ANIMAL":     {"budget_estimate": 39600,  "is_capital": False},
}

DEMO_ALLOCATIONS = {"2024-25": BUDGET_2024_25, "2023-24": BUDGET_2023_24}


async def seed_demo_allocations(db: AsyncSession) -> int:
    """Insert the demo allocations that aren't there yet. Returns the number of rows added."""
    dept_ids = dict((await db.execute(select(Department.code, Department.id))).all())
    existing = set((await db.execute(
        select(BudgetAllocation.department_id, BudgetAllocation.financial_year)
        .where(BudgetAllocation.is_demo.is_(True))
    )).all())
    added = 0
    for fy, budgets in DEMO_ALLOCATIONS.items():
        for code, budget in budgets.items():
            dept_id = dept_ids.get(code)
            if dept_id is None or (dept_id, fy) in existing:
                continue
            db.add(BudgetAllocation(
                department_id=dept_id,
                financial_year=fy,
                budget_estimate=budget["budget_estimate"],
                is_capital=budget["is_capital"],
                source=DEMO_SOURCE,
                is_demo=True,
            ))
            added += 1
    await db.flush()
    return added


async def delete_demo_rows(db: AsyncSession) -> int:
    """Remove every demo row. Called on startup when DEMO_MODE is off."""
    result = await db.execute(delete(BudgetAllocation).where(BudgetAllocation.is_demo.is_(True)))
    return result.rowcount or 0
