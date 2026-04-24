"""
APScheduler job definitions.
All collector jobs live here. Scheduler is started inside FastAPI lifespan.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import get_settings
from database.connection import SyncSessionLocal
from collectors.mgnrega_collector import MGNREGACollector
from collectors.jjm_collector import JJMCollector
from processors.gap_calculator import recalculate_all_gaps

settings = get_settings()


def run_mgnrega():
    """Daily job: fetch MGNREGA J&K data from nreganarayan.nic.in"""
    logger.info("⏰ Scheduler: Starting MGNREGA collection")
    db = SyncSessionLocal()
    try:
        collector = MGNREGACollector(db)
        collector.run()
        recalculate_all_gaps(db)
    finally:
        db.close()


def run_jjm():
    """Daily job: fetch JJM J&K data from ejalshakti.gov.in"""
    logger.info("⏰ Scheduler: Starting JJM collection")
    db = SyncSessionLocal()
    try:
        collector = JJMCollector(db)
        collector.run()
        recalculate_all_gaps(db)
    finally:
        db.close()


def run_all_daily():
    """
    Master daily job — runs all daily collectors in sequence.
    Runs at 6:00 AM IST (00:30 UTC).
    """
    logger.info("⏰ Scheduler: Running ALL daily collectors")
    run_mgnrega()
    run_jjm()
    # Phase 2 collectors will be added here:
    # run_pmay()
    # run_dbt()


def create_scheduler() -> BackgroundScheduler:
    """
    Build and return a configured APScheduler instance.
    Called once during FastAPI startup.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    if not settings.scheduler_enabled:
        logger.warning("Scheduler is DISABLED (SCHEDULER_ENABLED=false). No auto-updates.")
        return scheduler

    # ── Daily jobs (6:00 AM IST) ──────────────────────────────────────────────
    scheduler.add_job(
        run_all_daily,
        trigger=CronTrigger(hour=settings.mgnrega_fetch_hour, minute=0, timezone="Asia/Kolkata"),
        id="daily_all_collectors",
        name="Daily: All Collectors",
        replace_existing=True,
        misfire_grace_time=3600,    # if missed, run within 1 hour
    )

    # ── Individual jobs (can be triggered manually via API too) ───────────────
    scheduler.add_job(
        run_mgnrega,
        id="mgnrega_manual",
        name="MGNREGA Collector",
        replace_existing=True,
    )

    scheduler.add_job(
        run_jjm,
        id="jjm_manual",
        name="JJM Collector",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler configured. Daily run at {settings.mgnrega_fetch_hour}:00 IST. "
        f"Jobs: {[j.name for j in scheduler.get_jobs()]}"
    )
    return scheduler
