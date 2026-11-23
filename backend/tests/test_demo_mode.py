"""DEMO_MODE (todo.md 1.1): made-up allocations load only when asked, are flagged, and never reach production."""
import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import Settings
from database.connection import add_missing_columns
from database.demo_data import DEMO_ALLOCATIONS, DEMO_SOURCE, delete_demo_rows, seed_demo_allocations
from database.models import Base, BudgetAllocation, SourceSnapshot
from database.seeds import seed_departments


def test_demo_mode_is_off_by_default():
    assert Settings(_env_file=None).demo_mode is False


def test_demo_mode_refused_in_production():
    with pytest.raises(ValidationError, match="DEMO_MODE"):
        Settings(_env_file=None, demo_mode=True, app_env="production")
    assert Settings(_env_file=None, demo_mode=True, app_env="development").demo_mode is True


def test_seed_and_delete_demo_rows(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'demo.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            await seed_departments(db)
            expected = sum(len(b) for b in DEMO_ALLOCATIONS.values())
            assert await seed_demo_allocations(db, tmp_path) == expected
            assert await seed_demo_allocations(db, tmp_path) == 0   # idempotent
            await db.commit()
            rows = (await db.execute(select(BudgetAllocation))).scalars().all()
            assert len(rows) == expected
            assert all(r.is_demo and r.source == DEMO_SOURCE for r in rows)
            # demo rows point at a saved copy of the demo table, like every fact row (todo.md 1.4)
            snapshot = (await db.execute(select(SourceSnapshot))).scalar_one()
            assert {r.snapshot_id for r in rows} == {snapshot.id}
            assert b"NOT REAL" in (tmp_path / snapshot.storage_path).read_bytes()

            assert await delete_demo_rows(db) == expected
            await db.commit()
            assert (await db.execute(select(BudgetAllocation))).first() is None
            assert (await db.execute(select(SourceSnapshot))).first() is None
        await engine.dispose()

    asyncio.run(scenario())


def test_reference_seeding_adds_no_allocations(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ref.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine)() as db:
            await seed_departments(db)
            await db.commit()
            assert (await db.execute(select(BudgetAllocation))).first() is None
        await engine.dispose()

    asyncio.run(scenario())


def test_is_demo_column_added_to_an_existing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # simulate a database created before is_demo existed
        conn.execute(text("DROP INDEX ix_budget_allocations_is_demo"))
        conn.execute(text("ALTER TABLE budget_allocations DROP COLUMN is_demo"))
        conn.execute(text(
            "INSERT INTO departments (id, name, code, division) VALUES (1, 'PWD', 'PWD', 'CENTRAL')"
        ))
        conn.execute(text(
            "INSERT INTO source_snapshots (id, source_type, source_url, sha256, storage_path, byte_size, fetched_at) "
            "VALUES (1, 't', 'u', 'x', 'p', 1, '2026-11-22')"
        ))
        conn.execute(text(
            "INSERT INTO budget_allocations (department_id, financial_year, budget_estimate, snapshot_id) "
            "VALUES (1, '2024-25', 5, 1)"
        ))
    with engine.begin() as conn:
        assert "budget_allocations.is_demo" in add_missing_columns(conn)
        assert add_missing_columns(conn) == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT is_demo FROM budget_allocations")).scalar() in (0, False)
    indexes = {i["name"] for i in inspect(engine).get_indexes("budget_allocations")}
    assert "ix_budget_allocations_is_demo" in indexes
