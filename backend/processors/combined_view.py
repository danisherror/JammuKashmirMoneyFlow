"""
Live / Official / Combined views of the same figure (todo.md 2.2a).

  live      portal collectors and the budget tables; provisional
  official  CAG Appropriation Accounts (audited, per department grant)
  combined  worked out here at query time, never stored:
            1. an official figure exists       -> show it
            2. only a live figure exists       -> show it, marked provisional
            3. both exist and differ by > 2%   -> show the official figure with a mismatch flag
            4. neither exists                  -> no data (None), never 0

This module is pure (no database), so the rules can be tested on their own.
All values are ₹ lakhs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

MISMATCH_THRESHOLD_PCT = 2.0


class View(str, Enum):
    LIVE = "live"
    OFFICIAL = "official"
    COMBINED = "combined"


@dataclass(frozen=True)
class Figure:
    """One number from one source, with everything needed to trace it."""
    value: float
    source_type: str                     # "live" | "official"
    label: str                           # "Official · Appropriation Accounts 2022-23, p.4"
    measure: str | None = None           # what the number is: "final_grant", "budget_estimate", ...
    source_url: str | None = None
    snapshot_id: int | None = None
    page: int | None = None
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class Mismatch:
    live: float
    official: float
    diff_pct: float | None               # (live - official) / official * 100; None when official is 0


@dataclass(frozen=True)
class Resolved:
    figure: Figure | None                # None = no data
    provisional: bool = False
    mismatch: Mismatch | None = None
    note: str | None = None              # why there is no figure, when there isn't one

    @property
    def value(self) -> float | None:
        return self.figure.value if self.figure else None


def compare(live: float, official: float) -> Mismatch | None:
    """A Mismatch when live and official differ by more than the threshold, else None."""
    if official == 0:
        return Mismatch(live, official, None) if live != 0 else None
    diff_pct = (live - official) / abs(official) * 100
    if abs(diff_pct) <= MISMATCH_THRESHOLD_PCT:
        return None
    return Mismatch(live, official, round(diff_pct, 2))


def resolve(
    view: View,
    live: Figure | None,
    official: Figure | None,
    *,
    comparable: bool = True,
    note: str | None = None,
) -> Resolved:
    """
    Pick the figure to show for `view`.

    `comparable=False` turns off the mismatch check, for figures where live and official don't cover
    the same thing (e.g. the UT-wide total: the budget tables list only some departments, the CAG
    accounts all 36 grants). Live and official are compared only per department.
    """
    if view is View.LIVE:
        return Resolved(live, provisional=live is not None, note=None if live else note)
    if view is View.OFFICIAL:
        return Resolved(official, note=None if official else note)

    if official is not None:
        mismatch = compare(live.value, official.value) if live is not None and comparable else None
        return Resolved(official, mismatch=mismatch)
    if live is not None:
        return Resolved(live, provisional=True)
    return Resolved(None, note=note)
