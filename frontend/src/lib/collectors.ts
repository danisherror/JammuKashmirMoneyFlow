/**
 * Provenance for figures written by the portal collectors (todo.md 1.3), read from
 * `GET /alerts/sync-status`: which portal a collector reads and when it last fetched data
 * successfully. Pure functions only, so they can be unit-tested without a DOM.
 *
 * This is per collector, not per row: every row a collector wrote shares the collector's source
 * and last successful fetch. Per-row snapshots come with todo.md 1.4.
 */
import { format, parseISO } from 'date-fns'
import type { SyncStatusItem } from './api'

/** The collectors that write `scheme_progress` rows (district and scheme-district figures). */
export const SCHEME_PROGRESS_COLLECTORS = [
  'mgnrega_collector',
  'jjm_collector',
  'pmay_collector',
  'pfms_collector',
] as const

/** "22 Nov 2026" */
export function fmtDay(iso: string): string {
  return format(parseISO(iso), 'd MMM yyyy')
}

/** "fetched 22 Nov 2026", or why there is no fetch date. */
export function fetchedText(item: SyncStatusItem): string {
  if (item.last_success) return `fetched ${fmtDay(item.last_success)}`
  if (item.status === 'never_run') return 'never run'
  return 'never fetched successfully'
}

/** Status rows for `names`, in the order given; names the API doesn't know are skipped. */
export function pickCollectors(items: SyncStatusItem[] | undefined, names: readonly string[]): SyncStatusItem[] {
  const byName = new Map((items ?? []).map(i => [i.collector_name, i]))
  return names.flatMap(n => byName.get(n) ?? [])
}

/** Which collectors write a scheme's district rows (PFMS adds central releases to each). */
export function collectorsForScheme(code: string | null | undefined): string[] {
  switch (code) {
    case 'MGNREGA':
      return ['mgnrega_collector', 'pfms_collector']
    case 'JJM':
      return ['jjm_collector', 'pfms_collector']
    case 'PMAY_G':
      return ['pmay_collector', 'pfms_collector']
    default:
      return ['pfms_collector']   // no collector reads this scheme's district figures yet
  }
}

/**
 * Why a panel backed by this collector is empty (todo.md 1.3), e.g.
 * "No data collected yet from jktenders.gov.in — last attempt failed: HTTP 403".
 * Once the collector has fetched data, an empty panel means the selection has no rows in it.
 */
export function emptyStateText(item: SyncStatusItem): string {
  const from = item.source_url ? item.source_name : item.label
  const reason = item.error_message?.trim() || 'no reason recorded'

  if (item.last_success) {
    const base = `No rows for this selection in the data fetched from ${from} on ${fmtDay(item.last_success)}`
    if (item.status === 'failed' || item.status === 'no_source') {
      return `${base}; the latest attempt failed: ${reason}`
    }
    return `${base}.`
  }

  const head = `No data collected yet from ${from}`
  switch (item.status) {
    case 'never_run':
      return `${head} — the collector has never run.`
    case 'running':
      return `${head} — a collection run is in progress.`
    case 'no_source':
      return `${head} — no usable source: ${reason}`
    case 'partial':
      return `${head} — the last attempt wrote no usable rows${item.error_message ? `: ${reason}` : '.'}`
    default:
      return `${head} — last attempt failed: ${reason}`
  }
}

/** True when none of these collectors has ever fetched data successfully. */
export function neverCollected(items: SyncStatusItem[]): boolean {
  return items.every(i => !i.last_success)
}
