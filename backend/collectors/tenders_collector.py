"""
Tenders collector for J&K.

NO LIVE SOURCE YET. The previous version loaded jktenders.gov.in, never parsed
it, raised unconditionally and then saved random tenders with invented
contractor names. That path is gone. Contractors may be named only from a
linked official award notice (todo.md 2.4). Until a public, automation-friendly
source is found and recorded with a URL and date checked, every run is logged
as `no_source`.

Candidate to check (not yet checked): https://jktenders.gov.in/nicgep/app
"""
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError

TENDERS_URL = "https://jktenders.gov.in/nicgep/app"


class TendersCollector(BaseCollector):
    collector_name = "tenders_collector"

    def __init__(self, db: Session, **_ignored):
        super().__init__(db)

    def run_collection(self):
        raise SourceUnavailableError(
            f"No live source for J&K tenders yet. Whether {TENDERS_URL} can be read "
            "without a CAPTCHA or login is not yet checked (todo.md 2.4)."
        )
