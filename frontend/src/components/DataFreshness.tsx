import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { fetchSyncStatus } from '../lib/api'
import { Link } from 'react-router-dom'

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
      <div className="flex items-center gap-2 px-6 py-2 border-b" style={{ borderColor: '#1a2a3a', background: 'rgba(255,51,102,0.05)' }}>
        <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
        <span className="mono text-[9px] text-red">NO DATA YET — Trigger collectors from Sync Status page to fetch live data</span>
        <Link to="/sync" className="mono text-[8px] text-blue hover:underline ml-auto">→ GO TO SYNC</Link>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-4 px-6 py-2 border-b overflow-x-auto" style={{ borderColor: '#1a2a3a', background: 'rgba(13,21,32,0.5)' }}>
      <span className="mono text-[8px] text-dim tracking-widest flex-shrink-0">DATA FRESHNESS</span>
      {data.map(s => {
        const healthy   = s.is_healthy
        const neverRun  = !s.last_run
        const dotColor  = neverRun ? '#5a7a9a' : healthy ? '#00ff88' : '#ff3366'
        const timeLabel = neverRun
          ? 'Never fetched'
          : s.last_success
            ? formatDistanceToNow(parseISO(s.last_success), { addSuffix: true })
            : 'Never succeeded'

        return (
          <div key={s.collector_name} className="flex items-center gap-1.5 flex-shrink-0">
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: dotColor }} />
            <span className="mono text-[8px]" style={{ color: dotColor }}>
              {COLLECTOR_LABELS[s.collector_name] ?? s.collector_name.replace('_collector', '').toUpperCase()}
            </span>
            <span className="mono text-[8px] text-dim">{timeLabel}</span>
          </div>
        )
      })}
      <Link to="/sync" className="mono text-[8px] text-dim hover:text-blue ml-auto flex-shrink-0 transition-colors">
        → SYNC STATUS
      </Link>
    </div>
  )
}
