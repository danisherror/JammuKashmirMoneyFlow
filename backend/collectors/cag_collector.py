"""
CAG audit findings for J&K.

NO SOURCE YET. The previous version stored a hardcoded list of invented audit
paragraphs (MOCK_FINDINGS) as if they came from CAG reports. That path is gone.
Real findings need the published J&K audit reports split into paragraphs with
page numbers, and every extracted amount checked against the verbatim text
before it is shown (todo.md 2.3). Until then every run is logged as
`no_source`.
"""
from sqlalchemy.orm import Session

from collectors.base_collector import BaseCollector, SourceUnavailableError


class CAGCollector(BaseCollector):
    collector_name = "cag_collector"

    def __init__(self, db: Session, **_ignored):
        super().__init__(db)

    def run_collection(self):
        raise SourceUnavailableError(
            "Extraction of findings from the real J&K audit reports is not built yet "
            "(todo.md 2.3)."
        )
