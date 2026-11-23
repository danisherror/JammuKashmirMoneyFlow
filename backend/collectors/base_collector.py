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

from collectors.http_policy import check_robots, http_headers
from database.models import DataSyncLog, CollectorStatus, SourceSnapshot
from database.snapshots import save_snapshot


class SourceUnavailableError(Exception):
    """
    Raised by a collector when there is no public, automation-friendly source
    to collect from (CAPTCHA, login, bot block, or no published endpoint yet).
    run() logs this as NO_SOURCE instead of FAILED: nothing broke, there is
    simply nothing honest to fetch. Never fall back to invented data.
    """


def outcome_status(written: int, skipped: int) -> CollectorStatus:
    """
    Status of a run that finished without raising.
    SUCCESS only when real rows were written and none were skipped.
    """
    if written > 0 and skipped == 0:
        return CollectorStatus.SUCCESS
    return CollectorStatus.PARTIAL


class BaseCollector(ABC):
    """
    Every collector inherits from this.
    Subclasses implement: collector_name, run_collection()
    """

    # Override in subclass
    collector_name: str = "base"
    # Shown on the dashboard next to the figures this collector writes, and in empty states.
    label: str = "base"
    source_name: str = "unknown"          # portal host, or why there is none
    source_url: Optional[str] = None      # the page the collector reads; None when not yet known
    # How many seconds to wait between requests (be polite to govt servers)
    request_delay: float = 1.0
    # Timeout for each HTTP request
    request_timeout: float = 30.0
    # Where snapshot() stores raw responses; None = settings.raw_snapshot_dir (tests override it)
    snapshot_dir: Optional[str] = None

    def __init__(self, db: Session):
        self.db = db
        self.sync_log: Optional[DataSyncLog] = None
        self._records_fetched = 0
        self._records_updated = 0
        self._records_inserted = 0
        self._records_skipped = 0
        self._skip_reasons: list[str] = []
        self._robots: dict[str, dict] = {}     # robots.txt result per URL fetched this run
        self._snapshot_ids: list[int] = []     # source_snapshots saved this run

    # ── HTTP client setup ─────────────────────────────────────────────────────

    def get_http_client(self) -> httpx.Client:
        """
        httpx client that identifies the tracker honestly (collectors/http_policy.py).
        Never swap in a browser User-Agent: if a portal refuses ours, fetch_url
        reports the collector as no_source.
        """
        return httpx.Client(
            timeout=self.request_timeout,
            follow_redirects=True,
            headers=http_headers(),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    def fetch_url(self, client: httpx.Client, url: str, **kwargs) -> httpx.Response:
        """
        Fetch a URL with automatic retry on timeout/connection errors, after
        checking robots.txt. Disallowed by robots.txt, or refused with 401/403,
        raises SourceUnavailableError (logged as no_source).
        """
        robots = check_robots(client, url)
        self._robots[url] = robots.as_record()
        if not robots.allowed:
            raise SourceUnavailableError(
                f"{robots.robots_url} disallows {url} for our User-Agent "
                f"(checked {robots.checked_at:%Y-%m-%d})."
            )
        logger.debug(f"[{self.collector_name}] GET {url}")
        response = client.get(url, **kwargs)
        if response.status_code in (401, 403):
            raise SourceUnavailableError(
                f"{url} refused our honest User-Agent (HTTP {response.status_code}). "
                "Not retrying with a browser User-Agent (todo.md 1.6)."
            )
        response.raise_for_status()
        return response

    def snapshot(self, response: httpx.Response, title: Optional[str] = None) -> SourceSnapshot:
        """
        Save the raw response body before parsing it (todo.md 1.4), so every figure derived from it
        can point at the exact bytes. Returns the snapshot row; set its id on the rows you write.
        Rolled back with everything else if the run fails (the file stays, unreferenced).
        """
        snapshot = save_snapshot(
            self.db,
            response.content,
            source_url=str(response.url),
            source_type=self.collector_name,
            content_type=response.headers.get("content-type"),
            collector_name=self.collector_name,
            title=title,
            snapshot_dir=self.snapshot_dir,
        )
        if snapshot.id not in self._snapshot_ids:
            self._snapshot_ids.append(snapshot.id)
        return snapshot

    def skip(self, reason: str):
        """Record a fetched row that could not be saved (e.g. unknown district)."""
        self._records_skipped += 1
        if len(self._skip_reasons) < 20:
            self._skip_reasons.append(reason)

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
        extra = dict(self.sync_log.extra_info or {})
        if self._records_skipped:
            extra.update(records_skipped=self._records_skipped, skip_reasons=self._skip_reasons)
        if self._robots:
            extra["robots"] = self._robots
        if self._snapshot_ids:
            extra["snapshot_ids"] = self._snapshot_ids
        if extra:
            self.sync_log.extra_info = extra
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
        except SourceUnavailableError as e:
            logger.warning(f"[{self.collector_name}] No source: {e}")
            self.db.rollback()
            self._finish_log(CollectorStatus.NO_SOURCE, error=str(e))
            return
        except Exception as e:
            logger.exception(f"[{self.collector_name}] FAILED: {e}")
            self.db.rollback()
            self._finish_log(CollectorStatus.FAILED, error=str(e))
            raise

        written = self._records_inserted + self._records_updated
        status = outcome_status(written, self._records_skipped)
        error = None
        if written == 0:
            error = "Finished without writing any rows."
        elif self._records_skipped:
            error = f"Skipped {self._records_skipped} fetched row(s): " + "; ".join(self._skip_reasons)
        self._finish_log(status, error=error)

    @abstractmethod
    def run_collection(self):
        """
        Subclasses implement actual data fetching logic here.
        Use self._records_fetched, self._records_inserted, self._records_updated
        to track counts.
        """
        raise NotImplementedError
