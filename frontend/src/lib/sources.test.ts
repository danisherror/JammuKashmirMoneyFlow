import { describe, expect, it } from 'vitest'
import type { FigureSource } from './api'
import {
  badgeText,
  fieldHeading,
  measureLabel,
  mismatchText,
  pageRef,
  parseView,
  searchWithView,
  sourceKind,
} from './sources'

const base: FigureSource = {
  source_type: 'official',
  label: 'Official · Appropriation Accounts 2023-24, p.9',
  measure: 'final_grant',
  source_url: 'https://cag.gov.in/example.pdf',
  snapshot_id: 3,
  page: 9,
  fetched_at: '2026-11-22T06:07:50Z',
  provisional: false,
  mismatch: null,
}

describe('parseView', () => {
  it('accepts the three views', () => {
    expect(parseView('live')).toBe('live')
    expect(parseView('official')).toBe('official')
    expect(parseView('combined')).toBe('combined')
  })
  it('falls back to combined', () => {
    expect(parseView(null)).toBe('combined')
    expect(parseView('LIVE')).toBe('combined')
    expect(parseView('')).toBe('combined')
  })
})

describe('searchWithView', () => {
  it('adds a non-default view and keeps other params', () => {
    expect(searchWithView('?tab=2', 'official')).toBe('?tab=2&view=official')
  })
  it('writes the default view too', () => {
    expect(searchWithView('', 'combined')).toBe('?view=combined')
    expect(searchWithView('?view=live&tab=2', 'combined')).toBe('?view=combined&tab=2')
  })
  it('replaces an existing view', () => {
    expect(searchWithView('?view=live', 'official')).toBe('?view=official')
  })
})

describe('sourceKind / badgeText', () => {
  it('no source or null source_type is no data', () => {
    expect(sourceKind(undefined)).toBe('none')
    expect(sourceKind({ ...base, source_type: null })).toBe('none')
    expect(badgeText(undefined)).toBe('No data')
  })
  it('a value without a recorded source is unsourced, not no data', () => {
    const seed = { ...base, source_type: null, label: 'Reference value from database/seeds.py' }
    expect(sourceKind(seed, 1200)).toBe('unsourced')
    expect(badgeText(seed, 0)).toBe('Unsourced')
    expect(sourceKind(seed, null)).toBe('none')
  })
  it('official and live', () => {
    expect(sourceKind(base)).toBe('official')
    expect(sourceKind({ ...base, source_type: 'live', provisional: true })).toBe('live')
  })
  it('a mismatch makes it flagged', () => {
    const s = { ...base, mismatch: { live: 801000, official: 6818616.88, diff_pct: -88.25 } }
    expect(sourceKind(s)).toBe('flagged')
    expect(badgeText(s)).toBe('Official ⚑')
  })
})

describe('measure labels', () => {
  it('names official measures honestly', () => {
    expect(measureLabel(base)).toBe('Final grant (original + supplementary)')
    expect(fieldHeading(base, 'Allocated')).toBe('Final grant')
    expect(fieldHeading({ ...base, measure: 'gross_expenditure' }, 'Utilized')).toBe('Gross expenditure')
  })
  it('keeps the fallback heading for live measures', () => {
    expect(fieldHeading({ ...base, measure: 'budget_estimate' }, 'Allocated')).toBe('Allocated')
    expect(fieldHeading(undefined, 'Allocated')).toBe('Allocated')
    expect(measureLabel({ ...base, measure: null })).toBeNull()
  })
})

describe('mismatchText', () => {
  it('shows both numbers and the difference', () => {
    const s = { ...base, mismatch: { live: 801000, official: 6818616.88, diff_pct: -88.25 } }
    expect(mismatchText(s)).toBe('Portal said ₹8,010 Cr, audited accounts say ₹68,186 Cr (−88.3%)')
  })
  it('omits the percentage when official is 0', () => {
    const s = { ...base, mismatch: { live: 50, official: 0, diff_pct: null } }
    expect(mismatchText(s)).toBe('Portal said ₹50 L, audited accounts say ₹0 L')
  })
  it('is null without a mismatch', () => {
    expect(mismatchText(base)).toBeNull()
  })
})

describe('pageRef', () => {
  it('formats a page', () => {
    expect(pageRef(base)).toBe('p.9')
    expect(pageRef({ ...base, page: null })).toBeNull()
  })
})
