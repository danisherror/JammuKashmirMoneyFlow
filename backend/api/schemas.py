"""
Pydantic schemas for all API request/response models.
These define exactly what the frontend receives from every endpoint.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from enum import Enum


# ── Shared ────────────────────────────────────────────────────────────────────

class DivisionEnum(str, Enum):
    JAMMU = "jammu"
    KASHMIR = "kashmir"
    CENTRAL = "central"


class SchemeTypeEnum(str, Enum):
    CSS = "css"
    CENTRAL = "central"
    UT = "ut"


# ── Budget ────────────────────────────────────────────────────────────────────

class BudgetOverview(BaseModel):
    financial_year: str
    total_budget_lakhs: int
    total_capital_lakhs: int
    total_revenue_lakhs: int
    capital_pct: float
    revenue_pct: float
    total_departments: int
    data_as_of: Optional[date]

    class Config:
        from_attributes = True


class DepartmentSummary(BaseModel):
    id: int
    name: str
    code: str
    division: DivisionEnum
    financial_year: str
    budget_estimate_lakhs: int
    revised_estimate_lakhs: Optional[int]
    utilized_lakhs: Optional[int]
    utilization_pct: Optional[float]
    is_capital: bool
    data_as_of: Optional[date]

    class Config:
        from_attributes = True


class DepartmentDetail(DepartmentSummary):
    monthly_expenditure: list[dict] = []       # [{month: 1, amount: 12345}, ...]
    schemes: list[dict] = []
    year_over_year: Optional[dict] = None      # {current: X, previous: Y, change_pct: Z}


class GapAnalysisItem(BaseModel):
    department_id: int
    department_name: str
    department_code: str
    allocated_lakhs: int
    utilized_lakhs: int
    gap_lakhs: int
    utilization_pct: float
    gap_flag: str                              # "critical" | "warning" | "on_track"


# ── Schemes ───────────────────────────────────────────────────────────────────

class SchemeSummary(BaseModel):
    id: int
    name: str
    code: str
    scheme_type: SchemeTypeEnum
    department_name: str
    total_outlay_lakhs: Optional[int]
    funds_allocated_lakhs: Optional[int]
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


class SchemeVelocity(BaseModel):
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
    verdict: str                              # "ON TRACK" | "AT RISK" | "CRITICAL" | "NO DATA"

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
    absorption_grade: str                      # "A" | "B" | "C" | "D" | "F"

    class Config:
        from_attributes = True


class DistrictDetail(DistrictHeatmapItem):
    scheme_progress: list[SchemeDistrictProgress] = []
    dbt_summary: Optional[dict] = None


# ── Alerts ────────────────────────────────────────────────────────────────────

class SyncStatusItem(BaseModel):
    collector_name: str
    status: str
    last_run: Optional[datetime]
    last_success: Optional[datetime]
    records_last_run: int
    next_run: Optional[str]
    is_healthy: bool

    class Config:
        from_attributes = True


class LowUtilizationAlert(BaseModel):
    scheme_name: str
    scheme_code: str
    district_name: str
    department_name: str
    funds_allocated_lakhs: int
    funds_utilized_lakhs: int
    utilization_pct: float
    severity: str                              # "critical" (<20%) | "warning" (<40%)
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
