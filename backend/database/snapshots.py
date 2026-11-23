"""
Raw snapshots (todo.md 1.4): every source document a figure comes from, saved byte for byte.

A snapshot is one fetched response (PDF, HTML or JSON) stored at
<raw_snapshot_dir>/<source_type>/<sha256><ext> with a `source_snapshots` row recording where and
when it was fetched and by which collector or loader. Fact rows point at it through `snapshot_id`,
so anyone can download the file (GET /api/v1/snapshots/{id}) and check its SHA-256.

The table is `source_snapshots`, not the `raw_snapshots` the roadmap first named: it already held
the CAG Appropriation Accounts PDFs and has the same fields.

Identical bytes are stored once: fetching a document again that hasn't changed returns the
existing row (its `fetched_at` stays the first fetch).
"""
from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import SourceSnapshot

_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/json": ".json",
    "text/html": ".html",
    "text/csv": ".csv",
    "text/plain": ".txt",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extension_for(content_type: str | None) -> str:
    media_type = (content_type or "").split(";")[0].strip().lower()
    return _EXTENSIONS.get(media_type) or mimetypes.guess_extension(media_type or "") or ".bin"


def snapshot_root(snapshot_dir: str | Path | None = None) -> Path:
    if snapshot_dir is not None:
        return Path(snapshot_dir)
    from config import get_settings

    return Path(get_settings().raw_snapshot_dir)


def write_snapshot_file(content: bytes, source_type: str, content_type: str | None,
                        snapshot_dir: str | Path | None = None) -> tuple[str, str]:
    """Write `content` under the snapshot directory (atomically, once). Returns (sha256, relative path)."""
    sha256 = sha256_hex(content)
    relative = Path(source_type) / f"{sha256}{extension_for(content_type)}"
    target = snapshot_root(snapshot_dir) / relative
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        tmp.write_bytes(content)
        tmp.replace(target)
    return sha256, relative.as_posix()


def save_snapshot(
    db: Session,
    content: bytes,
    *,
    source_url: str,
    source_type: str,
    content_type: str | None,
    collector_name: str | None = None,
    title: str | None = None,
    fetched_at: datetime | None = None,
    snapshot_dir: str | Path | None = None,
) -> SourceSnapshot:
    """
    Store `content` and return its snapshot row (flushed, so it has an id; the caller commits).
    The file is written before the row, so a row never points at a missing file.
    """
    sha256, relative = write_snapshot_file(content, source_type, content_type, snapshot_dir)
    snapshot = db.execute(select(SourceSnapshot).where(SourceSnapshot.sha256 == sha256)).scalar_one_or_none()
    if snapshot is None:
        snapshot = SourceSnapshot(
            source_type=source_type,
            collector_name=collector_name,
            title=title,
            source_url=source_url,
            sha256=sha256,
            storage_path=relative,
            content_type=content_type,
            byte_size=len(content),
            fetched_at=fetched_at or datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.flush()
    return snapshot


def snapshot_file(snapshot: SourceSnapshot, snapshot_dir: str | Path | None = None) -> Path:
    """Absolute path of a snapshot's stored file. Refuses a storage_path that escapes the directory."""
    root = snapshot_root(snapshot_dir).resolve()
    path = (root / snapshot.storage_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"snapshot {snapshot.id} storage_path escapes the snapshot directory")
    return path
