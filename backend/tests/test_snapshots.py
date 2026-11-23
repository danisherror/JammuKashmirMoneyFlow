"""Raw snapshots (todo.md 1.4): saved byte for byte, deduplicated by SHA-256, recorded with their collector."""
import hashlib

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector
from database.models import Base, CollectorStatus, DataSyncLog, SourceSnapshot
from database.snapshots import extension_for, save_snapshot, snapshot_file

URL = "https://ejalshakti.gov.in/jjmreport/api/example"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_save_snapshot_stores_the_exact_bytes_once(db, tmp_path):
    content = b'{"districts": []}'
    first = save_snapshot(db, content, source_url=URL, source_type="jjm_collector",
                          content_type="application/json; charset=utf-8", collector_name="jjm_collector",
                          snapshot_dir=tmp_path)
    again = save_snapshot(db, content, source_url=URL + "?again", source_type="jjm_collector",
                          content_type="application/json", collector_name="jjm_collector", snapshot_dir=tmp_path)
    assert again.id == first.id
    assert first.sha256 == hashlib.sha256(content).hexdigest()
    assert first.storage_path == f"jjm_collector/{first.sha256}.json"
    assert first.collector_name == "jjm_collector" and first.byte_size == len(content)
    stored = snapshot_file(first, tmp_path)
    assert stored.read_bytes() == content
    assert len(db.execute(select(SourceSnapshot)).all()) == 1


def test_extension_for():
    assert extension_for("text/html; charset=utf-8") == ".html"
    assert extension_for("application/pdf") == ".pdf"
    assert extension_for(None) == ".bin"


def test_snapshot_file_refuses_paths_outside_the_directory(tmp_path):
    bad = SourceSnapshot(id=1, storage_path="../../etc/passwd")
    with pytest.raises(ValueError):
        snapshot_file(bad, tmp_path)


class EchoCollector(BaseCollector):
    collector_name = "echo_collector"

    def __init__(self, db, response, snapshot_dir):
        super().__init__(db)
        self.response = response
        self.snapshot_dir = str(snapshot_dir)

    def run_collection(self):
        self.snapshot(self.response, title="echo")
        self._records_inserted = 1


def test_collector_snapshot_is_logged_with_the_run(db, tmp_path):
    response = httpx.Response(
        200, content=b"<html>table</html>", headers={"content-type": "text/html"},
        request=httpx.Request("GET", URL),
    )
    EchoCollector(db, response, tmp_path).run()

    snapshot = db.execute(select(SourceSnapshot)).scalar_one()
    assert (snapshot.collector_name, snapshot.source_type, snapshot.source_url) == ("echo_collector",) * 2 + (URL,)
    assert snapshot_file(snapshot, tmp_path).read_bytes() == b"<html>table</html>"
    log = db.execute(select(DataSyncLog)).scalar_one()
    assert log.status is CollectorStatus.SUCCESS
    assert log.extra_info["snapshot_ids"] == [snapshot.id]
