"""
J&K Public Money Flow Tracker — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import get_settings
from database.connection import init_db, seed_reference_data
from scheduler.jobs import create_scheduler
from api.routes import budget, schemes, districts, alerts

settings = get_settings()
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("Starting J&K Money Flow API...")
    await init_db()
    await seed_reference_data()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="J&K Public Money Flow API",
    description="Tracks how public funds are allocated and spent across J&K UT",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(budget.router, prefix="/api/v1")
app.include_router(schemes.router, prefix="/api/v1")
app.include_router(districts.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
