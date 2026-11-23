"""
Provenance for figures read from the fact tables (todo.md 1.4): every row has a snapshot_id, and
the API reports it as a FigureSource (source URL, fetch time, snapshot id and download link).

Aggregates (sums over districts or schemes) report the most recently saved snapshot (highest id)
among the rows they add up; the label says how many snapshots were combined.
"""
from __future__ import annotations

from typing import Iterable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import FigureSource
from database.models import SourceSnapshot


def snapshot_label(snapshot: SourceSnapshot, source_type: str = "live") -> str:
    prefix = "Official" if source_type == "official" else "Live"
    return f"{prefix} · {snapshot.title or snapshot.source_type}"


def snapshot_source(
    snapshot: SourceSnapshot | None,
    *,
    measure: str | None = None,
    source_type: Literal["live", "official"] = "live",
    label: str | None = None,
    combined: int = 1,
) -> FigureSource | None:
    """FigureSource for a figure read from `snapshot`; None when there is no snapshot."""
    if snapshot is None:
        return None
    text = label or snapshot_label(snapshot, source_type)
    if combined > 1:
        text += f" (most recently saved of {combined} snapshots)"
    return FigureSource(
        source_type=source_type,
        label=text,
        measure=measure,
        source_url=snapshot.source_url,
        snapshot_id=snapshot.id,
        fetched_at=snapshot.fetched_at,
        provisional=source_type == "live",
    )


async def load_snapshots(db: AsyncSession, ids: Iterable[int | None]) -> dict[int, SourceSnapshot]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db.execute(select(SourceSnapshot).where(SourceSnapshot.id.in_(wanted)))).scalars()
    return {s.id: s for s in rows}


def newest_id(ids: Iterable[int | None]) -> int | None:
    """Highest snapshot id (the most recently saved), ignoring rows saved before snapshots existed."""
    return max((i for i in ids if i is not None), default=None)
