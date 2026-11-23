"""BaseCollector.run() reports SUCCESS only when real rows were written."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError, outcome_status
from database.models import Base, CollectorStatus, DataSyncLog


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_collector(body):
    class _Collector(BaseCollector):
        collector_name = "test_collector"

        def run_collection(self):
            body(self)

    return _Collector


def last_log(db) -> DataSyncLog:
    return db.execute(select(DataSyncLog).order_by(DataSyncLog.id.desc())).scalars().first()


@pytest.mark.parametrize(
    ("written", "skipped", "expected"),
    [
        (5, 0, CollectorStatus.SUCCESS),
        (5, 2, CollectorStatus.PARTIAL),
        (0, 0, CollectorStatus.PARTIAL),
        (0, 3, CollectorStatus.PARTIAL),
    ],
)
def test_outcome_status(written, skipped, expected):
    assert outcome_status(written, skipped) is expected


def test_rows_written_is_success(db):
    def body(c):
        c._records_fetched = 3
        c._records_inserted = 2
        c._records_updated = 1

    make_collector(body)(db).run()
    log = last_log(db)
    assert log.status is CollectorStatus.SUCCESS
    assert log.error_message is None


def test_zero_rows_is_partial_not_success(db):
    make_collector(lambda c: None)(db).run()
    log = last_log(db)
    assert log.status is CollectorStatus.PARTIAL
    assert "without writing any rows" in log.error_message


def test_skipped_rows_are_partial_and_recorded(db):
    def body(c):
        c._records_inserted = 4
        c.skip("district XYZ not in DB")

    make_collector(body)(db).run()
    log = last_log(db)
    assert log.status is CollectorStatus.PARTIAL
    assert "XYZ" in log.error_message
    assert log.extra_info["records_skipped"] == 1


def test_source_unavailable_is_no_source_and_does_not_raise(db):
    def body(c):
        raise SourceUnavailableError("portal requires a CAPTCHA")

    make_collector(body)(db).run()
    log = last_log(db)
    assert log.status is CollectorStatus.NO_SOURCE
    assert log.error_message == "portal requires a CAPTCHA"


def test_other_errors_are_failed_and_raise(db):
    def body(c):
        raise ValueError("table layout changed")

    with pytest.raises(ValueError):
        make_collector(body)(db).run()
    log = last_log(db)
    assert log.status is CollectorStatus.FAILED
    assert log.finished_at is not None


@pytest.mark.parametrize(
    "module_name, class_name",
    [
        ("collectors.pmay_collector", "PMAYCollector"),
        ("collectors.pfms_collector", "PFMSCollector"),
        ("collectors.tenders_collector", "TendersCollector"),
        ("collectors.dbt_collector", "DBTCollector"),
        ("collectors.cga_collector", "CGACollector"),
        ("collectors.cag_collector", "CAGCollector"),
    ],
)
def test_collectors_without_a_source_write_nothing(db, module_name, class_name):
    """These collectors used to invent numbers when their 'live' path failed."""
    import importlib

    from database.models import CAGFinding, DBTTransfer, Expenditure, SchemeProgress, Tender

    collector_class = getattr(importlib.import_module(module_name), class_name)
    collector_class(db).run()

    log = last_log(db)
    assert log.status is CollectorStatus.NO_SOURCE
    assert log.error_message
    for model in (SchemeProgress, DBTTransfer, Tender, Expenditure, CAGFinding):
        assert db.execute(select(model)).first() is None
