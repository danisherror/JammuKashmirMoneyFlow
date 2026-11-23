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
