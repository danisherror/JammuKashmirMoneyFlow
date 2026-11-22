"""Tests for the grant-page parser against real J&K Appropriation Accounts pages.

Fixtures (see fixtures/appropriation_accounts/SOURCES.md) hold a few grants per year, chosen for
the layout quirks they show. The summary table comes from the existing summary fixtures. Expected
figures were read by hand from the printed PDFs and are in ₹ thousand (₹ lakh × 100).
"""
from dataclasses import replace
from pathlib import Path

import pytest

import parsers.appropriation_details as details_module
from parsers.appropriation_accounts import parse_appropriation_summary
from parsers.appropriation_details import (
    AppropriationDetailsError,
    _lakh_to_thousand,
    _norm,
    _note_category,
    _split_glued,
    parse_appropriation_details,
    validate_details,
)

FIXTURES = Path(__file__).parent / "fixtures" / "appropriation_accounts"
YEARS = ("2021-22", "2022-23", "2023-24")


@pytest.fixture(scope="module")
def summaries():
    return {year: parse_appropriation_summary(FIXTURES / f"jk-appropriation-{year}-summary.pdf") for year in YEARS}


@pytest.fixture(scope="module")
def parsed(summaries):
    return {
        year: parse_appropriation_details(
            FIXTURES / f"jk-appropriation-{year}-grants.pdf", summary=summaries[year], partial=True
        )
        for year in YEARS
    }


def head(details, grant_no, head_code, category=None):
    rows = [
        h
        for h in details.heads
        if h.grant_no == grant_no and h.head_code == head_code and (category is None or h.category == category)
    ]
    assert len(rows) == 1, f"expected one row for grant {grant_no} head {head_code}, got {len(rows)}"
    return rows[0]


def amounts(h):
    return (h.original, h.supplementary, h.reappropriation, h.final_grant, h.expenditure, h.saving, h.excess)


def total(details, grant_no, section, kind):
    (t,) = [t for t in details.section_totals if (t.grant_no, t.section, t.kind) == (grant_no, section, kind)]
    return t


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1,711.00", 171100),
        ("(-)164.50", -16450),
        ("(+)18.90", 1890),
        ("0.01", 1),
        ("6,00,006.00", 60000600),
        ("2,29,492.28", 22949228),
    ],
)
def test_lakh_amounts_become_exact_thousands(text, expected):
    assert _lakh_to_thousand(text) == expected


def test_glued_remark_is_split_from_its_number():
    word = {"text": "(-)34.24mainly", "x0": 398.0, "x1": 450.0, "top": 10.0, "bottom": 18.0}
    number, rest = _split_glued([word])
    assert number["text"] == "(-)34.24" and rest["text"] == "mainly"
    assert number["x1"] < rest["x0"] + 0.01 and rest["glued_remark"]


def test_doubled_bold_glyphs_are_normalised():
    assert _norm("AAmmoouunntt ssuurrrreennddeered") == _norm("Amount surrendered")


@pytest.mark.parametrize(
    "text, category",
    [
        ("Significant saving in the Section occurred under the following Heads/ Schemes", "saving"),
        ("SavingintheSectionoccurredmainlyunderthefollowingHeads/Schemes;reasonsforwhichwerenot", "saving"),
        ("Saving was partly counterbalanced by the excess under the following Heads/ Schemes", "excess"),
        ("In the Capital Charged Section excess occurred mainly under the following Head/Schemes", "excess"),
        ("Entireprovisionremainedun-utilisedthroughouttheyearunderthefollowingHeads/Schemes", "unutilised"),
        ("Entire Supplementaryprovision remained un-utilised throughoutthe year", "unutilised_supplementary"),
        ("ExpenditureunderthefollowingHead/SchemeswasincurredwithoutBudgetaryProvision", "without_provision"),
        ("In the Revenue Voted Section provision of 52,918.07 lakh proved excessive", "comment"),
    ],
)
def test_note_category(text, category):
    assert _note_category(text) == category


# ── 2023-24 (grants 1, 2, 24, 36) ─────────────────────────────────────────────


def test_2023_24_section_blocks(parsed):
    d = parsed["2023-24"]
    t = total(d, 1, "revenue", "voted")  # Original 5,29,18,07 / 4,43,36,49 / (-)85,81,58
    assert (t.original, t.supplementary, t.final_grant, t.expenditure, t.saving, t.excess) == (
        5291807, 0, 5291807, 4433649, 858158, 0
    )
    t = total(d, 1, "revenue", "charged")
    assert (t.final_grant, t.expenditure, t.saving) == (316844, 246660, 70184)
    t = total(d, 1, "capital", "voted")
    assert (t.final_grant, t.expenditure, t.saving) == (1634119, 292920, 1341199)
    # Grant 36 prints no "Voted" label; the block is voted and has an excess.
    t = total(d, 36, "revenue", "voted")
    assert (t.original, t.supplementary, t.final_grant, t.expenditure, t.excess) == (
        711969, 40534, 752503, 776490, 23987
    )


def test_2023_24_capital_section_heading_in_the_block(parsed):
    # Grant 31 heads its capital block "Capital Section" instead of "Capital-".
    t = total(parsed["2023-24"], 31, "capital", "voted")  # 1,70,07,16 / 15,87,59 / (-)1,54,19,57
    assert (t.final_grant, t.expenditure, t.saving) == (1700716, 158759, 1541957)


def test_2023_24_saving_row_with_reappropriation(parsed):
    h = head(parsed["2023-24"], 1, "2052.090.0099.0518")
    assert amounts(h) == (639050, 0, -17715, 621335, 425259, 196076, 0)
    assert [p.level for p in h.path] == ["major", "minor", "sub_head", "detailed"]
    assert h.head_name == "General Administration Department"
    assert (h.section, h.kind, h.category, h.reasons_not_communicated) == ("revenue", "voted", "saving", True)
    assert h.remark == (
        "Less expenditure against the provision mainly in respect of Salary, TE, Training and nil "
        "expenditure in respect of Uniform"
    )


def test_2023_24_excess_row(parsed):
    h = head(parsed["2023-24"], 1, "2251.090.0099.0426")  # excess; exact rupee figure in brackets ignored
    assert amounts(h) == (67925, 0, -1100, 66825, 73237, 0, 6412)
    assert h.category == "excess"


def test_2023_24_unutilised_row_has_only_the_grant(parsed):
    h = head(parsed["2023-24"], 1, "2013.101.0099.0431")
    assert h.category == "unutilised"
    assert (h.final_grant, h.expenditure, h.saving, h.original) == (65000, None, None, None)


def test_2023_24_same_detailed_head_under_two_sub_heads(parsed):
    d = parsed["2023-24"]
    assert head(d, 1, "5452.80.800.0011.0270").final_grant == 285931
    assert amounts(head(d, 1, "5452.80.800.0031.0270")) == (50000, 0, None, 50000, 41543, 8457, 0)


def test_2023_24_orphan_branch_is_dropped(parsed):
    # The PDF prints "214 Border Management / 0011 General" with no row, then "216 ...".
    h = head(parsed["2023-24"], 2, "4055.216.0011.0727")
    assert h.path[1].name == "Other Police Organisations"
    assert (h.final_grant, h.expenditure, h.saving) == (149203, 1940, 147263)


def test_2023_24_table_without_header(parsed):
    d = parsed["2023-24"]
    assert d.headerless_tables == ["page 15, grant 24, note 5"]
    h = head(d, 24, "4059.60.800.0011.0464")
    assert amounts(h) == (250000, 35000, None, 285000, 290620, 0, 5620)
    assert h.category == "excess"


def test_2023_24_grant_36_note_tables(parsed):
    d = parsed["2023-24"]
    h = head(d, 36, "2425.107.0031.6028")  # O "..", S and R on separate lines
    assert amounts(h) == (0, 39609, -17500, 22109, 59371, 0, 37262)

    h = head(d, 36, "2425.001.0031.6058")
    assert h.category == "unutilised_supplementary"
    assert h.final_grant == 771  # "7.71is mainly ..." — number glued to the remark
    assert h.head_name == "Scheme for Computerisation of office of Registrar Co-operative Societies"
    assert h.remark == "Nil expenditure against the provision is mainly in respect of GIA"

    rows = [h for h in d.heads if h.grant_no == 36 and h.category == "without_provision"]
    assert [(h.head_code, h.expenditure, h.final_grant) for h in rows] == [
        ("2425.107.0099.6028", 14843, None),
        ("2425.108.0031.6059", 2625, None),
        ("2425.108.0099.6059", 525, None),
    ]
    assert rows[1].head_name == "Scheme for Computerisation of Agriculture and Rural Development Banks"


def test_2023_24_notes(parsed):
    d = parsed["2023-24"]
    assert [(n.number, n.category) for n in d.notes if n.grant_no == 36] == [
        (1, "comment"), (2, "excess"), (3, "saving"), (4, "unutilised_supplementary"),
        (5, "without_provision"), (6, "comment"), (7, "saving"),
    ]
    (note,) = [n for n in d.notes if n.grant_no == 1 and n.number == 1]
    assert (note.section, note.kind) == ("revenue", "voted")
    assert "No portion of final saving of 8,581.58 lakh has been anticipated and surrendered." in note.text


# ── 2022-23 (grants 2, 5, 6, 32, 33) ──────────────────────────────────────────


def test_2022_23_amount_below_its_label(parsed):
    # "R" on one line and "5,590.87" with the totals on the next.
    h = head(parsed["2022-23"], 2, "2055.003.0099.0181")
    assert amounts(h) == (846258, None, 559087, 1405345, 785032, 620313, 0)


def test_2022_23_grant_without_amounts(parsed):
    d = parsed["2022-23"]
    assert 5 in d.grants
    assert not [t for t in d.section_totals if t.grant_no == 5]
    assert not [h for h in d.heads if h.grant_no == 5]


def test_2022_23_shifted_margin_and_surrender(parsed):
    d = parsed["2022-23"]
    h = head(d, 6, "4801.05.001.0011.1307")
    assert amounts(h) == (5000000, None, 178009, 5178009, 2388137, 2789872, 0)
    assert total(d, 6, "revenue", "voted").surrendered == 19060089


def test_2022_23_printed_error_is_kept_and_flagged(parsed):
    h = head(parsed["2022-23"], 32, "4401.800.0011.0222")
    assert (h.final_grant, h.expenditure, h.saving) == (311099, 197952, 113137)  # as printed
    assert "1,131.47" in h.printed_error


def test_2022_23_note_numbers_can_skip(parsed):
    d = parsed["2022-23"]
    assert [n.number for n in d.notes if n.grant_no == 33] == [1, 2, 3, 4, 5, 7]
    (note,) = [n for n in d.notes if n.grant_no == 33 and n.number == 7]
    assert note.text.startswith("State Disaster Response Fund")
    # The row printed just above note 7 must not swallow the note's text into its name.
    assert head(d, 33, "4235.01.201.0011.2165").head_name == "Rehabilitation"


# ── 2021-22 (grants 2, 6, 9, 28, 34) ──────────────────────────────────────────


def test_2021_22_supplementary_reappropriation_block(parsed):
    d = parsed["2021-22"]
    t = total(d, 2, "revenue", "voted")
    assert (t.original, t.reappropriation, t.final_grant, t.expenditure, t.saving, t.surrendered) == (
        88650598, 3632610, 92283208, 74641496, 17641712, 0
    )
    names = {m.code: m.name for m in d.major_heads if m.grant_no == 2 and m.section == "capital"}
    assert names["4070"] == "Capital Outlay on Other Administrative Services"  # wrapped onto "Voted"


def test_2021_22_withdrawn_block(parsed):
    t = total(parsed["2021-22"], 9, "revenue", "charged")
    assert (t.original, t.reappropriation, t.final_grant, t.expenditure) == (8710, -8710, 0, 0)


def test_2021_22_missing_o_label(parsed):
    h = head(parsed["2021-22"], 28, "2515.001.0099.0105")
    assert amounts(h) == (1483091, -165667, None, 1317424, 848372, 469052, 0)


def test_2021_22_row_filed_by_its_major_head(parsed):
    d = parsed["2021-22"]
    h = head(d, 34, "2230.03.101.0031.2505")
    assert (h.section, h.category, h.final_grant) == ("revenue", "unutilised", 110000)
    assert len(d.misfiled) == 1 and "head 2230" in d.misfiled[0]


def test_2021_22_non_head_tables_and_footnotes(parsed):
    d = parsed["2021-22"]
    assert len(d.skipped_tables) == 1 and "Works Outlay" in d.skipped_tables[0]
    assert any("Difference of 0.01 lakh due to machine rounding" in f for f in d.footnotes)


# ── Every parsed row ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("year", YEARS)
def test_every_row_has_a_major_head_and_a_name(parsed, year):
    d = parsed[year]
    assert d.heads
    majors = {(m.grant_no, m.section, m.code) for m in d.major_heads}
    for h in d.heads:
        assert (h.grant_no, h.section, h.path[0].code) in majors
        assert all(p.name for p in h.path)
        assert h.kind in ("voted", "charged")
        assert d.unit == "INR thousand"


@pytest.mark.parametrize("year", YEARS)
def test_section_blocks_match_the_summary(parsed, summaries, year):
    rows = {(r.grant_no, r.section, r.kind): r for r in summaries[year].lines}
    for t in parsed[year].section_totals:
        if t.final_grant == 0 and t.expenditure == 0:
            continue  # withdrawn block, not in the summary
        r = rows[(t.grant_no, t.section, t.kind)]
        assert (t.final_grant, t.expenditure) == (r.grant_amount, r.expenditure)


# ── Validation ────────────────────────────────────────────────────────────────


def test_validation_rejects_a_row_that_does_not_add_up(parsed, summaries):
    d = parsed["2023-24"]
    broken = replace(d, heads=[replace(d.heads[0], expenditure=d.heads[0].expenditure + 100), *d.heads[1:]])
    with pytest.raises(AppropriationDetailsError, match="total grant"):
        validate_details(broken, summaries["2023-24"], partial=True)


def test_validation_rejects_a_block_that_differs_from_the_summary(parsed, summaries):
    d = parsed["2023-24"]
    t = d.section_totals[0]
    broken = replace(
        d, section_totals=[replace(t, final_grant=t.final_grant + 10, original=t.original + 10), *d.section_totals[1:]]
    )
    with pytest.raises(AppropriationDetailsError, match="summary"):
        validate_details(broken, summaries["2023-24"], partial=True)


def test_validation_rejects_missing_grants_unless_partial(parsed, summaries):
    with pytest.raises(AppropriationDetailsError, match="differ from the summary"):
        validate_details(parsed["2023-24"], summaries["2023-24"])


def test_validation_rejects_a_stale_printed_error_entry(parsed, summaries, monkeypatch):
    stale = dict(details_module.KNOWN_PRINTED_ERRORS)
    stale[("2023-24", 1, "2015.102.0099.0414", "saving")] = "not actually wrong"
    monkeypatch.setattr(details_module, "KNOWN_PRINTED_ERRORS", stale)
    d = parsed["2023-24"]
    flagged = replace(
        d,
        heads=[replace(h, printed_error="x") if h.head_code == "2015.102.0099.0414" else h for h in d.heads],
    )
    with pytest.raises(AppropriationDetailsError, match="figures add up"):
        validate_details(flagged, summaries["2023-24"], partial=True)


def test_validation_rejects_a_table_note_without_rows(parsed, summaries):
    d = parsed["2023-24"]
    broken = replace(d, heads=[h for h in d.heads if not (h.grant_no == 36 and h.note_number == 5)])
    with pytest.raises(AppropriationDetailsError, match="without_provision note with no rows"):
        validate_details(broken, summaries["2023-24"], partial=True)


# ── Full documents (only where the loader has saved them locally) ────────────

SNAPSHOTS = Path(__file__).parent.parent / "raw_snapshots" / "appropriation_accounts"
FULL_DOCUMENTS = {  # SHA-256 from SOURCES.md → expected counts, checked 2026-11-22
    "2021-22": ("9b66c686bf4b6c9c56bb63029699d6e18195fd5f7b8c76e1ed3ffc5f171413e7", 985, 75),
    "2022-23": ("0f6df1b40ca39d3703e9361b08de24f90b8a51b461867ba91a52dabc7979bcea", 999, 75),
    "2023-24": ("8c8133ea414c69513c0a6b7ebef1297f5664b0565dc8498391d04e30fa6290b8", 1021, 77),
}


@pytest.mark.parametrize("year", YEARS)
def test_full_document(year):
    sha256, n_heads, n_blocks = FULL_DOCUMENTS[year]
    path = SNAPSHOTS / f"{sha256}.pdf"
    if not path.exists():
        pytest.skip(f"{path.name} not downloaded (run loaders.appropriation_accounts)")
    d = parse_appropriation_details(path)  # validates against the summary, every grant present
    assert d.financial_year == year
    assert (len(d.heads), len(d.section_totals)) == (n_heads, n_blocks)
