import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts'
import { useAppStore } from '../store'
import { fetchDepartmentDetail } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, divisionLabel } from '../lib/utils'
import UtilBar from '../components/UtilBar'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { ChevronLeft } from 'lucide-react'

const MONTH_NAMES = ['Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar']

export default function DepartmentDetail() {
  const { id } = useParams<{ id: string }>()
  const { financialYear } = useAppStore()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dept-detail', id, financialYear],
    queryFn: () => fetchDepartmentDetail(Number(id), financialYear),
    enabled: !!id,
  })

  const monthlyData = data?.monthly_expenditure?.map((m: any) => ({
    month: MONTH_NAMES[m.month - 1] ?? `M${m.month}`,
    amount: m.amount_lakhs,
  })) ?? []

  return (
    <div>
      <PageHeader
        title={data?.name?.split('(')[0].trim() ?? 'DEPARTMENT'}
        subtitle={`${data?.code ?? ''} — FY ${financialYear}`}
        right={
          <Link to="/departments" className="flex items-center gap-1 mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
            style={{ borderColor: '#1a2a3a' }}>
            <ChevronLeft size={12} /> BACK
          </Link>
        }
      />

      <div className="p-6 space-y-6">
        {isLoading && (
          <div className="panel h-40 flex items-center justify-center mono text-[10px] text-dim animate-pulse">
            Loading department data...
          </div>
        )}
        {isError && <ErrorBox />}
        {data && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'BUDGET ESTIMATE', val: data.budget_estimate_lakhs, fmt: 'lakhs', dir: 'neutral' },
                { label: 'REVISED ESTIMATE', val: data.revised_estimate_lakhs, fmt: 'lakhs', dir: 'neutral' },
                { label: 'UTILIZED SO FAR', val: data.utilized_lakhs, fmt: 'lakhs', dir: data.utilization_pct && data.utilization_pct > 50 ? 'up' : 'down' },
                { label: 'UTILIZATION', val: data.utilization_pct, fmt: 'pct', dir: data.utilization_pct && data.utilization_pct > 50 ? 'up' : 'down' },
              ].map(({ label, val, fmt, dir }) => {
                const display = fmt === 'lakhs' ? fmtLakhs(val) : fmtPct(val)
                const color = dir === 'up' ? '#00ff88' : dir === 'down' ? '#ff3366' : '#ffd700'
                return (
                  <div key={label} className="panel">
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color }} />
                    <div className="mono text-[8px] text-dim tracking-widest mb-2">{label}</div>
                    <div className="display text-2xl" style={{ color }}>{display}</div>
                    <div className="mono text-[8px] text-dim mt-1">{divisionLabel(data.division)}</div>
                  </div>
                )
              })}
            </div>

            {/* Utilization bar */}
            <div className="panel">
              <div className="panel-title">FUND UTILIZATION BREAKDOWN</div>
              <UtilBar
                allocated={data.budget_estimate_lakhs}
                utilized={data.utilized_lakhs}
              />
              <div className="flex justify-between mt-2 mono text-[9px] text-dim">
                <span>₹0</span>
                <span>{fmtLakhs(data.budget_estimate_lakhs)} total</span>
              </div>
            </div>

            {/* Monthly chart */}
            {monthlyData.length > 0 && (
              <div className="panel">
                <div className="panel-title">MONTHLY EXPENDITURE TREND</div>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={monthlyData}>
                    <defs>
                      <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00ff88" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="month" tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }} />
                    <YAxis tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }}
                      tickFormatter={v => `₹${(v/100).toFixed(0)}Cr`} />
                    <Tooltip
                      formatter={(v: number) => [fmtLakhs(v), 'Expenditure']}
                      contentStyle={{ background: '#0d1520', border: '1px solid #1a2a3a', fontFamily: 'Space Mono', fontSize: 10 }}
                    />
                    <Area type="monotone" dataKey="amount" stroke="#00ff88" strokeWidth={2}
                      fill="url(#areaGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {monthlyData.length === 0 && (
              <div className="panel p-6 text-center">
                <div className="mono text-[10px] text-dim">
                  Monthly expenditure data populates after CGA runs (monthly, 26th of each month).
                  Trigger it manually from the{' '}
                  <a href="/sync" className="text-blue hover:underline">Sync Status page</a>.
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
