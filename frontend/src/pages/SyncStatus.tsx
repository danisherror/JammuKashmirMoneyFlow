import { useQuery, useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { fetchSyncStatus, triggerCollector } from '../lib/api'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'

/** Trigger route key: the collector name without its `_collector` suffix (alerts.COLLECTOR_MAP). */
const triggerKey = (collectorName: string) => collectorName.replace(/_collector$/, '')

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  try { return formatDistanceToNow(parseISO(iso), { addSuffix: true }) }
  catch { return iso }
}

export default function SyncStatus() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['sync-status'],
    queryFn: fetchSyncStatus,
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

        {/* Every scheduled collector, with its source, as reported by the API */}
        <div>
          <div className="mono text-[8px] text-dim tracking-widest mb-3 flex items-center gap-2">
            COLLECTORS
            <div style={{ flex: 1, height: 1, background: '#1a2a3a' }} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(data ?? []).map(s => {
              const key = triggerKey(s.collector_name)
              const neverRun = s.status === 'never_run'
              const healthy = s.is_healthy
              const status = s.status.replace('_', ' ')
              // partial = finished but wrote no rows / skipped some; no_source = nothing honest to fetch
              const warn = s.status === 'partial' || s.status === 'no_source'
              const dotColor = healthy ? '#00ff88' : warn ? '#ffb020' : neverRun ? '#5a7a9a' : '#ff3366'
              const borderColor = healthy
                ? 'rgba(0,255,136,0.25)'
                : warn ? 'rgba(255,176,32,0.25)' : neverRun ? '#1a2a3a' : 'rgba(255,51,102,0.25)'

              return (
                <div key={s.collector_name} className="panel space-y-4" style={{ borderColor }}>
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: dotColor }} />

                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="mono text-[11px] font-bold text-white">{s.label.toUpperCase()}</div>
                      {s.source_url ? (
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mono text-[8px] text-blue hover:underline"
                        >
                          {s.source_name} ↗
                        </a>
                      ) : (
                        <span className="mono text-[8px] text-amber-300">{s.source_name}</span>
                      )}
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
                      { label: 'LAST RUN', val: timeAgo(s.last_run) },
                      { label: 'LAST SUCCESS', val: timeAgo(s.last_success) },
                      { label: 'NEXT RUN', val: s.next_run ? timeAgo(s.next_run) : 'Not scheduled' },
                      { label: 'RECORDS (LAST)', val: neverRun ? '—' : String(s.records_last_run) },
                    ].map(({ label, val }) => (
                      <div key={label}>
                        <div className="mono text-[7px] text-dim tracking-widest mb-0.5">{label}</div>
                        <div className="mono text-[9px] text-white">{val}</div>
                      </div>
                    ))}
                  </div>

                  {/* Error message if failed */}
                  {!neverRun && !s.is_healthy && (
                    <div
                      className="mono text-[8px] p-2 leading-relaxed"
                      style={warn
                        ? { background: 'rgba(255,176,32,0.08)', border: '1px solid rgba(255,176,32,0.2)', color: '#ffcc77' }
                        : { background: 'rgba(255,51,102,0.08)', border: '1px solid rgba(255,51,102,0.2)', color: '#ff8888' }}
                    >
                      <div className="mb-1" style={{ color: dotColor }}>
                        {s.status === 'no_source' ? 'NO SOURCE:' : s.status === 'partial' ? 'PARTIAL RUN:' : 'LAST ERROR:'}
                      </div>
                      {s.error_message ? s.error_message : (
                        'Check docker logs for details. Common causes: portal maintenance window, ' +
                        'changed HTML structure, network timeout.'
                      )}
                    </div>
                  )}

                  {/* Trigger button */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => trigger.mutate(key)}
                      disabled={trigger.isPending}
                      className="mono text-[8px] px-3 py-1.5 border tracking-widest transition-all hover:border-green-600/50 hover:text-green hover:bg-green-900/20 text-dim disabled:opacity-40"
                      style={{ borderColor: '#1a2a3a' }}
                    >
                      {trigger.isPending && trigger.variables === key
                        ? '⟳ RUNNING...'
                        : '▶ TRIGGER NOW'
                      }
                    </button>
                    {s.source_url && (
                      <a
                        href={s.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mono text-[8px] px-3 py-1.5 border tracking-widest text-dim hover:text-blue hover:border-blue-800/50 transition-all"
                        style={{ borderColor: '#1a2a3a' }}
                      >
                        VERIFY ON SOURCE ↗
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>



        {/* How it works */}
        <div className="panel p-4 space-y-2">
          <div className="mono text-[8px] text-white tracking-widest">HOW DATA FLOWS</div>
          <div className="mono text-[9px] text-dim leading-loose">
            <span className="text-white">Sunday 6:00 AM IST</span> → Scheduler runs every collector, one after another (CGA also on the 26th of each month)<br />
            <span className="text-white">Collector</span> → HTTP/Playwright to govt portal → parse HTML/JSON → validate<br />
            <span className="text-white">On success</span> → write to <code className="text-blue">scheme_progress</code> table → gap_calculator updates all %s<br />
            <span className="text-white">On failure</span> → write FAILED to <code className="text-blue">data_sync_log</code> → dashboard shows previous snapshot with its date<br />
            <span className="text-white">You</span> → see "Source: &lt;portal&gt; · fetched &lt;date&gt;" on each panel, not silently stale data
          </div>
        </div>

      </div>
    </div>
  )
}
