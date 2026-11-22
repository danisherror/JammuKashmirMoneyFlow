"""The Live / Official / Combined rules (processors.combined_view), without a database."""
import pytest

from processors.combined_view import MISMATCH_THRESHOLD_PCT, Figure, Mismatch, View, compare, resolve

LIVE = Figure(value=103.0, source_type="live", label="Live · portal")
OFFICIAL = Figure(value=100.0, source_type="official", label="Official · Appropriation Accounts 2022-23, p.2",
                  snapshot_id=1, page=2)


def test_threshold_is_two_percent():
    assert MISMATCH_THRESHOLD_PCT == 2.0


@pytest.mark.parametrize(
    "live, official, expected",
    [
        (100.0, 100.0, None),
        (102.0, 100.0, None),                        # exactly 2% is not a mismatch
        (98.0, 100.0, None),
        (102.01, 100.0, Mismatch(102.01, 100.0, 2.01)),
        (97.0, 100.0, Mismatch(97.0, 100.0, -3.0)),
        (0.0, 0.0, None),
        (5.0, 0.0, Mismatch(5.0, 0.0, None)),        # no percentage against zero
        (0.0, 50.0, Mismatch(0.0, 50.0, -100.0)),
    ],
)
def test_compare(live, official, expected):
    assert compare(live, official) == expected


def test_rule_1_official_wins_in_combined():
    close_live = Figure(value=101.0, source_type="live", label="Live · portal")
    r = resolve(View.COMBINED, close_live, OFFICIAL)
    assert (r.figure, r.provisional, r.mismatch) == (OFFICIAL, False, None)


def test_rule_2_live_only_is_provisional():
    r = resolve(View.COMBINED, LIVE, None)
    assert (r.figure, r.provisional, r.mismatch) == (LIVE, True, None)


def test_rule_3_official_with_flag_when_they_differ():
    r = resolve(View.COMBINED, LIVE, OFFICIAL)
    assert r.figure == OFFICIAL
    assert r.value == 100.0
    assert r.mismatch == Mismatch(live=103.0, official=100.0, diff_pct=3.0)
    assert not r.provisional


def test_rule_4_neither_is_no_data_not_zero():
    r = resolve(View.COMBINED, None, None, note="No budget figure for 2019-20")
    assert r.figure is None
    assert r.value is None
    assert r.note == "No budget figure for 2019-20"


def test_not_comparable_skips_the_flag():
    r = resolve(View.COMBINED, LIVE, OFFICIAL, comparable=False)
    assert (r.figure, r.mismatch) == (OFFICIAL, None)


def test_live_view_ignores_official():
    r = resolve(View.LIVE, LIVE, OFFICIAL)
    assert (r.figure, r.provisional, r.mismatch) == (LIVE, True, None)
    assert resolve(View.LIVE, None, OFFICIAL, note="none").figure is None


def test_official_view_ignores_live_and_never_flags():
    r = resolve(View.OFFICIAL, LIVE, OFFICIAL)
    assert (r.figure, r.provisional, r.mismatch) == (OFFICIAL, False, None)
    missing = resolve(View.OFFICIAL, LIVE, None, note="No CAG figure")
    assert (missing.figure, missing.note) == (None, "No CAG figure")


def test_view_values():
    assert [v.value for v in View] == ["live", "official", "combined"]
