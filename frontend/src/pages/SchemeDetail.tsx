import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { useAppStore } from '../store'
import { fetchSchemeDetail, fetchSchemeHistory } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, utilColorVar, schemeBadge, schemeTypeLabel } from '../lib/utils'
import UtilBar from '../components/UtilBar'
import SourceBadge from '../components/SourceBadge'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import MapWidget from '../components/MapWidget'
import VelocityChart from '../components/VelocityChart'
import { ChevronLeft, ExternalLink } from 'lucide-react'

export default function SchemeDetail() {
  const { id } = useParams<{ id: string }>()
  const { financialYear, view } = useAppStore()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['scheme-detail', id, financialYear, view],
    queryFn: () => fetchSchemeDetail(Number(id), financialYear, view),
    enabled: !!id,
  })

  const { data: velocity } = useQuery({
    queryKey: ['scheme-velocity', id, financialYear, view],
    queryFn: () => fetchSchemeHistory(Number(id), financialYear, view),
    enabled: !!id,
  })

  const districtChartData = data?.district_progress
    .slice()
    .sort((a, b) => (b.utilization_pct ?? 0) - (a.utilization_pct ?? 0))
    .slice(0, 15)
    .map(d => ({
      name: d.district_code,
      utilized: d.utilization_pct ?? 0,
      physical: d.physical_pct ?? 0,
      fullName: d.district_name,
    })) ?? []

  return (
    <div>
      <PageHeader
        title={data?.name ?? 'SCHEME DETAIL'}
        subtitle={`${data?.code ?? ''} — ${data?.department_name ?? ''} — FY ${financialYear}`}
        right={
          <div className="flex items-center gap-2">
            {data && <span className={schemeBadge(data.scheme_type)}>{schemeTypeLabel(data.scheme_type)}</span>}
            {data?.source_url && (
              <a href={data.source_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 mono text-[9px] text-dim hover:text-blue border px-3 py-1.5 transition-colors"
                style={{ borderColor: '#1a2a3a' }}>
                <ExternalLink size={10} /> SOURCE
              </a>
            )}
            <Link to="/schemes" className="flex items-center gap-1 mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
              style={{ borderColor: '#1a2a3a' }}>
              <ChevronLeft size={12} /> BACK
            </Link>
          </div>
        }
      />

      <div className="p-6 space-y-6">
        {isLoading && (
          <div className="panel h-40 flex items-center justify-center mono text-[10px] text-dim animate-pulse">
            Loading scheme data...
          </div>
        )}
        {isError && <ErrorBox />}

        {data && (
          <>
            {view === 'official' && (
          <div className="panel border-l-2 border-emerald-500/40 mono text-[10px] text-dim">
            The CAG accounts report by department grant, not by scheme, so there are no official scheme figures.
            Switch to Live or Combined to see the portal figures (provisional).
          </div>
        )}
            {data.description && (
              <div className="panel border-l-2 border-yellow-500/30">
                <p className="mono text-[10px] text-dim leading-relaxed">{data.description}</p>
              </div>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { key: 'total_outlay_lakhs', label: 'TOTAL OUTLAY', val: data.total_outlay_lakhs, fmt: 'lakhs', color: '#5a7a9a' },
                { key: 'funds_allocated_lakhs', label: 'FUNDS ALLOCATED', val: data.funds_allocated_lakhs, fmt: 'lakhs', color: '#00aaff' },
                { key: 'funds_utilized_lakhs', label: 'FUNDS UTILIZED', val: data.funds_utilized_lakhs, fmt: 'lakhs', color: data.utilization_pct && data.utilization_pct >= 50 ? '#00ff88' : '#ff3366' },
                { key: 'physical_pct', label: 'PHYSICAL PROGRESS', val: data.physical_pct, fmt: 'pct', color: utilColorVar(data.physical_pct) },
              ].map(({ key, label, val, fmt, color }) => (
                <div key={label} className="panel">
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color }} />
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="mono text-[8px] text-dim tracking-widest">{label}</div>
                    <SourceBadge source={data.sources[key]} value={val} />
                  </div>
                  <div className="display text-2xl" style={{ color }}>
                    {fmt === 'lakhs' ? fmtLakhs(val as number) : fmtPct(val as number)}
                  </div>
                </div>
              ))}
            </div>

            {/* Velocity & Projection Chart */}
            {velocity && <VelocityChart velocity={velocity} />}

            {/* Overall bar */}
            <div className="panel">
              <div className="panel-title">OVERALL UTILIZATION — ALL DISTRICTS</div>
              <UtilBar
                allocated={data.funds_allocated_lakhs}
                released={data.funds_released_lakhs}
                utilized={data.funds_utilized_lakhs}
              />
            </div>

            {/* District Map and Chart Grid */}
            {data.district_progress.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* District Map */}
                <div className="panel p-0 flex flex-col">
                  <div className="panel-title p-4 pb-0 mb-0">DISTRICT MAP (FUNDS ALLOCATED & UTILIZED)</div>
                  <div className="flex-1 min-h-[300px]">
                    <MapWidget data={data.district_progress} height={350} />
                  </div>
                </div>

                {/* District chart */}
                <div className="panel">
                  <div className="panel-title">DISTRICT-WISE UTILIZATION %</div>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={districtChartData} barSize={18} margin={{ top: 20, right: 20, left: -20, bottom: 20 }}>
                      <XAxis dataKey="name" tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }} />
                      <YAxis domain={[0, 100]} tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'Space Mono' }}
                        tickFormatter={v => `${v}%`} />
                      <Tooltip
                        formatter={(v: number, name: string) => [`${v.toFixed(1)}%`, name === 'utilized' ? 'Financial' : 'Physical']}
                        contentStyle={{ background: '#0d1520', border: '1px solid #1a2a3a', fontFamily: 'Space Mono', fontSize: 10 }}
                      />
                      <Bar dataKey="utilized" name="utilized">
                        {districtChartData.map((d, i) => (
                          <Cell key={i}
                            fill={d.utilized >= 75 ? 'rgba(0,255,136,0.6)' : d.utilized >= 40 ? 'rgba(255,215,0,0.6)' : 'rgba(255,51,102,0.6)'}
                            stroke={d.utilized >= 75 ? '#00ff88' : d.utilized >= 40 ? '#ffd700' : '#ff3366'}
                            strokeWidth={1}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* District table */}
            {data.district_progress.length > 0 && (
              <div className="panel">
                <div className="flex items-center justify-between gap-2">
                  <div className="panel-title">DISTRICT-WISE BREAKDOWN</div>
                  <SourceBadge source={data.sources.district_progress} />
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b" style={{ borderColor: '#1a2a3a' }}>
                        {['DISTRICT', 'DIV', 'TARGET', 'ACHIEVED', 'PHYS%', 'ALLOCATED', 'RELEASED', 'UTILIZED', 'UTIL%'].map(h => (
                          <th key={h} className="mono text-[8px] text-dim text-left pb-2 pr-4 tracking-widest">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.district_progress.map(d => (
                        <tr key={d.district_id} className="border-b hover:bg-white/5 transition-colors"
                          style={{ borderColor: '#1a2a3a' }}>
                          <td className="py-2 pr-4 mono text-[10px]">{d.district_name}</td>
                          <td className="pr-4 mono text-[8px] text-dim">{d.division.slice(0, 3).toUpperCase()}</td>
                          <td className="pr-4 mono text-[9px] text-dim">{d.target_physical?.toLocaleString() ?? '—'}</td>
                          <td className="pr-4 mono text-[9px]">{d.achieved_physical?.toLocaleString() ?? '—'}</td>
                          <td className="pr-4">
                            <span className={`mono text-[9px] ${utilColor(d.physical_pct)}`}>{fmtPct(d.physical_pct)}</span>
                          </td>
                          <td className="pr-4 mono text-[9px] text-blue">{fmtLakhs(d.funds_allocated_lakhs)}</td>
                          <td className="pr-4 mono text-[9px] text-purple" title="Central funds released via PFMS">
                            {d.funds_released_lakhs != null ? fmtLakhs(d.funds_released_lakhs) : <span className="text-dim">—</span>}
                          </td>
                          <td className="pr-4 mono text-[9px] text-green">{fmtLakhs(d.funds_utilized_lakhs)}</td>
                          <td>
                            <span className={`mono text-[9px] ${utilColor(d.utilization_pct)}`}>
                              {fmtPct(d.utilization_pct)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {data.district_progress.length === 0 && (
              <div className="panel p-6 text-center">
                <div className="mono text-[10px] text-dim">
                  District-wise data will populate after the next scheduled collector run (daily 6AM IST).
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
