"""
Parser for the grant pages of the J&K Appropriation Accounts: how each grant's money was used.

`parsers.appropriation_accounts` reads only the "Summary of Appropriation Accounts" table at the
front of the PDF. After it, every grant has its own pages (printed page 1 onwards), which this
module reads. Layout checked 2026-11-22 in the three PDFs listed in
`tests/fixtures/appropriation_accounts/SOURCES.md` (2021-22, 2022-23, 2023-24).

What a grant's pages contain
----------------------------
1. A heading ("GRANT NO. 1-GENERAL ADMINISTRATION DEPARTMENT"), then for each section (Revenue /
   Capital) the list of MAJOR HEADS and, per Voted / Charged block, the lines
       Original <amount> / Supplementary <amount> / final grant, actual expenditure, saving or
       excess / Amount surrendered during the year <amount>
   in ₹ THOUSAND, Indian digit grouping. "Voted" is not always printed when a section has only a
   voted block (2023-24 grant 36), so a block with no label is taken as voted and then checked
   against the summary table.
2. "Notes and Comments", grouped under "<Revenue|Capital> <Voted|Charged> Section" headings. Each
   numbered note is a sentence (e.g. "Saving in the Section occurred under the following Heads/
   Schemes; reasons for which were not communicated [July 2024].") usually followed by a table
   with the columns "Head | Total Grant/Appropriation | Actual Expenditure | Saving(-) or
   Excess(+) | Remarks" in ₹ LAKH with two decimals. Table variants seen:
     * saving and excess tables: per head, O (original), S (supplementary) and R
       (re-appropriation) amounts, then total grant, actual and the variation, and a remark.
       2021-22 has no R line: its S is "Supplementary/Re-appropriation" combined and can be
       negative;
     * "Entire provision remained un-utilised" (and "Entire Supplementary provision ..."):
       only the total grant column;
     * "Expenditure ... was incurred without Budgetary Provision": only the actual column.
   The head column lists the head path one code per line: major head (4 digits), optional
   sub-major (2), minor (3), sub-head (4, e.g. 0099 General) and detailed head (4).

Layout quirks handled
---------------------
  * Remark text is often glued to the number before it ("(-)34.24mainly", "7.71is"); the number
    is split off and its right edge estimated from its share of the characters.
  * Some notes are printed without spaces ("Entireprovisionremainedun-utilised..."), so note text
    is classified after removing spaces.
  * Excess rows carry the exact rupee figure in brackets ("(18,89,773)"); it is ignored.
  * Head names and remarks wrap onto extra lines, and a head's values can sit on a wrapped line.
  * A note number can sit a few points away from its first text line.

Units
-----
Section totals are printed in ₹ thousand, note tables in ₹ lakh with two decimals. 1 lakh = 100
thousand, so a lakh amount with two decimals is an exact whole number of thousands. Every amount
here is returned as an integer in ₹ THOUSAND, the same unit as the summary table; nothing is
rounded.

Checks
------
`validate_details` rejects the whole document if anything is inconsistent: each section block must
satisfy original + supplementary = final grant and final grant - actual = saving - excess and must
match the summary table row for that grant/section/kind; each note row must satisfy
O + S + R = total grant and total grant - actual = saving - excess, and its major head must be one
listed for that grant and section. The notes list only selected heads, so they do not add up to
the section totals and are not checked against them.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import BinaryIO

import pdfplumber

from parsers.appropriation_accounts import (
    ROW_TOLERANCE,
    AppropriationAccountsError,
    AppropriationSummary,
    _is_number,
    _to_int,
    parse_appropriation_summary,
)

UNIT = "INR thousand"

# Note rows are printed to 0.01 lakh = 1 thousand; allow one unit of rounding.
HEAD_TOLERANCE = 1

# Rows whose printed figures don't add up in the PDF itself. They are kept exactly as printed and
# carry `printed_error`, so the dashboard can show the discrepancy instead of hiding the row.
# Key: (financial year, grant, head code, note category). Each entry is checked: the row must
# exist and must actually fail a check, so a stale entry fails validation. Pages in the comments
# are PDF pages of the full documents in SOURCES.md.
KNOWN_PRINTED_ERRORS: dict[tuple[str, int, str, str], str] = {
    ("2022-23", 18, "4236.02.800.0011.1287", "saving"): (  # page 107
        "Printed saving (-)79.91 lakh, but total grant 2,500.00 - actual 2,420.81 = 79.19 lakh"
    ),
    ("2022-23", 32, "4401.800.0011.0222", "saving"): (  # page 150
        "Printed saving (-)1,131.37 lakh, but total grant 3,110.99 - actual 1,979.52 = 1,131.47 lakh"
    ),
    ("2023-24", 17, "4210.04.101.0011.1544", "saving"): (  # page 87
        "Printed saving (-)1,433.07 lakh, but total grant 2,500.00 - actual 1,066.33 = 1,433.67 lakh"
    ),
}

LEVELS = ("major", "sub_major", "minor", "sub_head", "detailed")

_GRANT_HEADING_RE = re.compile(r"^GRANT\s+NO\.?\s*(\d+)\s*-?\s*(.*)$", re.IGNORECASE)  # "Grant No. 8(Contd.)"
_LAKH_RE = re.compile(r"^(?:\(([-+])\))?(\d[\d,]*)\.(\d{2})$")
_GLUED_LAKH_RE = re.compile(r"^((?:\([-+]\))?\d[\d,]*\.\d{2})(\D.*)$")
_BRACKETED_RE = re.compile(r"^\([\d,.]+\)$")
_SIGNED_THOUSAND_RE = re.compile(r"^\(([-+])\)(.+)$")
_NIL_TOKENS = {"..", "...", "-", "--", "—", "–", "Nil", "NIL"}
_CODE_RE = re.compile(r"^\d{2,4}$")
_SECTION_HEADING_RE = re.compile(r"^(revenue|capital)(voted|charged)?section$")  # matched on _norm()

# Head codes start at the page's left margin (x≈53-84, it alternates between odd and even pages);
# O/S/R labels start ~75pt right of it and head names ~25pt right of it.
_CODE_COLUMN_WIDTH = 15.0
_LABEL_MIN_OFFSET = 50.0


class AppropriationDetailsError(AppropriationAccountsError):
    """The grant pages could not be parsed, or the parsed numbers failed a consistency check."""


# ── Output ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MajorHead:
    grant_no: int
    section: str  # "revenue" | "capital"
    code: str
    name: str
    page: int


@dataclass(frozen=True)
class SectionTotal:
    """One Voted/Charged block at the top of a grant's pages (₹ thousand)."""

    grant_no: int
    section: str
    kind: str  # "voted" | "charged"
    original: int
    supplementary: int
    reappropriation: int  # only printed in 2021-22 ("Supplementary/ Re-appropriation")
    final_grant: int
    expenditure: int
    saving: int
    excess: int
    surrendered: int
    page: int


@dataclass(frozen=True)
class Note:
    grant_no: int
    section: str | None
    kind: str | None
    number: int
    text: str
    category: str  # see _note_category
    reasons_not_communicated: bool
    page: int


@dataclass(frozen=True)
class HeadPart:
    level: str  # one of LEVELS
    code: str
    name: str


@dataclass(frozen=True)
class HeadLine:
    """One row of a note table (₹ thousand). Amounts the table does not print are None."""

    grant_no: int
    section: str
    kind: str | None  # None until resolved by _resolve_kinds (section printed without Voted/Charged)
    note_number: int
    category: str
    reasons_not_communicated: bool
    path: tuple[HeadPart, ...]
    original: int | None
    supplementary: int | None
    reappropriation: int | None
    final_grant: int | None
    expenditure: int | None
    saving: int | None
    excess: int | None
    remark: str
    page: int
    printed_error: str | None = None  # see KNOWN_PRINTED_ERRORS

    @property
    def head_code(self) -> str:
        return ".".join(part.code for part in self.path)

    @property
    def head_name(self) -> str:
        return self.path[-1].name


@dataclass
class AppropriationDetails:
    financial_year: str
    unit: str
    grants: dict[int, str] = field(default_factory=dict)
    major_heads: list[MajorHead] = field(default_factory=list)
    section_totals: list[SectionTotal] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    heads: list[HeadLine] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)  # note tables that are not head tables
    misfiled: list[str] = field(default_factory=list)  # rows printed under the other section's heading
    footnotes: list[str] = field(default_factory=list)
    headerless_tables: list[str] = field(default_factory=list)  # note tables printed without a header

    def to_dict(self) -> dict:
        return {
            "financial_year": self.financial_year,
            "unit": self.unit,
            "grants": self.grants,
            "major_heads": [asdict(m) for m in self.major_heads],
            "section_totals": [asdict(s) for s in self.section_totals],
            "notes": [asdict(n) for n in self.notes],
            "heads": [{**asdict(h), "head_code": h.head_code} for h in self.heads],
            "skipped_tables": self.skipped_tables,
            "misfiled": self.misfiled,
            "footnotes": self.footnotes,
            "headerless_tables": self.headerless_tables,
        }


# ── Token helpers ─────────────────────────────────────────────────────────────


def _lakh_to_thousand(text: str) -> int:
    match = _LAKH_RE.match(text)
    if not match:
        raise AppropriationDetailsError(f"not a lakh amount: {text!r}")
    sign, whole, decimals = match.groups()
    value = int(whole.replace(",", "")) * 100 + int(decimals)
    return -value if sign == "-" else value


def _thousand(text: str) -> int:
    """Signed ₹ thousand amount from the section blocks, e.g. "(-)85,81,58"."""
    match = _SIGNED_THOUSAND_RE.match(text)
    if match:
        value = _to_int(match.group(2))
        return -value if match.group(1) == "-" else value
    return _to_int(text)


def _is_thousand(text: str) -> bool:
    match = _SIGNED_THOUSAND_RE.match(text)
    return _is_number(match.group(2) if match else text)


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _norm(text: str) -> str:
    """Squeezed text with runs of a repeated character collapsed.

    Bold text in 2021-22 is extracted with every glyph doubled ("AAmmoouunntt"), and some notes
    have no spaces at all. Always compare through `_has` / `_starts`, which normalise both sides.
    """
    return re.sub(r"(.)\1+", r"\1", _squeeze(text))


def _has(normed: str, *keywords: str) -> bool:
    return any(_norm(k) in normed for k in keywords)


def _starts(normed: str, *keywords: str) -> bool:
    return any(normed.startswith(_norm(k)) for k in keywords)


def _split_glued(words: list[dict]) -> list[dict]:
    """Split "(-)34.24mainly" into a number word and a text word, and join "(-)" "34.24"."""
    out: list[dict] = []
    for word in words:
        text = word["text"]
        match = _GLUED_LAKH_RE.match(text)
        if match and not _LAKH_RE.match(text):
            number, rest = match.groups()
            share = len(number) / len(text)
            cut = word["x0"] + (word["x1"] - word["x0"]) * share
            out.append({**word, "text": number, "x1": cut})
            out.append({**word, "text": rest, "x0": cut, "glued_remark": True})
            continue
        if out and out[-1]["text"] in ("(-)", "(+)") and abs(out[-1]["top"] - word["top"]) < 3 and (
            _LAKH_RE.match(text) or _is_number(text)
        ):
            prev = out.pop()
            out.append({**word, "text": prev["text"] + text, "x0": prev["x0"]})
            continue
        out.append(word)
    return out


def _lines(words: list[dict], tolerance: float = 3.5) -> list[list[dict]]:
    """Group words into visual lines. Unlike the summary parser's grouping, each word is compared
    with the previous word's top, not the line's first word: O/S/R labels, amounts and wrapped
    remarks on one visual line can be spread over ~4pt (2022-23 grant 6)."""
    lines: list[list[dict]] = []
    last_top = None
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and last_top is not None and word["top"] - last_top <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
        last_top = word["top"]
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _is_rupee_glyph(text: str) -> bool:
    """The ₹ sign is extracted as one or more backticks."""
    return bool(text) and set(text) <= {"`", "₹"}


def _line_text(line: list[dict]) -> str:
    return " ".join(w["text"] for w in line)


# ── Table columns ─────────────────────────────────────────────────────────────


@dataclass
class _NoteColumns:
    total_right: float | None
    actual_right: float | None
    variation_right: float | None
    remarks_left: float
    first_value_left: float  # left edge of the leftmost value column header

    def value_rights(self) -> dict[str, float]:
        cols = {"final_grant": self.total_right, "expenditure": self.actual_right, "variation": self.variation_right}
        return {name: x for name, x in cols.items() if x is not None}


def _split_header_words(words: list[dict]) -> list[dict]:
    """2022-23 glues "Remarks" to the column before it ("Saving(-)Remarks", "ActualRemarks",
    "Grant/Remarks"); split it off, placing the cut by the share of characters."""
    out = []
    for word in words:
        match = re.match(r"^(.+?)(Remarks)$", word["text"])
        if not match:
            out.append(word)
            continue
        head = match.group(1)
        cut = word["x0"] + (word["x1"] - word["x0"]) * len(head) / len(word["text"])
        out.append({**word, "text": head, "x1": cut})
        out.append({**word, "text": "Remarks", "x0": cut})
    return out


def _note_columns(header_words: list[dict]) -> _NoteColumns:
    """Columns from a note table header ("Head Total Grant/ Actual Saving(-) Remarks" + lines below)."""
    header_words = _split_header_words(header_words)
    total = [w for w in header_words if w["text"] in ("Total", "Grant", "Grant/", "Appropriation")]
    actual = [w for w in header_words if w["text"] in ("Actual", "Expenditure")]
    variation = [w for w in header_words if re.match(r"^(Saving|Excess)", w["text"])]
    remarks = [w for w in header_words if w["text"] == "Remarks"]
    if not remarks:
        raise AppropriationDetailsError(f"note table header without a Remarks column: {_line_text(header_words)!r}")
    total_right = max(w["x1"] for w in total) if total else None
    actual_right = max(w["x1"] for w in actual) if actual else None
    variation_right = max(w["x1"] for w in variation) if variation else None
    rights = [x for x in (total_right, actual_right, variation_right) if x is not None]
    if not rights:
        raise AppropriationDetailsError(f"note table header without value columns: {_line_text(header_words)!r}")
    lefts = [w["x0"] for w in total + actual + variation]
    return _NoteColumns(
        total_right=total_right,
        actual_right=actual_right,
        variation_right=variation_right,
        remarks_left=max(rights) + 1.5,
        first_value_left=min(lefts),
    )


# ── Head nodes (one code line and the lines under it) ─────────────────────────


@dataclass
class _Node:
    code: str
    page: int
    name_words: list[str] = field(default_factory=list)
    remark_words: list[str] = field(default_factory=list)
    osr: dict[str, int] = field(default_factory=dict)  # "O" / "S" / "R"
    values: dict[str, int] = field(default_factory=dict)  # final_grant / expenditure / variation
    nil_values: set[str] = field(default_factory=set)
    pending_labels: list[str] = field(default_factory=list)  # O/S/R printed without an amount (yet)

    @property
    def has_values(self) -> bool:
        return bool(self.osr or self.values or self.nil_values or self.pending_labels)

    @property
    def name(self) -> str:
        return " ".join(self.name_words).strip()


def _add_line_to_node(node: _Node, line: list[dict], cols: _NoteColumns, margin: float, where: str) -> None:
    label: str | None = None
    for index, word in enumerate(line):
        text = word["text"]
        x0, x1 = word["x0"], word["x1"]
        if _is_rupee_glyph(text):
            continue
        if x0 >= cols.remarks_left - 0.5 or word.get("glued_remark"):
            node.remark_words.append(text)
            continue
        if text in ("O", "S", "R") and index == 0 and x0 > margin + _LABEL_MIN_OFFSET and x1 < cols.first_value_left:
            # O/S/R labels start their own line at x≈135, right of where head names start (x≈87).
            label = text
            continue
        if label and index > 0:
            node.pending_labels.append(label)
            label = None
        is_amount = bool(_LAKH_RE.match(text))
        is_nil = text in _NIL_TOKENS
        if (is_amount or is_nil) and x1 < cols.first_value_left and (label or node.pending_labels):
            # The amount usually follows its label on the same line; when the line breaks it is
            # printed below (2022-23 grant 2: "R" then "5,590.87" on the next line).
            target = label or node.pending_labels.pop(0)
            if target in node.osr:
                raise AppropriationDetailsError(f"{where}: two {target} amounts")
            node.osr[target] = _lakh_to_thousand(text) if is_amount else 0
            label = None
            continue
        if is_amount and x1 < cols.first_value_left and not node.osr:
            # The "O" label is missing (2021-22 grant 28, head 0105: "14,830.91" alone, then
            # "S (-)1,656.67" and total 13,174.24). The first provision amount is the original;
            # the O + S + R = total grant check confirms it.
            node.osr["O"] = _lakh_to_thousand(text)
            continue
        if is_amount and x1 < cols.first_value_left:
            raise AppropriationDetailsError(f"{where}: provision amount {text!r} without an O/S/R label")
        if _BRACKETED_RE.match(text) and x1 > cols.first_value_left - 10:
            continue  # exact rupee figure under an excess
        if (is_amount or is_nil) and x1 > cols.first_value_left - 10:
            rights = cols.value_rights()
            column = min(rights, key=lambda c: abs(rights[c] - x1))
            # Columns are ~70pt apart; amounts are sometimes printed well left of their column's
            # right edge (2021-22 grant 28: 26pt), so accept up to half the spacing.
            if abs(rights[column] - x1) > 35:
                raise AppropriationDetailsError(f"{where}: amount {text!r} at x={x1:.0f} is in no column")
            if column in node.values or column in node.nil_values:
                raise AppropriationDetailsError(f"{where}: two amounts in the {column} column")
            if is_amount:
                node.values[column] = _lakh_to_thousand(text)
            else:
                node.nil_values.add(column)
            continue
        node.name_words.append(text)
    if label:
        node.pending_labels.append(label)


def _assign_levels(run: list[_Node], majors: set[str], where: str) -> list[HeadPart]:
    """Give each node in a run of head lines (ancestors first, the row's own head last) its level.

    The PDFs sometimes print a branch with no row under it (2023-24 grant 2: "214 Border
    Management / 0011 General", then "216 Other Police Organisations / 0011 General / 0727 ...").
    When a code can't follow the one before it, the branch before it is dropped and the levels are
    worked out again from that code; the dropped branch has no amounts, so nothing is lost.
    """
    for start in range(len(run)):
        try:
            return _assign_levels_strict(run[start:], majors, where)
        except AppropriationDetailsError:
            if start == len(run) - 1:
                raise
    raise AssertionError("unreachable")


def _assign_levels_strict(run: list[_Node], majors: set[str], where: str) -> list[HeadPart]:
    parts: list[HeadPart] = []
    previous: str | None = None
    for index, node in enumerate(run):
        code = node.code
        is_last = index == len(run) - 1
        if previous is None:
            if len(code) == 4 and code in majors and not is_last:
                level = "major"
            elif len(code) == 2:
                level = "sub_major"
            elif len(code) == 3:
                level = "minor"
            elif len(code) == 4:
                level = "detailed" if is_last else "sub_head"
            else:
                raise AppropriationDetailsError(f"{where}: unexpected head code {code!r}")
        elif len(code) == 2 and previous == "major":
            level = "sub_major"
        elif len(code) == 3 and previous in ("major", "sub_major"):
            level = "minor"
        elif len(code) == 4 and previous == "minor":
            level = "sub_head"
        elif len(code) == 4 and previous == "sub_head":
            level = "detailed"
        else:
            path = " > ".join(n.code for n in run)
            raise AppropriationDetailsError(f"{where}: head code {code!r} can't follow a {previous} head ({path})")
        parts.append(HeadPart(level=level, code=code, name=node.name))
        previous = level
    return parts


def _merge_path(previous: tuple[HeadPart, ...], new: list[HeadPart]) -> tuple[HeadPart, ...]:
    rank = LEVELS.index(new[0].level)
    kept = [part for part in previous if LEVELS.index(part.level) < rank]
    return tuple(kept + new)


# ── Notes ─────────────────────────────────────────────────────────────────────


def _note_category(text: str) -> str:
    """What a note's table lists: saving, excess, unutilised, unutilised_supplementary,
    without_provision; "comment" for notes with no head table (e.g. the section summary)."""
    t = _norm(text)
    if _has(t, "un-utilised", "unutilised"):
        return "unutilised_supplementary" if _has(t, "entire supplementary") else "unutilised"
    if _has(t, "without budgetary provision", "without provision"):
        return "without_provision"
    if _has(t, "counterbalanced"):
        return "excess"  # "Saving was partly counterbalanced by the excess under the following Heads"
    if not _has(t, "occurred", "following"):
        return "comment"
    # Whichever is named first: "Saving in the Section occurred ...", "In the Capital Charged
    # Section excess occurred mainly under ..." (2023-24 grant 8).
    saving, excess = t.find("saving"), t.find("exces")
    if saving >= 0 and (excess < 0 or saving < excess):
        return "saving"
    if excess >= 0:
        return "excess"
    return "comment"


# ── Parsing ───────────────────────────────────────────────────────────────────


@dataclass
class _State:
    page: int = 0
    grant_no: int | None = None
    grant_name: str = ""
    mode: str = "before"  # before | top | notes | done
    # top block
    section: str | None = None
    in_major_list: bool = False
    top_cols: dict[str, float] | None = None
    block_kind: str | None = None
    block_lines: list[tuple[str, list[dict], int]] = field(default_factory=list)
    # notes
    note_section: str | None = None
    heading_kind: str | None = None  # Voted/Charged as printed in the section heading, if at all
    note_kind: str | None = None  # heading_kind, or the kind the latest note names
    note: Note | None = None  # the current note; final once note_open is False
    note_open: bool = False  # still collecting the note's text
    note_text: list[str] = field(default_factory=list)
    header_words: list[dict] | None = None
    cols: _NoteColumns | None = None
    run: list[_Node] = field(default_factory=list)
    path: tuple[HeadPart, ...] = ()
    last_note_number: int = 0
    skipping: bool = False


class _Parser:
    def __init__(self) -> None:
        self.s = _State()
        self.margin = 0.0
        self.code_max = 0.0
        self.full_cols: _NoteColumns | None = None
        self.out = AppropriationDetails(financial_year="", unit=UNIT)

    # ── helpers
    def where(self) -> str:
        return f"page {self.s.page}, grant {self.s.grant_no}"

    def majors(self, section: str) -> set[str]:
        return {m.code for m in self.out.major_heads if m.grant_no == self.s.grant_no and m.section == section}

    # ── top block
    def flush_block(self) -> None:
        s = self.s
        if not s.block_lines:
            return
        if s.section is None or s.top_cols is None:
            raise AppropriationDetailsError(f"{self.where()}: Voted/Charged block before section header or columns")
        provision: dict[str, int] = {}
        values: dict[str, int] = {}
        surrendered = 0
        page = s.block_lines[0][2]
        cols = s.top_cols
        any_number = False
        nil_columns: set[str] = set()
        last_label: str | None = None
        for label, words, _ in s.block_lines:
            if label in ("original", "supplementary", "reappropriation"):
                last_label = label
            rights = {k: v for k, v in cols.items() if k != "total_left"}
            for word in words:
                text = word["text"]
                if text in _NIL_TOKENS and label != "surrendered" and word["x1"] > cols["total_left"]:
                    nil_columns.add(min(rights, key=lambda c: abs(rights[c] - word["x1"])))
                    continue
                if _BRACKETED_RE.match(text) or text in _NIL_TOKENS or not _is_thousand(text):
                    continue
                any_number = True
                if label == "surrendered":
                    surrendered = abs(_thousand(text))
                    continue
                if word["x1"] < cols["total_left"]:
                    # A provision amount; when the line breaks it sits below its label (2021-22).
                    if last_label is None or last_label in provision:
                        raise AppropriationDetailsError(f"{self.where()}: provision amount {text!r} without a label")
                    provision[last_label] = _thousand(text)
                    continue
                column = min(rights, key=lambda c: abs(rights[c] - word["x1"]))
                if column in values:
                    raise AppropriationDetailsError(f"{self.where()}: two values in the {column} column of a section block")
                values[column] = _thousand(text)
        if not any_number:
            # Every amount is nil (2022-23 grant 5, Mining: listed but with no provision); the
            # summary table has no row for it either.
            s.block_lines = []
            s.block_kind = None
            return
        if "final_grant" not in values:
            if "final_grant" not in nil_columns:
                raise AppropriationDetailsError(f"{self.where()}: section block without a final grant")
            # The whole provision was withdrawn (2021-22 grant 9 charged: Original 87,10,
            # Re-appropriation (-)87,10, final grant ".."). The summary table has no row for it.
            values["final_grant"] = 0
        variation = values.get("variation", 0)
        self.out.section_totals.append(
            SectionTotal(
                grant_no=s.grant_no,
                section=s.section,
                kind=s.block_kind or "voted",
                original=provision.get("original", 0),
                supplementary=provision.get("supplementary", 0),
                reappropriation=provision.get("reappropriation", 0),
                final_grant=values["final_grant"],
                expenditure=values.get("expenditure", 0),
                saving=-variation if variation < 0 else 0,
                excess=variation if variation > 0 else 0,
                surrendered=surrendered,
                page=page,
            )
        )
        s.block_lines = []
        s.block_kind = None

    def extend_last_major_head(self, text: str) -> None:
        heads = self.out.major_heads
        if not heads or heads[-1].grant_no != self.s.grant_no or heads[-1].section != self.s.section:
            raise AppropriationDetailsError(f"{self.where()}: text in the major-head list before any head: {text!r}")
        last = heads.pop()
        heads.append(replace(last, name=f"{last.name} {text}"))

    def top_line(self, line: list[dict], text: str, first: str) -> None:
        s = self.s
        squeezed = _norm(text)
        if _starts(squeezed, "notes and comments"):
            self.flush_block()
            s.mode = "notes"
            s.note_section = s.note_kind = None
            s.cols = None
            s.run = []
            s.path = ()
            s.last_note_number = 0
            return
        # "Revenue-", "Revenue -", and "Capital Section" (2022-23 and 2023-24 grant 31)
        section_heading = re.match(r"^(revenue|capital)(-|section)?$", squeezed)
        if section_heading:
            self.flush_block()
            s.section = section_heading.group(1)
            # 2023-24 grant 17 lists the capital major head without a "MAJOR HEAD" line.
            s.in_major_list = True
            s.block_kind = None
            return
        if _starts(squeezed, "major head"):
            s.in_major_list = True
            return
        if s.in_major_list and _CODE_RE.match(first) and len(first) == 4 and line[0]["x0"] < self.code_max:
            self.out.major_heads.append(
                MajorHead(s.grant_no, s.section, first, " ".join(w["text"] for w in line[1:]), s.page)
            )
            return
        if _starts(squeezed, "total grant", "appropriation"):
            s.in_major_list = False
            if _starts(squeezed, "total grant"):
                total = next(w for w in line if w["text"] == "Total")
                s.top_cols = {"total_left": total["x0"]}
            else:
                if s.top_cols is None:
                    raise AppropriationDetailsError(f"{self.where()}: section header without 'Total Grant'")
                s.top_cols["final_grant"] = next(w for w in line if w["text"] == "Appropriation")["x1"]
                s.top_cols["expenditure"] = next(w for w in line if w["text"] == "Expenditure")["x1"]
                s.top_cols["variation"] = max(w["x1"] for w in line)
            return
        if _has(squeezed, "in thousand"):
            return
        is_values = all(
            _is_thousand(w["text"]) or _BRACKETED_RE.match(w["text"]) or w["text"] in _NIL_TOKENS for w in line
        )
        if s.in_major_list and line[0]["x0"] >= self.code_max and not is_values:
            self.extend_last_major_head(text)  # wrapped major-head name
            return
        kind_label = first.rstrip("-:").lower()
        if kind_label in ("voted", "charged") and (
            len(line) == 1 or (s.in_major_list and line[1]["x0"] >= self.code_max)
        ):
            if len(line) > 1:
                # 2021-22 grant 2: the last major-head name wraps onto the "Voted" line.
                self.extend_last_major_head(" ".join(w["text"] for w in line[1:]))
            s.in_major_list = False
            self.flush_block()
            s.block_kind = kind_label
            return
        s.in_major_list = False
        if first[:1] in "*#$^@" and not is_values:
            # footnote under a section block (e.g. "*Represents amount augmented ...")
            self.out.footnotes.append(f"page {s.page}, grant {s.grant_no}: {text}")
            return
        label = _norm(first)
        if label == _norm("Original"):
            if s.block_lines:
                self.flush_block()
            s.block_lines.append(("original", line[1:], s.page))
            return
        if label in (_norm("Supplementary"), _norm("Supplementary/")):
            # 2021-22 prints "Supplementary/" on its own line and "Re-appropriation <amount>" below.
            s.block_lines.append(("supplementary", line[1:], s.page))
            return
        if label in (_norm("Re-appropriation"), _norm("Re-appropriation/"), _norm("Surrender")):
            # "Re-appropriation" (2021-22) and "Re-appropriation/ Surrender" (2022-23 grant 5).
            s.block_lines.append(("reappropriation", line[1:], s.page))
            return
        if _starts(squeezed, "amount surrendered"):
            s.block_lines.append(("surrendered", line, s.page))
            self.flush_block()
            return
        if is_values:
            if not s.block_lines:
                raise AppropriationDetailsError(f"{self.where()}: amounts outside a Voted/Charged block: {text!r}")
            s.block_lines.append(("values", line, s.page))
            return
        if s.section is None and s.mode == "top" and not s.top_cols:
            s.grant_name += " " + text  # wrapped grant name
            return
        raise AppropriationDetailsError(f"{self.where()}: unexpected line in the section block: {text!r}")

    # ── notes
    def flush_note(self) -> None:
        s = self.s
        if s.note is None or not s.note_open:
            return
        s.note_open = False
        text = " ".join(s.note_text)
        if s.heading_kind is None:
            normed = _norm(text)
            voted, charged = _has(normed, "voted section"), _has(normed, "charged section")
            if voted != charged:
                s.note_kind = "voted" if voted else "charged"
        note = Note(
            grant_no=s.note.grant_no,
            section=s.note.section,
            kind=s.note_kind,
            number=s.note.number,
            text=text,
            category=_note_category(text),
            reasons_not_communicated=_has(_norm(text), "reasons for which were not communicated"),
            page=s.note.page,
        )
        self.out.notes.append(note)
        s.note = note
        s.note_text = []

    def flush_node(self) -> None:
        """Called when a head node is complete (a new code line, a note, or the end of the table)."""
        s = self.s
        if not s.run or not s.run[-1].has_values:
            return
        node = s.run[-1]
        where = f"page {node.page}, grant {s.grant_no}, head {' > '.join(n.code for n in s.run)}"
        if s.note is None or s.note_section is None:
            raise AppropriationDetailsError(f"{where}: table row outside a note")
        all_majors = self.majors("revenue") | self.majors("capital")
        parts = _assign_levels(s.run, all_majors, where)
        path = _merge_path(s.path, parts)
        if path[0].level != "major":
            raise AppropriationDetailsError(f"{where}: no major head for this row")
        # The major head decides Revenue vs Capital. 2021-22 grant 34 prints a revenue head (2230)
        # in a note under "Capital Section"; such a row is filed under its major head's section.
        section = s.note_section
        if path[0].code not in self.majors(section):
            other = "capital" if section == "revenue" else "revenue"
            if path[0].code not in self.majors(other):
                raise AppropriationDetailsError(f"{where}: major head {path[0].code} is not listed for this grant")
            self.out.misfiled.append(
                f"page {node.page}, grant {s.grant_no}, note {s.note.number}: head {path[0].code} printed under "
                f"the {section} section, filed under {other}"
            )
            section = other
        variation = node.values.get("variation")
        self.out.heads.append(
            HeadLine(
                grant_no=s.grant_no,
                section=section,
                kind=s.note.kind,
                note_number=s.note.number,
                category=s.note.category,
                reasons_not_communicated=s.note.reasons_not_communicated,
                path=path,
                original=node.osr.get("O"),
                supplementary=node.osr.get("S"),
                reappropriation=node.osr.get("R"),
                final_grant=node.values.get("final_grant", 0 if "final_grant" in node.nil_values else None),
                expenditure=node.values.get("expenditure", 0 if "expenditure" in node.nil_values else None),
                saving=(-variation if variation < 0 else 0) if variation is not None else None,
                excess=(variation if variation > 0 else 0) if variation is not None else None,
                remark=" ".join(node.remark_words),
                page=node.page,
            )
        )
        s.path = path
        s.run = []

    def notes_line(self, line: list[dict], text: str, first: str) -> None:
        s = self.s
        squeezed = _norm(text)
        if first[:1] in "*#$^@" and line[0]["x0"] < self.code_max:
            # footnote, e.g. "* Difference of 0.01 lakh due to machine rounding" (2021-22 grant 9)
            self.out.footnotes.append(f"page {s.page}, grant {s.grant_no}: {text}")
            return
        section = _SECTION_HEADING_RE.match(squeezed)
        if section:
            new_section, new_kind = section.group(1), section.group(2)
            if new_section == s.note_section and (new_kind is None or new_kind == s.heading_kind):
                return  # the section heading repeated at the top of a continuation page
            self.flush_node()
            self.flush_note()
            s.note_section, s.heading_kind, s.note_kind = new_section, new_kind, new_kind
            s.note = None
            s.skipping = False
            s.cols = None
            s.run, s.path = [], ()
            return

        # A numbered note: "3 Saving in the Section ...". Head codes are 2-4 digits, so a single
        # digit at the margin is always a note number; numbers can skip one (2022-23 grant 33 goes
        # from note 5 to note 7). A 2-digit number must be the next one and its line must run
        # across the table, unlike a sub-major head ("10 ...").
        if (
            first.isdigit()
            and not first.startswith("0")
            and line[0]["x0"] < self.code_max
            and (
                (len(first) == 1 and s.last_note_number < int(first) <= s.last_note_number + 2)
                or (
                    int(first) == s.last_note_number + 1
                    and (len(line) == 1 or not s.cols or line[-1]["x1"] > s.cols.remarks_left)
                )
            )
        ):
            self.flush_node()
            self.flush_note()
            s.last_note_number = int(first)
            s.note = Note(s.grant_no, s.note_section, s.note_kind, int(first), "", "comment", False, s.page)
            s.note_open = True
            s.note_text = [" ".join(w["text"] for w in line[1:])] if len(line) > 1 else []
            s.header_words = None
            s.cols = None
            s.skipping = False
            s.run, s.path = [], ()
            return

        if first == "Head" and line[0]["x0"] < self.code_max:
            self.flush_node()
            self.flush_note()
            s.header_words = list(line)
            s.skipping = False
            s.run = []
            return
        if s.header_words is not None:
            s.header_words.extend(line)
            if _has(squeezed, "in lakh"):
                try:
                    s.cols = _note_columns(s.header_words)
                    c = s.cols
                    if c.total_right and c.actual_right and c.variation_right:
                        # remembered relative to the margin, for tables printed without a header
                        self.full_cols = _NoteColumns(
                            total_right=c.total_right - self.margin,
                            actual_right=c.actual_right - self.margin,
                            variation_right=c.variation_right - self.margin,
                            remarks_left=c.remarks_left - self.margin,
                            first_value_left=c.first_value_left - self.margin,
                        )
                except AppropriationDetailsError:
                    # Not a head table (e.g. 2021-22 grant 6 note 8: establishment and tools-and-
                    # plant charges as a percentage of works outlay). Keep the note text, skip the
                    # table until the next note or section, and record that it was skipped.
                    self.out.skipped_tables.append(
                        f"page {s.page}, grant {s.grant_no}, note {s.last_note_number}: {_line_text(s.header_words)}"
                    )
                    s.skipping = True
                s.header_words = None
            elif _has(squeezed, "in thousand"):
                raise AppropriationDetailsError(f"{self.where()}: note table in ₹ thousand; expected ₹ lakh")
            return

        if s.skipping:
            return
        if (
            s.cols is None
            and s.note_open
            and _CODE_RE.match(first)
            and len(first) == 4
            and line[0]["x0"] < self.code_max
            and first in (self.majors("revenue") | self.majors("capital"))
            and _note_category(" ".join(s.note_text)) in ("saving", "excess")
        ):
            # A table printed without its column header (2022-23 grant 17 note 6, 2023-24 grant 24
            # note 5): the rows follow the note text directly. Only saving/excess tables are
            # handled, with the last full header's columns moved to this page's margin. Other
            # notes (fund and suspense statements) stay text; validate_details rejects a
            # saving/excess/unutilised/without-provision note that ends up with no rows.
            if self.full_cols is None:
                raise AppropriationDetailsError(f"{self.where()}: table without a column header; can't place its columns")
            self.flush_note()
            c = self.full_cols
            s.cols = _NoteColumns(
                total_right=c.total_right + self.margin,
                actual_right=c.actual_right + self.margin,
                variation_right=c.variation_right + self.margin,
                remarks_left=c.remarks_left + self.margin,
                first_value_left=c.first_value_left + self.margin,
            )
            self.out.headerless_tables.append(f"page {s.page}, grant {s.grant_no}, note {s.note.number}")
        if s.cols is None:
            # note text (between the note number and its table)
            if s.note is None or not s.note_open:
                raise AppropriationDetailsError(f"{self.where()}: text outside a note: {text!r}")
            s.note_text.append(text)
            return

        # inside a table
        if _CODE_RE.match(first) and line[0]["x0"] < self.code_max:
            self.flush_node()
            node = _Node(code=first, page=s.page)
            _add_line_to_node(node, line[1:], s.cols, self.margin, self.where())
            s.run.append(node)
            return
        if not s.run:
            raise AppropriationDetailsError(f"{self.where()}: table line before any head code: {text!r}")
        _add_line_to_node(s.run[-1], line, s.cols, self.margin, self.where())

    # ── driver
    def page(self, page_no: int, words: list[dict]) -> None:
        s = self.s
        s.page = page_no
        if not words:
            return
        self.margin = min(w["x0"] for w in words)
        self.code_max = self.margin + _CODE_COLUMN_WIDTH
        lines = _lines(_split_glued(words))
        lines = [line for line in lines if not all(_is_rupee_glyph(w["text"]) for w in line)]
        if not lines:
            return
        start = 0
        # running page number at the top
        if len(lines[0]) == 1 and re.match(r"^([0-9]+|[ivxlc]+)$", lines[0][0]["text"]):
            start = 1
        for index in range(start, len(lines)):
            line = [w for w in lines[index] if not _is_rupee_glyph(w["text"])]
            text = _line_text(line)
            first = line[0]["text"]
            heading = _GRANT_HEADING_RE.match(text)
            if s.mode in ("before", "top", "notes") and heading and index <= start + 1:
                number, rest = int(heading.group(1)), heading.group(2).strip()
                if rest.startswith("(Cont") or rest.startswith("(Concl"):
                    if number != s.grant_no:
                        raise AppropriationDetailsError(f"page {page_no}: continuation of grant {number} inside grant {s.grant_no}")
                    if s.mode == "notes" and s.header_words is not None:
                        raise AppropriationDetailsError(f"page {page_no}: table header split across pages")
                    continue
                self.end_grant()
                s.grant_no, s.grant_name, s.mode = number, rest, "top"
                s.section, s.in_major_list, s.top_cols = None, False, None
                continue
            if s.mode != "before" and index <= start + 1 and re.match(r"^APPENDI(X|CES)", text):
                self.end_grant()
                s.mode = "done"
                return
            if s.mode == "top":
                self.top_line(line, text, first)
            elif s.mode == "notes":
                self.notes_line(line, text, first)

    def end_grant(self) -> None:
        s = self.s
        if s.grant_no is None:
            return
        if s.mode == "top":
            self.flush_block()
        self.flush_node()
        self.flush_note()
        if s.run:
            raise AppropriationDetailsError(
                f"grant {s.grant_no}: head lines without amounts at the end: {[n.code for n in s.run]}"
            )
        self.out.grants[s.grant_no] = re.sub(r"\s+", " ", s.grant_name).strip()
        s.note = None
        s.cols = None
        s.path = ()
        s.skipping = False


def parse_appropriation_details(
    source: str | Path | BinaryIO,
    summary: AppropriationSummary | None = None,
    validate: bool = True,
    partial: bool = False,
) -> AppropriationDetails:
    """Parse the grant pages of a J&K Appropriation Accounts PDF.

    If `summary` is not given, the summary table is parsed from the same document; it supplies the
    financial year and the figures the section blocks are checked against. `partial=True` is for
    documents holding only some grants' pages (test fixtures): every row is still checked, but
    not that every grant in the summary is present.
    """
    if summary is None:
        if hasattr(source, "seek"):
            source.seek(0)
        summary = parse_appropriation_summary(source)
        if hasattr(source, "seek"):
            source.seek(0)

    parser = _Parser()
    with pdfplumber.open(source) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            parser.page(page_no, page.extract_words())
            if parser.s.mode == "done":
                break
    parser.end_grant()

    details = parser.out
    details.financial_year = summary.financial_year
    _resolve_kinds(details)
    details.heads = [
        replace(h, printed_error=KNOWN_PRINTED_ERRORS.get((details.financial_year, h.grant_no, h.head_code, h.category)))
        for h in details.heads
    ]
    if not details.grants:
        raise AppropriationDetailsError("no grant pages found")
    if validate:
        validate_details(details, summary, partial=partial)
    return details


def _resolve_kinds(details: AppropriationDetails) -> None:
    """Rows in a section printed without Voted/Charged (2021-22, 2022-23 "Revenue Section"), and
    whose note doesn't name one either, belong to the section's only block when it has just one.
    Rows that stay ambiguous keep kind None and fail validation."""
    kinds: dict[tuple[int, str], set[str]] = {}
    for t in details.section_totals:
        kinds.setdefault((t.grant_no, t.section), set()).add(t.kind)
    resolved = []
    for h in details.heads:
        if h.kind is None:
            only = kinds.get((h.grant_no, h.section), set())
            if len(only) == 1:
                h = replace(h, kind=next(iter(only)))
        resolved.append(h)
    details.heads = resolved
    notes = []
    for n in details.notes:
        if n.kind is None and n.section is not None:
            only = kinds.get((n.grant_no, n.section), set())
            if len(only) == 1:
                n = replace(n, kind=next(iter(only)))
        notes.append(n)
    details.notes = notes


# ── Validation ────────────────────────────────────────────────────────────────


def _arithmetic_problems(h: HeadLine) -> list[str]:
    problems = []
    if h.original is not None or h.supplementary is not None or h.reappropriation is not None:
        provision = (h.original or 0) + (h.supplementary or 0) + (h.reappropriation or 0)
        if h.final_grant is None or abs(provision - h.final_grant) > HEAD_TOLERANCE:
            problems.append(f"O + S + R = {provision} != total grant {h.final_grant}")
    if h.saving is not None and h.final_grant is not None and h.expenditure is not None:
        if abs((h.final_grant - h.expenditure) - (h.saving - h.excess)) > HEAD_TOLERANCE:
            problems.append(
                f"total grant {h.final_grant} - actual {h.expenditure} != saving {h.saving} - excess {h.excess}"
            )
    return problems


def validate_details(details: AppropriationDetails, summary: AppropriationSummary, partial: bool = False) -> None:
    """Raise AppropriationDetailsError listing every inconsistency found."""
    problems: list[str] = []
    present = set(details.grants)

    summary_rows = {(line.grant_no, line.section, line.kind): line for line in summary.lines}
    totals = {(t.grant_no, t.section, t.kind): t for t in details.section_totals}

    # A grant can have pages but no amounts (2022-23 grant 5, Mining); the summary skips it too.
    with_amounts = {t.grant_no for t in details.section_totals}
    if not partial and with_amounts != set(summary.grants):
        problems.append(
            f"grants with amounts on the grant pages {sorted(with_amounts)} differ from the summary "
            f"{sorted(summary.grants)}"
        )
    seen: set[tuple[int, str, str]] = set()
    for t in details.section_totals:
        key = (t.grant_no, t.section, t.kind)
        where = f"grant {t.grant_no} {t.section}/{t.kind} (page {t.page})"
        if key in seen:
            problems.append(f"{where}: section block appears twice")
        seen.add(key)
        if abs(t.original + t.supplementary + t.reappropriation - t.final_grant) > ROW_TOLERANCE:
            problems.append(f"{where}: original + supplementary (+ re-appropriation) != final grant")
        if abs((t.final_grant - t.expenditure) - (t.saving - t.excess)) > ROW_TOLERANCE:
            problems.append(f"{where}: final grant - expenditure != saving - excess")
        row = summary_rows.get(key)
        if row is None:
            if t.final_grant or t.expenditure:
                problems.append(f"{where}: no matching row in the summary table")
            continue
        if abs(row.grant_amount - t.final_grant) > ROW_TOLERANCE or abs(row.expenditure - t.expenditure) > ROW_TOLERANCE:
            problems.append(
                f"{where}: grant/expenditure {t.final_grant}/{t.expenditure} != summary "
                f"{row.grant_amount}/{row.expenditure}"
            )
    for key in set(summary_rows) - set(totals):
        if partial and key[0] not in present:
            continue
        problems.append(f"grant {key[0]} {key[1]}/{key[2]}: in the summary but no section block found")

    majors = {(m.grant_no, m.section, m.code) for m in details.major_heads}
    listed = {
        k for k in KNOWN_PRINTED_ERRORS if k[0] == details.financial_year and (not partial or k[1] in present)
    }
    for h in details.heads:
        where = f"grant {h.grant_no} {h.section}/{h.kind} note {h.note_number} head {h.head_code} (page {h.page})"
        arithmetic = _arithmetic_problems(h)
        if h.printed_error is not None:
            listed.discard((details.financial_year, h.grant_no, h.head_code, h.category))
            if not arithmetic:
                problems.append(f"{where}: listed in KNOWN_PRINTED_ERRORS but its figures add up")
        else:
            problems.extend(f"{where}: {p}" for p in arithmetic)
        if (h.grant_no, h.section, h.path[0].code) not in majors:
            problems.append(f"{where}: major head {h.path[0].code} is not listed for this grant and section")
        if h.kind is None:
            problems.append(f"{where}: can't tell whether this row is Voted or Charged")
        elif (h.grant_no, h.section, h.kind) not in totals:
            problems.append(f"{where}: no section block for {h.section}/{h.kind}")
        if h.final_grant is None and h.expenditure is None:
            problems.append(f"{where}: row has neither a total grant nor an actual expenditure")
        if not h.path[-1].name:
            problems.append(f"{where}: head has no name")

    for key in sorted(listed):
        problems.append(f"KNOWN_PRINTED_ERRORS entry {key} matches no parsed row")

    rows_per_note: dict[tuple[int, int], int] = {}
    for h in details.heads:
        rows_per_note[(h.grant_no, h.note_number)] = rows_per_note.get((h.grant_no, h.note_number), 0) + 1
    for n in details.notes:
        if n.category != "comment" and not rows_per_note.get((n.grant_no, n.number)):
            problems.append(f"grant {n.grant_no} note {n.number} (page {n.page}): a {n.category} note with no rows")

    if problems:
        raise AppropriationDetailsError(
            f"Appropriation Accounts {details.financial_year} grant pages failed validation:\n  - "
            + "\n  - ".join(problems)
        )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import csv
    import json
    import sys

    parser = argparse.ArgumentParser(description="Extract the grant pages of a J&K Appropriation Accounts PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--no-validate", action="store_true", help="print what was parsed even if checks fail")
    args = parser.parse_args(argv)

    try:
        details = parse_appropriation_details(args.pdf, validate=not args.no_validate)
    except AppropriationAccountsError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.format == "json":
        json.dump(details.to_dict(), sys.stdout, indent=2)
        print()
    else:
        fields = [f for f in HeadLine.__dataclass_fields__ if f != "path"]
        writer = csv.DictWriter(
            sys.stdout, fieldnames=["financial_year", "unit", "head_code", "head_path", *fields]
        )
        writer.writeheader()
        for h in details.heads:
            row = {f: getattr(h, f) for f in fields}
            writer.writerow(
                {
                    "financial_year": details.financial_year,
                    "unit": details.unit,
                    "head_code": h.head_code,
                    "head_path": " > ".join(f"{p.code} {p.name}" for p in h.path),
                    **row,
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
