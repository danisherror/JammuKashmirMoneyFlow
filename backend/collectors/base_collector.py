"""
Base class for all data collectors.
Handles: retry logic, sync log writing, error capture, shared HTTP client.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.orm import Session

from database.models import DataSyncLog, CollectorStatus


class BaseCollector(ABC):
    """
    Every collector inherits from this.
    Subclasses implement: collector_name, run_collection()
    """

    # Override in subclass
    collector_name: str = "base"
    # How many seconds to wait between requests (be polite to govt servers)
    request_delay: float = 1.0
    # Timeout for each HTTP request
    request_timeout: float = 30.0

    def __init__(self, db: Session):
        self.db = db
        self.sync_log: Optional[DataSyncLog] = None
        self._records_fetched = 0
        self._records_updated = 0
        self._records_inserted = 0

    # ── HTTP client setup ─────────────────────────────────────────────────────

    def get_http_client(self) -> httpx.Client:
        """
        Returns a configured httpx client with headers that mimic a browser.
        Govt portals sometimes block non-browser user agents.
        """
        return httpx.Client(
            timeout=self.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-IN,en;q=0.9",
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    def fetch_url(self, client: httpx.Client, url: str, **kwargs) -> httpx.Response:
        """Fetch a URL with automatic retry on timeout/connection errors."""
        logger.debug(f"[{self.collector_name}] GET {url}")
        response = client.get(url, **kwargs)
        response.raise_for_status()
        return response

    # ── Sync log management ───────────────────────────────────────────────────

    def _start_log(self) -> DataSyncLog:
        log = DataSyncLog(
            collector_name=self.collector_name,
            status=CollectorStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        self.sync_log = log
        logger.info(f"[{self.collector_name}] Started. Log ID: {log.id}")
        return log

    def _finish_log(self, status: CollectorStatus, error: Optional[str] = None):
        if not self.sync_log:
            return
        self.sync_log.status = status
        self.sync_log.finished_at = datetime.now(timezone.utc)
        self.sync_log.records_fetched = self._records_fetched
        self.sync_log.records_updated = self._records_updated
        self.sync_log.records_inserted = self._records_inserted
        if error:
            self.sync_log.error_message = error[:2000]   # truncate long stack traces
        self.db.commit()
        logger.info(
            f"[{self.collector_name}] Finished. "
            f"Status={status} Fetched={self._records_fetched} "
            f"Inserted={self._records_inserted} Updated={self._records_updated}"
        )

    # ── Main entrypoint ───────────────────────────────────────────────────────

    def run(self):
        """
        Called by the scheduler. Wraps run_collection() with logging + error handling.
        """
        self._start_log()
        try:
            self.run_collection()
            self._finish_log(CollectorStatus.SUCCESS)
        except Exception as e:
            logger.exception(f"[{self.collector_name}] FAILED: {e}")
            self._finish_log(CollectorStatus.FAILED, error=str(e))
            raise

    @abstractmethod
    def run_collection(self):
        """
        Subclasses implement actual data fetching logic here.
        Use self._records_fetched, self._records_inserted, self._records_updated
        to track counts.
        """
        raise NotImplementedError
