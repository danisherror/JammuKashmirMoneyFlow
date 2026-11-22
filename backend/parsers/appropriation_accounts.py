"""
Parser for the "Summary of Appropriation Accounts" table in the J&K Appropriation Accounts.

Source documents
----------------
The Appropriation Accounts of the Union Territory of Jammu and Kashmir are prepared by the
Principal Accountant General (A&E), J&K, and published by the CAG. Each year's PDF has a
"Summary of Appropriation Accounts" near the front: one block per grant (department), split
into Revenue / Capital and Voted / Charged rows, with columns
    Amount of the Grant or Appropriation | Expenditure | Saving | Excess | Percentage ...
in ₹ thousand, followed by a "Total :" block.

Verified layouts (2026-11-22):
  2021-22  https://saiindia.gov.in/uploads/state_accounts_report/account-report-Appropriation-2021-22-English-08-12-2022-063aa89a8638765-77820288.pdf
           (same file is served under https://cag.gov.in/uploads/state_accounts_report/...)
  2022-23  https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2022-23-J-K-English-28-02-2024-066bf1b4e8f88f3-67986467.pdf
  2023-24  https://cag.gov.in/uploads/state_accounts_report/account-report-Appropriation-2023-24-UT-JK-English-28-03-2025-069d791c2d23943-29281571.pdf

Layout quirks this parser handles (seen in the PDFs above):
  * Numbers use Indian digit grouping ("1,07,71,19,60" = 107,711,960 thousand).
  * Column headers are not right-aligned with the numbers under them (2022-23), so each number is
    assigned to the column whose header centre is nearest, not by header edges.
  * When a row has an excess, the excess and expenditure cells wrap onto extra lines above/below
    the "Voted"/"Charged" label (2021-22), and a whole-rupee figure in brackets is printed under
    them. Numbers are attached to the nearest row label vertically; bracketed figures are ignored.
  * Footnote markers (*, #, $, ^) are glued to some numbers; "-", "--" and ".." mean nil.

What the numbers mean
---------------------
"Amount of the Grant or Appropriation" is the FINAL grant (original + supplementary), not the
Budget Estimate. "Expenditure" is GROSS expenditure (recoveries are deducted only in the Finance
Accounts). Do not load these figures as Budget Estimates or as net spend.

Every parse is checked: each row must satisfy grant - expenditure = saving - excess, and the
rows must add up to the printed "Total :" block. A document that fails is rejected, never
partially loaded.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable

import pdfplumber

UNIT = "INR thousand"

# Rows: grant - expenditure must equal saving - excess within this many thousand rupees.
ROW_TOLERANCE = 2
# Totals: the PDFs note that printed totals can differ from the sum of rows by 1-2 thousand
# because of "machine rounding" (2021-22 footnotes), so allow a little slack.
TOTAL_TOLERANCE = 5

_NUMBER_RE = re.compile(r"^(\d{1,3}(?:,\d{2})*(?:,\d{3})?|\d+)[*#$^@]*$")
_BRACKETED_RE = re.compile(r"^\([\d,]+\)[*#$^@]*$")
_NIL_TOKENS = {"-", "--", "..", "...", "—", "–"}
_FY_RE = re.compile(r"^(\d{4})-(\d{2})$")
_COLUMNS = ("grant", "expenditure", "saving", "excess")


class AppropriationAccountsError(ValueError):
    """The PDF could not be parsed, or the parsed numbers failed a consistency check."""


@dataclass(frozen=True)
class GrantLine:
    grant_no: int
    grant_name: str
    section: str  # "revenue" | "capital"
    kind: str  # "voted" | "charged"
    grant_amount: int  # final grant/appropriation, ₹ thousand
    expenditure: int  # gross expenditure, ₹ thousand
    saving: int
    excess: int
    page: int  # 1-based page number in the parsed PDF


@dataclass(frozen=True)
class TotalLine:
    section: str
    kind: str
    grant_amount: int
    expenditure: int
    saving: int
    excess: int
    page: int


@dataclass
class AppropriationSummary:
    financial_year: str
    unit: str
    lines: list[GrantLine] = field(default_factory=list)
    totals: list[TotalLine] = field(default_factory=list)

    @property
    def grants(self) -> dict[int, str]:
        return {line.grant_no: line.grant_name for line in self.lines}

    def to_dict(self) -> dict:
        return {
            "financial_year": self.financial_year,
            "unit": self.unit,
            "lines": [asdict(line) for line in self.lines],
            "totals": [asdict(total) for total in self.totals],
        }


# ── Word helpers ──────────────────────────────────────────────────────────────


def _is_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text))


def _is_value_token(text: str) -> bool:
    return _is_number(text) or text in _NIL_TOKENS or bool(_BRACKETED_RE.match(text))


def _to_int(text: str) -> int:
    match = _NUMBER_RE.match(text)
    if not match:
        raise AppropriationAccountsError(f"not a number: {text!r}")
    return int(match.group(1).replace(",", ""))


def _center_x(word: dict) -> float:
    return (word["x0"] + word["x1"]) / 2


def _center_y(words: list[dict]) -> float:
    return sum((w["top"] + w["bottom"]) / 2 for w in words) / len(words)


def _group_lines(words: Iterable[dict], tolerance: float = 3.0) -> list[list[dict]]:
    """Group words into visual lines by their top coordinate."""
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0]["top"] - word["top"]) <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _label(text: str) -> str:
    return text.rstrip("-:").strip().lower()


# ── Page layout ───────────────────────────────────────────────────────────────


@dataclass
class _Layout:
    boundaries: tuple[float, float, float, float]  # grant|exp, exp|saving, saving|excess, excess|percentage
    data_top: float
    years: list[str]


def _find_layout(words: list[dict]) -> _Layout | None:
    """Locate the column headers. Returns None for pages that are not part of the summary table."""
    lines = _group_lines(words)
    for line in lines:
        texts = [w["text"] for w in line]
        if not {"Expenditure", "Saving", "Excess", "Amount"} <= set(texts):
            continue
        by_text = {w["text"]: w for w in line}
        amount_idx = texts.index("Amount")
        amount_end = line[amount_idx + 1] if amount_idx + 1 < len(line) else line[amount_idx]
        centers = [
            (line[amount_idx]["x0"] + amount_end["x1"]) / 2,
            _center_x(by_text["Expenditure"]),
            _center_x(by_text["Saving"]),
            _center_x(by_text["Excess"]),
        ]
        percentage = by_text.get("Percentage")
        pct_left = percentage["x0"] if percentage else centers[3] + 50
        boundaries = (
            (centers[0] + centers[1]) / 2,
            (centers[1] + centers[2]) / 2,
            (centers[2] + centers[3]) / 2,
            (centers[3] + pct_left) / 2,
        )

        header_top = line[0]["top"]
        unit_words = [w for w in words if w["text"].startswith("thousand") and w["top"] > header_top]
        if not unit_words:
            raise AppropriationAccountsError("summary page does not state '(₹ in thousand)'; unit unknown")
        data_top = min(w["bottom"] for w in unit_words)
        years = sorted({w["text"] for w in words if _FY_RE.match(w["text"]) and header_top < w["top"] < data_top})
        return _Layout(boundaries=boundaries, data_top=data_top, years=years)
    return None


def _column(word: dict, boundaries: tuple[float, float, float, float]) -> str | None:
    x = _center_x(word)
    for name, edge in zip(_COLUMNS, boundaries):
        if x < edge:
            return name
    return None  # percentage columns


# ── Parsing ───────────────────────────────────────────────────────────────────


@dataclass
class _Row:
    kind: str
    words: list[dict]
    grant_no: int | None
    grant_name: str
    section: str | None
    is_total: bool


def _is_heading(line: list[dict]) -> bool:
    first = line[0]
    return (
        len(line) >= 2
        and first["text"].isdigit()
        and len(first["text"]) <= 3
        and not _is_value_token(line[1]["text"])
    )


def parse_appropriation_summary(source: str | Path | BinaryIO, validate: bool = True) -> AppropriationSummary:
    """Parse the Summary of Appropriation Accounts from a J&K Appropriation Accounts PDF.

    `source` may be a path or a binary file object, and may be the full document or just the
    summary pages. Amounts are integers in ₹ thousand, exactly as printed.
    """
    lines_out: list[GrantLine] = []
    totals_out: list[TotalLine] = []
    years_seen: set[str] = set()

    grant_no: int | None = None
    grant_name = ""
    section: str | None = None
    in_totals = False
    expect_name_continuation = False
    found_table = False

    with pdfplumber.open(source) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            layout = _find_layout(words)
            if layout is None:
                if found_table and in_totals:
                    break  # past the table (regularisation / reconciliation pages)
                continue
            found_table = True
            years_seen.update(layout.years)

            body = [w for w in words if w["top"] >= layout.data_top]
            text_lines: list[tuple[list[dict], float]] = []
            value_lines: list[list[dict]] = []
            for line in _group_lines(body):
                if all(_is_value_token(w["text"]) for w in line):
                    value_lines.append(line)
                else:
                    text_lines.append((line, _center_y(line)))

            # Walk text lines top to bottom to track grant/section state and create row anchors.
            rows: list[_Row] = []
            anchors: list[tuple[float, _Row | None]] = []
            for line, y in text_lines:
                first = _label(line[0]["text"])
                row: _Row | None = None
                if _is_heading(line):
                    grant_no = int(line[0]["text"])
                    grant_name = " ".join(w["text"] for w in line[1:])
                    section = None
                    in_totals = False
                    expect_name_continuation = True
                elif first in ("revenue", "capital"):
                    section = first
                    expect_name_continuation = False
                elif first in ("voted", "charged"):
                    row = _Row(
                        kind=first,
                        words=line[1:],
                        grant_no=grant_no,
                        grant_name=_clean_name(grant_name),
                        section=section,
                        is_total=in_totals,
                    )
                    rows.append(row)
                    expect_name_continuation = False
                elif first == "total":
                    in_totals = True
                    section = None
                    expect_name_continuation = False
                elif expect_name_continuation and section is None and not in_totals:
                    grant_name += " " + " ".join(w["text"] for w in line)
                    continue
                else:
                    expect_name_continuation = False  # note / footnote line: anchors nothing
                anchors.append((y, row))

            if not anchors:
                continue

            # Attach wrapped value-only lines to the nearest text line, if that line is a row.
            for line in value_lines:
                y = _center_y(line)
                _, nearest = min(anchors, key=lambda a: abs(a[0] - y))
                if nearest is not None:
                    nearest.words.extend(line)

            for row in rows:
                g_no, g_name, sec, is_total = row.grant_no, row.grant_name, row.section, row.is_total
                where = f"page {page_index}, " + ("Total" if is_total else f"grant {g_no}") + f" {sec}/{row.kind}"
                if sec is None:
                    raise AppropriationAccountsError(f"{where}: row has no Revenue/Capital heading")
                values: dict[str, int] = {}
                for word in row.words:
                    text = word["text"]
                    if not _is_number(text):
                        continue  # nil markers and bracketed whole-rupee figures
                    column = _column(word, layout.boundaries)
                    if column is None:
                        continue
                    if column in values:
                        raise AppropriationAccountsError(f"{where}: two values in the {column} column")
                    values[column] = _to_int(text)
                if "grant" not in values:
                    raise AppropriationAccountsError(f"{where}: no grant amount found")
                amounts = {c: values.get(c, 0) for c in _COLUMNS}
                if is_total:
                    totals_out.append(
                        TotalLine(
                            section=sec,
                            kind=row.kind,
                            grant_amount=amounts["grant"],
                            expenditure=amounts["expenditure"],
                            saving=amounts["saving"],
                            excess=amounts["excess"],
                            page=page_index,
                        )
                    )
                else:
                    if g_no is None:
                        raise AppropriationAccountsError(f"{where}: row appears before any grant heading")
                    lines_out.append(
                        GrantLine(
                            grant_no=g_no,
                            grant_name=g_name,
                            section=sec,
                            kind=row.kind,
                            grant_amount=amounts["grant"],
                            expenditure=amounts["expenditure"],
                            saving=amounts["saving"],
                            excess=amounts["excess"],
                            page=page_index,
                        )
                    )

    if not found_table:
        raise AppropriationAccountsError("no 'Summary of Appropriation Accounts' table found")
    if not years_seen:
        raise AppropriationAccountsError("could not find the financial year in the table header")

    summary = AppropriationSummary(financial_year=max(years_seen), unit=UNIT, lines=lines_out, totals=totals_out)
    if validate:
        validate_summary(summary)
    return summary


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().rstrip("-").strip()


# ── Validation ────────────────────────────────────────────────────────────────


def validate_summary(summary: AppropriationSummary) -> None:
    """Raise AppropriationAccountsError listing every inconsistency found."""
    problems: list[str] = []

    if not summary.lines:
        problems.append("no grant rows parsed")
    if not summary.totals:
        problems.append("no 'Total :' block parsed")

    for line in summary.lines:
        diff = (line.grant_amount - line.expenditure) - (line.saving - line.excess)
        if abs(diff) > ROW_TOLERANCE:
            problems.append(
                f"grant {line.grant_no} {line.section}/{line.kind} (page {line.page}): "
                f"grant - expenditure != saving - excess (off by {diff})"
            )
        if line.saving and line.excess:
            problems.append(f"grant {line.grant_no} {line.section}/{line.kind}: both saving and excess set")

    seen: set[tuple[int, str, str]] = set()
    for line in summary.lines:
        key = (line.grant_no, line.section, line.kind)
        if key in seen:
            problems.append(f"grant {line.grant_no} {line.section}/{line.kind} appears twice")
        seen.add(key)

    totals = {(t.section, t.kind): t for t in summary.totals}
    row_keys = {(line.section, line.kind) for line in summary.lines}
    for key in row_keys - set(totals):
        problems.append(f"no printed total for {key[0]}/{key[1]}")
    for key, total in totals.items():
        rows = [line for line in summary.lines if (line.section, line.kind) == key]
        for attr_line, attr_total in (
            ("grant_amount", "grant_amount"),
            ("expenditure", "expenditure"),
            ("saving", "saving"),
            ("excess", "excess"),
        ):
            row_sum = sum(getattr(line, attr_line) for line in rows)
            printed = getattr(total, attr_total)
            if abs(row_sum - printed) > TOTAL_TOLERANCE:
                problems.append(
                    f"{key[0]}/{key[1]} {attr_line}: rows add up to {row_sum}, printed total is {printed}"
                )

    if problems:
        raise AppropriationAccountsError(
            f"Appropriation Accounts {summary.financial_year} failed validation:\n  - " + "\n  - ".join(problems)
        )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import csv
    import json
    import sys

    parser = argparse.ArgumentParser(description="Extract the Summary of Appropriation Accounts from a J&K PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)

    try:
        summary = parse_appropriation_summary(args.pdf)
    except AppropriationAccountsError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.format == "json":
        json.dump(summary.to_dict(), sys.stdout, indent=2)
        print()
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=["financial_year", "unit", *GrantLine.__dataclass_fields__])
        writer.writeheader()
        for line in summary.lines:
            writer.writerow({"financial_year": summary.financial_year, "unit": summary.unit, **asdict(line)})
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
