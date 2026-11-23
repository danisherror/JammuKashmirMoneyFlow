"""Test helpers for fact rows, which all need a snapshot_id (todo.md 1.4)."""
import hashlib
from datetime import datetime, timezone

from sqlalchemy import MetaData

from database.models import Base, SourceSnapshot

FETCHED = datetime(2026, 11, 22, 6, 0, tzinfo=timezone.utc)


def make_snapshot(db, name: str = "test", url: str | None = None) -> SourceSnapshot:
    """A snapshot row (no file on disk) to hang hand-made fact rows on."""
    sha = hashlib.sha256(name.encode()).hexdigest()
    snapshot = SourceSnapshot(
        source_type=name, collector_name=name, title=f"Test document {name}",
        source_url=url or f"https://example.gov.in/{name}", sha256=sha, storage_path=f"{name}/{sha}.json",
        content_type="application/json", byte_size=1, fetched_at=FETCHED,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def legacy_metadata() -> MetaData:
    """The schema as an old database has it: snapshot_id columns added as nullable, with NULL rows."""
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        copy = table.to_metadata(metadata)
        if "snapshot_id" in copy.c and table.name not in {
            t.name for t in Base.metadata.sorted_tables if t.name.startswith("appropriation_")
        }:
            copy.c.snapshot_id.nullable = True
    return metadata
