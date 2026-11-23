"""
Raw snapshot downloads (todo.md 1.4)
GET /api/v1/snapshots/{id}        the stored source document, byte for byte
GET /api/v1/snapshots/{id}/meta   where and when it was fetched, and its SHA-256

Every figure's `snapshot_id` (FigureSource, row schemas) leads here, so anyone can fetch the exact
file a number came from and check it against the published hash.
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import SnapshotInfo
from database.connection import get_db
from database.models import SourceSnapshot
from database.snapshots import extension_for, snapshot_file

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])


def snapshot_info(snapshot: SourceSnapshot) -> SnapshotInfo:
    return SnapshotInfo(
        id=snapshot.id,
        source_type=snapshot.source_type,
        collector_name=snapshot.collector_name,
        title=snapshot.title,
        source_url=snapshot.source_url,
        fetched_at=snapshot.fetched_at,
        sha256=snapshot.sha256,
        content_type=snapshot.content_type,
        byte_size=snapshot.byte_size,
        download_url=f"/api/v1/snapshots/{snapshot.id}",
    )


async def _get(db: AsyncSession, snapshot_id: int) -> SourceSnapshot:
    snapshot = await db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.get("/{snapshot_id}/meta", response_model=SnapshotInfo)
async def get_snapshot_meta(snapshot_id: int, db: AsyncSession = Depends(get_db)):
    return snapshot_info(await _get(db, snapshot_id))


@router.get(
    "/{snapshot_id}",
    response_class=FileResponse,
    responses={
        200: {"description": "The stored file; its SHA-256 is in the X-Content-SHA256 header"},
        404: {"description": "No such snapshot, or its file is missing from storage"},
        500: {"description": "The stored file no longer matches its recorded SHA-256"},
    },
)
async def download_snapshot(snapshot_id: int, db: AsyncSession = Depends(get_db)):
    """
    The raw file. Its SHA-256 is checked before it is served, so a corrupted or replaced file is
    never passed off as the original.
    """
    snapshot = await _get(db, snapshot_id)
    try:
        path = snapshot_file(snapshot)
    except ValueError:
        raise HTTPException(status_code=500, detail="Snapshot storage path is invalid")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot file is missing from storage")

    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != snapshot.sha256:
        raise HTTPException(status_code=500, detail="Stored file does not match its recorded SHA-256")

    return FileResponse(
        path,
        media_type=snapshot.content_type or "application/octet-stream",
        filename=f"{snapshot.source_type}-{snapshot.sha256[:12]}{extension_for(snapshot.content_type)}",
        headers={"X-Content-SHA256": snapshot.sha256},
    )
