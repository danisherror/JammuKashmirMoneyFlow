from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import Enum as SAEnum, create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from loguru import logger

from config import get_settings
from database.models import Base

settings = get_settings()

# ── Async engine (used by FastAPI request handlers) ───────────────────────────
async_engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,           # test connection before using from pool
    echo=settings.sql_echo,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (used by collectors / APScheduler jobs) ──────────────────────
sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.sql_echo,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)


# ── Dependency for FastAPI routes ─────────────────────────────────────────────
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Sync session context manager for collectors ───────────────────────────────
@asynccontextmanager
async def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Create all tables (called on startup) ─────────────────────────────────────
def add_missing_enum_values(sync_conn) -> list[str]:
    """
    create_all creates Postgres enum types but never adds a value to one that
    already exists, so a database created before e.g. CollectorStatus.PARTIAL
    would reject the new status. Add any missing labels. Remove this once
    Alembic manages the schema (todo.md 3.1).

    Postgres 12+ allows ALTER TYPE ... ADD VALUE inside a transaction as long
    as the new value isn't used in the same transaction:
    https://www.postgresql.org/docs/16/sql-altertype.html (Notes)
    """
    if sync_conn.dialect.name != "postgresql":
        return []
    added, seen = [], set()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            enum_type = column.type
            if not isinstance(enum_type, SAEnum) or not enum_type.name or enum_type.name in seen:
                continue
            seen.add(enum_type.name)
            existing = set(sync_conn.execute(
                text(
                    "SELECT e.enumlabel FROM pg_enum e "
                    "JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :name"
                ),
                {"name": enum_type.name},
            ).scalars())
            if not existing:
                continue   # type doesn't exist yet; create_all makes it with every label
            for label in enum_type.enums:
                if label not in existing:
                    quoted = label.replace("'", "''")
                    sync_conn.execute(text(f'ALTER TYPE "{enum_type.name}" ADD VALUE IF NOT EXISTS \'{quoted}\''))
                    added.append(f"{enum_type.name}.{label}")
    return added


async def init_db():
    logger.info("Initializing database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        added = await conn.run_sync(add_missing_enum_values)
    if added:
        logger.info(f"Added enum values: {', '.join(added)}")
    logger.info("Database tables ready.")


# ── Seed reference data (departments, districts, schemes) ─────────────────────
async def seed_reference_data():
    """
    Insert static reference data that doesn't come from scrapers.
    Safe to call multiple times — uses INSERT OR IGNORE logic.
    """
    from database.seeds import seed_departments, seed_districts, seed_schemes, seed_grant_department_map
    async with AsyncSessionLocal() as db:
        await seed_departments(db)
        await seed_districts(db)
        await seed_schemes(db)
        await seed_grant_department_map(db)
        await db.commit()
    logger.info("Reference data seeded.")
