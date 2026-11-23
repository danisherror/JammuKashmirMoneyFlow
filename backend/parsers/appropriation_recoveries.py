"""
Parser for Appendix II of the J&K Appropriation Accounts: recoveries adjusted in reduction of
expenditure, per grant (Budget Estimate and actual, Revenue and Capital, ₹ thousand).

What Appendix II is (checked 2026-11-23 in the three PDFs listed in
`tests/fixtures/appropriation_accounts/SOURCES.md`)
-------------------------------------------------------------------------------------------
Its title is "Grant-wise details of estimates and actuals in respect of recoveries adjusted in the
accounts in reduction of expenditure". It is NOT the Budget Estimates of expenditure: the grants and
the expenditure in the rest of the accounts are gross, and these recoveries are what is deducted to
get net expenditure. The summary's closing page says so ("As the Grants and Charged Appropriations
are for gross amounts ... the expenditure figures shown against them do not include recoveries ...
The net expenditure figures are shown in the Finance Accounts") and prints a reconciliation table
whose "Deduct Recoveries shown in Appendix-II" line must equal the Appendix II total.

Layout
------
Each Appendix II spread is two pages:
  * left page: "Number and Name of Grant | Budget Estimates Revenue | Capital";
  * right page: "Actuals Revenue | Capital | Actuals compared with Budget Estimates More(+)/Less(-)
    Revenue | Capital".
The rows of a right page continue the rows of the left page before it, in the same order; the last
spread ends with a "Total" row. 2023-24 lists every grant (mostly "-"); 2021-22 and 2022-23 list
only the grants with recoveries.

Amounts are right-aligned, and nil cells are usually printed "-" but sometimes left blank (2021-22
grant 15, Revenue). Each amount is therefore put in a column by its right edge: the right edges on a
page fall into exactly 2 (left page) or 4 (right page) groups, ordered left to right. A blank cell is
nil, like "-"; the arithmetic checks below catch a misplaced amount.

Checks (any failure rejects the document)
-----------------------------------------
  * per row and section: actual − Budget Estimate = printed variation;
  * the grant rows add up to the Total row, per column;
  * the actual total (Revenue + Capital) equals the sum of the amounts on the reconciliation's
    "Deduct Recoveries" line;
  * every grant number is one of the grants in the summary table.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import BinaryIO

import pdfplumber

from parsers.appropriation_accounts import (
    TOTAL_TOLERANCE,
    AppropriationAccountsError,
    AppropriationSummary,
    _is_number,
    _to_int,
    parse_appropriation_summary,
)
from parsers.appropriation_details import _has, _lines, _norm

UNIT = "INR thousand"

_SIGNED_RE = re.compile(r"^\(([-+])\)(.+)$")
_NIL = {"-", "--", "–", "—", "..", "..."}
_GRANT_NO_RE = re.compile(r"^\d{1,2}$")
_COLUMN_GAP = 20.0  # right edges of one column stay within a few points; columns are ~100pt apart
_SCAN_LAST_PAGES = 40  # Appendix II is near the end; 2021-22 has 172 pages, the appendix starts at 168


class AppropriationRecoveriesError(AppropriationAccountsError):
    """Appendix II could not be parsed, or its numbers failed a consistency check."""


@dataclass(frozen=True)
class RecoveryLine:
    """Recoveries for one grant and section (₹ thousand). Nil is 0."""

    grant_no: int
    grant_name: str
    section: str  # "revenue" | "capital"
    budget_estimate: int
    actual: int
    page: int  # left page (grant name and Budget Estimate)
    actuals_page: int  # right page (actual and variation)


@dataclass
class AppropriationRecoveries:
    financial_year: str
    unit: str
    lines: list[RecoveryLine] = field(default_factory=list)
    total_budget_estimate: dict[str, int] = field(default_factory=dict)  # per section, as printed
    total_actual: dict[str, int] = field(default_factory=dict)
    reconciliation_recoveries: int | None = None  # sum of the "Deduct Recoveries" line
    reconciliation_page: int | None = None

    def to_dict(self) -> dict:
        return {**asdict(self), "lines": [asdict(line) for line in self.lines]}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_amount(text: str) -> bool:
    if text in _NIL:
        return True
    match = _SIGNED_RE.match(text)
    return _is_number(match.group(2) if match else text)


def _amount(text: str) -> int:
    if text in _NIL:
        return 0
    match = _SIGNED_RE.match(text)
    if match:
        value = _to_int(match.group(2))
        return -value if match.group(1) == "-" else value
    return _to_int(text)


def _columns(words: list[dict], expected: int, where: str) -> list[float]:
    """Right edges of the amount columns, left to right."""
    edges = sorted(w["x1"] for w in words)
    groups: list[list[float]] = []
    for edge in edges:
        if groups and edge - groups[-1][-1] <= _COLUMN_GAP:
            groups[-1].append(edge)
        else:
            groups.append([edge])
    if len(groups) != expected:
        raise AppropriationRecoveriesError(
            f"{where}: expected {expected} amount columns, found {len(groups)} (right edges {edges})"
        )
    return [max(g) for g in groups]


def _column_of(word: dict, columns: list[float]) -> int:
    return min(range(len(columns)), key=lambda i: abs(columns[i] - word["x1"]))


def _body_lines(words: list[dict]) -> list[list[dict]]:
    """Lines below the "(₹ in thousand)" line, which ends the column headers."""
    lines = _lines(words)
    for i, line in enumerate(lines):
        if any(_has(_norm(w["text"]), "thousand") for w in line):
            return lines[i + 1:]
    return []


def _page_kind(words: list[dict]) -> str | None:
    text = _norm(" ".join(w["text"] for w in words[:60]))
    if _has(text, "GRANT-WISE DETAILS OF ESTIMATES AND ACTUALS") and _has(text, "Budget Estimates"):
        return "left"
    if _has(text, "RECOVERIES ADJUSTED IN THE ACCOUNTS") and _has(text, "Actuals compared with"):
        return "right"
    return None


@dataclass
class _LeftRow:
    grant_no: int | None  # None for the Total row
    name: list[str]
    amounts: list[dict]
    page: int


def _left_rows(words: list[dict], page_no: int) -> list[_LeftRow]:
    rows: list[_LeftRow] = []
    for line in _body_lines(words):
        first = line[0]["text"]
        starts_row = _GRANT_NO_RE.match(first) or _norm(first) == _norm("Total")
        if starts_row:
            grant_no = int(first) if first.isdigit() else None
            rest = line[1:] if grant_no is not None else line[1:]
            rows.append(_LeftRow(grant_no, [], [], page_no))
        elif not rows:
            continue  # nothing above the first row but headers
        else:
            rest = line
        for word in rest:
            (rows[-1].amounts if _is_amount(word["text"]) else rows[-1].name).append(
                word if _is_amount(word["text"]) else word["text"]
            )
    return rows


def _right_rows(words: list[dict]) -> list[list[dict]]:
    return [[w for w in line if _is_amount(w["text"])] for line in _body_lines(words) if any(
        _is_amount(w["text"]) for w in line
    )]


def _reconciliation(words: list[dict]) -> int | None:
    """Sum of the amounts on the "Deduct Recoveries shown in Appendix-II" line(s)."""
    lines = _lines(words)
    start = next(
        (i for i, line in enumerate(lines) if _has(_norm(" ".join(w["text"] for w in line)), "Deduct Recoveries")), None
    )
    if start is None:
        return None
    total = 0
    for line in lines[start:]:
        text = _norm(" ".join(w["text"] for w in line))
        if line is not lines[start] and _has(text, "Net Total", "Net Expenditure"):
            break
        total += sum(_amount(w["text"]) for w in line if _is_amount(w["text"]))
        if _has(text, "Appendix"):
            break
    return total


# ── Parser ────────────────────────────────────────────────────────────────────


def parse_appropriation_recoveries(
    source: str | Path | BinaryIO,
    summary: AppropriationSummary | None = None,
    validate: bool = True,
) -> AppropriationRecoveries:
    if summary is None:
        if hasattr(source, "seek"):
            source.seek(0)
        summary = parse_appropriation_summary(source)
        if hasattr(source, "seek"):
            source.seek(0)

    out = AppropriationRecoveries(financial_year=summary.financial_year, unit=UNIT)
    pages: list[tuple[int, str, list[dict]]] = []
    with pdfplumber.open(source) as pdf:
        n = len(pdf.pages)
        for page_no in range(1, n + 1):
            near_end = page_no > n - _SCAN_LAST_PAGES
            if out.reconciliation_page is None or near_end:
                words = pdf.pages[page_no - 1].extract_words()
            else:
                continue
            if out.reconciliation_page is None:
                recoveries = _reconciliation(words)
                if recoveries is not None and _has(_norm(" ".join(w["text"] for w in words)), "Appendix-II"):
                    out.reconciliation_recoveries = recoveries
                    out.reconciliation_page = page_no
                    continue
            if near_end:
                kind = _page_kind(words)
                if kind:
                    pages.append((page_no, kind, words))

    if not pages:
        raise AppropriationRecoveriesError("no Appendix II pages found")

    totals_seen = False
    for i in range(0, len(pages), 2):
        left_no, left_kind, left_words = pages[i]
        if left_kind != "left" or i + 1 >= len(pages) or pages[i + 1][1] != "right":
            raise AppropriationRecoveriesError(f"page {left_no}: Appendix II pages are not in left/right pairs")
        right_no, _, right_words = pages[i + 1]

        left = _left_rows(left_words, left_no)
        right = _right_rows(right_words)
        if len(left) != len(right):
            raise AppropriationRecoveriesError(
                f"pages {left_no}/{right_no}: {len(left)} grant rows but {len(right)} rows of actuals"
            )
        left_cols = _columns([w for r in left for w in r.amounts], 2, f"page {left_no}")
        right_cols = _columns([w for r in right for w in r], 4, f"page {right_no}")

        for row, actual_words in zip(left, right):
            be = [0, 0]
            for w in row.amounts:
                be[_column_of(w, left_cols)] = _amount(w["text"])
            act = [0, 0, 0, 0]
            for w in actual_words:
                act[_column_of(w, right_cols)] = _amount(w["text"])
            where = f"pages {left_no}/{right_no}, " + (f"grant {row.grant_no}" if row.grant_no else "Total")
            for s, section in enumerate(("revenue", "capital")):
                if act[s] - be[s] != act[2 + s]:
                    raise AppropriationRecoveriesError(
                        f"{where} {section}: actual {act[s]} − estimate {be[s]} != printed variation {act[2 + s]}"
                    )
            if row.grant_no is None:
                out.total_budget_estimate = {"revenue": be[0], "capital": be[1]}
                out.total_actual = {"revenue": act[0], "capital": act[1]}
                totals_seen = True
                continue
            name = " ".join(row.name).strip()
            for s, section in enumerate(("revenue", "capital")):
                out.lines.append(RecoveryLine(row.grant_no, name, section, be[s], act[s], left_no, right_no))

    if not totals_seen:
        raise AppropriationRecoveriesError("Appendix II has no Total row")
    if validate:
        validate_recoveries(out, summary)
    return out


def validate_recoveries(rec: AppropriationRecoveries, summary: AppropriationSummary) -> None:
    problems: list[str] = []
    for section in ("revenue", "capital"):
        be = sum(line.budget_estimate for line in rec.lines if line.section == section)
        act = sum(line.actual for line in rec.lines if line.section == section)
        if abs(be - rec.total_budget_estimate.get(section, 0)) > TOTAL_TOLERANCE:
            problems.append(f"{section} estimates add up to {be}, Total row says {rec.total_budget_estimate.get(section)}")
        if abs(act - rec.total_actual.get(section, 0)) > TOTAL_TOLERANCE:
            problems.append(f"{section} actuals add up to {act}, Total row says {rec.total_actual.get(section)}")
    if rec.reconciliation_recoveries is None:
        problems.append("no reconciliation table with a 'Deduct Recoveries' line found")
    elif abs(sum(rec.total_actual.values()) - rec.reconciliation_recoveries) > TOTAL_TOLERANCE:
        problems.append(
            f"Appendix II actual total {sum(rec.total_actual.values())} != reconciliation "
            f"'Deduct Recoveries' {rec.reconciliation_recoveries} (page {rec.reconciliation_page})"
        )
    unknown = sorted({line.grant_no for line in rec.lines} - set(summary.grants))
    if unknown:
        problems.append(f"grants {unknown} are not in the summary table")
    seen: set[tuple[int, str]] = set()
    for line in rec.lines:
        if (line.grant_no, line.section) in seen:
            problems.append(f"grant {line.grant_no} {line.section} appears twice")
        seen.add((line.grant_no, line.section))
        if not line.grant_name:
            problems.append(f"grant {line.grant_no} (page {line.page}) has no name")
    if problems:
        raise AppropriationRecoveriesError(
            f"Appropriation Accounts {rec.financial_year} Appendix II failed validation:\n  - " + "\n  - ".join(problems)
        )


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Extract Appendix II (recoveries) of a J&K Appropriation Accounts PDF.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args(argv)
    try:
        rec = parse_appropriation_recoveries(args.pdf)
    except AppropriationAccountsError as exc:
        print(exc, file=sys.stderr)
        return 1
    json.dump(rec.to_dict(), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
