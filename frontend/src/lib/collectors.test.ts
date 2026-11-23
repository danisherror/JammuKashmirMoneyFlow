import { describe, expect, it } from 'vitest'
import type { SyncStatusItem } from './api'
import { fetchedText, pickCollectors } from './collectors'

const item = (over: Partial<SyncStatusItem> = {}): SyncStatusItem => ({
  collector_name: 'tenders_collector',
  label: 'Tenders',
  source_name: 'jktenders.gov.in',
  source_url: 'https://jktenders.gov.in/nicgep/app',
  status: 'success',
  last_run: '2026-11-22T06:00:00+05:30',
  last_success: '2026-11-22T06:01:00+05:30',
  records_last_run: 12,
  next_run: null,
  is_healthy: true,
  error_message: null,
  ...over,
})

describe('fetchedText', () => {
  it('gives the last successful fetch date', () => {
    expect(fetchedText(item())).toBe('fetched 22 Nov 2026')
  })
  it('says when a collector never succeeded or never ran', () => {
    expect(fetchedText(item({ status: 'no_source', last_success: null }))).toBe('never fetched successfully')
    expect(fetchedText(item({ status: 'never_run', last_run: null, last_success: null }))).toBe('never run')
  })
})

describe('pickCollectors', () => {
  it('keeps the requested order and skips unknown names', () => {
    const a = item({ collector_name: 'jjm_collector' })
    const b = item({ collector_name: 'mgnrega_collector' })
    expect(pickCollectors([a, b], ['mgnrega_collector', 'nope', 'jjm_collector'])).toEqual([b, a])
    expect(pickCollectors(undefined, ['jjm_collector'])).toEqual([])
  })
})
