"""
Public Financial Management System (PFMS) collector for J&K: central releases
to J&K implementing agencies.

NO LIVE SOURCE YET. The previous version loaded pfms.nic.in, never parsed it,
raised unconditionally and then overwrote `funds_released` with random factors
of the allocation. That path is gone. Until a public, automation-friendly
source is found and recorded with a URL and date checked (todo.md 2.4), every
run is logged as `no_source`.

Candidate to check (not yet checked): https://pfms.nic.in/NewDefaultHome.aspx
robots.txt: not yet checked.
"""
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError

PFMS_URL = "https://pfms.nic.in/NewDefaultHome.aspx"


class PFMSCollector(BaseCollector):
    collector_name = "pfms_collector"

    def __init__(self, db: Session, **_ignored):
        super().__init__(db)

    def run_collection(self):
        raise SourceUnavailableError(
            f"No live source for PFMS central releases yet. Whether {PFMS_URL} "
            "offers an automation-friendly report is not yet checked (todo.md 2.4)."
        )
