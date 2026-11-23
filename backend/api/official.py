"""
Official figures from the grant pages and Appendix II of the CAG Appropriation Accounts.

`api.figures` covers the summary table (one final grant and gross expenditure per grant). This
module reads the tables filled by the same loader from the rest of each PDF:
  * appropriation_section_blocks  → the original → final grant → spent chain,
  * appropriation_recoveries      → recoveries and net expenditure.
Amounts are stored in ₹ thousand and returned in ₹ lakhs (÷ 100, exact to two decimals).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.figures import lakhs_from_thousand, pages_label
from api.schemas import FigureSource, OfficialChain
from database.models import (
    AppropriationRecovery,
    AppropriationSectionBlock,
    GrantDepartmentMap,
    SourceSnapshot,
)


async def department_grants(db: AsyncSession, financial_year: str, department_id: int) -> list[int]:
    rows = await db.execute(
        select(GrantDepartmentMap.grant_no).where(
            GrantDepartmentMap.financial_year == financial_year,
            GrantDepartmentMap.department_id == department_id,
        )
    )
    return sorted(rows.scalars())


@dataclass
class _Sum:
    thousand: int = 0
    pages: set[int] = field(default_factory=set)

    def add(self, amount: int, page: int) -> None:
        self.thousand += amount
        self.pages.add(page)


_BLOCK_FIELDS = {
    # chain field → (model column, measure)
    "original_lakhs": ("original_thousand", "original_grant"),
    "supplementary_lakhs": ("supplementary_thousand", "supplementary_grant"),
    "reappropriation_lakhs": ("reappropriation_thousand", "reappropriation"),
    "final_grant_lakhs": ("final_grant_thousand", "final_grant"),
    "surrendered_lakhs": ("surrendered_thousand", "surrendered"),
    "gross_expenditure_lakhs": ("expenditure_thousand", "gross_expenditure"),
    "saving_lakhs": ("saving_thousand", "saving"),
    "excess_lakhs": ("excess_thousand", "excess"),
}


def _source(snapshot: SourceSnapshot, year: str, pages: set[int], measure: str, where: str) -> FigureSource:
    return FigureSource(
        source_type="official",
        label=f"Official · Appropriation Accounts {year}, {where} {pages_label(pages)}",
        measure=measure,
        source_url=snapshot.source_url,
        snapshot_id=snapshot.id,
        page=min(pages),
        fetched_at=snapshot.fetched_at,
    )


async def official_chain(
    db: AsyncSession, financial_year: str, grants: list[int] | None = None
) -> OfficialChain | None:
    """The chain summed over `grants` (every grant when None). None when no grant pages are loaded."""
    query = (
        select(AppropriationSectionBlock, SourceSnapshot)
        .join(SourceSnapshot, AppropriationSectionBlock.snapshot_id == SourceSnapshot.id)
        .where(AppropriationSectionBlock.financial_year == financial_year)
    )
    if grants is not None:
        query = query.where(AppropriationSectionBlock.grant_no.in_(grants))
    blocks = (await db.execute(query)).all()
    if not blocks:
        return None

    snapshot = blocks[0][1]
    sums = {name: _Sum() for name in _BLOCK_FIELDS}
    for block, _ in blocks:
        for name, (column, _measure) in _BLOCK_FIELDS.items():
            sums[name].add(getattr(block, column), block.page)

    query = select(AppropriationRecovery).where(AppropriationRecovery.financial_year == financial_year)
    if grants is not None:
        query = query.where(AppropriationRecovery.grant_no.in_(grants))
    recovery_rows = (await db.execute(query)).scalars().all()
    # Appendix II lists only grants with recoveries in some years: a grant missing from it had none,
    # but only if Appendix II was loaded for the year at all.
    appendix_loaded = bool(recovery_rows) or bool(
        (await db.execute(
            select(AppropriationRecovery.id).where(AppropriationRecovery.financial_year == financial_year).limit(1)
        )).first()
    )

    sources = {
        name: _source(snapshot, financial_year, sums[name].pages, measure, "grant pages")
        for name, (_column, measure) in _BLOCK_FIELDS.items()
    }
    recoveries = estimate = net = None
    if appendix_loaded:
        actual = _Sum()
        planned = _Sum()
        for row in recovery_rows:
            actual.add(row.actual_thousand, row.actuals_page)
            planned.add(row.budget_estimate_thousand, row.page)
        recoveries = lakhs_from_thousand(actual.thousand)
        estimate = lakhs_from_thousand(planned.thousand)
        net = lakhs_from_thousand(sums["gross_expenditure_lakhs"].thousand - actual.thousand)
        if recovery_rows:
            sources["recoveries_lakhs"] = _source(snapshot, financial_year, actual.pages, "recoveries", "Appendix II,")
            sources["recoveries_estimate_lakhs"] = _source(
                snapshot, financial_year, planned.pages, "recoveries_estimate", "Appendix II,"
            )
            sources["net_expenditure_lakhs"] = _source(
                snapshot, financial_year, sums["gross_expenditure_lakhs"].pages | actual.pages,
                "net_expenditure", "grant pages and Appendix II,",
            )
        else:
            none_listed = FigureSource(
                source_type="official",
                label=f"Official · Appropriation Accounts {financial_year}: no recoveries listed in Appendix II",
                measure="recoveries",
                source_url=snapshot.source_url,
                snapshot_id=snapshot.id,
                fetched_at=snapshot.fetched_at,
            )
            sources["recoveries_lakhs"] = none_listed
            sources["recoveries_estimate_lakhs"] = none_listed.model_copy(update={"measure": "recoveries_estimate"})
            sources["net_expenditure_lakhs"] = sources["gross_expenditure_lakhs"].model_copy(
                update={"measure": "net_expenditure"}
            )
    else:
        missing = FigureSource(source_type=None, label=f"Appendix II for {financial_year} is not loaded")
        sources.update(recoveries_lakhs=missing, recoveries_estimate_lakhs=missing, net_expenditure_lakhs=missing)

    return OfficialChain(
        financial_year=financial_year,
        grants=sorted({block.grant_no for block, _ in blocks}),
        **{name: lakhs_from_thousand(s.thousand) for name, s in sums.items()},
        recoveries_lakhs=recoveries,
        recoveries_estimate_lakhs=estimate,
        net_expenditure_lakhs=net,
        sources=sources,
    )
