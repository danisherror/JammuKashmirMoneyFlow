"""Shared fixture PDFs: the cut-down fixtures of one year merged into one document.

The loader reads a whole Appropriation Accounts PDF, so tests merge the fixtures in the order of the
original: summary pages, the reconciliation page (first page of `-recoveries.pdf`), grant pages, then
Appendix II (the rest of `-recoveries.pdf`). Pages are copied unchanged with pypdfium2. The result is
cached so every caller gets the same bytes (and therefore the same SHA-256).
"""
import io
from functools import lru_cache
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"
YEARS = ("2021-22", "2022-23", "2023-24")


@lru_cache(maxsize=None)
def accounts_pdf(year: str) -> bytes:
    import pypdfium2 as pdfium

    def part(name: str):
        return pdfium.PdfDocument(FIXTURES / f"jk-appropriation-{year}-{name}.pdf")

    merged = pdfium.PdfDocument.new()
    recoveries = part("recoveries")
    merged.import_pages(part("summary"))
    merged.import_pages(recoveries, [0])
    merged.import_pages(part("grants"))
    merged.import_pages(recoveries, list(range(1, len(recoveries))))
    buffer = io.BytesIO()
    merged.save(buffer)
    return buffer.getvalue()
