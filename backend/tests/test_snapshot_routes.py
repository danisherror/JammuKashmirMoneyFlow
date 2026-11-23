"""GET /api/v1/snapshots/{id}: the stored file, byte for byte, checked against its SHA-256 (todo.md 1.4)."""
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from api.routes import snapshots
from config import get_settings
from database.connection import get_db
from database.models import Base
from database.snapshots import save_snapshot, snapshot_file

URL = "https://cag.gov.in/uploads/example.pdf"
CONTENT = b"%PDF-1.7 example"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "raw_snapshot_dir", str(tmp_path / "snapshots"))
    path = tmp_path / "db.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        snapshot = save_snapshot(db, CONTENT, source_url=URL, source_type="appropriation_accounts",
                                 content_type="application/pdf", collector_name="appropriation_accounts_loader",
                                 title="Appropriation Accounts 2022-23")
        db.commit()
        ids = {"snapshot": snapshot.id}
        stored = snapshot_file(snapshot)

    sessions = async_sessionmaker(create_async_engine(f"sqlite+aiosqlite:///{path}"), expire_on_commit=False)

    async def override_db():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(snapshots.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c, ids["snapshot"], stored
    engine.dispose()


def test_download_returns_the_exact_bytes(client):
    c, snapshot_id, _ = client
    response = c.get(f"/api/v1/snapshots/{snapshot_id}")
    assert response.status_code == 200
    assert response.content == CONTENT
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert "attachment" in response.headers["content-disposition"]


def test_meta(client):
    c, snapshot_id, _ = client
    meta = c.get(f"/api/v1/snapshots/{snapshot_id}/meta").json()
    assert meta["source_url"] == URL
    assert meta["collector_name"] == "appropriation_accounts_loader"
    assert meta["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    assert meta["byte_size"] == len(CONTENT)
    assert meta["download_url"] == f"/api/v1/snapshots/{snapshot_id}"


def test_unknown_snapshot_is_404(client):
    c, _, _ = client
    assert c.get("/api/v1/snapshots/999").status_code == 404
    assert c.get("/api/v1/snapshots/999/meta").status_code == 404


def test_missing_file_is_404(client):
    c, snapshot_id, stored = client
    stored.unlink()
    assert c.get(f"/api/v1/snapshots/{snapshot_id}").status_code == 404


def test_tampered_file_is_refused(client):
    c, snapshot_id, stored = client
    stored.write_bytes(b"%PDF-1.7 altered")
    response = c.get(f"/api/v1/snapshots/{snapshot_id}")
    assert response.status_code == 500
    assert "SHA-256" in response.json()["detail"]
