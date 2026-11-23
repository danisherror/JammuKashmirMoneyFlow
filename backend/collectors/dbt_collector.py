"""
Direct Benefit Transfer (DBT) collector for J&K.

NO LIVE SOURCE YET. The previous version loaded dbtbharat.gov.in, never parsed
it, raised unconditionally and then saved random enrolment and payment numbers.
That path is gone. Until a public, automation-friendly source is found and
recorded with a URL and date checked (todo.md 2.4), every run is logged as
`no_source`.

Candidate to check (not yet checked): https://dbtbharat.gov.in/data/statewise
robots.txt: not yet checked.
"""
from typing import Optional

from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError

DBT_URL = "https://dbtbharat.gov.in/data/statewise"


class DBTCollector(BaseCollector):
    collector_name = "dbt_collector"
    label = "DBT transfers"
    source_name = "dbtbharat.gov.in"
    source_url = DBT_URL

    def __init__(self, db: Session, financial_year: Optional[str] = None):
        super().__init__(db)
        self.financial_year = financial_year

    def run_collection(self):
        raise SourceUnavailableError(
            f"No live source for DBT transfers yet. Whether {DBT_URL} offers an "
            "automation-friendly district report is not yet checked (todo.md 2.4)."
        )
