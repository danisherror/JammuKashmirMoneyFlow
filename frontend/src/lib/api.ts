/**
 * Typed API client for the FastAPI backend.
 *
 * Types mirror `backend/api/schemas.py` by hand. Keep them in sync until the
 * types are generated from `/openapi.json` (see todo.md, task 0.1).
 * All money values are in ₹ lakhs.
 */
import axios from 'axios'

export const api = axios.create({
  // VITE_API_BASE_URL includes the version prefix, e.g. http://localhost:8000/api/v1.
  // Falling back to a relative path lets the Vite dev proxy (vite.config.ts) handle it.
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 30_000,
})

// ── Shared ────────────────────────────────────────────────────────────────────

export type Division = 'jammu' | 'kashmir' | 'central'
export type SchemeType = 'css' | 'central' | 'ut'
/** ISO date, `YYYY-MM-DD`. */
export type ISODate = string
/** ISO datetime. */
export type ISODateTime = string

// ── Provenance (todo.md 2.2a) ─────────────────────────────────────────────────

/** Which figures to show: portal collectors, CAG accounts, or the two merged (default). */
export type View = 'live' | 'official' | 'combined'

/** Set in the combined view when the portal and the audited accounts differ by more than 2%. */
export interface MismatchInfo {
  live: number
  official: number
  /** (live − official) / official × 100; null when official is 0. */
  diff_pct: number | null
}

/** Where one figure comes from. `source_type` null means there is no data; `label` says why. */
export interface FigureSource {
  source_type: 'live' | 'official' | null
  label: string
  /** budget_estimate, revised_estimate, final_grant, gross_expenditure, utilized, released, allocated, total_outlay */
  measure: string | null
  source_url: string | null
  snapshot_id: number | null
  /** First page of the figure in the snapshot PDF. */
  page: number | null
  fetched_at: ISODateTime | null
  provisional: boolean
  mismatch: MismatchInfo | null
}

/** Fields shared by every response that carries per-figure provenance. */
export interface Sourced {
  view: View
  /** Keyed by the figure's field name, e.g. `sources.total_budget_lakhs`. */
  sources: Record<string, FigureSource>
}

// ── Budget ────────────────────────────────────────────────────────────────────

/**
 * How a year's audited grant became spending (CAG Appropriation Accounts, ₹ lakhs):
 * original + supplementary (+ re-appropriation) = final grant; final grant − gross expenditure =
 * saving − excess; gross expenditure − recoveries = net expenditure. The original grant is what was
 * passed with the budget; it is not called a Budget Estimate because that hasn't been checked
 * against the J&K budget documents.
 */
export interface OfficialChain {
  financial_year: string
  grants: number[]
  original_lakhs: number
  supplementary_lakhs: number
  reappropriation_lakhs: number
  final_grant_lakhs: number
  surrendered_lakhs: number
  gross_expenditure_lakhs: number
  saving_lakhs: number
  excess_lakhs: number
  /** null when Appendix II isn't loaded for the year. */
  recoveries_lakhs: number | null
  recoveries_estimate_lakhs: number | null
  net_expenditure_lakhs: number | null
  sources: Record<string, FigureSource>
}

export interface BudgetOverview extends Sourced {
  financial_year: string
  total_budget_lakhs: number | null
  total_capital_lakhs: number | null
  total_revenue_lakhs: number | null
  capital_pct: number | null
  revenue_pct: number | null
  /** Official figures: number of CAG grants. */
  total_departments: number
  data_as_of: ISODate | null
  /** Every grant; null in the live view or for a year without CAG accounts. */
  official_chain: OfficialChain | null
}

export interface DepartmentSummary extends Sourced {
  id: number
  name: string
  code: string
  division: Division
  financial_year: string
  /** Official figures: the final grant (original + supplementary); see `sources[...].measure`. */
  budget_estimate_lakhs: number | null
  revised_estimate_lakhs: number | null
  /** Official figures: gross expenditure. */
  utilized_lakhs: number | null
  utilization_pct: number | null
  /** null for official figures, which cover revenue + capital together. */
  is_capital: boolean | null
  data_as_of: ISODate | null
}

export interface MonthlyExpenditure {
  month: number
  amount_lakhs: number
}

export interface DepartmentDetail extends DepartmentSummary {
  monthly_expenditure: MonthlyExpenditure[]
  schemes: Record<string, unknown>[]
  year_over_year: { current: number; previous: number; change_pct: number | null } | null
  /** The department's mapped grants; null in the live view, without a mapped grant or CAG accounts. */
  official_chain: OfficialChain | null
}

export type GapFlag = 'critical' | 'warning' | 'on_track' | 'no_data'

export interface GapAnalysisItem extends Sourced {
  department_id: number
  department_name: string
  department_code: string
  allocated_lakhs: number
  /** null when no PFMS release figure exists. */
  released_lakhs: number | null
  utilized_lakhs: number | null
  gap_lakhs: number | null
  utilization_pct: number | null
  gap_flag: GapFlag
}

// ── Schemes ───────────────────────────────────────────────────────────────────

export interface SchemeSummary extends Sourced {
  id: number
  name: string
  code: string
  scheme_type: SchemeType
  department_name: string
  total_outlay_lakhs: number | null
  funds_allocated_lakhs: number | null
  funds_released_lakhs: number | null
  funds_utilized_lakhs: number | null
  utilization_pct: number | null
  physical_pct: number | null
  last_updated: ISODate | null
}

export interface SchemeDistrictProgress {
  district_id: number
  district_name: string
  district_code: string
  division: Division
  target_physical: number | null
  achieved_physical: number | null
  physical_unit: string | null
  physical_pct: number | null
  funds_allocated_lakhs: number | null
  funds_released_lakhs: number | null
  funds_utilized_lakhs: number | null
  utilization_pct: number | null
  release_pct: number | null
  snapshot_date: ISODate | null
  scheme_name?: string | null
  scheme_code?: string | null
}

export interface SchemeDetail extends SchemeSummary {
  description: string | null
  start_year: number | null
  end_year: number | null
  source_url: string | null
  district_progress: SchemeDistrictProgress[]
}

export interface SchemeHistoryPoint {
  snapshot_date: ISODate
  funds_allocated_lakhs: number
  funds_utilized_lakhs: number
  utilization_pct: number | null
}

export type Verdict = 'ON TRACK' | 'AT RISK' | 'CRITICAL' | 'NO DATA'

export interface SchemeVelocity extends Sourced {
  scheme_id: number
  scheme_name: string
  financial_year: string
  history: SchemeHistoryPoint[]
  days_elapsed: number
  days_remaining: number
  daily_run_rate_lakhs: number | null
  projected_utilized_lakhs: number | null
  total_allocated_lakhs: number | null
  on_track: boolean | null
  surrender_risk_lakhs: number | null
  verdict: Verdict
}

// ── Districts ─────────────────────────────────────────────────────────────────

export type AbsorptionGrade = 'A' | 'B' | 'C' | 'D' | 'F'

export interface DistrictHeatmapItem {
  id: number
  name: string
  code: string
  division: Division
  population: number | null
  is_border_district: boolean
  avg_utilization_pct: number | null
  total_funds_allocated_lakhs: number | null
  total_funds_utilized_lakhs: number | null
  active_schemes_count: number
  absorption_score: number | null
  absorption_grade: AbsorptionGrade
}

export interface DistrictDetail extends DistrictHeatmapItem {
  scheme_progress: SchemeDistrictProgress[]
  dbt_summary: Record<string, unknown> | null
}

// ── Alerts / sync ─────────────────────────────────────────────────────────────

export interface SyncStatusItem {
  collector_name: string
  status: string
  last_run: ISODateTime | null
  last_success: ISODateTime | null
  records_last_run: number
  next_run: string | null
  is_healthy: boolean
  error_message?: string | null
}

export interface LowUtilizationAlert {
  scheme_name: string
  scheme_code: string
  district_name: string
  department_name: string
  funds_allocated_lakhs: number
  funds_utilized_lakhs: number
  utilization_pct: number
  severity: 'critical' | 'warning'
  snapshot_date: ISODate
}

/** Shape returned by `GET /alerts/cag-findings` (built inline in `backend/api/routes/alerts.py`). */
export interface CAGFinding {
  id: number
  report_year: string | null
  report_title: string | null
  department_name: string | null
  finding_summary: string | null
  finding_raw: string | null
  amount_flagged_lakhs: number | null
  severity: string | null
  paragraph_ref: string | null
  source_pdf_url: string | null
}

export interface TriggerResponse {
  message: string
  started_at: ISODateTime
  financial_year?: string
}

// ── Tenders ───────────────────────────────────────────────────────────────────

export interface TenderSummary {
  id: number
  tender_ref: string
  title: string
  department_name: string
  estimated_cost_lakhs: number | null
  awarded_cost_lakhs: number | null
  contractor_name: string | null
  status: string | null
  published_date: ISODate | null
  award_date: ISODate | null
}

export interface ContractorLeaderboardItem {
  contractor_name: string
  total_tenders_won: number
  total_awarded_lakhs: number
}

// ── DBT ───────────────────────────────────────────────────────────────────────

export interface DBTSchemeSummary {
  scheme_id: number
  scheme_name: string
  scheme_code: string
  financial_year: string
  total_beneficiaries_enrolled: number
  total_beneficiaries_paid: number
  total_amount_transferred_lakhs: number
  overall_gap_pct: number
}

export interface DBTDistrictGap {
  district_id: number
  district_name: string
  district_code: string
  beneficiaries_enrolled: number
  beneficiaries_paid: number
  amount_transferred_lakhs: number
  last_mile_gap_pct: number
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

const get = async <T>(url: string, params?: Record<string, unknown>): Promise<T> =>
  (await api.get<T>(url, { params })).data

const post = async <T>(url: string, params?: Record<string, unknown>): Promise<T> =>
  (await api.post<T>(url, null, { params })).data

// Budget
// Budget and scheme routes take `view` (todo.md 2.2a); the backend defaults to combined.
export const fetchBudgetOverview = (financialYear: string, view?: View) =>
  get<BudgetOverview>('/budget/overview', { financial_year: financialYear, view })

export const fetchDepartments = (
  financialYear: string,
  view?: View,
  division?: Division,
  sortBy?: 'budget_estimate' | 'utilization_pct',
) =>
  get<DepartmentSummary[]>('/budget/departments', {
    financial_year: financialYear,
    view,
    division,
    sort_by: sortBy,
  })

export const fetchDepartmentDetail = (id: number, financialYear: string, view?: View) =>
  get<DepartmentDetail>(`/budget/departments/${id}`, { financial_year: financialYear, view })

export const fetchGapAnalysis = (financialYear: string, view?: View, minAllocationLakhs?: number) =>
  get<GapAnalysisItem[]>('/budget/gap-analysis', {
    financial_year: financialYear,
    view,
    min_allocation_lakhs: minAllocationLakhs,
  })

// Schemes
export const fetchSchemes = (
  financialYear: string,
  view?: View,
  schemeType?: SchemeType,
  departmentId?: number,
) =>
  get<SchemeSummary[]>('/schemes', {
    financial_year: financialYear,
    view,
    scheme_type: schemeType,
    department_id: departmentId,
  })

export const fetchSchemeDetail = (id: number, financialYear: string, view?: View) =>
  get<SchemeDetail>(`/schemes/${id}`, { financial_year: financialYear, view })

export const fetchSchemeHistory = (id: number, financialYear: string, view?: View) =>
  get<SchemeVelocity>(`/schemes/${id}/history`, { financial_year: financialYear, view })

// Districts
export const fetchDistrictHeatmap = (financialYear: string, schemeCode?: string) =>
  get<DistrictHeatmapItem[]>('/districts/heatmap', {
    financial_year: financialYear,
    scheme_code: schemeCode,
  })

export const fetchDistrictDetail = (id: number, financialYear: string) =>
  get<DistrictDetail>(`/districts/${id}`, { financial_year: financialYear })

// Alerts / sync
export const fetchSyncStatus = () => get<SyncStatusItem[]>('/alerts/sync-status')

export const triggerCollector = (name: string) => post<TriggerResponse>(`/alerts/trigger/${name}`)

export const triggerAllCollectors = (financialYear: string) =>
  post<TriggerResponse>('/alerts/trigger-all', { financial_year: financialYear })

export const fetchLowUtilAlerts = (
  financialYear: string,
  thresholdPct?: number,
  minAllocationLakhs?: number,
) =>
  get<LowUtilizationAlert[]>('/alerts/low-utilization', {
    financial_year: financialYear,
    threshold_pct: thresholdPct,
    min_allocation_lakhs: minAllocationLakhs,
  })

export const fetchCAGFindings = (limit = 50) => get<CAGFinding[]>('/alerts/cag-findings', { limit })

// Tenders
export const fetchTenders = (params: { limit?: number; departmentId?: number; status?: string } = {}) =>
  get<TenderSummary[]>('/tenders', {
    limit: params.limit,
    department_id: params.departmentId,
    status: params.status,
  })

export const fetchContractorLeaderboard = (limit = 20) =>
  get<ContractorLeaderboardItem[]>('/tenders/contractors', { limit })

// DBT
export const fetchDBTSchemes = (financialYear: string) =>
  get<DBTSchemeSummary[]>('/dbt/schemes', { financial_year: financialYear })

export const fetchDBTGap = (schemeId: number, financialYear: string) =>
  get<DBTDistrictGap[]>(`/dbt/schemes/${schemeId}/gap`, { financial_year: financialYear })
