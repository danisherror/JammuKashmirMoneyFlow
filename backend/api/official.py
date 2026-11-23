"""
Official figures from the grant pages and Appendix II of the CAG Appropriation Accounts.

`api.figures` covers the summary table (one final grant and gross expenditure per grant). This
module reads the tables filled by the same loader from the rest of each PDF:
  * appropriation_section_blocks  → the original → final grant → spent chain,
  * appropriation_recoveries      → recoveries and net expenditure,
  * appropriation_head_lines, _notes, _major_heads, _document_issues → the per-grant breakdown.
Amounts are stored in ₹ thousand and returned in ₹ lakhs (÷ 100, exact to two decimals).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.figures import lakhs_from_thousand, pages_label
from api.schemas import (
    AccountabilityFlag,
    DocumentIssueItem,
    FigureSource,
    GrantBreakdown,
    GrantInfo,
    HeadNode,
    HeadPathPart,
    HeadRowItem,
    NoteItem,
    OfficialChain,
    SectionBlockItem,
)
from database.models import (
    AppropriationAccountLine,
    AppropriationDocumentIssue,
    AppropriationHeadLine,
    AppropriationNote,
    AppropriationRecovery,
    AppropriationSectionBlock,
    GrantDepartmentMap,
    SourceSnapshot,
)
from processors.accountability import Flag, accountability_flags


def _lakhs(thousand: int | None) -> float | None:
    return None if thousand is None else lakhs_from_thousand(thousand)


async def latest_detail_year(db: AsyncSession) -> str | None:
    """Newest financial year with grant pages loaded ("2023-24" sorts after "2022-23")."""
    return await db.scalar(select(func.max(AppropriationSectionBlock.financial_year)))


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


# ── Grants and breakdown ──────────────────────────────────────────────────────

async def list_grants(db: AsyncSession, financial_year: str) -> list[GrantInfo]:
    """Every grant in the year's summary table, with its mapped department (if any) and totals."""
    rows = (await db.execute(
        select(
            AppropriationAccountLine.grant_no,
            func.max(AppropriationAccountLine.grant_name_raw).label("name"),
            func.sum(AppropriationAccountLine.final_grant_thousand).label("final_grant"),
            func.sum(AppropriationAccountLine.gross_expenditure_thousand).label("expenditure"),
            func.min(AppropriationAccountLine.page).label("page"),
            func.max(AppropriationAccountLine.snapshot_id).label("snapshot_id"),
        )
        .where(AppropriationAccountLine.financial_year == financial_year)
        .group_by(AppropriationAccountLine.grant_no)
        .order_by(AppropriationAccountLine.grant_no)
    )).all()
    mapped = dict((await db.execute(
        select(GrantDepartmentMap.grant_no, GrantDepartmentMap.department_id)
        .where(GrantDepartmentMap.financial_year == financial_year)
    )).all())
    snapshot_ids = {r.snapshot_id for r in rows}
    snapshots = {
        snap.id: snap for snap in (await db.execute(
            select(SourceSnapshot).where(SourceSnapshot.id.in_(snapshot_ids))
        )).scalars()
    } if snapshot_ids else {}
    return [
        GrantInfo(
            grant_no=r.grant_no,
            name=r.name,
            department_id=mapped.get(r.grant_no),
            final_grant_lakhs=_lakhs(r.final_grant),
            gross_expenditure_lakhs=_lakhs(r.expenditure),
            source=_page_source(snapshots[r.snapshot_id], financial_year, r.page, "final_grant")
            if r.snapshot_id in snapshots else None,
        )
        for r in rows
    ]


def _page_source(snapshot: SourceSnapshot, year: str, page: int, measure: str | None = None) -> FigureSource:
    return FigureSource(
        source_type="official",
        label=f"Official · Appropriation Accounts {year}, p.{page}",
        measure=measure,
        source_url=snapshot.source_url,
        snapshot_id=snapshot.id,
        page=page,
        fetched_at=snapshot.fetched_at,
    )


def head_row_item(line: AppropriationHeadLine, snapshot: SourceSnapshot) -> HeadRowItem:
    return HeadRowItem(
        grant_no=line.grant_no,
        section=line.section,
        kind=line.kind,
        note_number=line.note_number,
        category=line.category,
        reasons_not_communicated=line.reasons_not_communicated,
        head_code=line.head_code,
        head_name=line.head_name,
        head_path=[HeadPathPart(**part) for part in line.head_path],
        original_lakhs=_lakhs(line.original_thousand),
        supplementary_lakhs=_lakhs(line.supplementary_thousand),
        reappropriation_lakhs=_lakhs(line.reappropriation_thousand),
        final_grant_lakhs=_lakhs(line.final_grant_thousand),
        expenditure_lakhs=_lakhs(line.expenditure_thousand),
        saving_lakhs=_lakhs(line.saving_thousand),
        excess_lakhs=_lakhs(line.excess_thousand),
        remark=line.remark,
        printed_error=line.printed_error,
        source=_page_source(snapshot, line.financial_year, line.page, f"note {line.note_number} ({line.category})"),
    )


def build_tree(rows: list[HeadRowItem]) -> list[HeadNode]:
    """Nest rows by their head path, keeping the order in which heads first appear in the PDF."""
    roots: list[HeadNode] = []
    index: dict[tuple[int, str, str], HeadNode] = {}
    for row in rows:
        siblings = roots
        codes: list[str] = []
        node: HeadNode | None = None
        for part in row.head_path:
            codes.append(part.code)
            key = (row.grant_no, row.section, ".".join(codes))
            node = index.get(key)
            if node is None:
                node = HeadNode(
                    level=part.level, code=part.code, name=part.name, head_code=key[2],
                    section=row.section, grant_no=row.grant_no, rows=[], children=[],
                )
                index[key] = node
                siblings.append(node)
            siblings = node.children
        if node is not None:
            node.rows.append(row)
    return roots


async def grant_breakdown(
    db: AsyncSession, financial_year: str, grants: list[int], department_id: int | None = None
) -> GrantBreakdown:
    infos = [g for g in await list_grants(db, financial_year) if g.grant_no in set(grants)]
    empty = GrantBreakdown(
        financial_year=financial_year, department_id=department_id, grants=infos,
        section_blocks=[], tree=[], notes=[], issues=[],
    )
    if not grants:
        return empty.model_copy(update={"note": f"No CAG grant is mapped to this department for {financial_year}"})

    blocks = (await db.execute(
        select(AppropriationSectionBlock, SourceSnapshot)
        .join(SourceSnapshot, AppropriationSectionBlock.snapshot_id == SourceSnapshot.id)
        .where(AppropriationSectionBlock.financial_year == financial_year,
               AppropriationSectionBlock.grant_no.in_(grants))
        .order_by(AppropriationSectionBlock.grant_no, AppropriationSectionBlock.id)
    )).all()
    if not blocks:
        return empty.model_copy(update={"note": f"No grant pages loaded for {financial_year}"})

    flags = await grant_flags(db, financial_year, grants, infos)
    head_rows = (await db.execute(
        select(AppropriationHeadLine, SourceSnapshot)
        .join(SourceSnapshot, AppropriationHeadLine.snapshot_id == SourceSnapshot.id)
        .where(AppropriationHeadLine.financial_year == financial_year,
               AppropriationHeadLine.grant_no.in_(grants))
        .order_by(AppropriationHeadLine.grant_no, AppropriationHeadLine.id)
    )).all()
    notes = (await db.execute(
        select(AppropriationNote, SourceSnapshot)
        .join(SourceSnapshot, AppropriationNote.snapshot_id == SourceSnapshot.id)
        .where(AppropriationNote.financial_year == financial_year, AppropriationNote.grant_no.in_(grants))
        .order_by(AppropriationNote.grant_no, AppropriationNote.number)
    )).all()
    issues = (await db.execute(
        select(AppropriationDocumentIssue)
        .where(AppropriationDocumentIssue.financial_year == financial_year,
               AppropriationDocumentIssue.grant_no.in_(grants))
        .order_by(AppropriationDocumentIssue.id)
    )).scalars().all()

    return GrantBreakdown(
        financial_year=financial_year,
        department_id=department_id,
        grants=infos,
        section_blocks=[
            SectionBlockItem(
                grant_no=b.grant_no, section=b.section, kind=b.kind,
                original_lakhs=lakhs_from_thousand(b.original_thousand),
                supplementary_lakhs=lakhs_from_thousand(b.supplementary_thousand),
                reappropriation_lakhs=lakhs_from_thousand(b.reappropriation_thousand),
                final_grant_lakhs=lakhs_from_thousand(b.final_grant_thousand),
                expenditure_lakhs=lakhs_from_thousand(b.expenditure_thousand),
                saving_lakhs=lakhs_from_thousand(b.saving_thousand),
                excess_lakhs=lakhs_from_thousand(b.excess_thousand),
                surrendered_lakhs=lakhs_from_thousand(b.surrendered_thousand),
                source=_page_source(snap, financial_year, b.page, "section block"),
            )
            for b, snap in blocks
        ],
        tree=build_tree([head_row_item(line, snap) for line, snap in head_rows]),
        notes=[
            NoteItem(
                grant_no=n.grant_no, number=n.number, section=n.section, kind=n.kind, category=n.category,
                reasons_not_communicated=n.reasons_not_communicated, text=n.text,
                source=_page_source(snap, financial_year, n.page, "note"),
            )
            for n, snap in notes
        ],
        issues=[DocumentIssueItem(grant_no=i.grant_no, kind=i.kind, page=i.page, text=i.text) for i in issues],
        flags=flags,
    )


# ── Accountability flags ──────────────────────────────────────────────────────

async def grant_flags(
    db: AsyncSession, financial_year: str, grants: list[int] | None = None, infos: list[GrantInfo] | None = None
) -> list[AccountabilityFlag]:
    """Flags for `grants` (every grant when None), each with its PDF page as the source."""
    block_query = (
        select(AppropriationSectionBlock, SourceSnapshot)
        .join(SourceSnapshot, AppropriationSectionBlock.snapshot_id == SourceSnapshot.id)
        .where(AppropriationSectionBlock.financial_year == financial_year)
    )
    head_query = select(AppropriationHeadLine).where(AppropriationHeadLine.financial_year == financial_year)
    if grants is not None:
        block_query = block_query.where(AppropriationSectionBlock.grant_no.in_(grants))
        head_query = head_query.where(AppropriationHeadLine.grant_no.in_(grants))
    blocks = (await db.execute(block_query)).all()
    if not blocks:
        return []
    snapshot = blocks[0][1]
    heads = (await db.execute(head_query)).scalars().all()
    names = {g.grant_no: g for g in (infos if infos is not None else await list_grants(db, financial_year))}

    def item(flag: Flag) -> AccountabilityFlag:
        info = names.get(flag.grant_no)
        pages = set(flag.pages) or {flag.page}
        return AccountabilityFlag(
            kind=flag.kind,
            financial_year=financial_year,
            grant_no=flag.grant_no,
            grant_name=info.name if info else f"Grant {flag.grant_no}",
            department_id=info.department_id if info else None,
            section=flag.section,
            block_kind=flag.block_kind,
            head_code=flag.head_code,
            head_name=flag.head_name,
            amount_lakhs=_lakhs(flag.amount_thousand),
            share_pct=flag.share_pct,
            detail=flag.detail,
            source=FigureSource(
                source_type="official",
                label=f"Official · Appropriation Accounts {financial_year}, {pages_label(pages)}",
                measure=flag.kind,
                source_url=snapshot.source_url,
                snapshot_id=snapshot.id,
                page=flag.page,
                fetched_at=snapshot.fetched_at,
            ),
        )

    return [item(f) for f in accountability_flags([b for b, _ in blocks], heads)]
