"""
Load live and official figures for the budget routes and resolve them for a view.

Live:     `budget_allocations` (allocation) and `expenditures` (spending). Each row has a snapshot
          (todo.md 1.4); a live figure summed over several rows points at the newest one.
Official: `appropriation_account_lines` (CAG, ₹ thousand) linked to departments through
          `grant_department_map`. Final grant is compared with the live allocation, gross
          expenditure with live spending.

The Combined rules themselves live in processors.combined_view.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import FigureSource, MismatchInfo
from database.models import (
    AppropriationAccountLine,
    BudgetAllocation,
    Expenditure,
    GrantDepartmentMap,
    SourceSnapshot,
)
from api.provenance import load_snapshots
from processors.combined_view import Figure, Resolved, View, resolve


def to_source(resolved: Resolved) -> FigureSource:
    figure = resolved.figure
    if figure is None:
        return FigureSource(source_type=None, label=resolved.note or "No data")
    label = f"{figure.label} (provisional)" if resolved.provisional else figure.label
    return FigureSource(
        source_type=figure.source_type,
        label=label,
        measure=figure.measure,
        source_url=figure.source_url,
        snapshot_id=figure.snapshot_id,
        page=figure.page,
        fetched_at=figure.fetched_at,
        provisional=resolved.provisional,
        mismatch=MismatchInfo(**asdict(resolved.mismatch)) if resolved.mismatch else None,
    )


def as_of(*resolved: Resolved) -> date | None:
    """Date of the newest figure among `resolved`, for the old `data_as_of` field."""
    times = [r.figure.fetched_at for r in resolved if r.figure and r.figure.fetched_at]
    return max(times).date() if times else None


def pct(part: float | None, whole: float | None) -> float | None:
    if part is None or whole is None or whole <= 0:
        return None
    return round(part / whole * 100, 2)


# ── Official (CAG Appropriation Accounts) ─────────────────────────────────────

def lakhs_from_thousand(thousand: int) -> float:
    return round(thousand / 100, 2)


def pages_label(pages: set[int]) -> str:
    ordered = sorted(pages)
    if len(ordered) == 1:
        return f"p.{ordered[0]}"
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"pp.{ordered[0]}–{ordered[-1]}"
    return "pp." + ", ".join(str(p) for p in ordered)


@dataclass
class OfficialTotals:
    """Sum of appropriation lines (₹ thousand) for one department, or for the whole year."""
    financial_year: str
    snapshot: SourceSnapshot
    final_grant: int = 0
    expenditure: int = 0
    capital_final_grant: int = 0
    revenue_final_grant: int = 0
    pages: set[int] = field(default_factory=set)
    grants: set[int] = field(default_factory=set)

    def add(self, line: AppropriationAccountLine) -> None:
        self.final_grant += line.final_grant_thousand
        self.expenditure += line.gross_expenditure_thousand
        if line.section == "capital":
            self.capital_final_grant += line.final_grant_thousand
        else:
            self.revenue_final_grant += line.final_grant_thousand
        self.pages.add(line.page)
        self.grants.add(line.grant_no)

    def figure(self, thousand: int, measure: str) -> Figure:
        return Figure(
            value=lakhs_from_thousand(thousand),
            source_type="official",
            label=f"Official · Appropriation Accounts {self.financial_year}, {pages_label(self.pages)}",
            measure=measure,
            source_url=self.snapshot.source_url,
            snapshot_id=self.snapshot.id,
            page=min(self.pages),
            fetched_at=self.snapshot.fetched_at,
        )


@dataclass
class OfficialYear:
    total: OfficialTotals | None                     # every grant, mapped or not
    by_department: dict[int, OfficialTotals]         # mapped grants only


async def load_official_year(db: AsyncSession, financial_year: str) -> OfficialYear:
    rows = (await db.execute(
        select(AppropriationAccountLine, SourceSnapshot, GrantDepartmentMap.department_id)
        .join(SourceSnapshot, AppropriationAccountLine.snapshot_id == SourceSnapshot.id)
        .outerjoin(GrantDepartmentMap, and_(
            GrantDepartmentMap.financial_year == AppropriationAccountLine.financial_year,
            GrantDepartmentMap.grant_no == AppropriationAccountLine.grant_no,
        ))
        .where(AppropriationAccountLine.financial_year == financial_year)
    )).all()

    total: OfficialTotals | None = None
    by_department: dict[int, OfficialTotals] = {}
    for line, snapshot, department_id in rows:
        if total is None:
            total = OfficialTotals(financial_year, snapshot)
        total.add(line)
        if department_id is not None:
            by_department.setdefault(department_id, OfficialTotals(financial_year, snapshot)).add(line)
    return OfficialYear(total, by_department)


# ── Live (budget tables) ──────────────────────────────────────────────────────

def live_label(sources: set[str | None]) -> str:
    names = sorted(s for s in sources if s)
    return "Live · " + (", ".join(names) if names else "source not recorded")


@dataclass
class LiveAllocation:
    budget_estimate: int = 0
    revised_estimate: int | None = None
    capital: int = 0
    revenue: int = 0
    capital_flags: set[bool] = field(default_factory=set)
    sources: set[str | None] = field(default_factory=set)
    updated: datetime | None = None
    snapshot: SourceSnapshot | None = None     # newest snapshot among the rows added

    def add(self, alloc: BudgetAllocation, snapshot: SourceSnapshot | None = None) -> None:
        self.budget_estimate += alloc.budget_estimate
        if alloc.revised_estimate is not None:
            self.revised_estimate = (self.revised_estimate or 0) + alloc.revised_estimate
        if alloc.is_capital:
            self.capital += alloc.budget_estimate
        else:
            self.revenue += alloc.budget_estimate
        self.capital_flags.add(bool(alloc.is_capital))
        self.sources.add(alloc.source)
        if alloc.last_updated and (self.updated is None or alloc.last_updated > self.updated):
            self.updated = alloc.last_updated
        if snapshot is not None and (self.snapshot is None or snapshot.id > self.snapshot.id):
            self.snapshot = snapshot

    @property
    def is_capital(self) -> bool | None:
        return next(iter(self.capital_flags)) if len(self.capital_flags) == 1 else None

    def figure(self, value: float, measure: str) -> Figure:
        snap = self.snapshot
        return Figure(value=value, source_type="live", label=live_label(self.sources), measure=measure,
                      source_url=snap.source_url if snap else None, snapshot_id=snap.id if snap else None,
                      fetched_at=snap.fetched_at if snap else self.updated)


async def load_live_allocations(
    db: AsyncSession, financial_year: str, department_ids: list[int] | None = None
) -> dict[int, LiveAllocation]:
    query = (
        select(BudgetAllocation, SourceSnapshot)
        .outerjoin(SourceSnapshot, BudgetAllocation.snapshot_id == SourceSnapshot.id)
        .where(BudgetAllocation.financial_year == financial_year)
    )
    if department_ids is not None:
        query = query.where(BudgetAllocation.department_id.in_(department_ids))
    out: dict[int, LiveAllocation] = {}
    for alloc, snapshot in (await db.execute(query)).all():
        out.setdefault(alloc.department_id, LiveAllocation()).add(alloc, snapshot)
    return out


async def load_live_spending(
    db: AsyncSession, financial_year: str, department_ids: list[int] | None = None
) -> dict[int, Figure]:
    """Sum of monthly utilised amounts per department. Departments without a figure are left out."""
    query = (
        select(
            Expenditure.department_id,
            func.sum(Expenditure.utilized_amount).label("total"),
            func.max(Expenditure.source).label("source"),
            func.max(Expenditure.created_at).label("updated"),
            func.max(Expenditure.snapshot_id).label("snapshot_id"),
        )
        .where(Expenditure.financial_year == financial_year)
        .group_by(Expenditure.department_id)
    )
    if department_ids is not None:
        query = query.where(Expenditure.department_id.in_(department_ids))
    rows = [r for r in (await db.execute(query)).all() if r.total is not None]
    snapshots = await load_snapshots(db, (r.snapshot_id for r in rows))
    out = {}
    for row in rows:
        snap = snapshots.get(row.snapshot_id)
        out[row.department_id] = Figure(
            value=float(row.total), source_type="live", label=live_label({row.source}), measure="utilized",
            source_url=snap.source_url if snap else None, snapshot_id=snap.id if snap else None,
            fetched_at=snap.fetched_at if snap else row.updated,
        )
    return out


# ── Per-department resolution ─────────────────────────────────────────────────

@dataclass(frozen=True)
class DepartmentFigures:
    allocated: Resolved
    revised: Resolved
    utilized: Resolved
    is_capital: bool | None

    @property
    def utilization_pct(self) -> float | None:
        return pct(self.utilized.value, self.allocated.value)

    def sources(self) -> dict[str, FigureSource]:
        return {
            "budget_estimate_lakhs": to_source(self.allocated),
            "revised_estimate_lakhs": to_source(self.revised),
            "utilized_lakhs": to_source(self.utilized),
        }


async def department_figures(
    db: AsyncSession, financial_year: str, view: View, department_ids: list[int] | None = None
) -> dict[int, DepartmentFigures]:
    """Resolved figures for every department that has any figure in `view` (or for `department_ids`)."""
    live_alloc = await load_live_allocations(db, financial_year, department_ids)
    live_spend = await load_live_spending(db, financial_year, department_ids)
    official = (await load_official_year(db, financial_year)).by_department

    if department_ids is not None:
        ids = set(department_ids)
    elif view is View.LIVE:
        ids = set(live_alloc)
    elif view is View.OFFICIAL:
        ids = set(official)
    else:
        ids = set(live_alloc) | set(official)

    no_official = f"No CAG Appropriation Accounts figure for {financial_year}"
    out: dict[int, DepartmentFigures] = {}
    for dept_id in ids:
        live = live_alloc.get(dept_id)
        off = official.get(dept_id)

        allocated = resolve(
            view,
            live.figure(float(live.budget_estimate), "budget_estimate") if live else None,
            off.figure(off.final_grant, "final_grant") if off else None,
            note=no_official if view is View.OFFICIAL else f"No allocation figure for {financial_year}",
        )
        utilized = resolve(
            view,
            live_spend.get(dept_id),
            off.figure(off.expenditure, "gross_expenditure") if off else None,
            note=no_official if view is View.OFFICIAL else f"No spending figure for {financial_year}",
        )
        revised = resolve(
            view,
            live.figure(float(live.revised_estimate), "revised_estimate")
            if live and live.revised_estimate is not None else None,
            None,
            note="The CAG accounts have no revised estimate" if view is View.OFFICIAL
            else f"No revised estimate for {financial_year}",
        )
        is_capital = live.is_capital if live and allocated.figure and allocated.figure.source_type == "live" else None
        out[dept_id] = DepartmentFigures(allocated, revised, utilized, is_capital)
    return out
