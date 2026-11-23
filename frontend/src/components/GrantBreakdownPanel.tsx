import { ExternalLink } from 'lucide-react'
import type { FigureSource, GrantBreakdown, HeadNode, HeadRowItem } from '../lib/api'
import { fmtLakhs } from '../lib/utils'
import FlagList from './FlagList'
import { biggestUnspent, categoryLabel, headCodePath, nodeTotal, pdfPageUrl } from '../lib/breakdown'

const BORDER = { borderColor: '#1a2a3a' }

function PageLink({ source }: { source: FigureSource }) {
  const href = pdfPageUrl(source)
  if (!href) return null
  return (
    <a href={href} target="_blank" rel="noreferrer" title={source.label}
      className="inline-flex items-center gap-1 text-sky-300 hover:underline whitespace-nowrap">
      p.{source.page} <ExternalLink size={10} aria-hidden />
    </a>
  )
}

function Tag({ children, tone = 'dim' }: { children: React.ReactNode; tone?: 'dim' | 'amber' | 'red' }) {
  const cls = tone === 'amber' ? 'text-amber-300 border-amber-500/40'
    : tone === 'red' ? 'text-rose-300 border-rose-500/40' : 'text-dim border-slate-600/40'
  return <span className={`inline-block border px-1 py-px text-[8px] uppercase tracking-wider ${cls}`}>{children}</span>
}

function RowTags({ row }: { row: HeadRowItem }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Tag tone={row.category === 'excess' || row.category === 'without_provision' ? 'red' : 'dim'}>
        {categoryLabel(row.category)}
      </Tag>
      {row.reasons_not_communicated && <Tag tone="amber">Reasons not communicated</Tag>}
      {row.printed_error && <span title={row.printed_error}><Tag tone="amber">Doesn't add up in PDF</Tag></span>}
    </span>
  )
}

function HeadRow({ row }: { row: HeadRowItem }) {
  return (
    <li className="py-1.5 border-t" style={BORDER}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <RowTags row={row} />
        <span className="text-dim">
          grant {fmtLakhs(row.final_grant_lakhs)} · spent {fmtLakhs(row.expenditure_lakhs)}
          {row.saving_lakhs ? ` · saving ${fmtLakhs(row.saving_lakhs)}` : ''}
          {row.excess_lakhs ? ` · excess ${fmtLakhs(row.excess_lakhs)}` : ''}
          {' · '}<PageLink source={row.source} />
        </span>
      </div>
      {row.remark && <blockquote className="mt-1 pl-2 border-l text-slate-300" style={BORDER}>“{row.remark}”</blockquote>}
    </li>
  )
}

function Node({ node, depth }: { node: HeadNode; depth: number }) {
  const grant = nodeTotal(node, 'final_grant_lakhs')
  return (
    <details className={depth ? 'ml-3' : ''}>
      <summary className="cursor-pointer py-1 hover:text-white">
        <span className="text-dim">{node.code}</span> {node.name || <em className="text-dim">unnamed</em>}
        {grant !== null && <span className="text-dim"> — {fmtLakhs(grant)} in commented heads</span>}
      </summary>
      <div className="ml-3">
        {node.rows.length > 0 && <ul>{node.rows.map(r => <HeadRow key={`${r.head_code}-${r.note_number}`} row={r} />)}</ul>}
        {node.children.map(child => <Node key={child.head_code} node={child} depth={depth + 1} />)}
      </div>
    </details>
  )
}

interface Props {
  breakdown: GrantBreakdown
  /** Set when showing a different year than the one selected, to say why. */
  yearNote?: string
}

/**
 * Where a grant went (todo.md 2.2b): Voted/Charged blocks, the biggest unspent heads with the
 * official reason, the head tree and the verbatim notes, each linked to its page in the CAG PDF.
 */
export default function GrantBreakdownPanel({ breakdown, yearNote }: Props) {
  const unspent = biggestUnspent(breakdown)
  const sections = ['revenue', 'capital'] as const

  return (
    <div className="space-y-4">
      <div className="panel">
        <div className="panel-title">WHERE THE MONEY WENT — AUDITED {breakdown.financial_year}</div>
        {yearNote && <p className="mono text-[9px] text-amber-300 mb-2">{yearNote}</p>}
        <p className="mono text-[9px] text-dim mb-3 leading-relaxed">
          From the grant pages of the CAG Appropriation Accounts
          ({breakdown.grants.map(g => `grant ${g.grant_no}, ${g.name}`).join('; ')}). The notes list only the
          heads the CAG commented on, so they don't add up to the grant; the blocks below do.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full mono text-[10px]">
            <caption className="sr-only">Voted and charged blocks, ₹</caption>
            <thead>
              <tr className="text-dim text-left">
                <th className="py-1 pr-2 font-normal">Section</th>
                <th className="py-1 pr-2 font-normal text-right">Original</th>
                <th className="py-1 pr-2 font-normal text-right">Suppl.</th>
                <th className="py-1 pr-2 font-normal text-right">Final grant</th>
                <th className="py-1 pr-2 font-normal text-right">Spent</th>
                <th className="py-1 pr-2 font-normal text-right">Saving / excess</th>
                <th className="py-1 pr-2 font-normal text-right">Surrendered</th>
                <th className="py-1 font-normal text-right">Page</th>
              </tr>
            </thead>
            <tbody>
              {breakdown.section_blocks.map(b => (
                <tr key={`${b.grant_no}-${b.section}-${b.kind}`} className="border-t" style={BORDER}>
                  <td className="py-1 pr-2 capitalize whitespace-nowrap">
                    {breakdown.grants.length > 1 && `G${b.grant_no} `}{b.section} · {b.kind}
                  </td>
                  <td className="py-1 pr-2 text-right">{fmtLakhs(b.original_lakhs)}</td>
                  <td className="py-1 pr-2 text-right">{fmtLakhs(b.supplementary_lakhs)}</td>
                  <td className="py-1 pr-2 text-right">{fmtLakhs(b.final_grant_lakhs)}</td>
                  <td className="py-1 pr-2 text-right">{fmtLakhs(b.expenditure_lakhs)}</td>
                  <td className={`py-1 pr-2 text-right ${b.excess_lakhs ? 'text-red' : ''}`}>
                    {b.excess_lakhs ? `+${fmtLakhs(b.excess_lakhs)} excess` : fmtLakhs(b.saving_lakhs)}
                  </td>
                  <td className="py-1 pr-2 text-right">{fmtLakhs(b.surrendered_lakhs)}</td>
                  <td className="py-1 text-right"><PageLink source={b.source} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title">ACCOUNTABILITY FLAGS</div>
        <FlagList flags={breakdown.flags ?? []} />
      </div>

      <div className="panel">
        <div className="panel-title">BIGGEST UNSPENT ITEMS</div>
        {unspent.length === 0 ? (
          <p className="mono text-[10px] text-dim">The notes list no unspent heads for this grant.</p>
        ) : (
          <ol className="mono text-[10px] space-y-3">
            {unspent.map(({ row, unspent: amount }, i) => (
              <li key={`${row.head_code}-${row.note_number}`} className="border-t pt-2" style={BORDER}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span><span className="text-dim">{i + 1}.</span> {row.head_name}</span>
                  <span className="text-gold whitespace-nowrap">{fmtLakhs(amount)} unspent</span>
                </div>
                <div className="text-dim text-[9px] mt-0.5 flex flex-wrap gap-2 items-center">
                  <span>{headCodePath(row)}</span>
                  <span>of {fmtLakhs(row.final_grant_lakhs)}</span>
                  <RowTags row={row} />
                  <PageLink source={row.source} />
                </div>
                <blockquote className="mt-1 pl-2 border-l text-slate-300" style={BORDER}>
                  {row.remark ? `“${row.remark}”` : <em className="text-dim">No remark printed.</em>}
                </blockquote>
              </li>
            ))}
          </ol>
        )}
      </div>

      {sections.map(section => {
        const nodes = breakdown.tree.filter(n => n.section === section)
        if (nodes.length === 0) return null
        return (
          <div key={section} className="panel">
            <div className="panel-title">{section.toUpperCase()} — HEADS COMMENTED ON</div>
            <div className="mono text-[10px]">
              {nodes.map(n => <Node key={`${n.grant_no}-${n.head_code}`} node={n} depth={0} />)}
            </div>
          </div>
        )
      })}

      {breakdown.notes.length > 0 && (
        <details className="panel">
          <summary className="panel-title cursor-pointer">NOTES AND COMMENTS (VERBATIM)</summary>
          <ol className="mono text-[10px] space-y-2 mt-2">
            {breakdown.notes.map(n => (
              <li key={`${n.grant_no}-${n.number}`} className="border-t pt-2" style={BORDER}>
                <div className="flex flex-wrap gap-2 items-center text-dim text-[9px]">
                  <span>{breakdown.grants.length > 1 && `Grant ${n.grant_no}, `}note {n.number}</span>
                  {n.section && <span className="capitalize">{n.section}{n.kind ? ` · ${n.kind}` : ''}</span>}
                  <Tag>{categoryLabel(n.category)}</Tag>
                  {n.reasons_not_communicated && <Tag tone="amber">Reasons not communicated</Tag>}
                  <PageLink source={n.source} />
                </div>
                <p className="mt-1 text-slate-300 leading-relaxed">{n.text}</p>
              </li>
            ))}
          </ol>
        </details>
      )}

      {breakdown.issues.length > 0 && (
        <div className="panel">
          <div className="panel-title">KEPT ASIDE BY THE PARSER</div>
          <ul className="mono text-[9px] text-dim space-y-1">
            {breakdown.issues.map((issue, i) => <li key={i}>{issue.kind.replace('_', ' ')}: {issue.text}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
