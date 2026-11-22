from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
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
async def init_db():
    logger.info("Initializing database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
