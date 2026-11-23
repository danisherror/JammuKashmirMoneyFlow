/**
 * Typed API client for the FastAPI backend.
 *
 * The response types are generated from the backend's OpenAPI schema into `./api-schema.ts`;
 * don't edit that file. After changing `backend/api/schemas.py` or a route's `response_model`:
 *
 *   cd backend && python -m scripts.export_openapi ../frontend/openapi.json
 *   cd ../frontend && npm run gen:api
 *
 * CI fails when either generated file is out of date. All money values are in ₹ lakhs.
 */
import axios from 'axios'
import type { components } from './api-schema'

export const api = axios.create({
  // VITE_API_BASE_URL includes the version prefix, e.g. http://localhost:8000/api/v1.
  // Falling back to a relative path lets the Vite dev proxy (vite.config.ts) handle it.
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 30_000,
})

// ── Types (generated; see the header) ─────────────────────────────────────────

type Schemas = components['schemas']

export type Division = Schemas['DivisionEnum']
export type SchemeType = Schemas['SchemeTypeEnum']
/** ISO date, `YYYY-MM-DD`. */
export type ISODate = string
/** ISO datetime. */
export type ISODateTime = string

// Provenance (todo.md 2.2a)
/** Which figures to show: portal collectors, CAG accounts, or the two merged (default). */
export type View = Schemas['View']
/** Set in the combined view when the portal and the audited accounts differ by more than 2%. */
export type MismatchInfo = Schemas['MismatchInfo']
/** Where one figure comes from. `source_type` null means there is no data; `label` says why. */
export type FigureSource = Schemas['FigureSource']
/** Fields shared by every response that carries per-figure provenance. */
export type Sourced = Pick<Schemas['BudgetOverview'], 'view' | 'sources'>

// Budget
/** How a year's audited grant became spending (CAG Appropriation Accounts, ₹ lakhs). */
export type OfficialChain = Schemas['OfficialChain']
export type BudgetOverview = Schemas['BudgetOverview']
export type DepartmentSummary = Schemas['DepartmentSummary']
export type MonthlyExpenditure = Schemas['MonthlyExpenditure']
export type DepartmentDetail = Schemas['DepartmentDetail']

// Grant breakdown (CAG Appropriation Accounts grant pages, todo.md 2.2b)
export type GrantInfo = Schemas['GrantInfo']
export type SectionBlockItem = Schemas['SectionBlockItem']
export type HeadPathPart = Schemas['HeadPathPart']
export type NoteCategory = Schemas['NoteItem']['category']
/** One row of a note table (₹ lakhs). Amounts the PDF doesn't print are null, not 0. */
export type HeadRowItem = Schemas['HeadRowItem']
export type HeadNode = Schemas['HeadNode']
export type NoteItem = Schemas['NoteItem']
export type DocumentIssueItem = Schemas['DocumentIssueItem']
export type FlagKind = Schemas['AccountabilityFlag']['kind']
/** A fact restated from the printed CAG figures (backend processors/accountability.py). */
export type AccountabilityFlag = Schemas['AccountabilityFlag']
/**
 * Where a department's (or one grant's) money went. The head rows are only the heads the CAG
 * commented on, so they don't add up to the grant total; the section blocks do.
 */
export type GrantBreakdown = Schemas['GrantBreakdown']
export type GapFlag = Schemas['GapAnalysisItem']['gap_flag']
export type GapAnalysisItem = Schemas['GapAnalysisItem']

// Schemes
export type SchemeSummary = Schemas['SchemeSummary']
export type SchemeDistrictProgress = Schemas['SchemeDistrictProgress']
export type SchemeDetail = Schemas['SchemeDetail']
export type SchemeHistoryPoint = Schemas['SchemeHistoryPoint']
export type Verdict = Schemas['SchemeVelocity']['verdict']
export type SchemeVelocity = Schemas['SchemeVelocity']

// Districts
export type AbsorptionGrade = Schemas['DistrictHeatmapItem']['absorption_grade']
export type DistrictHeatmapItem = Schemas['DistrictHeatmapItem']
export type DistrictDetail = Schemas['DistrictDetail']

// Alerts / sync
/** `status`: success | partial | no_source | failed | running | skipped */
export type SyncStatusItem = Schemas['SyncStatusItem']
export type LowUtilizationAlert = Schemas['LowUtilizationAlert']
export type CAGFinding = Schemas['CAGFindingItem']
export type TriggerResponse = Schemas['TriggerResponse']

// Tenders
export type TenderSummary = Schemas['TenderSummary']
export type ContractorLeaderboardItem = Schemas['ContractorLeaderboardItem']

// DBT
export type DBTSchemeSummary = Schemas['DBTSchemeSummary']
export type DBTDistrictGap = Schemas['DBTDistrictGap']

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

/** Official only, so no view. Omit the year to get the latest year with CAG grant pages loaded. */
export const fetchDepartmentBreakdown = (id: number, financialYear?: string) =>
  get<GrantBreakdown>(`/budget/departments/${id}/breakdown`, { financial_year: financialYear })

export const fetchGrantBreakdown = (grantNo: number, financialYear?: string) =>
  get<GrantBreakdown>(`/budget/grants/${grantNo}/breakdown`, { financial_year: financialYear })

/** Omit the year for the latest year with CAG grant pages loaded. */
export const fetchAccountabilityFlags = (financialYear?: string, kind?: FlagKind) =>
  get<AccountabilityFlag[]>('/alerts/accountability', { financial_year: financialYear, kind })

export const fetchGrants = (financialYear?: string) =>
  get<GrantInfo[]>('/budget/grants', { financial_year: financialYear })

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
