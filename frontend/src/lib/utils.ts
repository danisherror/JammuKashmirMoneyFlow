/**
 * Formatting and colour helpers shared by the pages.
 * Missing values (null/undefined/NaN) always render as "—", never as 0.
 */
import type { SchemeType } from './api'

const isMissing = (v: number | null | undefined): v is null | undefined =>
  v === null || v === undefined || Number.isNaN(v)

/**
 * Format an amount given in ₹ lakhs.
 * ≥ 1 lakh crore → "₹1.23L Cr", ≥ 100 lakhs → "₹12.3 Cr", otherwise "₹45.6 L".
 * (1 crore = 100 lakhs.)
 */
export function fmtLakhs(v: number | null | undefined): string {
  if (isMissing(v)) return '—'
  const sign = v < 0 ? '-' : ''
  const abs = Math.abs(v)
  const crore = abs / 100
  if (crore >= 100_000) return `${sign}₹${(crore / 100_000).toFixed(2)}L Cr`
  if (crore >= 1) {
    return `${sign}₹${crore.toLocaleString('en-IN', { maximumFractionDigits: crore >= 100 ? 0 : 1 })} Cr`
  }
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: 2 })} L`
}

/** Format a count (people, transactions) with Indian digit grouping; "—" when unknown. A real 0 shows as "0". */
export function fmtCount(v: number | null | undefined): string {
  if (isMissing(v)) return '—'
  return v.toLocaleString('en-IN')
}

/** a − b, or null when either is unknown (an unknown figure never counts as 0). */
export function difference(a: number | null | undefined, b: number | null | undefined): number | null {
  return isMissing(a) || isMissing(b) ? null : a - b
}

/** Sum of the known values; null when none is known, so "no data" doesn't show as ₹0. */
export function sumKnown(values: Array<number | null | undefined>): number | null {
  const known = values.filter((v): v is number => !isMissing(v))
  return known.length ? known.reduce((s, v) => s + v, 0) : null
}

/** Format a percentage value that is already on a 0–100 scale. */
export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (isMissing(v)) return '—'
  return `${v.toFixed(digits)}%`
}

/** Tailwind/CSS text-colour class for a utilisation percentage (see `.text-*` in index.css). */
export function utilColor(pct: number | null | undefined): string {
  if (isMissing(pct)) return 'text-dim'
  if (pct >= 75) return 'text-green'
  if (pct >= 40) return 'text-gold'
  return 'text-red'
}

/** CSS colour value (a `var(--accent-*)`) for a utilisation percentage, for inline styles. */
export function utilColorVar(pct: number | null | undefined): string {
  if (isMissing(pct)) return 'var(--text-muted)'
  if (pct >= 75) return 'var(--accent-green)'
  if (pct >= 40) return 'var(--accent-gold)'
  return 'var(--accent-red)'
}

const GRADE_COLORS: Record<string, string> = {
  A: '#34d399',
  B: '#38bdf8',
  C: '#fbbf24',
  D: '#fb923c',
  F: '#fb7185',
}

/** Hex colour for a district absorption grade (A–F). */
export function gradeColor(grade: string | null | undefined): string {
  return (grade && GRADE_COLORS[grade]) || '#64748b'
}

const DIVISION_LABELS: Record<string, string> = {
  jammu: 'Jammu Division',
  kashmir: 'Kashmir Division',
  central: 'UT-wide',
}

export function divisionLabel(division: string | null | undefined): string {
  if (!division) return '—'
  return DIVISION_LABELS[division] ?? division
}

/** Badge classes for a scheme type (see `.badge-*` in index.css). */
export function schemeBadge(type: SchemeType | string): string {
  switch (type) {
    case 'css':
    case 'central':
      return 'badge badge-css'
    case 'ut':
      return 'badge badge-ut'
    default:
      return 'badge'
  }
}

const SCHEME_TYPE_LABELS: Record<string, string> = {
  css: 'Centrally Sponsored',
  central: 'Central Sector',
  ut: 'UT Scheme',
}

export function schemeTypeLabel(type: SchemeType | string): string {
  return SCHEME_TYPE_LABELS[type] ?? type.toUpperCase()
}
