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
