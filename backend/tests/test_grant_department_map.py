"""The grant → department mapping must match the grant names printed in each year's accounts."""
from pathlib import Path

import pytest

from database.seeds import DEPARTMENTS, GRANT_DEPARTMENT_MAP, GRANT_MAP_YEARS
from parsers.appropriation_accounts import parse_appropriation_summary

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"


@pytest.fixture(scope="module")
def grants_by_year():
    return {
        year: parse_appropriation_summary(FIXTURES / f"jk-appropriation-{year}-summary.pdf").grants
        for year in GRANT_MAP_YEARS
    }


@pytest.mark.parametrize("year", GRANT_MAP_YEARS)
def test_mapped_grant_names_match_the_pdf(grants_by_year, year):
    grants = grants_by_year[year]
    for grant_no, fragment, code, _note in GRANT_DEPARTMENT_MAP:
        assert grant_no in grants, f"{year}: grant {grant_no} ({code}) is not in the accounts"
        assert fragment.lower() in grants[grant_no].lower(), (
            f"{year}: grant {grant_no} is {grants[grant_no]!r}, expected it to contain {fragment!r}"
        )


def test_mapping_refers_to_real_departments_once_each():
    codes = {d["code"] for d in DEPARTMENTS}
    mapped = [code for _, _, code, _ in GRANT_DEPARTMENT_MAP]
    assert set(mapped) <= codes
    assert len(mapped) == len(set(mapped))
    grant_numbers = [g for g, _, _, _ in GRANT_DEPARTMENT_MAP]
    assert len(grant_numbers) == len(set(grant_numbers))
