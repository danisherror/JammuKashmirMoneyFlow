"""
PM Awas Yojana (Gramin) collector for J&K.

NO LIVE SOURCE YET. The previous version loaded pmayg.nic.in, never parsed it,
raised unconditionally and then saved random targets and spending as if they
were real. That path is gone. Until a public, automation-friendly source for
J&K district progress is found and recorded with a URL and date checked
(todo.md 2.4), every run is logged as `no_source`.

Candidate to check (not yet checked): https://pmayg.nic.in/netiay/home.aspx
robots.txt: not yet checked.
"""
from typing import Optional

from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError

PMAY_URL = "https://pmayg.nic.in/netiay/home.aspx"


class PMAYCollector(BaseCollector):
    collector_name = "pmay_collector"
    label = "PM Awas Yojana (Gramin)"
    source_name = "pmayg.nic.in"
    source_url = PMAY_URL

    def __init__(self, db: Session, financial_year: Optional[str] = None):
        super().__init__(db)
        self.financial_year = financial_year

    def run_collection(self):
        raise SourceUnavailableError(
            f"No live source for PMAY-G district progress yet. Whether {PMAY_URL} "
            "offers an automation-friendly report is not yet checked (todo.md 2.4)."
        )
