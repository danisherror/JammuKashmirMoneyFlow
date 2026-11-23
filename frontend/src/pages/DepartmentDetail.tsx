import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts'
import { useAppStore } from '../store'
import { fetchDepartmentDetail } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, divisionLabel } from '../lib/utils'
import { fieldHeading } from '../lib/sources'
import UtilBar from '../components/UtilBar'
import SourceBadge from '../components/SourceBadge'
import OfficialChainPanel from '../components/OfficialChainPanel'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { ChevronLeft } from 'lucide-react'

const MONTH_NAMES = ['Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar']

export default function DepartmentDetail() {
  const { id } = useParams<{ id: string }>()
  const { financialYear, view } = useAppStore()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dept-detail', id, financialYear, view],
    queryFn: () => fetchDepartmentDetail(Number(id), financialYear, view),
    enabled: !!id,
  })

  const monthlyData = data?.monthly_expenditure?.map(m => ({
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
                { label: fieldHeading(data.sources.budget_estimate_lakhs, 'Budget estimate'), val: data.budget_estimate_lakhs, fmt: 'lakhs', dir: 'neutral', source: data.sources.budget_estimate_lakhs },
                { label: 'Revised estimate', val: data.revised_estimate_lakhs, fmt: 'lakhs', dir: 'neutral', source: data.sources.revised_estimate_lakhs },
                { label: fieldHeading(data.sources.utilized_lakhs, 'Utilized so far'), val: data.utilized_lakhs, fmt: 'lakhs', dir: data.utilization_pct && data.utilization_pct > 50 ? 'up' : 'down', source: data.sources.utilized_lakhs },
                { label: 'Utilization', val: data.utilization_pct, fmt: 'pct', dir: data.utilization_pct && data.utilization_pct > 50 ? 'up' : 'down', source: undefined },
              ].map(({ label, val, fmt, dir, source }) => {
                const display = fmt === 'lakhs' ? fmtLakhs(val) : fmtPct(val)
                const color = dir === 'up' ? '#00ff88' : dir === 'down' ? '#ff3366' : '#ffd700'
                return (
                  <div key={label} className="panel">
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color }} />
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="mono text-[8px] text-dim tracking-widest uppercase">{label}</div>
                      {source !== undefined && <SourceBadge source={source} />}
                    </div>
                    <div className="display text-2xl" style={{ color }}>{display}</div>
                    <div className="mono text-[8px] text-dim mt-1">{divisionLabel(data.division)}</div>
                  </div>
                )
              })}
            </div>

            {data.official_chain && (
              <OfficialChainPanel
                chain={data.official_chain}
                scope={`Grant${data.official_chain.grants.length > 1 ? 's' : ''} ${data.official_chain.grants.join(', ')}`}
              />
            )}

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
                <div className="flex items-center justify-between gap-2">
                  <div className="panel-title">MONTHLY EXPENDITURE TREND</div>
                  <SourceBadge source={data.sources.monthly_expenditure} />
                </div>
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
                  No monthly expenditure: {data.sources.monthly_expenditure?.label ?? `no figures for FY ${financialYear}`}.
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
