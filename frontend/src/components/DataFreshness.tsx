import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { fetchSyncStatus } from '../lib/api'
import { Link } from 'react-router-dom'
import clsx from 'clsx'

const COLLECTOR_LABELS: Record<string, string> = {
  'mgnrega_collector': 'MGNREGA',
  'jjm_collector': 'JJM',
  'pmay_collector': 'PMAY-G',
  'dbt_collector': 'DBT',
  'pfms_collector': 'PFMS',
  'tenders_collector': 'TENDERS',
  'cga_collector': 'CGA (EXP)',
  'cag_collector': 'CAG AUDITS',
}

/**
 * Shows a strip of data freshness badges — one per active collector.
 * If data is stale or never fetched, it shows clearly so users
 * know they're not looking at live numbers.
 */
export default function DataFreshness() {
  const { data } = useQuery({
    queryKey: ['sync-status'],
    queryFn:  fetchSyncStatus,
    refetchInterval: 60_000,
  })

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-between px-6 py-3 border-b border-rose-500/20 bg-rose-500/5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
          </span>
          <span className="text-[11px] font-medium text-rose-400 tracking-wide">NO DATA YET — Trigger collectors from Sync Status page to fetch live data</span>
        </div>
        <Link to="/sync" className="text-[10px] font-bold text-rose-400 hover:text-rose-300 transition-colors uppercase tracking-widest px-3 py-1 rounded-md bg-rose-500/10 hover:bg-rose-500/20">
          Sync Now →
        </Link>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-6 px-6 py-3 border-b border-slate-700/50 bg-slate-800/20 backdrop-blur-md overflow-x-auto overflow-y-hidden">
      <span className="text-[10px] font-bold text-slate-400 tracking-widest flex-shrink-0 uppercase">Data Freshness</span>
      {data.map(s => {
        const healthy   = s.is_healthy
        const neverRun  = !s.last_run
        const warn      = s.status === 'partial' || s.status === 'no_source'
        const dotColor  = neverRun ? 'bg-slate-400' : healthy ? 'bg-emerald-400' : warn ? 'bg-amber-400' : 'bg-rose-400'
        const textColor = neverRun ? 'text-slate-400' : healthy ? 'text-emerald-400' : warn ? 'text-amber-400' : 'text-rose-400'
        const timeLabel = neverRun
          ? 'Never fetched'
          : s.status === 'no_source'
            ? 'No source'
            : s.last_success
            ? formatDistanceToNow(parseISO(s.last_success), { addSuffix: true })
            : 'Never succeeded'

        return (
          <div key={s.collector_name} className="flex items-center gap-2 flex-shrink-0 bg-slate-800/40 px-3 py-1.5 rounded-full border border-slate-700/50">
            <div className={clsx("w-2 h-2 rounded-full", dotColor, healthy && "shadow-[0_0_8px_rgba(52,211,153,0.8)]")} />
            <span className={clsx("text-[10px] font-bold tracking-wide", textColor)}>
              {COLLECTOR_LABELS[s.collector_name] ?? s.collector_name.replace('_collector', '').toUpperCase()}
            </span>
            <span className="text-[10px] font-medium text-slate-500 ml-1">{timeLabel}</span>
          </div>
        )
      })}
      <Link to="/sync" className="text-[10px] font-bold text-slate-400 hover:text-blue-400 ml-auto flex-shrink-0 transition-colors tracking-widest uppercase flex items-center gap-1">
        Sync Status <span className="text-blue-500">→</span>
      </Link>
    </div>
  )
}
