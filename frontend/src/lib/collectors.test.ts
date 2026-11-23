import { describe, expect, it } from 'vitest'
import type { SyncStatusItem } from './api'
import { collectorsForScheme, emptyStateText, fetchedText, neverCollected, pickCollectors } from './collectors'

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

describe('emptyStateText', () => {
  it('quotes the failure reason when nothing was ever collected', () => {
    expect(emptyStateText(item({ status: 'failed', last_success: null, error_message: 'HTTP 404' })))
      .toBe('No data collected yet from jktenders.gov.in — last attempt failed: HTTP 404')
    expect(emptyStateText(item({ status: 'failed', last_success: null, error_message: null })))
      .toBe('No data collected yet from jktenders.gov.in — last attempt failed: no reason recorded')
  })
  it('names the missing source', () => {
    expect(emptyStateText(item({ status: 'no_source', last_success: null, error_message: 'CAPTCHA' })))
      .toBe('No data collected yet from jktenders.gov.in — no usable source: CAPTCHA')
    // Without a source page, the collector's own name stands in for the portal.
    expect(emptyStateText(item({
      label: 'Monthly expenditure (CGA)', source_name: 'no published monthly source found yet', source_url: null,
      status: 'no_source', last_success: null, error_message: 'not found',
    }))).toBe('No data collected yet from Monthly expenditure (CGA) — no usable source: not found')
  })
  it('covers never-run, running and partial runs', () => {
    expect(emptyStateText(item({ status: 'never_run', last_run: null, last_success: null })))
      .toBe('No data collected yet from jktenders.gov.in — the collector has never run.')
    expect(emptyStateText(item({ status: 'running', last_success: null })))
      .toBe('No data collected yet from jktenders.gov.in — a collection run is in progress.')
    expect(emptyStateText(item({ status: 'partial', last_success: null })))
      .toBe('No data collected yet from jktenders.gov.in — the last attempt wrote no usable rows.')
  })
  it('does not say "never collected" once data was fetched', () => {
    expect(emptyStateText(item()))
      .toBe('No rows for this selection in the data fetched from jktenders.gov.in on 22 Nov 2026.')
    expect(emptyStateText(item({ status: 'failed', error_message: 'timeout' })))
      .toBe('No rows for this selection in the data fetched from jktenders.gov.in on 22 Nov 2026; the latest attempt failed: timeout')
  })
})

describe('neverCollected', () => {
  it('is true only when no collector ever succeeded', () => {
    expect(neverCollected([item({ last_success: null }), item({ last_success: null })])).toBe(true)
    expect(neverCollected([item({ last_success: null }), item()])).toBe(false)
  })
})

describe('collectorsForScheme', () => {
  it('maps scheme codes to the collectors that write their rows', () => {
    expect(collectorsForScheme('JJM')).toEqual(['jjm_collector', 'pfms_collector'])
    expect(collectorsForScheme('PMAY_U')).toEqual(['pfms_collector'])
  })
})
