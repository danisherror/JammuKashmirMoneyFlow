"""Rules in processors.accountability, on hand-made rows (₹ thousand)."""
from types import SimpleNamespace

from processors.accountability import accountability_flags, block_flags, head_flags


def block(**over):
    base = dict(grant_no=1, section="revenue", kind="voted", supplementary_thousand=0, final_grant_thousand=1000,
                expenditure_thousand=1000, saving_thousand=0, excess_thousand=0, surrendered_thousand=0, page=5)
    return SimpleNamespace(**{**base, **over})


def head(**over):
    base = dict(grant_no=1, section="revenue", kind="voted", category="saving", reasons_not_communicated=False,
                head_code="2052.090", head_name="Secretariat", final_grant_thousand=100, page=6)
    return SimpleNamespace(**{**base, **over})


def kinds(flags):
    return [(f.kind, f.amount_thousand) for f in flags]


def test_block_on_budget_has_no_flags():
    assert block_flags([block()]) == []


def test_excess_over_grant():
    (flag,) = block_flags([block(expenditure_thousand=1200, excess_thousand=200)])
    assert (flag.kind, flag.amount_thousand, flag.page) == ("excess_over_grant", 200, 5)
    assert "regularisation" in flag.detail and "₹2.00 lakh" in flag.detail


def test_savings_not_surrendered_counts_only_the_unsurrendered_part():
    assert kinds(block_flags([block(expenditure_thousand=600, saving_thousand=400, surrendered_thousand=150)])) == [
        ("savings_not_surrendered", 250)
    ]
    assert block_flags([block(expenditure_thousand=600, saving_thousand=400, surrendered_thousand=400)]) == []


def test_supplementary_not_needed_when_saving_covers_it():
    flags = block_flags([block(supplementary_thousand=300, final_grant_thousand=1300, expenditure_thousand=900,
                               saving_thousand=400, surrendered_thousand=400)])
    assert kinds(flags) == [("supplementary_not_needed", 300)]
    # Saving smaller than the supplementary: part of it was needed.
    assert block_flags([block(supplementary_thousand=300, final_grant_thousand=1300, expenditure_thousand=1100,
                              saving_thousand=200, surrendered_thousand=200)]) == []


def test_fully_unutilised_heads():
    flags = head_flags([
        head(category="unutilised", final_grant_thousand=65000),
        head(category="unutilised_supplementary", final_grant_thousand=771, head_code="2425.001"),
        head(category="without_provision", final_grant_thousand=None),
    ])
    assert kinds(flags) == [("fully_unutilised", 65000), ("fully_unutilised", 771)]
    assert flags[1].detail.startswith("Entire supplementary provision of ₹7.71 lakh")


def test_reasons_not_communicated_share_per_grant():
    flags = head_flags([
        head(reasons_not_communicated=True, page=7),
        head(reasons_not_communicated=True, category="excess", page=9),
        head(reasons_not_communicated=False),
        head(reasons_not_communicated=True, category="unutilised", final_grant_thousand=None),  # not a variation
        head(grant_no=2, reasons_not_communicated=False),
    ])
    (flag,) = flags
    assert (flag.kind, flag.grant_no, flag.share_pct, flag.pages) == ("reasons_not_communicated", 1, 66.7, (7, 9))
    assert "2 of the 3 heads" in flag.detail


def test_flags_are_ordered_by_kind_then_amount():
    flags = accountability_flags(
        [block(saving_thousand=10, expenditure_thousand=990), block(grant_no=2, saving_thousand=50,
                                                                    expenditure_thousand=950),
         block(grant_no=3, excess_thousand=5, expenditure_thousand=1005)],
        [head(category="unutilised", final_grant_thousand=7)],
    )
    assert [(f.kind, f.grant_no) for f in flags] == [
        ("excess_over_grant", 3), ("savings_not_surrendered", 2), ("savings_not_surrendered", 1),
        ("fully_unutilised", 1),
    ]
