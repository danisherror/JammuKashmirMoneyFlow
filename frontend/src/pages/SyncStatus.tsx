import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { fetchSyncStatus, triggerCollector } from '../lib/api'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { formatDistanceToNow } from 'date-fns'

export default function SyncStatus() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['sync-status'],
    queryFn: fetchSyncStatus,
    refetchInterval: 30000,   // poll every 30s
  })

  const trigger = useMutation({
    mutationFn: triggerCollector,
    onSuccess: (_, name) => {
      toast.success(`${name} collector triggered`)
      setTimeout(() => refetch(), 3000)
    },
    onError: () => toast.error('Failed to trigger collector'),
  })

  const KNOWN_COLLECTORS = [
    { name: 'mgnrega_collector', label: 'MGNREGA', trigger_key: 'mgnrega', source: 'nreganarayan.nic.in', schedule: 'Daily 6AM IST' },
    { name: 'jjm_collector',     label: 'JAL JEEVAN MISSION', trigger_key: 'jjm', source: 'ejalshakti.gov.in', schedule: 'Daily 6AM IST' },
    // Future collectors listed but not yet built
    { name: 'pmay_collector',    label: 'PM AWAS YOJANA', trigger_key: null, source: 'pmayg.nic.in', schedule: 'Weekly (Phase 2)' },
    { name: 'dbt_collector',     label: 'DBT TRACKER', trigger_key: null, source: 'dbtbharat.gov.in', schedule: 'Daily (Phase 2)' },
    { name: 'tender_collector',  label: 'TENDERS', trigger_key: null, source: 'jktenders.gov.in', schedule: 'Daily (Phase 2)' },
    { name: 'cag_collector',     label: 'CAG REPORTS', trigger_key: null, source: 'cag.gov.in', schedule: 'Monthly (Phase 2)' },
  ]

  const statusByName = Object.fromEntries((data ?? []).map(s => [s.collector_name, s]))

  return (
    <div>
      <PageHeader
        title="SYNC STATUS"
        subtitle="DATA COLLECTOR HEALTH — AUTO-UPDATES EVERY 30S"
        right={
          <button onClick={() => refetch()}
            className="mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
            style={{ borderColor: '#1a2a3a' }}>
            ⟳ REFRESH
          </button>
        }
      />

      <div className="p-6 space-y-4">
        {isError && <ErrorBox />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {KNOWN_COLLECTORS.map(col => {
            const status = statusByName[col.name]
            const isBuilt = col.trigger_key !== null
            const isHealthy = status?.is_healthy ?? false
            const borderColor = !isBuilt ? '#1a2a3a' : isHealthy ? 'rgba(0,255,136,0.3)' : 'rgba(255,51,102,0.3)'
            const dotColor   = !isBuilt ? '#1a2a3a' : isHealthy ? '#00ff88' : '#ff3366'
            const statusText = !isBuilt ? 'PHASE 2' : status ? status.status.toUpperCase() : 'NEVER RUN'

            return (
              <div key={col.name} className="panel" style={{ borderColor }}>
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: dotColor }} />

                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="mono text-[11px] font-bold text-white">{col.label}</div>
                    <div className="mono text-[8px] text-dim mt-0.5">{col.source}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}` }} />
                    <span className="mono text-[8px]" style={{ color: dotColor }}>{statusText}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3 mono text-[8px]">
                  <div>
                    <div className="text-dim mb-0.5">SCHEDULE</div>
                    <div className="text-white">{col.schedule}</div>
                  </div>
                  <div>
                    <div className="text-dim mb-0.5">LAST RUN</div>
                    <div className="text-white">
                      {status?.last_run
                        ? formatDistanceToNow(new Date(status.last_run), { addSuffix: true })
                        : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-dim mb-0.5">RECORDS (LAST)</div>
                    <div className="text-white">{status?.records_last_run ?? '—'}</div>
                  </div>
                  <div>
                    <div className="text-dim mb-0.5">LAST SUCCESS</div>
                    <div className="text-white">
                      {status?.last_success
                        ? formatDistanceToNow(new Date(status.last_success), { addSuffix: true })
                        : '—'}
                    </div>
                  </div>
                </div>

                {col.trigger_key && (
                  <button
                    onClick={() => trigger.mutate(col.trigger_key!)}
                    disabled={trigger.isPending}
                    className="mono text-[8px] px-3 py-1.5 border tracking-widest transition-colors hover:bg-green-900/20 hover:border-green-800/50 hover:text-green text-dim"
                    style={{ borderColor: '#1a2a3a' }}
                  >
                    {trigger.isPending ? '⟳ RUNNING...' : '▶ TRIGGER NOW'}
                  </button>
                )}
              </div>
            )
          })}
        </div>

        <div className="panel p-4 mono text-[9px] text-dim leading-relaxed">
          <div className="text-white mb-1 tracking-widest text-[8px]">HOW AUTO-UPDATES WORK</div>
          All data collectors run automatically via APScheduler inside the FastAPI backend.
          MGNREGA and JJM data fetches at 6:00 AM IST daily from official government portals.
          If the live portal is unavailable (common during maintenance windows),
          the system uses the last known good data. You can also manually trigger any collector using the button above.
        </div>
      </div>
    </div>
  )
}
