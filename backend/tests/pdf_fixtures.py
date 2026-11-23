"""Shared fixture PDFs: the summary and grant-page fixtures of one year merged into one document.

The loader reads a whole Appropriation Accounts PDF (summary first, then the grant pages), so tests
merge the two cut-down fixtures in that order. Pages are copied unchanged with pypdfium2. The result
is cached so every caller gets the same bytes (and therefore the same SHA-256).
"""
import io
from functools import lru_cache
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"
YEARS = ("2021-22", "2022-23", "2023-24")


@lru_cache(maxsize=None)
def accounts_pdf(year: str) -> bytes:
    import pypdfium2 as pdfium

    merged = pdfium.PdfDocument.new()
    for part in ("summary", "grants"):
        merged.import_pages(pdfium.PdfDocument(FIXTURES / f"jk-appropriation-{year}-{part}.pdf"))
    buffer = io.BytesIO()
    merged.save(buffer)
    return buffer.getvalue()
