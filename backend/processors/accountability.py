"""
Accountability flags computed from the stored grant pages of the CAG Appropriation Accounts
(todo.md 2.2b). Nothing here is invented or estimated: each flag restates printed figures.

Flags
-----
excess_over_grant        A Voted/Charged block spent more than its final grant. An excess over a
                         grant must be regularised by the legislature (the summary prints "The
                         excesses over the following charged appropriations/voted grants require
                         regularisation").
savings_not_surrendered  A block ended with a saving larger than the amount surrendered during the
                         year. Flag amount = saving − surrendered.
supplementary_not_needed A block took a supplementary grant but its final saving is at least as
                         large, so the money was not needed. Flag amount = the supplementary.
fully_unutilised         A head whose entire provision (or entire supplementary provision) remained
                         un-utilised, as the note says. Flag amount = that provision.
reasons_not_communicated Per grant: the share of heads listed under saving / excess notes whose
                         note says the reasons were not communicated.

Pure functions over plain values, so they can be tested without a database; amounts are in
₹ thousand like the stored rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

KINDS = (
    "excess_over_grant",
    "savings_not_surrendered",
    "supplementary_not_needed",
    "fully_unutilised",
    "reasons_not_communicated",
)


class BlockLike(Protocol):
    grant_no: int
    section: str
    kind: str
    supplementary_thousand: int
    final_grant_thousand: int
    expenditure_thousand: int
    saving_thousand: int
    excess_thousand: int
    surrendered_thousand: int
    page: int


class HeadLike(Protocol):
    grant_no: int
    section: str
    kind: str
    category: str
    reasons_not_communicated: bool
    head_code: str
    head_name: str
    final_grant_thousand: int | None
    page: int


@dataclass(frozen=True)
class Flag:
    kind: str
    grant_no: int
    detail: str
    page: int
    amount_thousand: int | None = None
    section: str | None = None
    block_kind: str | None = None  # voted | charged
    head_code: str | None = None
    head_name: str | None = None
    share_pct: float | None = None
    pages: tuple[int, ...] = ()


def _lakh(thousand: int) -> str:
    """₹ lakh with two decimals, as the PDFs print the notes."""
    return f"₹{thousand / 100:,.2f} lakh"


def block_flags(blocks: Iterable[BlockLike]) -> list[Flag]:
    flags: list[Flag] = []
    for b in blocks:
        where = dict(grant_no=b.grant_no, section=b.section, block_kind=b.kind, page=b.page)
        label = f"{b.section.capitalize()} {b.kind}"
        if b.excess_thousand > 0:
            flags.append(Flag(
                "excess_over_grant", amount_thousand=b.excess_thousand,
                detail=f"{label}: spent {_lakh(b.expenditure_thousand)} against a final grant of "
                       f"{_lakh(b.final_grant_thousand)}, an excess of {_lakh(b.excess_thousand)} that needs "
                       "regularisation by the legislature",
                **where,
            ))
        unsurrendered = b.saving_thousand - b.surrendered_thousand
        if b.saving_thousand > 0 and unsurrendered > 0:
            flags.append(Flag(
                "savings_not_surrendered", amount_thousand=unsurrendered,
                detail=f"{label}: saving of {_lakh(b.saving_thousand)}, of which {_lakh(b.surrendered_thousand)} "
                       f"was surrendered during the year; {_lakh(unsurrendered)} was not",
                **where,
            ))
        if b.supplementary_thousand > 0 and b.saving_thousand >= b.supplementary_thousand:
            flags.append(Flag(
                "supplementary_not_needed", amount_thousand=b.supplementary_thousand,
                detail=f"{label}: supplementary grant of {_lakh(b.supplementary_thousand)}, but the final "
                       f"saving was {_lakh(b.saving_thousand)}",
                **where,
            ))
    return flags


def head_flags(heads: Iterable[HeadLike]) -> list[Flag]:
    heads = list(heads)
    flags: list[Flag] = []
    for h in heads:
        if h.category in ("unutilised", "unutilised_supplementary") and h.final_grant_thousand:
            what = "Entire supplementary provision" if h.category == "unutilised_supplementary" else "Entire provision"
            flags.append(Flag(
                "fully_unutilised", grant_no=h.grant_no, section=h.section, block_kind=h.kind,
                head_code=h.head_code, head_name=h.head_name, amount_thousand=h.final_grant_thousand,
                detail=f"{what} of {_lakh(h.final_grant_thousand)} under {h.head_code} {h.head_name} "
                       "remained un-utilised",
                page=h.page,
            ))

    by_grant: dict[int, list[HeadLike]] = {}
    for h in heads:
        if h.category in ("saving", "excess"):
            by_grant.setdefault(h.grant_no, []).append(h)
    for grant_no, rows in sorted(by_grant.items()):
        missing = [h for h in rows if h.reasons_not_communicated]
        if not missing:
            continue
        share = round(len(missing) / len(rows) * 100, 1)
        pages = tuple(sorted({h.page for h in missing}))
        flags.append(Flag(
            "reasons_not_communicated", grant_no=grant_no, share_pct=share, page=pages[0], pages=pages,
            detail=f"Reasons were not communicated for {len(missing)} of the {len(rows)} heads with notable "
                   f"savings or excesses ({share:g}%)",
        ))
    return flags


def accountability_flags(blocks: Iterable[BlockLike], heads: Iterable[HeadLike]) -> list[Flag]:
    """All flags, ordered by kind (see KINDS) and then by amount, largest first."""
    flags = block_flags(blocks) + head_flags(heads)
    order = {kind: i for i, kind in enumerate(KINDS)}
    return sorted(flags, key=lambda f: (order[f.kind], -(f.amount_thousand or 0), -(f.share_pct or 0), f.grant_no))
