import { useQuery, useMutation } from '@tanstack/react-query'
import { useAppStore } from '../store'
import { fetchLowUtilAlerts, LowUtilizationAlert } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'

function AlertRow({ a }: { a: LowUtilizationAlert }) {
  return (
    <div className="flex items-center gap-4 py-3 border-b hover:bg-white/5 transition-colors" style={{ borderColor: '#1a2a3a' }}>
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0`}
        style={{
          background: a.severity === 'critical' ? '#ff3366' : '#ffd700',
          boxShadow: a.severity === 'critical' ? '0 0 8px #ff3366' : '0 0 8px #ffd700',
        }}
      />
      <div className="flex-1 min-w-0">
        <div className="mono text-[10px] text-white">{a.scheme_name}</div>
        <div className="mono text-[8px] text-dim">{a.district_name} · {a.department_name.split('(')[0].trim()}</div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="mono text-[9px] text-blue">{fmtLakhs(a.funds_allocated_lakhs)} allocated</div>
        <div className="mono text-[9px] text-red">{fmtLakhs(a.funds_utilized_lakhs)} utilized</div>
      </div>
      <div className="flex-shrink-0 w-16 text-right">
        <span className={`mono text-[11px] font-bold ${a.severity === 'critical' ? 'text-red' : 'text-gold'}`}>
          {fmtPct(a.utilization_pct)}
        </span>
      </div>
      <div className="flex-shrink-0">
        <span
          className="mono text-[8px] px-2 py-1 border"
          style={
            a.severity === 'critical'
              ? { color: '#ff3366', borderColor: 'rgba(255,51,102,0.4)', background: 'rgba(255,51,102,0.1)' }
              : { color: '#ffd700', borderColor: 'rgba(255,215,0,0.4)', background: 'rgba(255,215,0,0.1)' }
          }
        >
          {a.severity.toUpperCase()}
        </span>
      </div>
    </div>
  )
}

export default function Alerts() {
  const { financialYear } = useAppStore()

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['low-util-alerts', financialYear],
    queryFn: () => fetchLowUtilAlerts(financialYear),
  })

  const critical = (data ?? []).filter(a => a.severity === 'critical')
  const warning  = (data ?? []).filter(a => a.severity === 'warning')

  return (
    <div>
      <PageHeader
        title="ALERTS"
        subtitle={`FUND UTILIZATION FLAGS — FY ${financialYear}`}
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
        {isLoading && (
          <div className="panel h-40 flex items-center justify-center mono text-[10px] text-dim animate-pulse">
            Loading alerts...
          </div>
        )}
        {isError && <ErrorBox />}

        {data && data.length === 0 && (
          <div className="panel p-8 text-center">
            <div className="text-green mono text-[10px] mb-1">✓ NO ACTIVE ALERTS</div>
            <div className="text-dim mono text-[9px]">All tracked schemes are above utilization thresholds.</div>
          </div>
        )}

        {critical.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(255,51,102,0.25)' }}>
            <div className="panel-title">
              🔴 CRITICAL — UTILIZATION BELOW 20%
              <span className="mono text-[9px] text-red ml-2">{critical.length} items</span>
            </div>
            {critical.map((a, i) => <AlertRow key={i} a={a} />)}
          </div>
        )}

        {warning.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(255,215,0,0.25)' }}>
            <div className="panel-title">
              🟡 WARNING — UTILIZATION BELOW 40%
              <span className="mono text-[9px] text-gold ml-2">{warning.length} items</span>
            </div>
            {warning.map((a, i) => <AlertRow key={i} a={a} />)}
          </div>
        )}

        <div className="panel p-4">
          <div className="mono text-[9px] text-dim leading-relaxed">
            💡{' '}
            <span className="text-white">How to read alerts:</span>{' '}
            Critical alerts (&lt;20%) mean money is sitting idle — likely a tender delay, contractor issue, or court stay.
            Warning alerts (&lt;40%) indicate slow absorption. In J&K, Q4 (Jan–Mar) sees rushed spending to meet
            targets — watch these to spot where panic spending happens vs genuine implementation.
          </div>
        </div>
      </div>
    </div>
  )
}
