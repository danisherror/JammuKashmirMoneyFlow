import { useState } from 'react'
import { useAppStore } from '../store'
import PageHeader from '../components/PageHeader'
import { api } from '../lib/api'
import { Download, FileText, Archive, Database } from 'lucide-react'

interface ExportDef {
  id: string
  label: string
  description: string
  endpoint: string
  filename: (fy: string) => string
  type: 'csv' | 'zip'
  icon: React.ReactNode
  accent: string
}

const EXPORTS: ExportDef[] = [
  {
    id: 'zip',
    label: 'FULL DATABASE EXPORT',
    description: 'All datasets in one ZIP — scheme progress, tenders, DBT transfers, and a README. Best for research.',
    endpoint: '/export/zip',
    filename: (fy) => `jk_money_flow_${fy.replace('-','_')}.zip`,
    type: 'zip',
    icon: <Archive size={18} />,
    accent: '#00ff88',
  },
  {
    id: 'schemes',
    label: 'SCHEME PROGRESS (CSV)',
    description: 'District-wise physical & financial progress for all schemes — MGNREGA, JJM, PMAY, etc.',
    endpoint: '/export/schemes',
    filename: (fy) => `jk_scheme_progress_${fy.replace('-','_')}.csv`,
    type: 'csv',
    icon: <Database size={18} />,
    accent: '#00aaff',
  },
  {
    id: 'tenders',
    label: 'TENDERS (CSV)',
    description: 'All public works tenders — titles, departments, estimated costs, awarded amounts, contractor names.',
    endpoint: '/export/tenders',
    filename: () => 'jk_tenders.csv',
    type: 'csv',
    icon: <FileText size={18} />,
    accent: '#ffd700',
  },
  {
    id: 'dbt',
    label: 'DBT TRANSFERS (CSV)',
    description: 'Direct Benefit Transfer data — beneficiaries enrolled vs paid, last-mile gap percentage per district.',
    endpoint: '/export/dbt',
    filename: (fy) => `jk_dbt_${fy.replace('-','_')}.csv`,
    type: 'csv',
    icon: <FileText size={18} />,
    accent: '#ff6432',
  },
  {
    id: 'gap-analysis',
    label: 'FUND GAP ANALYSIS (CSV)',
    description: 'Department-level gap between allocated budget, central releases (PFMS), and actual utilization.',
    endpoint: '/export/gap-analysis',
    filename: (fy) => `jk_gap_analysis_${fy.replace('-','_')}.csv`,
    type: 'csv',
    icon: <Database size={18} />,
    accent: '#ff3366',
  },
  {
    id: 'cag',
    label: 'CAG FINDINGS (CSV)',
    description: 'All parsed CAG audit report findings, summaries, and flagged financial amounts.',
    endpoint: '/export/cag-findings',
    filename: () => 'jk_cag_findings.csv',
    type: 'csv',
    icon: <FileText size={18} />,
    accent: '#b366ff',
  },
]

export default function Export() {
  const { financialYear } = useAppStore()
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleDownload(exp: ExportDef) {
    setLoading(exp.id)
    setError(null)
    try {
      const resp = await api.get(exp.endpoint, {
        params: { financial_year: financialYear },
        responseType: 'blob',
      })

      const url = URL.createObjectURL(new Blob([resp.data]))
      const a   = document.createElement('a')
      a.href    = url
      a.download = exp.filename(financialYear)
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(`Download failed: ${e?.message ?? 'unknown error'}`)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div>
      <PageHeader
        title="DATA EXPORT"
        subtitle={`DOWNLOAD CLEAN DATASETS — FY ${financialYear}`}
      />

      <div className="p-6 space-y-6">

        {/* Info banner */}
        <div className="panel p-4" style={{ borderColor: 'rgba(0,170,255,0.3)' }}>
          <div className="mono text-[9px] text-blue leading-relaxed">
            ℹ️{' '}
            <span className="text-white">Open Data Policy.</span>{' '}
            All data exported from this system is derived from publicly available Government of India portals.
            Attribution is required when publishing. No personal data is included.
            ZIP exports include a README with source citations.
          </div>
        </div>

        {error && (
          <div className="panel p-3 mono text-[9px] text-red" style={{ borderColor: 'rgba(255,51,102,0.3)' }}>
            ✕ {error}
          </div>
        )}

        {/* Export cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {EXPORTS.map(exp => (
            <div
              key={exp.id}
              className="panel flex flex-col gap-4"
              style={{ borderColor: loading === exp.id ? exp.accent + '60' : '#1a2a3a' }}
            >
              {/* Accent top bar */}
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: exp.accent }} />

              {/* Header */}
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0" style={{ color: exp.accent }}>
                  {exp.icon}
                </div>
                <div className="flex-1">
                  <div className="mono text-[10px] font-bold text-white">{exp.label}</div>
                  <div className="mono text-[8px] text-dim mt-1 leading-relaxed">{exp.description}</div>
                </div>
                <div
                  className="mono text-[7px] px-2 py-0.5 flex-shrink-0"
                  style={{
                    color: exp.accent,
                    background: exp.accent + '18',
                    border: `1px solid ${exp.accent}40`,
                  }}
                >
                  .{exp.type.toUpperCase()}
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between">
                <div className="mono text-[7px] text-dim">
                  FY {financialYear} · {exp.filename(financialYear)}
                </div>
                <button
                  id={`export-btn-${exp.id}`}
                  onClick={() => handleDownload(exp)}
                  disabled={loading !== null}
                  className="flex items-center gap-2 mono text-[8px] px-4 py-2 border tracking-widest transition-all disabled:opacity-40"
                  style={{
                    borderColor: exp.accent + '50',
                    color: loading === exp.id ? exp.accent : '#5a7a9a',
                    background: loading === exp.id ? exp.accent + '10' : 'transparent',
                  }}
                >
                  {loading === exp.id ? (
                    <>
                      <span className="animate-spin inline-block">⟳</span> PREPARING...
                    </>
                  ) : (
                    <>
                      <Download size={11} /> DOWNLOAD
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* API Reference */}
        <div className="panel p-4 space-y-3">
          <div className="mono text-[9px] text-white tracking-widest">DIRECT API ENDPOINTS</div>
          <div className="mono text-[8px] text-dim leading-loose">
            For automated pipelines, you can query these endpoints directly:
          </div>
          <div className="space-y-1">
            {[
              ['GET', '/api/v1/export/zip',          'Full ZIP archive (all datasets)'],
              ['GET', '/api/v1/export/gap-analysis', 'Department gap analysis CSV'],
              ['GET', '/api/v1/export/cag-findings', 'CAG audit findings CSV'],
              ['GET', '/api/v1/export/schemes',      'Scheme progress CSV'],
              ['GET', '/api/v1/export/tenders',      'Tenders CSV'],
              ['GET', '/api/v1/export/dbt',          'DBT transfers CSV'],
            ].map(([method, path, desc]) => (
              <div key={path} className="flex items-center gap-3">
                <span className="mono text-[7px] px-1.5 py-0.5 text-green" style={{ background: 'rgba(0,255,136,0.1)', border: '1px solid rgba(0,255,136,0.2)' }}>
                  {method}
                </span>
                <code className="mono text-[8px] text-blue">{path}</code>
                <span className="mono text-[7px] text-dim hidden md:inline">— {desc}</span>
              </div>
            ))}
          </div>
          <div className="mono text-[7px] text-dim pt-2" style={{ borderTop: '1px solid #1a2a3a' }}>
            Add <code className="text-blue">?financial_year=2024-25</code> to filter by year.
            All endpoints return immediately with streamed content — no authentication required.
          </div>
        </div>

      </div>
    </div>
  )
}
