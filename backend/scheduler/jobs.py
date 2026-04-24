"""
APScheduler job definitions.
Each collector job runs independently — a failure in one does NOT
affect others. Failures are logged to data_sync_log so the
/alerts/sync-status endpoint can surface them to the dashboard.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import get_settings
from database.connection import SyncSessionLocal
from collectors.mgnrega_collector import MGNREGACollector
from collectors.jjm_collector import JJMCollector
from collectors.pmay_collector import PMAYCollector
from collectors.dbt_collector import DBTCollector
from collectors.tenders_collector import TendersCollector
from collectors.cga_collector import CGACollector
from collectors.cag_collector import CAGCollector
from collectors.pfms_collector import PFMSCollector
from processors.gap_calculator import recalculate_all_gaps

settings = get_settings()


def _run_collector(collector_class, **kwargs):
    """
    Helper that opens a DB session, runs the collector, recalculates gaps,
    and always closes the session — even on exception.
    The collector's own run() method handles logging to data_sync_log.
    """
    db = SyncSessionLocal()
    try:
        collector = collector_class(db, **kwargs)
        collector.run()         # raises on failure; run() writes FAILED to sync_log
        recalculate_all_gaps(db)
    except Exception as e:
        # run() already logged this to data_sync_log.
        # We log here so it also appears in docker logs.
        logger.error(f"[scheduler] {collector_class.__name__} failed: {e}")
    finally:
        db.close()


def run_mgnrega():
    logger.info("⏰ Scheduler: MGNREGA collection starting")
    _run_collector(MGNREGACollector)


def run_jjm():
    logger.info("⏰ Scheduler: JJM collection starting")
    _run_collector(JJMCollector)


def run_pmay():
    logger.info("⏰ Scheduler: PMAY collection starting")
    _run_collector(PMAYCollector)

def run_dbt():
    logger.info("⏰ Scheduler: DBT collection starting")
    _run_collector(DBTCollector)

def run_tenders():
    logger.info("⏰ Scheduler: Tenders collection starting")
    _run_collector(TendersCollector)

def run_cga():
    logger.info("⏰ Scheduler: CGA collection starting")
    _run_collector(CGACollector)

def run_cag_audit():
    logger.info("⏰ Scheduler: CAG Audit collection starting")
    _run_collector(CAGCollector)

def run_pfms():
    logger.info("⏰ Scheduler: PFMS collection starting")
    _run_collector(PFMSCollector)

def run_all_daily():
    """
    Master daily job — runs all collectors.
    Each runs independently so one failure doesn't block others.
    """
    logger.info("⏰ Scheduler: Daily collection run starting")
    run_mgnrega()
    run_jjm()
    run_pmay()
    run_dbt()
    run_tenders()
    run_pfms()
    logger.info("⏰ Scheduler: Daily collection run complete")


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    if not settings.scheduler_enabled:
        logger.warning("Scheduler DISABLED (SCHEDULER_ENABLED=false). No auto-updates will run.")
        return scheduler

    # Weekly run at 6:00 AM IST on Sunday
    scheduler.add_job(
        run_all_daily,
        trigger=CronTrigger(
            day_of_week="sun",
            hour=settings.mgnrega_fetch_hour,
            minute=0,
            timezone="Asia/Kolkata",
        ),
        id="weekly_all_collectors",
        name="Weekly: All Collectors",
        replace_existing=True,
        misfire_grace_time=3600,    # if server was down, run within 1 hour of missed time
    )

    # Monthly run for CGA (expenditure PDFs) on the 26th at 8:00 AM IST
    scheduler.add_job(
        run_cga,
        trigger=CronTrigger(
            day="26",
            hour=8,
            minute=0,
            timezone="Asia/Kolkata",
        ),
        id="monthly_cga",
        name="Monthly: CGA Budget Collector",
        replace_existing=True,
        misfire_grace_time=86400,   # 1 day grace time
    )

    logger.info(
        f"Scheduler ready. "
        f"Weekly run on Sunday at {settings.mgnrega_fetch_hour}:00 IST. "
        f"Jobs: {[j.name for j in scheduler.get_jobs()]}"
    )
    return scheduler
