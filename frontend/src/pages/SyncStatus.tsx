import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { fetchSyncStatus, triggerCollector } from '../lib/api'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'

interface CollectorDef {
  name:        string
  label:       string
  trigger_key: string | null
  source:      string
  source_url:  string
  schedule:    string
  phase:       number
}

const COLLECTORS: CollectorDef[] = [
  {
    name:        'mgnrega_collector',
    label:       'MGNREGA',
    trigger_key: 'mgnrega',
    source:      'nreganarayan.nic.in',
    source_url:  'https://nreganarayan.nic.in/netnrega/home.aspx',
    schedule:    'Weekly (Sunday 6:00 AM)',
    phase:       1,
  },
  {
    name:        'jjm_collector',
    label:       'JAL JEEVAN MISSION',
    trigger_key: 'jjm',
    source:      'ejalshakti.gov.in',
    source_url:  'https://ejalshakti.gov.in/jjmreport/JJMIndia.aspx',
    schedule:    'Weekly (Sunday 6:00 AM)',
    phase:       1,
  },
  {
    name:        'pmay_collector',
    label:       'PM AWAS YOJANA',
    trigger_key: 'pmay',
    source:      'pmayg.nic.in',
    source_url:  'https://pmayg.nic.in',
    schedule:    'Weekly (Sunday 6:00 AM)',
    phase:       1,
  },
  {
    name:        'dbt_collector',
    label:       'DBT TRANSFERS',
    trigger_key: 'dbt',
    source:      'dbtbharat.gov.in',
    source_url:  'https://dbtbharat.gov.in',
    schedule:    'Weekly (Sunday 6:00 AM)',
    phase:       1,
  },
  {
    name:        'tender_collector',
    label:       'TENDERS',
    trigger_key: 'tenders',
    source:      'jktenders.gov.in',
    source_url:  'https://jktenders.gov.in',
    schedule:    'Weekly (Sunday 6:00 AM)',
    phase:       1,
  },
  {
    name:        'cag_collector',
    label:       'CAG AUDIT REPORTS',
    trigger_key: null,
    source:      'cag.gov.in',
    source_url:  'https://cag.gov.in/en/audit-report?tags=Jammu+%26+Kashmir',
    schedule:    'Monthly (Phase 2)',
    phase:       2,
  },
]

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }) }
  catch { return iso }
}

export default function SyncStatus() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['sync-status'],
    queryFn:  fetchSyncStatus,
    refetchInterval: 30_000,
  })

  const trigger = useMutation({
    mutationFn: triggerCollector,
    onSuccess: (_, name) => {
      toast.success(`${name} triggered — check logs in ~30s`)
      setTimeout(() => refetch(), 5000)
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail ?? 'Trigger failed')
    },
  })

  const byName = Object.fromEntries((data ?? []).map(s => [s.collector_name, s]))

  return (
    <div>
      <PageHeader
        title="SYNC STATUS"
        subtitle="LIVE DATA COLLECTOR HEALTH — AUTO-POLLS EVERY 30S"
        right={
          <button
            onClick={() => refetch()}
            className="mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
            style={{ borderColor: '#1a2a3a' }}
          >
            ⟳ REFRESH
          </button>
        }
      />

      <div className="p-6 space-y-6">

        {/* Important notice */}
        <div className="panel p-4" style={{ borderColor: 'rgba(0,170,255,0.3)' }}>
          <div className="mono text-[9px] text-blue leading-relaxed">
            ℹ️ <span className="text-white">No fallback / hardcoded data.</span>{' '}
            If a collector fails, the dashboard shows the last successful snapshot
            (clearly labelled with its date) or nothing at all.
            An empty chart means the data was not yet fetched — not that it's zero.
          </div>
        </div>

        {isError && <ErrorBox message="Could not reach /alerts/sync-status. Is the API running?" />}

        {/* Phase 1 collectors */}
        <div>
          <div className="mono text-[8px] text-dim tracking-widest mb-3 flex items-center gap-2">
            PHASE 1 — ACTIVE COLLECTORS
            <div style={{ flex: 1, height: 1, background: '#1a2a3a' }} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {COLLECTORS.filter(c => c.phase === 1).map(col => {
              const s        = byName[col.name]
              const healthy  = s?.is_healthy ?? false
              const status   = s?.status ?? 'NEVER RUN'
              const dotColor = healthy ? '#00ff88' : s ? '#ff3366' : '#5a7a9a'
              const borderColor = healthy
                ? 'rgba(0,255,136,0.25)'
                : s ? 'rgba(255,51,102,0.25)' : '#1a2a3a'

              return (
                <div key={col.name} className="panel space-y-4" style={{ borderColor }}>
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: dotColor }} />

                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="mono text-[11px] font-bold text-white">{col.label}</div>
                      <a
                        href={col.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mono text-[8px] text-blue hover:underline"
                      >
                        {col.source} ↗
                      </a>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}` }}
                      />
                      <span className="mono text-[8px]" style={{ color: dotColor }}>
                        {status.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Stats grid */}
                  <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                    {[
                      { label: 'SCHEDULE',       val: col.schedule },
                      { label: 'LAST RUN',        val: timeAgo(s?.last_run ?? null) },
                      { label: 'LAST SUCCESS',    val: timeAgo(s?.last_success ?? null) },
                      { label: 'RECORDS (LAST)',  val: s ? String(s.records_last_run) : '—' },
                    ].map(({ label, val }) => (
                      <div key={label}>
                        <div className="mono text-[7px] text-dim tracking-widest mb-0.5">{label}</div>
                        <div className="mono text-[9px] text-white">{val}</div>
                      </div>
                    ))}
                  </div>

                  {/* Error message if failed */}
                  {s && !s.is_healthy && (
                    <div
                      className="mono text-[8px] p-2 leading-relaxed"
                      style={{ background: 'rgba(255,51,102,0.08)', border: '1px solid rgba(255,51,102,0.2)', color: '#ff8888' }}
                    >
                      <div className="text-red mb-1">LAST ERROR:</div>
                      {/* error_message comes via sync log — show truncated */}
                      Check docker logs for details. Common causes: portal maintenance window,
                      changed HTML structure, network timeout.
                    </div>
                  )}

                  {/* Trigger button */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => trigger.mutate(col.trigger_key!)}
                      disabled={trigger.isPending}
                      className="mono text-[8px] px-3 py-1.5 border tracking-widest transition-all hover:border-green-600/50 hover:text-green hover:bg-green-900/20 text-dim disabled:opacity-40"
                      style={{ borderColor: '#1a2a3a' }}
                    >
                      {trigger.isPending && trigger.variables === col.trigger_key
                        ? '⟳ RUNNING...'
                        : '▶ TRIGGER NOW'
                      }
                    </button>
                    <a
                      href={col.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mono text-[8px] px-3 py-1.5 border tracking-widest text-dim hover:text-blue hover:border-blue-800/50 transition-all"
                      style={{ borderColor: '#1a2a3a' }}
                    >
                      VERIFY ON SOURCE ↗
                    </a>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Phase 2 collectors — coming soon */}
        <div>
          <div className="mono text-[8px] text-dim tracking-widest mb-3 flex items-center gap-2">
            PHASE 2 — NOT YET BUILT
            <div style={{ flex: 1, height: 1, background: '#1a2a3a' }} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {COLLECTORS.filter(c => c.phase === 2).map(col => (
              <div key={col.name} className="panel opacity-50">
                <div className="mono text-[9px] font-bold text-dim mb-1">{col.label}</div>
                <a href={col.source_url} target="_blank" rel="noopener noreferrer"
                  className="mono text-[7px] text-blue hover:underline block mb-2">{col.source} ↗</a>
                <div className="mono text-[7px] text-dim">{col.schedule}</div>
              </div>
            ))}
          </div>
        </div>

        {/* How it works */}
        <div className="panel p-4 space-y-2">
          <div className="mono text-[8px] text-white tracking-widest">HOW DATA FLOWS</div>
          <div className="mono text-[9px] text-dim leading-loose">
            <span className="text-white">Sunday 6:00 AM IST</span> → Scheduler fires all collectors simultaneously<br />
            <span className="text-white">Collector</span> → HTTP/Playwright to govt portal → parse HTML/JSON → validate<br />
            <span className="text-white">On success</span> → write to <code className="text-blue">scheme_progress</code> table → gap_calculator updates all %s<br />
            <span className="text-white">On failure</span> → write FAILED to <code className="text-blue">data_sync_log</code> → dashboard shows previous snapshot with its date<br />
            <span className="text-white">You</span> → see "Updated 6 hours ago" on each data card, not silently stale data
          </div>
        </div>

      </div>
    </div>
  )
}
