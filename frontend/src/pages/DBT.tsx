import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store'
import { fetchDBTSchemes, fetchDBTGap, DBTSchemeSummary } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { ChevronRight } from 'lucide-react'
import CollectorSource from '../components/CollectorSource'

export default function DBT() {
  const { financialYear } = useAppStore()
  const [selectedScheme, setSelectedScheme] = useState<DBTSchemeSummary | null>(null)

  const { data: schemes, isLoading: loadingSchemes, isError: errorSchemes } = useQuery({
    queryKey: ['dbt-schemes', financialYear],
    queryFn: () => fetchDBTSchemes(financialYear),
  })

  const { data: gaps, isLoading: loadingGaps } = useQuery({
    queryKey: ['dbt-gap', selectedScheme?.scheme_id, financialYear],
    queryFn: () => selectedScheme ? fetchDBTGap(selectedScheme.scheme_id, financialYear) : Promise.resolve([]),
    enabled: !!selectedScheme,
  })

  // Auto-select first scheme when data loads (fix: was in render body causing React violation)
  useEffect(() => {
    if (schemes && schemes.length > 0 && !selectedScheme) {
      setSelectedScheme(schemes[0])
    }
  }, [schemes])

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="DIRECT BENEFIT TRANSFER (DBT)"
        subtitle={`LAST MILE DELIVERY GAP ANALYSIS — FY ${financialYear}`}
      />

      <div className="p-6 flex flex-col md:flex-row gap-6 flex-1 overflow-hidden">
        
        {/* Left Col: Scheme List */}
        <div className="w-full md:w-1/3 flex flex-col gap-4">
          <div className="px-1">
            <div className="mono text-[10px] text-dim tracking-widest">SCHEMES TRACKED</div>
            <CollectorSource collectors={['dbt_collector']} />
          </div>
          
          <div className="flex-1 overflow-auto space-y-2 pr-2 custom-scrollbar">
            {loadingSchemes && <div className="text-dim mono text-[10px] animate-pulse">Loading schemes...</div>}
            {errorSchemes && <ErrorBox />}
            
            {(schemes || []).map(s => {
              const isSelected = selectedScheme?.scheme_id === s.scheme_id
              return (
                <button
                  key={s.scheme_id}
                  onClick={() => setSelectedScheme(s)}
                  className={`w-full text-left p-3 border transition-all ${
                    isSelected 
                      ? 'bg-blue-900/10 border-blue-500/50 shadow-[0_0_15px_rgba(0,170,255,0.1)]' 
                      : 'bg-[#080e18] border-[#1a2a3a] hover:border-blue-500/30 hover:bg-white/5'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className={`mono text-[10px] font-bold ${isSelected ? 'text-blue' : 'text-white'}`}>
                      {s.scheme_name}
                    </div>
                    <ChevronRight size={14} className={isSelected ? 'text-blue' : 'text-dim opacity-0'} />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 mt-3">
                    <div>
                      <div className="mono text-[7px] text-dim mb-1">ENROLLED vs PAID</div>
                      <div className="mono text-[9px] text-white">
                        {s.total_beneficiaries_paid.toLocaleString()} <span className="text-dim">/ {s.total_beneficiaries_enrolled.toLocaleString()}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="mono text-[7px] text-dim mb-1">OVERALL GAP</div>
                      <div className={`mono text-[10px] font-bold ${s.overall_gap_pct > 10 ? 'text-red' : 'text-green'}`}>
                        {fmtPct(s.overall_gap_pct)}
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right Col: District Gap Chart */}
        <div className="w-full md:w-2/3 flex flex-col h-full">
          <div className="panel flex-1 flex flex-col">
            <div className="panel-title flex justify-between items-center border-b border-[#1a2a3a] pb-3 mb-4">
              <div>
                <span className="text-blue mr-2">LAST MILE GAP:</span>
                <span className="text-white">{selectedScheme?.scheme_name || 'Select a Scheme'}</span>
              </div>
              <CollectorSource collectors={['dbt_collector']} className="px-2 py-1 border border-[#1a2a3a] bg-white/5" />
            </div>

            {selectedScheme && (
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="p-3 border border-[#1a2a3a] bg-white/5">
                  <div className="mono text-[8px] text-dim mb-1">TOTAL TRANSFERRED</div>
                  <div className="mono text-lg text-gold">{fmtLakhs(selectedScheme.total_amount_transferred_lakhs)}</div>
                </div>
                <div className="p-3 border border-[#1a2a3a] bg-white/5">
                  <div className="mono text-[8px] text-dim mb-1">TOTAL ENROLLED</div>
                  <div className="mono text-lg text-white">{selectedScheme.total_beneficiaries_enrolled.toLocaleString()}</div>
                </div>
                <div className="p-3 border border-red-500/30 bg-red-500/10">
                  <div className="mono text-[8px] text-red mb-1">UNPAID GAP</div>
                  <div className="mono text-lg text-red">
                    {(selectedScheme.total_beneficiaries_enrolled - selectedScheme.total_beneficiaries_paid).toLocaleString()}
                  </div>
                </div>
              </div>
            )}

            <div className="flex-1 min-h-[300px]">
              {loadingGaps ? (
                <div className="h-full flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading District Data...</div>
              ) : !gaps || gaps.length === 0 ? (
                <div className="h-full flex items-center justify-center mono text-[10px] text-dim">No district data available.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={gaps} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                    <XAxis 
                      dataKey="district_name" 
                      tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'monospace' }}
                      angle={-45}
                      textAnchor="end"
                      height={70}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis 
                      tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'monospace' }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(val) => val >= 1000 ? `${(val/1000).toFixed(1)}k` : val}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const d = payload[0].payload
                          return (
                            <div className="bg-[#0a1018] border border-[#1a2a3a] p-3 shadow-xl">
                              <div className="mono text-[10px] text-white mb-2 pb-2 border-b border-[#1a2a3a]">
                                {d.district_name} District
                              </div>
                              <div className="flex justify-between gap-6 mb-1">
                                <span className="mono text-[9px] text-dim">Enrolled:</span>
                                <span className="mono text-[9px] text-white">{d.beneficiaries_enrolled.toLocaleString()}</span>
                              </div>
                              <div className="flex justify-between gap-6 mb-1">
                                <span className="mono text-[9px] text-dim">Paid:</span>
                                <span className="mono text-[9px] text-green">{d.beneficiaries_paid.toLocaleString()}</span>
                              </div>
                              <div className="flex justify-between gap-6 mt-2 pt-2 border-t border-[#1a2a3a]">
                                <span className="mono text-[9px] text-dim">Gap:</span>
                                <span className={`mono text-[10px] font-bold ${d.last_mile_gap_pct > 10 ? 'text-red' : 'text-gold'}`}>
                                  {fmtPct(d.last_mile_gap_pct)}
                                </span>
                              </div>
                            </div>
                          )
                        }
                        return null
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '9px', fontFamily: 'monospace', color: '#5a7a9a' }} />
                    <Bar dataKey="beneficiaries_enrolled" name="Total Enrolled" fill="#1a2a3a" radius={[2, 2, 0, 0]} />
                    <Bar dataKey="beneficiaries_paid" name="Successfully Paid" fill="#00aaff" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            
            <div className="mt-4 p-3 bg-white/5 border border-[#1a2a3a] rounded">
               <div className="mono text-[9px] text-dim leading-relaxed">
                 💡 <span className="text-white">Understanding the Gap:</span> This chart displays the difference between citizens who are approved for a scheme (enrolled) vs those who have actually received funds in their bank accounts (paid). High gaps indicate administrative delays, bank account linking issues, or frozen funds at the nodal level.
               </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  )
}
