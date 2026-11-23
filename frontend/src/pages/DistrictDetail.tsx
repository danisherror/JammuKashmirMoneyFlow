import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store'
import { fetchDistrictDetail } from '../lib/api'
import { fmtLakhs, fmtPct, utilColor, gradeColor, divisionLabel } from '../lib/utils'
import UtilBar from '../components/UtilBar'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { ChevronLeft } from 'lucide-react'
import CollectorSource from '../components/CollectorSource'
import { SCHEME_PROGRESS_COLLECTORS } from '../lib/collectors'

export default function DistrictDetail() {
  const { id } = useParams<{ id: string }>()
  const { financialYear } = useAppStore()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['district-detail', id, financialYear],
    queryFn: () => fetchDistrictDetail(Number(id), financialYear),
    enabled: !!id,
  })

  const gColor = data ? gradeColor(data.absorption_grade) : '#ffd700'

  return (
    <div>
      <PageHeader
        title={data?.name ?? 'DISTRICT'}
        subtitle={`${divisionLabel(data?.division ?? '')} DIVISION — FY ${financialYear}`}
        right={
          <Link to="/districts" className="flex items-center gap-1 mono text-[9px] text-dim hover:text-white border px-3 py-1.5 transition-colors"
            style={{ borderColor: '#1a2a3a' }}>
            <ChevronLeft size={12} /> BACK
          </Link>
        }
      />

      <div className="p-6 space-y-6">
        <CollectorSource collectors={SCHEME_PROGRESS_COLLECTORS} className="block" />
        {isLoading && <div className="panel h-40 flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading...</div>}
        {isError && <ErrorBox />}

        {data && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {[
                { label: 'ABSORPTION GRADE', val: data.absorption_grade, color: gColor, isText: true },
                { label: 'AVG UTILIZATION', val: fmtPct(data.avg_utilization_pct), color: gColor, isText: true },
                { label: 'TOTAL ALLOCATED', val: fmtLakhs(data.total_funds_allocated_lakhs), color: '#00aaff', isText: true },
                { label: 'TOTAL UTILIZED', val: fmtLakhs(data.total_funds_utilized_lakhs), color: gColor, isText: true },
                { label: 'POPULATION', val: data.population?.toLocaleString() ?? '—', color: '#5a7a9a', isText: true },
              ].map(({ label, val, color, isText }) => (
                <div key={label} className="panel">
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color }} />
                  <div className="mono text-[8px] text-dim tracking-widest mb-2">{label}</div>
                  <div className="display text-2xl" style={{ color }}>{val}</div>
                </div>
              ))}
            </div>

            {data.is_border_district && (
              <div className="panel border-yellow-500/30 p-3">
                <div className="mono text-[9px] text-gold tracking-widest">
                  ⭐ BORDER DISTRICT — Eligible for Border Area Development Programme (BADP) funds
                </div>
              </div>
            )}

            <div className="panel">
              <div className="panel-title">OVERALL FUND ABSORPTION</div>
              <UtilBar
                allocated={data.total_funds_allocated_lakhs ?? 1}
                utilized={data.total_funds_utilized_lakhs}
              />
            </div>

            {data.scheme_progress?.length > 0 && (
              <div className="panel">
                <div className="panel-title">SCHEME-WISE PROGRESS IN {data.name.toUpperCase()}</div>
                <div className="space-y-4">
                  {data.scheme_progress.map((sp: any) => (
                    <div key={sp.district_id + sp.snapshot_date} className="border-b pb-4" style={{ borderColor: '#1a2a3a' }}>
                      <div className="flex justify-between items-start mb-2">
                        <div className="mono text-[10px] text-white">
                          <span className="text-blue mr-2">{sp.scheme_name ?? 'SCHEME'}</span>
                          {sp.physical_unit ? `${sp.physical_unit.toUpperCase()} TARGET` : 'PROGRESS'}
                        </div>
                        <span className={`mono text-[9px] ${utilColor(sp.utilization_pct)}`}>
                          {fmtPct(sp.utilization_pct)} utilized
                        </span>
                      </div>
                      <UtilBar
                        allocated={sp.funds_allocated_lakhs ?? 1}
                        released={sp.funds_released_lakhs}
                        utilized={sp.funds_utilized_lakhs}
                        showLabels={false}
                      />
                      <div className="flex justify-between mt-1 mono text-[8px] text-dim">
                        <span>Allocated: {fmtLakhs(sp.funds_allocated_lakhs)}</span>
                        <span>Updated: {sp.snapshot_date ?? 'N/A'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!data.scheme_progress || data.scheme_progress.length === 0) && (
              <div className="panel p-6 text-center">
                <div className="mono text-[10px] text-dim">
                  Scheme-wise data will populate after the first collector run.
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
