"""
Monthly department spending for J&K.

NO SOURCE YET. The previous version never downloaded anything (`_fetch_pdf`
returned None) and then generated month-by-month spending curves from the seed
allocations ("Smart Simulation"). That path is gone. A published monthly
accounts source for J&K (CGA or the Accountant General) is not yet found
(todo.md 2.2), so every run is logged as `no_source` and the dashboard shows
"No data" for monthly spend.

Audited annual spending comes from the CAG Appropriation Accounts instead:
see loaders/appropriation_accounts.py.
"""
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError


class CGACollector(BaseCollector):
    collector_name = "cga_collector"

    def __init__(self, db: Session, **_ignored):
        super().__init__(db)

    def run_collection(self):
        raise SourceUnavailableError(
            "No published monthly accounts source for J&K found yet (todo.md 2.2). "
            "Audited annual figures come from the CAG Appropriation Accounts."
        )
