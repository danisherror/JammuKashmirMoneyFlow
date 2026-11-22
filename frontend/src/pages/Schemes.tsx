import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { fetchSchemes, fetchDepartments, type SchemeType } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, schemeBadge, schemeTypeLabel } from '../lib/utils'
import UtilBar from '../components/UtilBar'
import SourceBadge from '../components/SourceBadge'
import PageHeader from '../components/PageHeader'
import LoadingGrid from '../components/LoadingGrid'
import ErrorBox from '../components/ErrorBox'
import { Search } from 'lucide-react'

export default function Schemes() {
  const { financialYear, view } = useAppStore()
  const navigate = useNavigate()
  const [typeFilter, setTypeFilter] = useState<SchemeType | 'all'>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [deptFilter, setDeptFilter] = useState('all')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['schemes', financialYear, view, typeFilter],
    queryFn: () => fetchSchemes(financialYear, view, typeFilter === 'all' ? undefined : typeFilter),
  })

  const { data: departments } = useQuery({
    queryKey: ['departments', financialYear, view], // just for the list of names
    queryFn: () => fetchDepartments(financialYear, view),
  })

  const filteredSchemes = useMemo(() => {
    if (!data) return []
    return data.filter(s => {
      const matchSearch = s.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          s.code.toLowerCase().includes(searchTerm.toLowerCase())
      const matchDept = deptFilter === 'all' || s.department_name.includes(deptFilter)
      return matchSearch && matchDept
    })
  }, [data, searchTerm, deptFilter])

  return (
    <div>
      <PageHeader
        title="SCHEMES"
        subtitle={`FLAGSHIP SCHEME FUND TRACKER — FY ${financialYear}`}
        right={
          <div className="flex flex-col md:flex-row items-end md:items-center gap-4">
            <div className="flex items-center gap-2">
              {([
                { key: 'all', label: 'ALL' },
                { key: 'css', label: 'CSS' },
                { key: 'central', label: 'CENTRAL' },
                { key: 'ut', label: 'UT' },
              ] as const).map(({ key, label }) => (
                <button key={key} onClick={() => setTypeFilter(key)}
                  className={`mono text-[8px] px-3 py-1.5 tracking-widest border transition-colors ${
                    typeFilter === key
                      ? 'border-yellow-500/50 text-gold bg-yellow-900/20'
                      : 'border-border text-dim hover:text-white hover:border-white/20'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
                <input
                  type="text"
                  placeholder="Search scheme..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="bg-[#0a1018] border border-[#1a2a3a] text-white mono text-[10px] pl-9 pr-3 py-1.5 focus:outline-none focus:border-blue-500/50 w-48"
                />
              </div>
              <select
                value={deptFilter}
                onChange={e => setDeptFilter(e.target.value)}
                className="bg-[#0a1018] border border-[#1a2a3a] text-white mono text-[10px] px-3 py-1.5 focus:outline-none focus:border-blue-500/50 max-w-[150px]"
              >
                <option value="all">ALL DEPARTMENTS</option>
                {departments?.map(d => (
                  <option key={d.id} value={d.name}>{d.name}</option>
                ))}
              </select>
            </div>
          </div>
        }
      />

      <div className="p-6">
        {view === 'official' && (
          <div className="panel border-l-2 border-emerald-500/40 mono text-[10px] text-dim mb-4">
            The CAG accounts report by department grant, not by scheme, so there are no official scheme figures.
            Switch to Live or Combined to see the portal figures (provisional).
          </div>
        )}
        {isLoading ? <LoadingGrid count={6} /> :
         isError   ? <ErrorBox /> : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredSchemes.map(scheme => {
              const util = scheme.utilization_pct
              const phys = scheme.physical_pct
              return (
                <div
                  key={scheme.id}
                  onClick={() => navigate(`/schemes/${scheme.id}`)}
                  className="panel cursor-pointer hover:border-yellow-500/30 transition-all group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 pr-2">
                      <div className="mono text-[11px] font-bold text-white group-hover:text-gold transition-colors">
                        {scheme.name}
                      </div>
                      <div className="mono text-[8px] text-dim mt-0.5">
                        {scheme.department_name.split('(')[0].trim()}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className={schemeBadge(scheme.scheme_type)}>
                        {schemeTypeLabel(scheme.scheme_type)}
                      </span>
                    </div>
                  </div>

                  {/* Financial row */}
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    {[
                      { key: 'total_outlay_lakhs', label: 'OUTLAY', val: scheme.total_outlay_lakhs, color: '#5a7a9a' },
                      { key: 'funds_allocated_lakhs', label: 'ALLOCATED', val: scheme.funds_allocated_lakhs, color: '#00aaff' },
                      { key: 'funds_released_lakhs', label: 'RELEASED', val: scheme.funds_released_lakhs, color: '#b366ff' },
                      { key: 'funds_utilized_lakhs', label: 'UTILIZED', val: scheme.funds_utilized_lakhs, color: util != null && util >= 60 ? '#00ff88' : util != null && util >= 30 ? '#ffd700' : '#ff3366' },
                    ].map(({ key, label, val, color }) => (
                      <div key={label}>
                        <div className="flex items-center gap-1 mb-0.5 flex-wrap">
                          <span className="mono text-[7px] text-dim tracking-widest">{label}</span>
                          <SourceBadge source={scheme.sources[key]} value={val} />
                        </div>
                        <div className="display text-base" style={{ color }}>{fmtLakhs(val)}</div>
                      </div>
                    ))}
                  </div>

                  {/* Financial progress bar */}
                  <UtilBar
                    allocated={scheme.funds_allocated_lakhs}
                    released={scheme.funds_released_lakhs}
                    utilized={scheme.funds_utilized_lakhs}
                    showLabels={false}
                  />

                  {/* Physical progress if available */}
                  {phys != null && (
                    <div className="mt-2">
                      <div className="flex justify-between mb-1">
                        <span className="mono text-[7px] text-dim tracking-widest">PHYSICAL PROGRESS</span>
                        <span className={`mono text-[8px] ${utilColor(phys)}`}>{fmtPct(phys)}</span>
                      </div>
                      <div className="h-1.5 w-full" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid #1a2a3a' }}>
                        <div
                          className="h-full transition-all duration-700"
                          style={{
                            width: `${Math.min(phys, 100)}%`,
                            background: phys >= 75 ? '#00ff88' : phys >= 40 ? '#ffd700' : '#ff3366',
                          }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex justify-between mt-2">
                    <span className="mono text-[8px] text-dim">
                      {scheme.last_updated ? `Updated: ${scheme.last_updated}` : 'No data yet'}
                    </span>
                    <span className={`mono text-[9px] ${utilColor(util)}`}>
                      {fmtPct(util)} utilized
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
