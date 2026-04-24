import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { fetchDepartments } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, divisionLabel } from '../lib/utils'
import UtilBar from '../components/UtilBar'
import PageHeader from '../components/PageHeader'
import LoadingGrid from '../components/LoadingGrid'
import ErrorBox from '../components/ErrorBox'

export default function Departments() {
  const { financialYear } = useAppStore()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<string>('all')
  const [search, setSearch] = useState('')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['departments', financialYear],
    queryFn: () => fetchDepartments(financialYear),
  })

  const filtered = (data ?? []).filter(d => {
    if (filter !== 'all' && d.division !== filter) return false
    if (search && !d.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div>
      <PageHeader
        title="DEPARTMENTS"
        subtitle={`MINISTRY-WISE BUDGET ALLOCATION & UTILIZATION — FY ${financialYear}`}
        right={
          <div className="flex items-center gap-2">
            {['all', 'jammu', 'kashmir', 'central'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`mono text-[8px] px-3 py-1.5 tracking-widest border transition-colors ${
                  filter === f
                    ? 'border-yellow-500/50 text-gold bg-yellow-900/20'
                    : 'border-border text-dim hover:text-white hover:border-white/20'
                }`}>
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        }
      />

      <div className="p-6">
        <div className="mb-4">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search departments..."
            className="mono text-[10px] bg-transparent border px-3 py-2 w-72 text-white placeholder-dim outline-none focus:border-yellow-500/50 transition-colors"
            style={{ borderColor: '#1a2a3a' }}
          />
        </div>

        {isLoading ? <LoadingGrid count={8} /> :
         isError   ? <ErrorBox /> : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
            {filtered.map(dept => (
              <div
                key={dept.id}
                onClick={() => navigate(`/departments/${dept.id}`)}
                className="panel cursor-pointer hover:border-yellow-500/30 transition-all group"
              >
                {/* Top indicator bar */}
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                  background: dept.is_capital ? '#00aaff' : '#ffd700'
                }} />

                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 pr-2">
                    <div className="mono text-[10px] font-bold text-white group-hover:text-gold transition-colors">
                      {dept.name.length > 35 ? dept.name.substring(0, 35) + '...' : dept.name}
                    </div>
                    <div className="mono text-[8px] text-dim mt-0.5 tracking-widest">{dept.code}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className={`badge ${dept.is_capital ? 'badge-css' : 'badge-delay'}`}>
                      {dept.is_capital ? 'CAPITAL' : 'REVENUE'}
                    </span>
                    <span className="mono text-[8px] text-dim">{divisionLabel(dept.division)}</span>
                  </div>
                </div>

                <div className="flex justify-between items-end mb-2">
                  <div>
                    <div className="mono text-[8px] text-dim mb-0.5">ALLOCATED</div>
                    <div className="display text-xl text-blue">{fmtLakhs(dept.budget_estimate_lakhs)}</div>
                  </div>
                  {dept.utilized_lakhs != null && (
                    <div className="text-right">
                      <div className="mono text-[8px] text-dim mb-0.5">UTILIZED</div>
                      <div className={`display text-xl ${utilColor(dept.utilization_pct)}`}>
                        {fmtLakhs(dept.utilized_lakhs)}
                      </div>
                    </div>
                  )}
                </div>

                <UtilBar
                  allocated={dept.budget_estimate_lakhs}
                  utilized={dept.utilized_lakhs}
                  showLabels={false}
                />

                <div className="flex justify-between mt-1.5">
                  <span className="mono text-[8px] text-dim">
                    {dept.revised_estimate_lakhs ? `RE: ${fmtLakhs(dept.revised_estimate_lakhs)}` : 'No revision'}
                  </span>
                  <span className={`mono text-[9px] ${utilColor(dept.utilization_pct)}`}>
                    {fmtPct(dept.utilization_pct)} used
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
