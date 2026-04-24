import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store'
import { fetchLowUtilAlerts, fetchCAGFindings, LowUtilizationAlert, CAGFinding } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import { ExternalLink, AlertTriangle, TrendingDown, FileText } from 'lucide-react'

// ── Low Utilization Alert Row ─────────────────────────────────────────────────

function UtilRow({ a }: { a: LowUtilizationAlert }) {
  return (
    <div className="flex items-center gap-3 py-3 border-b hover:bg-white/5 transition-colors" style={{ borderColor: '#1a2a3a' }}>
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{
          background: a.severity === 'critical' ? '#ff3366' : '#ffd700',
          boxShadow: a.severity === 'critical' ? '0 0 8px #ff3366' : '0 0 8px #ffd700',
        }}
      />
      <div className="flex-1 min-w-0">
        <div className="mono text-[10px] text-white truncate">{a.scheme_name}</div>
        <div className="mono text-[8px] text-dim">{a.district_name} · {a.department_name.split('(')[0].trim()}</div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="mono text-[9px] text-blue">{fmtLakhs(a.funds_allocated_lakhs)}</div>
        <div className="mono text-[9px] text-red">{fmtLakhs(a.funds_utilized_lakhs)} used</div>
      </div>
      <div className="flex-shrink-0 w-14 text-right">
        <span className={`mono text-[11px] font-bold ${a.severity === 'critical' ? 'text-red' : 'text-gold'}`}>
          {fmtPct(a.utilization_pct)}
        </span>
      </div>
      <div className="flex-shrink-0">
        <span
          className="mono text-[8px] px-2 py-1 border"
          style={
            a.severity === 'critical'
              ? { color: '#ff3366', borderColor: 'rgba(255,51,102,0.4)', background: 'rgba(255,51,102,0.1)' }
              : { color: '#ffd700', borderColor: 'rgba(255,215,0,0.4)', background: 'rgba(255,215,0,0.1)' }
          }
        >
          {a.severity.toUpperCase()}
        </span>
      </div>
    </div>
  )
}

// ── CAG Audit Finding Card ────────────────────────────────────────────────────

const SEV_STYLES: Record<string, { color: string; bg: string; border: string; label: string }> = {
  HIGH:   { color: '#ff3366', bg: 'rgba(255,51,102,0.08)',  border: 'rgba(255,51,102,0.35)',  label: '🔴 HIGH RISK' },
  MEDIUM: { color: '#ffd700', bg: 'rgba(255,215,0,0.08)',   border: 'rgba(255,215,0,0.35)',   label: '🟡 MEDIUM' },
  LOW:    { color: '#00aaff', bg: 'rgba(0,170,255,0.08)',   border: 'rgba(0,170,255,0.35)',   label: '🔵 LOW' },
}

function CAGCard({ f }: { f: CAGFinding }) {
  const [expanded, setExpanded] = useState(false)
  const sev = SEV_STYLES[f.severity || 'MEDIUM'] ?? SEV_STYLES.MEDIUM

  return (
    <div
      className="p-4 border mb-3 transition-all cursor-pointer"
      style={{ borderColor: sev.border, background: sev.bg }}
      onClick={() => setExpanded(e => !e)}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <span
            className="mono text-[8px] px-2 py-0.5 border font-bold tracking-widest mb-2 inline-block"
            style={{ color: sev.color, borderColor: sev.border, background: 'rgba(0,0,0,0.3)' }}
          >
            {sev.label}
          </span>
          <div className="mono text-[11px] text-white font-bold leading-snug">
            {f.department_name || 'Unknown Department'}
          </div>
          <div className="mono text-[8px] text-dim mt-1">
            {f.paragraph_ref && `${f.paragraph_ref} · `}CAG Report {f.report_year}
          </div>
        </div>
        {f.amount_flagged_lakhs && (
          <div className="text-right flex-shrink-0">
            <div className="mono text-[8px] text-dim mb-1">AMOUNT FLAGGED</div>
            <div className="mono text-lg font-bold" style={{ color: sev.color }}>
              {fmtLakhs(f.amount_flagged_lakhs)}
            </div>
          </div>
        )}
      </div>

      {/* AI Summary */}
      {f.finding_summary && (
        <div className="mono text-[9px] text-dim leading-relaxed mb-3">
          {f.finding_summary}
        </div>
      )}

      {/* Raw text on expand */}
      {expanded && f.finding_raw && (
        <div className="mt-3 pt-3 border-t" style={{ borderColor: sev.border }}>
          <div className="mono text-[8px] text-dim mb-1 tracking-widest">RAW AUDIT TEXT:</div>
          <div className="mono text-[8px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>
            {f.finding_raw}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex justify-between items-center mt-3 pt-2" style={{ borderTop: `1px solid ${sev.border}` }}>
        <span className="mono text-[8px] text-dim">
          {expanded ? '▲ Hide raw text' : '▼ Show raw audit text'}
        </span>
        {f.source_pdf_url && (
          <a
            href={f.source_pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="flex items-center gap-1 mono text-[8px] hover:opacity-80 transition-opacity"
            style={{ color: sev.color }}
          >
            <ExternalLink size={10} />
            Source PDF
          </a>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Alerts() {
  const { financialYear } = useAppStore()

  const { data: utilAlerts, isLoading: loadingUtil, isError: errUtil } = useQuery({
    queryKey: ['low-util', financialYear],
    queryFn: () => fetchLowUtilAlerts(financialYear),
  })

  const { data: cagFindings, isLoading: loadingCAG, isError: errCAG } = useQuery({
    queryKey: ['cag-findings'],
    queryFn: () => fetchCAGFindings(50),
  })

  const highCount  = (cagFindings || []).filter(f => f.severity === 'HIGH').length
  const totalFlags = (cagFindings || []).reduce((s, f) => s + (f.amount_flagged_lakhs || 0), 0)

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="ALERTS & AUDIT FEED"
        subtitle="REAL-TIME FLAGS · CAG IRREGULARITIES · FUND UTILIZATION GAPS"
      />

      {/* Summary bar */}
      {cagFindings && cagFindings.length > 0 && (
        <div className="flex gap-4 px-6 pt-4">
          <div className="panel flex-1 flex items-center gap-3 p-3">
            <AlertTriangle size={16} className="text-red flex-shrink-0" />
            <div>
              <div className="mono text-[8px] text-dim">HIGH RISK FINDINGS</div>
              <div className="mono text-lg text-red font-bold">{highCount}</div>
            </div>
          </div>
          <div className="panel flex-1 flex items-center gap-3 p-3">
            <TrendingDown size={16} className="text-gold flex-shrink-0" />
            <div>
              <div className="mono text-[8px] text-dim">TOTAL AMOUNT FLAGGED</div>
              <div className="mono text-lg text-gold font-bold">{fmtLakhs(totalFlags)}</div>
            </div>
          </div>
          <div className="panel flex-1 flex items-center gap-3 p-3">
            <FileText size={16} className="text-blue flex-shrink-0" />
            <div>
              <div className="mono text-[8px] text-dim">CAG FINDINGS</div>
              <div className="mono text-lg text-blue font-bold">{cagFindings.length}</div>
            </div>
          </div>
        </div>
      )}

      <div className="p-6 flex flex-col md:flex-row gap-6 flex-1 overflow-hidden">

        {/* Left: Low Utilization Alerts */}
        <div className="w-full md:w-2/5 flex flex-col panel overflow-hidden">
          <div className="panel-title border-b border-[#1a2a3a] pb-3 mb-0 flex justify-between items-center">
            <span>⚠️ LOW UTILIZATION FLAGS</span>
            <span className="mono text-[8px] text-dim font-normal">FY {financialYear}</span>
          </div>
          <div className="flex-1 overflow-auto px-4 py-2 custom-scrollbar">
            {loadingUtil && <div className="mono text-[9px] text-dim animate-pulse py-4">Loading alerts...</div>}
            {errUtil && <ErrorBox />}
            {(utilAlerts || []).length === 0 && !loadingUtil && (
              <div className="mono text-[9px] text-dim py-4">No utilization flags. All schemes are on track!</div>
            )}
            {(utilAlerts || []).map((a, i) => <UtilRow key={i} a={a} />)}
          </div>
        </div>

        {/* Right: CAG Audit Feed */}
        <div className="w-full md:w-3/5 flex flex-col overflow-hidden">
          <div className="mono text-[10px] text-dim tracking-widest mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red animate-pulse inline-block" />
            CAG AUDIT FEED — AI-SUMMARIZED IRREGULARITIES
            <span className="mono text-[8px] text-dim ml-2 font-normal border border-[#1a2a3a] px-1.5 py-0.5 bg-white/5">ALL YEARS</span>
          </div>
          <div className="flex-1 overflow-auto custom-scrollbar">
            {loadingCAG && <div className="mono text-[9px] text-dim animate-pulse">Loading audit findings...</div>}
            {errCAG && <ErrorBox />}
            {(cagFindings || []).length === 0 && !loadingCAG && (
              <div className="panel p-6 text-center">
                <div className="mono text-[10px] text-dim mb-2">No CAG findings yet.</div>
                <div className="mono text-[9px] text-dim">
                  Trigger the <span className="text-white">CAG Audit Collector</span> from the Sync Status page.
                </div>
              </div>
            )}
            {(cagFindings || []).map(f => <CAGCard key={f.id} f={f} />)}

            {(cagFindings || []).length > 0 && (
              <div className="mono text-[8px] text-dim text-center mt-4 pb-4">
                💡 Findings are AI-summarized from actual CAG audit paragraphs using Gemini.{' '}
                <a href="https://cag.gov.in/en/audit-report?tags=Jammu+%26+Kashmir" target="_blank" rel="noopener noreferrer" className="text-blue hover:opacity-80">
                  View source reports ↗
                </a>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
