import { useQuery } from '@tanstack/react-query'
import { fetchTenders, fetchContractorLeaderboard } from '../lib/api'
import { fmtLakhs } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function Tenders() {
  const { data: tenders, isLoading: loadingTenders, isError: errorTenders } = useQuery({
    queryKey: ['tenders'],
    queryFn: () => fetchTenders(100),
  })

  const { data: leaderboard, isLoading: loadingLeaderboard } = useQuery({
    queryKey: ['contractors'],
    queryFn: () => fetchContractorLeaderboard(15),
  })

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="TENDERS & CONTRACTS"
        subtitle="PUBLIC WORKS AND CONTRACTOR LEADERBOARD"
      />

      <div className="p-6 space-y-6 flex-1 overflow-auto">
        
        {/* Leaderboard Chart */}
        <div className="panel flex flex-col h-[350px]">
          <div className="panel-title flex justify-between">
            <span>🏆 TOP CONTRACTORS BY AWARDED VALUE</span>
            <span className="mono text-[8px] text-dim font-normal">Top 15 — All Departments</span>
          </div>
          <div className="flex-1 p-4 relative">
            {loadingLeaderboard ? (
              <div className="absolute inset-0 flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading Leaderboard...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={leaderboard || []} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis 
                    dataKey="contractor_name" 
                    type="category" 
                    width={180}
                    tick={{ fill: '#5a7a9a', fontSize: 9, fontFamily: 'monospace' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        const d = payload[0].payload
                        return (
                          <div className="bg-[#0a1018] border border-[#1a2a3a] p-3 shadow-xl">
                            <div className="mono text-[10px] text-white mb-2">{d.contractor_name}</div>
                            <div className="mono text-[9px] text-gold">{fmtLakhs(d.total_awarded_lakhs)} total awarded</div>
                            <div className="mono text-[8px] text-dim">{d.total_tenders_won} tenders won</div>
                          </div>
                        )
                      }
                      return null
                    }}
                  />
                  <Bar dataKey="total_awarded_lakhs" radius={[0, 4, 4, 0]}>
                    {(leaderboard || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? '#ffd700' : index < 3 ? '#ffaa00' : '#1a2a3a'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Tenders Table */}
        <div className="panel flex-1 flex flex-col min-h-[400px]">
          <div className="panel-title flex justify-between items-center sticky top-0 bg-[#080e18] z-10 border-b border-[#1a2a3a]">
            <span>LATEST TENDERS</span>
            <span className="mono text-[9px] text-dim font-normal px-2 py-1 border border-[#1a2a3a] bg-white/5">
              Source: jktenders.gov.in
            </span>
          </div>
          
          <div className="flex-1 overflow-auto">
            {errorTenders ? <ErrorBox /> : (
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-[#080e18]/95 backdrop-blur z-10">
                  <tr className="mono text-[8px] text-dim border-b border-[#1a2a3a]">
                    <th className="p-3 font-normal tracking-widest w-[15%]">REF / DEPT</th>
                    <th className="p-3 font-normal tracking-widest w-[35%]">TITLE</th>
                    <th className="p-3 font-normal tracking-widest text-right">ESTIMATED</th>
                    <th className="p-3 font-normal tracking-widest text-right">AWARDED</th>
                    <th className="p-3 font-normal tracking-widest w-[15%]">CONTRACTOR</th>
                    <th className="p-3 font-normal tracking-widest text-right">STATUS</th>
                  </tr>
                </thead>
                <tbody className="mono text-[10px]">
                  {loadingTenders ? (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-dim animate-pulse">Loading Tenders...</td>
                    </tr>
                  ) : (
                    (tenders || []).map((t, i) => {
                      const est = t.estimated_cost_lakhs
                      const awd = t.awarded_cost_lakhs
                      const diff = (est && awd) ? awd - est : 0
                      const isOverrun = diff > 0
                      
                      return (
                        <tr key={t.id} className="border-b border-[#1a2a3a]/50 hover:bg-white/5 transition-colors">
                          <td className="p-3 align-top">
                            <div className="text-white text-[9px] mb-1 truncate" title={t.tender_ref}>{t.tender_ref}</div>
                            <div className="text-dim text-[8px] truncate" title={t.department_name}>{t.department_name.split('(')[0]}</div>
                          </td>
                          <td className="p-3 align-top text-dim leading-relaxed" title={t.title}>
                            <div className="line-clamp-2">{t.title}</div>
                          </td>
                          <td className="p-3 align-top text-right text-white">
                            {est ? fmtLakhs(est) : '-'}
                          </td>
                          <td className="p-3 align-top text-right">
                            <div className="text-gold">{awd ? fmtLakhs(awd) : '-'}</div>
                            {awd && est && (
                              <div className={`text-[8px] mt-1 ${isOverrun ? 'text-red' : 'text-green'}`}>
                                {isOverrun ? '+' : ''}{fmtLakhs(diff)}
                              </div>
                            )}
                          </td>
                          <td className="p-3 align-top">
                            <div className="text-blue truncate" title={t.contractor_name || ''}>
                              {t.contractor_name || '-'}
                            </div>
                            <div className="text-dim text-[8px] mt-1">{t.award_date || ''}</div>
                          </td>
                          <td className="p-3 align-top text-right">
                            <span className={`px-2 py-0.5 border text-[8px] tracking-widest ${
                              t.status === 'awarded' 
                                ? 'text-green border-green-500/30 bg-green-500/10' 
                                : 'text-dim border-[#1a2a3a] bg-white/5'
                            }`}>
                              {(t.status || 'UNKNOWN').toUpperCase()}
                            </span>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
