import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store'
import { fetchDistrictHeatmap } from '../lib/api'
import { fmtLakhs, fmtPct, gradeColor, divisionLabel } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import LoadingGrid from '../components/LoadingGrid'
import ErrorBox from '../components/ErrorBox'
import CollectorSource from '../components/CollectorSource'
import { SCHEME_PROGRESS_COLLECTORS } from '../lib/collectors'

export default function Districts() {
  const { financialYear } = useAppStore()
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['district-heatmap', financialYear],
    queryFn: () => fetchDistrictHeatmap(financialYear),
  })

  const jammu   = (data ?? []).filter(d => d.division === 'jammu')
  const kashmir = (data ?? []).filter(d => d.division === 'kashmir')

  const DivSection = ({ title, districts }: { title: string; districts: typeof data }) => (
    <div>
      <div className="mono text-[9px] text-dim tracking-widest mb-3 flex items-center gap-2">
        {title}
        <div style={{ flex: 1, height: 1, background: '#1a2a3a' }} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {(districts ?? []).map(d => {
          const score = d.absorption_score ?? 0
          const gColor = gradeColor(d.absorption_grade)
          return (
            <div
              key={d.id}
              onClick={() => navigate(`/districts/${d.id}`)}
              className="panel cursor-pointer hover:scale-105 transition-all group"
              style={{ borderColor: `${gColor}33` }}
            >
              {/* Grade indicator top */}
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: gColor }} />

              {/* Grade badge */}
              <div className="absolute top-2 right-2 display text-2xl" style={{ color: gColor }}>
                {d.absorption_grade}
              </div>

              <div className="mono text-[10px] font-bold text-white group-hover:text-gold transition-colors pr-8">
                {d.name}
              </div>
              {d.is_border_district && (
                <div className="mono text-[7px] text-gold tracking-widest mt-0.5">BORDER DISTRICT</div>
              )}

              <div className="mt-3 mb-1">
                {/* Score bar */}
                <div className="h-1 w-full mb-1" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid #1a2a3a' }}>
                  <div className="h-full" style={{ width: `${score}%`, background: gColor, transition: 'width 1s' }} />
                </div>
                <div className="mono text-[9px]" style={{ color: gColor }}>{fmtPct(score)} absorption</div>
              </div>

              <div className="space-y-0.5 mt-2">
                <div className="flex justify-between mono text-[8px]">
                  <span className="text-dim">ALLOCATED</span>
                  <span className="text-blue">{fmtLakhs(d.total_funds_allocated_lakhs)}</span>
                </div>
                <div className="flex justify-between mono text-[8px]">
                  <span className="text-dim">UTILIZED</span>
                  <span style={{ color: gColor }}>{fmtLakhs(d.total_funds_utilized_lakhs)}</span>
                </div>
                <div className="flex justify-between mono text-[8px]">
                  <span className="text-dim">POPULATION</span>
                  <span className="text-white">{d.population?.toLocaleString() ?? '—'}</span>
                </div>
                <div className="flex justify-between mono text-[8px]">
                  <span className="text-dim">SCHEMES</span>
                  <span className="text-white">{d.active_schemes_count}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )

  return (
    <div>
      <PageHeader
        title="DISTRICTS"
        subtitle={`FUND ABSORPTION MAP — ALL 20 DISTRICTS — FY ${financialYear}`}
        right={
          <div className="flex items-center gap-3 mono text-[8px] text-dim">
            {['A','B','C','D','F'].map(g => (
              <div key={g} className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ background: gradeColor(g) }} />
                <span style={{ color: gradeColor(g) }}>{g}</span>
              </div>
            ))}
            <span className="text-dim ml-2">= FUND ABSORPTION GRADE</span>
          </div>
        }
      />

      <div className="p-6 space-y-8">
        <CollectorSource collectors={SCHEME_PROGRESS_COLLECTORS} className="block" />
        {isLoading ? <LoadingGrid count={20} /> :
         isError   ? <ErrorBox /> : (
          <>
            <DivSection title="KASHMIR DIVISION" districts={kashmir} />
            <DivSection title="JAMMU DIVISION"   districts={jammu} />
          </>
        )}
      </div>
    </div>
  )
}
