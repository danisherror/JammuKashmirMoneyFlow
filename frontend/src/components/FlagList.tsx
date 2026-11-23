import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import type { AccountabilityFlag, FlagKind } from '../lib/api'
import { fmtLakhs } from '../lib/utils'
import { FLAG_KINDS, countFlags, pdfPageUrl } from '../lib/breakdown'

interface Props {
  flags: AccountabilityFlag[]
  /** Show the grant name and a link to its breakdown on each row (Alerts page). */
  showGrant?: boolean
  /** Rows shown per kind before "show all". */
  initial?: number
}

const TONE: Record<FlagKind, string> = {
  excess_over_grant: '#ff3366',
  savings_not_surrendered: '#ffd700',
  supplementary_not_needed: '#ffd700',
  fully_unutilised: '#f97316',
  reasons_not_communicated: '#fbbf24',
}

/**
 * Accountability flags (todo.md 2.2b) grouped by kind, each restating the printed figures and
 * linking to its page in the CAG PDF.
 */
export default function FlagList({ flags, showGrant = false, initial = 5 }: Props) {
  const counts = countFlags(flags).filter(c => c.count > 0)
  const [selected, setSelected] = useState<FlagKind | null>(null)
  const [expanded, setExpanded] = useState(false)
  const kind = selected ?? counts[0]?.kind ?? null

  if (counts.length === 0) {
    return <p className="mono text-[10px] text-dim">No flags: the printed figures show none of these patterns.</p>
  }
  const rows = flags.filter(f => f.kind === kind)
  const shown = expanded ? rows : rows.slice(0, initial)
  const hint = FLAG_KINDS.find(k => k.kind === kind)?.hint

  return (
    <div className="mono text-[10px]">
      <div className="flex flex-wrap gap-2 mb-3" role="tablist" aria-label="Flag kinds">
        {counts.map(c => (
          <button key={c.kind} role="tab" aria-selected={c.kind === kind}
            onClick={() => { setSelected(c.kind); setExpanded(false) }}
            className="border px-2 py-1 text-[9px] transition-colors"
            style={c.kind === kind
              ? { color: TONE[c.kind], borderColor: TONE[c.kind], background: 'rgba(255,255,255,0.04)' }
              : { color: '#5a7a9a', borderColor: '#1a2a3a' }}>
            {c.label} · {c.count}
          </button>
        ))}
      </div>
      {hint && <p className="text-dim text-[9px] mb-2">{hint}.</p>}
      <ul>
        {shown.map((f, i) => {
          const href = pdfPageUrl(f.source)
          return (
            <li key={`${f.grant_no}-${f.section}-${f.block_kind}-${f.head_code}-${i}`}
              className="py-2 border-t flex flex-wrap items-baseline justify-between gap-2" style={{ borderColor: '#1a2a3a' }}>
              <div className="min-w-0 flex-1">
                {showGrant && (
                  <div className="text-[9px] text-dim mb-0.5">
                    <Link to={`/grants/${f.grant_no}`} className="hover:text-white hover:underline">
                      Grant {f.grant_no} · {f.grant_name}
                    </Link>
                    {f.department_id != null && (
                      <> · <Link to={`/departments/${f.department_id}`} className="text-sky-300 hover:underline">department</Link></>
                    )}
                  </div>
                )}
                <div className="text-slate-300">{f.detail}</div>
              </div>
              <div className="flex items-center gap-3 whitespace-nowrap">
                {f.amount_lakhs != null && <span style={{ color: TONE[f.kind] }}>{fmtLakhs(f.amount_lakhs)}</span>}
                {f.share_pct != null && <span style={{ color: TONE[f.kind] }}>{f.share_pct}%</span>}
                {href && (
                  <a href={href} target="_blank" rel="noreferrer" title={f.source.label}
                    className="inline-flex items-center gap-1 text-sky-300 hover:underline">
                    p.{f.source.page} <ExternalLink size={10} aria-hidden />
                  </a>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      {rows.length > initial && (
        <button onClick={() => setExpanded(e => !e)} className="mt-2 text-[9px] text-sky-300 hover:underline">
          {expanded ? 'Show fewer' : `Show all ${rows.length}`}
        </button>
      )}
    </div>
  )
}
