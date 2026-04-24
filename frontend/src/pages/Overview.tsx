import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { useAppStore } from '../store'
import {
  fetchBudgetOverview, fetchDepartments,
  fetchGapAnalysis, fetchLowUtilAlerts, fetchSchemes
} from '../lib/api'
import { fmtLakhs, fmtPct, utilColor } from '../lib/utils'
import KpiCard from '../components/KpiCard'
import UtilBar from '../components/UtilBar'
import PageHeader from '../components/PageHeader'
import LoadingGrid from '../components/LoadingGrid'
import ErrorBox from '../components/ErrorBox'
import BudgetSankey from '../components/BudgetSankey'

const COLORS = ['#00ff88', '#00aaff', '#ffd700', '#ff6432', '#ff3366', '#aa44ff']

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="panel mono text-[10px] p-3" style={{ minWidth: 140 }}>
      <div className="text-dim mb-1 tracking-widest text-[8px]">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color }}>{p.name}: {fmtLakhs(p.value)}</div>
      ))}
    </div>
  )
}

export default function Overview() {
  const { financialYear } = useAppStore()

  const { data: overview, isLoading: ovLoading, isError: ovError } =
    useQuery({ queryKey: ['budget-overview', financialYear], queryFn: () => fetchBudgetOverview(financialYear) })

  const { data: departments, isLoading: deptLoading } =
    useQuery({ queryKey: ['departments', financialYear], queryFn: () => fetchDepartments(financialYear) })

  const { data: gaps } =
    useQuery({ queryKey: ['gap-analysis', financialYear], queryFn: () => fetchGapAnalysis(financialYear) })

  const { data: alerts } =
    useQuery({ queryKey: ['low-util-alerts', financialYear], queryFn: () => fetchLowUtilAlerts(financialYear) })

  const { data: schemes } =
    useQuery({ queryKey: ['schemes', financialYear], queryFn: () => fetchSchemes(financialYear) })

  const top10Depts = departments?.slice(0, 10) ?? []
  const criticalCount  = alerts?.filter(a => a.severity === 'critical').length ?? 0
  const warningCount   = alerts?.filter(a => a.severity === 'warning').length ?? 0

  const pieData = overview ? [
    { name: 'Capital', value: overview.total_capital_lakhs },
    { name: 'Revenue', value: overview.total_revenue_lakhs },
  ] : []

  return (
    <div className="p-0">
      <PageHeader
        title="J&K MONEY FLOW"
        subtitle={`PUBLIC FUND TRACKER — FY ${financialYear} — JAMMU & KASHMIR UT`}
        right={
          <div className="flex items-center gap-2">
            <span className="badge badge-live">LIVE</span>
            {criticalCount > 0 && (
              <span className="badge" style={{ background: 'rgba(255,51,102,0.15)', color: '#ff3366', border: '1px solid rgba(255,51,102,0.3)' }}>
                ⚠ {criticalCount} CRITICAL
              </span>
            )}
          </div>
        }
      />

      <div className="p-6 space-y-6">

        {/* KPI Row */}
        {ovLoading ? <LoadingGrid count={4} /> : ovError ? <ErrorBox /> : overview && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard label="Total Budget" value={overview.total_budget_lakhs} format="lakhs" direction="neutral" />
            <KpiCard label="Capital Expenditure" value={overview.total_capital_lakhs} format="lakhs" direction="up"
              sub={`${fmtPct(overview.capital_pct)} of total`} />
            <KpiCard label="Revenue Expenditure" value={overview.total_revenue_lakhs} format="lakhs" direction="neutral"
              sub={`${fmtPct(overview.revenue_pct)} of total`} />
            <KpiCard label="Funded Departments" value={overview.total_departments} direction="neutral"
              sub={`FY ${financialYear}`} />
          </div>
        )}

        {/* Alert summary strip */}
        {(criticalCount > 0 || warningCount > 0) && (
          <div className="panel border-red-800/30 p-3 flex items-center gap-6">
            <div className="mono text-[9px] text-dim tracking-widest">FUND UTILIZATION ALERTS</div>
            {criticalCount > 0 && (
              <div className="mono text-[10px] text-red">
                🔴 {criticalCount} scheme-districts with &lt;20% utilization
              </div>
            )}
            {warningCount > 0 && (
              <div className="mono text-[10px] text-gold">
                🟡 {warningCount} scheme-districts with &lt;40% utilization
              </div>
            )}
          </div>
        )}

        {/* Budget Flow Sankey Diagram */}
        <div className="grid grid-cols-1 gap-4">
          {overview && departments && schemes ? (
            <BudgetSankey overview={overview} departments={departments} schemes={schemes} />
          ) : (
            <div className="panel xl:col-span-3 h-96 flex items-center justify-center mono text-[10px] text-dim">
              Loading Flow Diagram...
            </div>
          )}
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

          {/* Top 10 Departments by allocation */}
          <div className="panel xl:col-span-2">
            <div className="panel-title">TOP DEPARTMENTS BY ALLOCATION</div>
            {deptLoading ? (
              <div className="h-64 flex items-center justify-center mono text-[10px] text-dim">Loading...</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={top10Depts.map(d => ({
                  name: d.code,
                  Allocated: d.budget_estimate_lakhs,
                  Utilized: d.utilized_lakhs ?? 0,
                }))} barGap={2}>
                  <XAxis dataKey="name" tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }} />
                  <YAxis tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }}
                    tickFormatter={v => `₹${(v/100).toFixed(0)}Cr`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="Allocated" fill="rgba(0,170,255,0.3)"  stroke="#00aaff" strokeWidth={1} />
                  <Bar dataKey="Utilized"  fill="rgba(0,255,136,0.35)" stroke="#00ff88" strokeWidth={1} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Capital vs Revenue Pie */}
          <div className="panel">
            <div className="panel-title">BUDGET COMPOSITION</div>
            {overview ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="45%" innerRadius={55} outerRadius={85}
                    dataKey="value" stroke="none">
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i]} opacity={0.8} />
                    ))}
                  </Pie>
                  <Legend
                    formatter={(v) => <span style={{ fontFamily: 'Space Mono', fontSize: 9, color: '#c8d8e8' }}>{v}</span>}
                  />
                  <Tooltip
                    formatter={(v: number) => [fmtLakhs(v), '']}
                    contentStyle={{ background: '#0d1520', border: '1px solid #1a2a3a', fontFamily: 'Space Mono', fontSize: 10 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : <div className="h-64" />}
          </div>
        </div>

        {/* Gap Analysis Table */}
        {gaps && gaps.length > 0 && (
          <div className="panel">
            <div className="panel-title">FUND GAP ANALYSIS — CENTRAL RELEASE TO UTILIZATION</div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b" style={{ borderColor: '#1a2a3a' }}>
                    {['DEPARTMENT', 'STATE RECEIPT', 'CENTRAL RELEASE', 'UTILIZED', 'PARKED GAP', 'UTILIZATION', 'STATUS'].map(h => (
                      <th key={h} className="mono text-[8px] text-dim text-left pb-2 pr-4 tracking-widest">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {gaps.slice(0, 10).map(g => (
                    <tr key={g.department_id} className="border-b border-opacity-30 hover:bg-white/5 transition-colors"
                      style={{ borderColor: '#1a2a3a' }}>
                      <td className="py-2 pr-4">
                        <div className="mono text-[10px]">{g.department_name.split('(')[0].trim()}</div>
                        <div className="mono text-[8px] text-dim">{g.department_code}</div>
                      </td>
                      <td className="mono text-[10px] pr-4 text-blue" title="Total Allocated to Department">
                        {fmtLakhs(g.allocated_lakhs)}
                      </td>
                      <td className="mono text-[10px] pr-4 text-purple" title="Central Funds Released (via PFMS)">
                        {fmtLakhs(g.released_lakhs)}
                      </td>
                      <td className="mono text-[10px] pr-4 text-green" title="Actual Amount Utilized on Ground">
                        {fmtLakhs(g.utilized_lakhs)}
                      </td>
                      <td className="mono text-[10px] pr-4 text-red" title="Idle money parked (Central Release - Utilized)">
                        {fmtLakhs(g.gap_lakhs)}
                      </td>
                      <td className="pr-4" style={{ minWidth: 120 }}>
                        <UtilBar allocated={g.released_lakhs > g.allocated_lakhs ? g.released_lakhs : g.allocated_lakhs} utilized={g.utilized_lakhs} showLabels={false} />
                        <div className={`mono text-[9px] mt-0.5 ${utilColor(g.utilization_pct)}`}>
                          {fmtPct(g.utilization_pct)}
                        </div>
                      </td>
                      <td>
                        <span className={`mono text-[8px] px-2 py-0.5 rounded-sm ${
                          g.gap_flag === 'critical' ? 'text-red bg-red-900/20 border border-red-800/40' :
                          g.gap_flag === 'warning'  ? 'text-gold bg-yellow-900/20 border border-yellow-800/40' :
                          'text-green bg-green-900/20 border border-green-800/40'
                        }`}>
                          {g.gap_flag.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {gaps.length > 10 && (
              <div className="mt-3 flex justify-end">
                <a href="/departments" className="mono text-[9px] text-blue hover:opacity-80 transition-opacity">
                  View all {gaps.length} departments →
                </a>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
