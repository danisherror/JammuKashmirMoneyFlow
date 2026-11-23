/**
 * Helpers for the Live / Official / Combined views and per-figure source badges (todo.md 2.2a).
 * Pure functions only, so they can be unit-tested without a DOM.
 */
import type { FigureSource, View } from './api'
import { fmtLakhs } from './utils'

export const VIEWS: { value: View; label: string; hint: string }[] = [
  { value: 'live', label: 'Live', hint: 'Portal collectors. Provisional.' },
  { value: 'official', label: 'Official', hint: 'CAG audited accounts, with a page reference.' },
  { value: 'combined', label: 'Combined', hint: 'Audited figure where one exists, otherwise the live figure.' },
]

export const DEFAULT_VIEW: View = 'combined'

/** Read a view from a query-string value; anything unknown falls back to combined. */
export function parseView(value: string | null | undefined): View {
  return value === 'live' || value === 'official' || value === 'combined' ? value : DEFAULT_VIEW
}

/**
 * Return `search` (a URL query string) with `view` set, keeping other parameters. The view is
 * always written, even the default, so every history entry says which view it showed and the
 * Back button restores it.
 */
export function searchWithView(search: string, view: View): string {
  const params = new URLSearchParams(search)
  params.set('view', view)
  return `?${params.toString()}`
}

export type SourceKind = 'official' | 'live' | 'flagged' | 'unsourced' | 'none'

/**
 * How a figure's badge looks: flagged (official with a mismatch), official, live, or no data.
 * A figure that has a value but no recorded source (e.g. a seed reference value) is "unsourced",
 * so a number never sits next to a "No data" badge. Pass `value` to tell the two apart.
 */
export function sourceKind(source: FigureSource | null | undefined, value?: number | null): SourceKind {
  if (!source || source.source_type === null) return value != null ? 'unsourced' : 'none'
  if (source.mismatch) return 'flagged'
  return source.source_type
}

const BADGE_TEXT: Record<SourceKind, string> = {
  official: 'Official',
  live: 'Live',
  flagged: 'Official ⚑',
  unsourced: 'Unsourced',
  none: 'No data',
}

export function badgeText(source: FigureSource | null | undefined, value?: number | null): string {
  return BADGE_TEXT[sourceKind(source, value)]
}

const MEASURE_LABELS: Record<string, string> = {
  budget_estimate: 'Budget estimate',
  revised_estimate: 'Revised estimate',
  final_grant: 'Final grant (original + supplementary)',
  gross_expenditure: 'Gross expenditure',
  utilized: 'Utilised',
  released: 'Released',
  allocated: 'Allocated',
  total_outlay: 'Total outlay',
  physical_progress_pct: 'Physical progress (%)',
  original_grant: 'Original grant (passed with the budget)',
  supplementary_grant: 'Supplementary grant',
  reappropriation: 'Re-appropriation',
  surrendered: 'Surrendered during the year',
  saving: 'Saving (final grant not spent)',
  excess: 'Excess over the final grant',
  recoveries: 'Recoveries deducted from expenditure (Appendix II)',
  recoveries_estimate: 'Budget estimate of recoveries (Appendix II)',
  net_expenditure: 'Net expenditure (gross − recoveries)',
}

/** Plain-language name of what a figure measures, or null if the source doesn't say. */
export function measureLabel(source: FigureSource | null | undefined): string | null {
  const m = source?.measure
  if (!m) return null
  return MEASURE_LABELS[m] ?? m.replace(/_/g, ' ')
}

/**
 * Short field heading that matches what the number actually is. Official department figures are
 * the final grant and gross expenditure, not a budget estimate and "utilised".
 */
export function fieldHeading(source: FigureSource | null | undefined, fallback: string): string {
  switch (source?.measure) {
    case 'final_grant':
      return 'Final grant'
    case 'gross_expenditure':
      return 'Gross expenditure'
    default:
      return fallback
  }
}

/** "Portal said ₹X, audited accounts say ₹Y (−88.3%)", or null when there is no mismatch. */
export function mismatchText(source: FigureSource | null | undefined): string | null {
  const m = source?.mismatch
  if (!m) return null
  const diff =
    m.diff_pct === null ? '' : ` (${m.diff_pct > 0 ? '+' : '−'}${Math.abs(m.diff_pct).toFixed(1)}%)`
  return `Portal said ${fmtLakhs(m.live)}, audited accounts say ${fmtLakhs(m.official)}${diff}`
}

/** "p.9" for a PDF page reference, or null. */
export function pageRef(source: FigureSource | null | undefined): string | null {
  return source?.page != null ? `p.${source.page}` : null
}

/**
 * Download link for the saved copy of a figure's source document (GET /snapshots/{id}, todo.md 1.4),
 * or null when the figure has no snapshot. `apiBase` is the API base URL including /api/v1.
 */
export function snapshotUrl(snapshotId: number | null | undefined, apiBase: string): string | null {
  if (snapshotId == null) return null
  return `${apiBase.replace(/\/+$/, '')}/snapshots/${snapshotId}`
}
