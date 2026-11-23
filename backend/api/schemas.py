"""
Pydantic schemas for all API request/response models.
These define exactly what the frontend receives from every endpoint.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date, datetime
from enum import Enum

from processors.combined_view import View as ViewEnum  # noqa: F401  (re-exported for routes)


# ── Shared ────────────────────────────────────────────────────────────────────

class DivisionEnum(str, Enum):
    JAMMU = "jammu"
    KASHMIR = "kashmir"
    CENTRAL = "central"


class SchemeTypeEnum(str, Enum):
    CSS = "css"
    CENTRAL = "central"
    UT = "ut"


# Closed sets of string values. They are Literals (not plain str) so /openapi.json, and the
# TypeScript types generated from it (frontend/src/lib/api-schema.ts), carry the exact values.
HeadLevel = Literal["major", "sub_major", "minor", "sub_head", "detailed"]
NoteCategory = Literal[
    "saving", "excess", "unutilised", "unutilised_supplementary", "without_provision", "comment",
]
GapFlag = Literal["critical", "warning", "on_track", "no_data"]
Verdict = Literal["ON TRACK", "AT RISK", "CRITICAL", "NO DATA"]
AbsorptionGrade = Literal["A", "B", "C", "D", "F"]


# ── Provenance (todo.md 2.2a) ─────────────────────────────────────────────────

class MismatchInfo(BaseModel):
    """Set in the combined view when the portal and the audited accounts differ by more than 2%."""
    live: float = Field(description="Live (portal / budget table) figure, ₹ lakhs")
    official: float = Field(description="Official (CAG accounts) figure, ₹ lakhs")
    diff_pct: Optional[float] = Field(description="(live − official) / official × 100; null when official is 0")


class FigureSource(BaseModel):
    """Where one figure in the response comes from. Keyed by the figure's field name in `sources`."""
    source_type: Optional[Literal["live", "official"]] = Field(description="null when there is no data")
    label: str = Field(description='e.g. "Official · Appropriation Accounts 2022-23, p.4"')
    measure: Optional[str] = Field(
        None,
        description="What the number is: budget_estimate, revised_estimate, final_grant (original + "
                    "supplementary), gross_expenditure, utilized, released, allocated",
    )
    source_url: Optional[str] = None
    snapshot_id: Optional[int] = Field(None, description="source_snapshots.id of the saved document")
    page: Optional[int] = Field(None, description="First page of the figure in the snapshot PDF")
    fetched_at: Optional[datetime] = None
    provisional: bool = False
    mismatch: Optional[MismatchInfo] = None


class Sourced(BaseModel):
    """Mixin: which view produced the response, and a FigureSource per figure field."""
    view: ViewEnum = ViewEnum.COMBINED
    sources: dict[str, FigureSource] = {}


# ── Budget ────────────────────────────────────────────────────────────────────

class OfficialChain(BaseModel):
    """
    How a year's audited grant became spending, from the CAG Appropriation Accounts (₹ lakhs):
    original + supplementary (+ re-appropriation, 2021-22 only) = final grant; final grant − gross
    expenditure = saving − excess; gross expenditure − recoveries (Appendix II) = net expenditure.
    The original grant is the amount passed with the budget; it has not been checked against the
    Budget Estimates in the J&K budget documents, so it is not called a Budget Estimate here.
    """
    financial_year: str
    grants: list[int] = Field(description="Grant numbers summed (a department can have several)")
    original_lakhs: float
    supplementary_lakhs: float
    reappropriation_lakhs: float
    final_grant_lakhs: float
    surrendered_lakhs: float = Field(description="Amount surrendered during the year")
    gross_expenditure_lakhs: float
    saving_lakhs: float
    excess_lakhs: float
    recoveries_lakhs: Optional[float] = Field(
        description="Recoveries deducted from expenditure (Appendix II); null if Appendix II isn't loaded"
    )
    recoveries_estimate_lakhs: Optional[float] = Field(description="Budget Estimate of those recoveries")
    net_expenditure_lakhs: Optional[float] = Field(description="Gross expenditure − recoveries")
    sources: dict[str, FigureSource] = {}


class BudgetOverview(Sourced):
    financial_year: str
    total_budget_lakhs: Optional[float]
    total_capital_lakhs: Optional[float]
    total_revenue_lakhs: Optional[float]
    capital_pct: Optional[float]
    revenue_pct: Optional[float]
    total_departments: int                     # official view: number of grants
    data_as_of: Optional[date]
    official_chain: Optional[OfficialChain] = None  # every grant; null in the live view

    class Config:
        from_attributes = True


class DepartmentSummary(Sourced):
    id: int
    name: str
    code: str
    division: DivisionEnum
    financial_year: str
    budget_estimate_lakhs: Optional[float]     # official: final grant — see sources[...].measure
    revised_estimate_lakhs: Optional[float]
    utilized_lakhs: Optional[float]            # official: gross expenditure
    utilization_pct: Optional[float]
    is_capital: Optional[bool]                 # null for official figures (revenue + capital)
    data_as_of: Optional[date]

    class Config:
        from_attributes = True


class MonthlyExpenditure(BaseModel):
    month: int = Field(description="Calendar month, 1-12")
    amount_lakhs: Optional[float] = Field(description="₹ lakhs")


class YearOverYear(BaseModel):
    current: float
    previous: float
    change_pct: Optional[float]


class DepartmentDetail(DepartmentSummary):
    monthly_expenditure: list[MonthlyExpenditure] = []
    schemes: list[dict] = []
    year_over_year: Optional[YearOverYear] = None
    official_chain: Optional[OfficialChain] = Field(
        None, description="Audited original → final grant → spent chain; null in the live view or for a year "
                          "without CAG accounts"
    )


# ── Grant breakdown (CAG Appropriation Accounts grant pages, todo.md 2.2b) ────

class GrantInfo(BaseModel):
    grant_no: int
    name: str = Field(description="Official grant name as printed in the summary table")
    department_id: Optional[int] = Field(description="Tracker department, via grant_department_map; null if unmapped")
    final_grant_lakhs: Optional[float] = None
    gross_expenditure_lakhs: Optional[float] = None
    source: Optional[FigureSource] = Field(None, description="Summary-table page of the grant in the snapshot PDF")


class SectionBlockItem(BaseModel):
    """One Voted/Charged block at the top of a grant's pages (₹ lakhs)."""
    grant_no: int
    section: str
    kind: str
    original_lakhs: float
    supplementary_lakhs: float
    reappropriation_lakhs: float
    final_grant_lakhs: float
    expenditure_lakhs: float
    saving_lakhs: float
    excess_lakhs: float
    surrendered_lakhs: float
    source: FigureSource


class HeadPathPart(BaseModel):
    level: HeadLevel
    code: str
    name: str


class HeadRowItem(BaseModel):
    """One row of a note table (₹ lakhs). Amounts the PDF doesn't print are null, not 0."""
    grant_no: int
    section: str
    kind: str
    note_number: int
    category: NoteCategory
    reasons_not_communicated: bool
    head_code: str
    head_name: str
    head_path: list[HeadPathPart]
    original_lakhs: Optional[float]
    supplementary_lakhs: Optional[float]
    reappropriation_lakhs: Optional[float]
    final_grant_lakhs: Optional[float]
    expenditure_lakhs: Optional[float]
    saving_lakhs: Optional[float]
    excess_lakhs: Optional[float]
    remark: str = Field(description="Official remark, verbatim")
    printed_error: Optional[str] = Field(description="Set when the printed figures don't add up in the PDF itself")
    source: FigureSource


class HeadNode(BaseModel):
    """A node of the head tree (major → sub-major → minor → sub-head → detailed head)."""
    level: HeadLevel
    code: str
    name: str
    head_code: str = Field(description="Codes from the major head down to this node, joined by dots")
    section: str
    grant_no: int
    rows: list[HeadRowItem] = Field(description="Note rows for exactly this head")
    children: list["HeadNode"] = []


class NoteItem(BaseModel):
    grant_no: int
    number: int
    section: Optional[str]
    kind: Optional[str]
    category: NoteCategory
    reasons_not_communicated: bool
    text: str = Field(description="Verbatim note text")
    source: FigureSource


class DocumentIssueItem(BaseModel):
    """Something the parser kept aside rather than guessing (a non-head table, a misfiled row, a footnote)."""
    grant_no: Optional[int]
    kind: Literal["skipped_table", "misfiled", "footnote", "headerless_table"]
    page: Optional[int]
    text: str


class AccountabilityFlag(BaseModel):
    """A fact worth a citizen's attention, restated from the printed figures (processors.accountability)."""
    kind: Literal[
        "excess_over_grant", "savings_not_surrendered", "supplementary_not_needed",
        "fully_unutilised", "reasons_not_communicated",
    ]
    financial_year: str
    grant_no: int
    grant_name: str
    department_id: Optional[int]
    section: Optional[str] = None
    block_kind: Optional[str] = Field(None, description="voted | charged")
    head_code: Optional[str] = None
    head_name: Optional[str] = None
    amount_lakhs: Optional[float] = Field(None, description="The amount the flag is about, ₹ lakhs")
    share_pct: Optional[float] = Field(None, description="reasons_not_communicated: share of commented heads")
    detail: str
    source: FigureSource


class GrantBreakdown(BaseModel):
    """
    Where a department's (or one grant's) money went, from the grant pages of the CAG Appropriation
    Accounts. The notes list only the heads with notable savings, excesses or unspent provisions,
    so the head rows do not add up to the grant total; the section blocks do.
    """
    financial_year: str
    department_id: Optional[int]
    grants: list[GrantInfo]
    section_blocks: list[SectionBlockItem]
    tree: list[HeadNode]
    notes: list[NoteItem]
    issues: list[DocumentIssueItem]
    flags: list[AccountabilityFlag] = []
    note: Optional[str] = Field(None, description="Why the breakdown is empty, when it is")


class GapAnalysisItem(Sourced):
    department_id: int
    department_name: str
    department_code: str
    allocated_lakhs: float
    released_lakhs: Optional[float]            # null when no PFMS release figure exists
    utilized_lakhs: Optional[float]
    gap_lakhs: Optional[float]
    utilization_pct: Optional[float]
    gap_flag: GapFlag


# ── Schemes ───────────────────────────────────────────────────────────────────

class SchemeSummary(Sourced):
    id: int
    name: str
    code: str
    scheme_type: SchemeTypeEnum
    department_name: str
    total_outlay_lakhs: Optional[int]
    funds_allocated_lakhs: Optional[int]
    funds_released_lakhs: Optional[int]          # PFMS central release aggregate
    funds_utilized_lakhs: Optional[int]
    utilization_pct: Optional[float]
    physical_pct: Optional[float]
    last_updated: Optional[date]

    class Config:
        from_attributes = True


class SchemeDistrictProgress(BaseModel):
    district_id: int
    district_name: str
    district_code: str
    division: DivisionEnum
    target_physical: Optional[float]
    achieved_physical: Optional[float]
    physical_unit: Optional[str]
    physical_pct: Optional[float]
    funds_allocated_lakhs: Optional[int]
    funds_released_lakhs: Optional[int]
    funds_utilized_lakhs: Optional[int]
    utilization_pct: Optional[float]
    release_pct: Optional[float]
    snapshot_date: Optional[date]
    scheme_name: Optional[str] = None           # populated in district detail view
    scheme_code: Optional[str] = None

    class Config:
        from_attributes = True


class SchemeDetail(SchemeSummary):
    description: Optional[str]
    start_year: Optional[int]
    end_year: Optional[int]
    source_url: Optional[str]
    district_progress: list[SchemeDistrictProgress] = []


class SchemeHistoryPoint(BaseModel):
    """One data point in the spending velocity time-series."""
    snapshot_date: date
    funds_allocated_lakhs: int
    funds_utilized_lakhs: int
    utilization_pct: Optional[float]

    class Config:
        from_attributes = True


class SchemeVelocity(Sourced):
    """Full velocity + projection payload for a scheme."""
    scheme_id: int
    scheme_name: str
    financial_year: str
    history: list[SchemeHistoryPoint]

    # Run-rate maths
    days_elapsed: int                         # days since FY start (Apr 1)
    days_remaining: int                       # days until Mar 31
    daily_run_rate_lakhs: Optional[float]     # average lakhs spent per day
    projected_utilized_lakhs: Optional[int]   # if run-rate holds
    total_allocated_lakhs: Optional[int]

    # Verdict
    on_track: Optional[bool]                  # True if projected >= allocated
    surrender_risk_lakhs: Optional[int]       # how much may be surrendered
    verdict: Verdict

    class Config:
        from_attributes = True


# ── Districts ─────────────────────────────────────────────────────────────────

class DistrictHeatmapItem(BaseModel):
    id: int
    name: str
    code: str
    division: DivisionEnum
    population: Optional[int]
    is_border_district: bool
    # Aggregate score across all schemes
    avg_utilization_pct: Optional[float]
    total_funds_allocated_lakhs: Optional[int]
    total_funds_utilized_lakhs: Optional[int]
    active_schemes_count: int
    # For map coloring
    absorption_score: Optional[float]         # 0-100 normalized score
    absorption_grade: Optional[AbsorptionGrade] = Field(description="null when the district has no data")

    class Config:
        from_attributes = True


class DistrictDetail(DistrictHeatmapItem):
    scheme_progress: list[SchemeDistrictProgress] = []
    dbt_summary: Optional[dict] = None


# ── Alerts ────────────────────────────────────────────────────────────────────

class SyncStatusItem(BaseModel):
    collector_name: str
    label: str = Field(description="Human name, e.g. 'Jal Jeevan Mission'")
    source_name: str = Field(description="Portal the collector reads, or why there is none")
    source_url: Optional[str] = Field(description="Page the collector reads; null when not yet known")
    status: str = Field(
        description="success | partial | no_source | failed | running | skipped, or never_run when the "
                    "collector has no logged run"
    )
    last_run: Optional[datetime]
    last_success: Optional[datetime]
    records_last_run: int
    next_run: Optional[datetime] = Field(
        None, description="Next scheduled run from APScheduler; null if the scheduler is disabled"
    )
    is_healthy: bool
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class TriggerResponse(BaseModel):
    message: str
    started_at: datetime
    financial_year: Optional[str] = None


class CAGFindingItem(BaseModel):
    """One row of GET /alerts/cag-findings."""
    id: int
    report_year: int
    report_title: Optional[str]
    department_name: Optional[str]
    finding_summary: Optional[str]
    finding_raw: str
    amount_flagged_lakhs: Optional[float]
    severity: Optional[Literal["high", "medium", "low"]]
    paragraph_ref: Optional[str]
    source_pdf_url: Optional[str]


class LowUtilizationAlert(BaseModel):
    scheme_name: str
    scheme_code: str
    district_name: str
    department_name: str
    funds_allocated_lakhs: int
    funds_utilized_lakhs: int
    utilization_pct: float
    severity: Literal["critical", "warning"] = Field(description="critical below 20%, warning below 40%")
    snapshot_date: date

    class Config:
        from_attributes = True


# ── Tenders ───────────────────────────────────────────────────────────────────

class TenderSummary(BaseModel):
    id: int
    tender_ref: str
    title: str
    department_name: str
    estimated_cost_lakhs: Optional[int]
    awarded_cost_lakhs: Optional[int]
    contractor_name: Optional[str]
    status: Optional[str]
    published_date: Optional[date]
    award_date: Optional[date]

    class Config:
        from_attributes = True


class ContractorLeaderboardItem(BaseModel):
    contractor_name: str
    total_tenders_won: int
    total_awarded_lakhs: int


# ── DBT ───────────────────────────────────────────────────────────────────────

class DBTSchemeSummary(BaseModel):
    scheme_id: int
    scheme_name: str
    scheme_code: str
    financial_year: str
    total_beneficiaries_enrolled: int
    total_beneficiaries_paid: int
    total_amount_transferred_lakhs: int
    overall_gap_pct: float


class DBTDistrictGap(BaseModel):
    district_id: int
    district_name: str
    district_code: str
    beneficiaries_enrolled: int
    beneficiaries_paid: int
    amount_transferred_lakhs: int
    last_mile_gap_pct: float

    class Config:
        from_attributes = True
