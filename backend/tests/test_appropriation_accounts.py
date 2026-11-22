"""Parser tests against real J&K Appropriation Accounts pages (see fixtures/appropriation_accounts/SOURCES.md).

Expected figures below were read by hand from the printed PDFs (₹ thousand).
"""
from dataclasses import replace
from pathlib import Path

import pytest

from parsers.appropriation_accounts import (
    AppropriationAccountsError,
    _to_int,
    parse_appropriation_summary,
    validate_summary,
)

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"


def fixture(year: str) -> Path:
    return FIXTURES / f"jk-appropriation-{year}-summary.pdf"


@pytest.fixture(scope="module")
def summaries():
    return {year: parse_appropriation_summary(fixture(year)) for year in ("2021-22", "2022-23", "2023-24")}


def line(summary, grant_no, section, kind):
    matches = [
        row for row in summary.lines if (row.grant_no, row.section, row.kind) == (grant_no, section, kind)
    ]
    assert len(matches) == 1, f"expected one row for grant {grant_no} {section}/{kind}"
    return matches[0]


def amounts(row):
    return (row.grant_amount, row.expenditure, row.saving, row.excess)


def total(summary, section, kind):
    (match,) = [t for t in summary.totals if (t.section, t.kind) == (section, kind)]
    return (match.grant_amount, match.expenditure, match.saving, match.excess)


# ── Number format ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1,07,71,19,60", 107711960),
        ("87,10", 8710),
        ("3,67", 367),
        ("5,18,27,45,62*$", 518274562),
        ("6,89,93,26,51*", 689932651),
        ("92,00", 9200),
    ],
)
def test_indian_digit_grouping(text, expected):
    assert _to_int(text) == expected


# ── Whole-document shape ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "year, n_grants, n_lines",
    [
        ("2021-22", 35, 73),  # grant 5 (Mining) is not in the 2021-22 accounts
        ("2022-23", 35, 75),  # grant 5 is listed but has no rows
        ("2023-24", 36, 77),
    ],
)
def test_shape(summaries, year, n_grants, n_lines):
    summary = summaries[year]
    assert summary.financial_year == year
    assert summary.unit == "INR thousand"
    assert len(summary.grants) == n_grants
    assert len(summary.lines) == n_lines


def test_printed_totals(summaries):
    assert total(summaries["2021-22"], "revenue", "voted") == (600341409, 518274562, 98343374, 16276527)
    assert total(summaries["2021-22"], "capital", "charged") == (414202000, 415751680, 0, 1549680)
    assert total(summaries["2022-23"], "revenue", "voted") == (689932651, 544194493, 147313956, 1575798)
    assert total(summaries["2022-23"], "capital", "charged") == (327208700, 340669071, 0, 13460371)
    assert total(summaries["2023-24"], "revenue", "charged") == (97700854, 100260002, 338651, 2897798)
    assert total(summaries["2023-24"], "capital", "voted") == (335163641, 121380543, 213783097, 0)


# ── Individual rows, including the awkward layouts ────────────────────────────


def test_2021_22_wrapped_excess_rows(summaries):
    """2021-22 prints excess rows over three lines with a bracketed whole-rupee figure."""
    s = summaries["2021-22"]
    assert amounts(line(s, 8, "revenue", "voted")) == (107711960, 122944716, 0, 15232756)
    assert amounts(line(s, 8, "revenue", "charged")) == (70936700, 73603136, 0, 2666436)
    assert amounts(line(s, 8, "capital", "charged")) == (414202000, 415751680, 0, 1549680)
    assert amounts(line(s, 16, "revenue", "voted")) == (11822463, 12866235, 0, 1043772)


def test_2021_22_simple_rows(summaries):
    s = summaries["2021-22"]
    assert amounts(line(s, 4, "capital", "voted")) == (9200, 2190, 7010, 0)
    assert amounts(line(s, 9, "revenue", "voted")) == (340404, 260703, 79702, 0)  # footnoted "7,97,02*"
    assert 5 not in s.grants


def test_2022_23_rows(summaries):
    """2022-23 headers are offset from the numbers below them."""
    s = summaries["2022-23"]
    assert amounts(line(s, 8, "capital", "charged")) == (327208700, 340669071, 0, 13460371)
    assert amounts(line(s, 16, "revenue", "voted")) == (12027563, 13603361, 0, 1575798)
    assert amounts(line(s, 4, "capital", "voted")) == (1004770, 367, 1004403, 0)
    assert amounts(line(s, 9, "revenue", "charged")) == (8710, 0, 8710, 0)  # expenditure printed as "--"
    assert 5 not in s.grants


def test_2023_24_rows_and_names(summaries):
    s = summaries["2023-24"]
    assert amounts(line(s, 36, "revenue", "voted")) == (752503, 776490, 0, 23987)
    assert amounts(line(s, 8, "revenue", "charged")) == (96351800, 99249598, 0, 2897798)
    assert amounts(line(s, 5, "revenue", "voted")) == (783461, 608297, 175164, 0)
    assert s.grants[33] == "Disaster Management, Relief, Rehabilitation and Reconstruction Department"
    assert s.grants[1] == "General Administration Department"
    assert s.grants[31] == "Culture Department"


def test_page_numbers_point_into_the_pdf(summaries):
    s = summaries["2023-24"]
    assert line(s, 1, "revenue", "voted").page == 1
    assert line(s, 36, "capital", "voted").page == 4


# ── Validation ────────────────────────────────────────────────────────────────


def test_validation_rejects_a_misread_row(summaries):
    s = summaries["2022-23"]
    bad_line = replace(s.lines[0], expenditure=s.lines[0].expenditure + 1000)
    tampered = replace(s, lines=[bad_line, *s.lines[1:]])
    with pytest.raises(AppropriationAccountsError, match="grant - expenditure"):
        validate_summary(tampered)


def test_validation_rejects_a_missing_row(summaries):
    s = summaries["2022-23"]
    tampered = replace(s, lines=s.lines[1:])
    with pytest.raises(AppropriationAccountsError, match="printed total"):
        validate_summary(tampered)


def test_non_summary_pdf_is_rejected(tmp_path):
    import pypdfium2 as pdfium

    blank = tmp_path / "blank.pdf"
    doc = pdfium.PdfDocument.new()
    doc.new_page(595, 842)
    doc.save(blank)
    with pytest.raises(AppropriationAccountsError, match="no 'Summary of Appropriation Accounts'"):
        parse_appropriation_summary(blank)
