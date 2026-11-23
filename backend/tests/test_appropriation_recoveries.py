"""Tests for the Appendix II (recoveries) parser against real J&K Appropriation Accounts pages.

Fixtures `jk-appropriation-<year>-recoveries.pdf` hold the reconciliation page from the end of the
summary and the Appendix II pages (see fixtures/appropriation_accounts/SOURCES.md). Expected figures
were read by hand from the printed PDFs, in ₹ thousand ("52,00,00" = 5,20,000 thousand).
"""
from dataclasses import replace
from pathlib import Path

import pytest

from parsers.appropriation_accounts import parse_appropriation_summary
from parsers.appropriation_recoveries import (
    AppropriationRecoveriesError,
    parse_appropriation_recoveries,
    validate_recoveries,
)

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"
YEARS = ("2021-22", "2022-23", "2023-24")


@pytest.fixture(scope="module")
def summaries():
    return {year: parse_appropriation_summary(FIXTURES / f"jk-appropriation-{year}-summary.pdf") for year in YEARS}


@pytest.fixture(scope="module")
def parsed(summaries):
    return {
        year: parse_appropriation_recoveries(FIXTURES / f"jk-appropriation-{year}-recoveries.pdf", summary=summaries[year])
        for year in YEARS
    }


def line(rec, grant_no, section):
    (found,) = [x for x in rec.lines if (x.grant_no, x.section) == (grant_no, section)]
    return found


def test_2023_24_lists_every_grant(parsed):
    rec = parsed["2023-24"]
    assert len(rec.lines) == 31 * 2
    assert rec.total_budget_estimate == {"revenue": 0, "capital": 520000}
    assert rec.total_actual == {"revenue": 5034906, "capital": 377114}
    assert rec.reconciliation_recoveries == 5034906 + 377114
    assert rec.reconciliation_page == 1


def test_2023_24_rows(parsed):
    rec = parsed["2023-24"]
    agri = line(rec, 12, "capital")
    assert (agri.grant_name, agri.budget_estimate, agri.actual) == ("Agriculture Department", 520000, 377114)
    assert (agri.page, agri.actuals_page) == (2, 3)
    education = line(rec, 7, "revenue")
    assert (education.budget_estimate, education.actual) == (0, 3984256)
    coop = line(rec, 36, "revenue")  # second spread
    assert (coop.actual, coop.page, coop.actuals_page) == (13, 4, 5)


def test_2023_24_wrapped_grant_name(parsed):
    food = line(parsed["2023-24"], 15, "revenue")
    assert food.grant_name == "Food Civil Supplies and Consumer Affairs Department"
    assert food.actual == 674


def test_2022_23_amounts_between_wrapped_name_lines(parsed):
    rec = parsed["2022-23"]
    food = line(rec, 15, "capital")
    assert food.grant_name == "Food, Civil Supplies and Consumer Affairs Department"
    assert (food.budget_estimate, food.actual) == (0, 47435)
    assert (line(rec, 12, "capital").budget_estimate, line(rec, 12, "capital").actual) == (510000, 441659)
    assert rec.reconciliation_recoveries == 489094


def test_2021_22_blank_cells_are_nil(parsed):
    """Grant 15's Revenue cells and the Total's Revenue cells are blank, not "-"."""
    rec = parsed["2021-22"]
    food = line(rec, 15, "capital")
    assert (food.budget_estimate, food.actual) == (0, 53470)
    assert line(rec, 15, "revenue").actual == 0
    assert rec.total_actual == {"revenue": 0, "capital": 181905}
    assert rec.total_budget_estimate == {"revenue": 0, "capital": 280000}


@pytest.mark.parametrize("year", YEARS)
def test_totals_match_the_reconciliation(parsed, year):
    rec = parsed[year]
    assert sum(x.actual for x in rec.lines) == rec.reconciliation_recoveries


def test_validation_rejects_rows_that_do_not_add_up(parsed, summaries):
    rec = parsed["2022-23"]
    broken = replace(rec, lines=[replace(x, actual=x.actual + 100) if x.grant_no == 12 else x for x in rec.lines])
    with pytest.raises(AppropriationRecoveriesError, match="Total row says"):
        validate_recoveries(broken, summaries["2022-23"])


def test_validation_rejects_a_reconciliation_mismatch(parsed, summaries):
    broken = replace(parsed["2022-23"], reconciliation_recoveries=1)
    with pytest.raises(AppropriationRecoveriesError, match="Deduct Recoveries"):
        validate_recoveries(broken, summaries["2022-23"])


def test_validation_rejects_an_unknown_grant(parsed, summaries):
    rec = parsed["2022-23"]
    broken = replace(rec, lines=[replace(x, grant_no=99) if x.grant_no == 15 else x for x in rec.lines])
    with pytest.raises(AppropriationRecoveriesError, match="not in the summary"):
        validate_recoveries(broken, summaries["2022-23"])


def test_a_pdf_without_appendix_ii_is_rejected(summaries):
    with pytest.raises(AppropriationRecoveriesError, match="no Appendix II"):
        parse_appropriation_recoveries(FIXTURES / "jk-appropriation-2022-23-summary.pdf", summary=summaries["2022-23"])


SNAPSHOTS = Path(__file__).parent.parent / "raw_snapshots" / "appropriation_accounts"
FULL_DOCUMENTS = {  # SHA-256 from SOURCES.md → (rows, actual total), checked 2026-11-23
    "2021-22": ("9b66c686bf4b6c9c56bb63029699d6e18195fd5f7b8c76e1ed3ffc5f171413e7", 4, 181905),
    "2022-23": ("0f6df1b40ca39d3703e9361b08de24f90b8a51b461867ba91a52dabc7979bcea", 4, 489094),
    "2023-24": ("8c8133ea414c69513c0a6b7ebef1297f5664b0565dc8498391d04e30fa6290b8", 62, 5412020),
}


@pytest.mark.parametrize("year", YEARS)
def test_full_document(year):
    sha256, n_lines, total = FULL_DOCUMENTS[year]
    path = SNAPSHOTS / f"{sha256}.pdf"
    if not path.exists():
        pytest.skip(f"{path.name} not downloaded (run loaders.appropriation_accounts)")
    rec = parse_appropriation_recoveries(path)
    assert rec.financial_year == year
    assert (len(rec.lines), sum(rec.total_actual.values())) == (n_lines, total)
