import { useMemo } from 'react'
import { Sankey, Tooltip, ResponsiveContainer } from 'recharts'
import type { BudgetOverview, DepartmentSummary } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import SourceBadge from './SourceBadge'

interface BudgetSankeyProps {
  overview: BudgetOverview
  departments: DepartmentSummary[]
}

const CustomTooltip = ({ active, payload, nodes }: any) => {
  if (!active || !payload || !payload.length) return null

  const data = payload[0].payload || payload[0]
  const isLink = data.source !== undefined && data.target !== undefined

  if (isLink) {
    // Recharts sometimes passes source/target as objects, or sometimes as indices.
    const sourceName = data.source?.name || (typeof data.source === 'number' && nodes ? nodes[data.source]?.name : 'Source')
    const targetName = data.target?.name || (typeof data.target === 'number' && nodes ? nodes[data.target]?.name : 'Target')

    return (
      <div className="panel p-4 min-w-[200px] z-50">
        <div className="text-[10px] font-bold text-slate-400 mb-2 tracking-widest uppercase">Fund Flow</div>
        <div className="text-sm font-medium text-slate-200 mb-1">
          {sourceName} → {targetName}
        </div>
        <div className="text-lg font-bold text-blue-400">
          {fmtLakhs(data.value)}
        </div>
        {data.percentOfTotal && (
          <div className="text-[11px] font-semibold text-emerald-400 mt-2 bg-emerald-400/10 inline-block px-2 py-1 rounded">
            {fmtPct(data.percentOfTotal)} of UT Budget
          </div>
        )}
      </div>
    )
  }

  // It's a node
  const nodeType = data.type || 'Entity'
  const utilPct = data.utilizationPct
  const exp = data.expenditure

  return (
    <div className="panel p-4 min-w-[200px] z-50">
      <div className="text-[10px] font-bold text-slate-400 mb-2 tracking-widest uppercase">{nodeType}</div>
      <div className="text-sm font-medium text-slate-200 mb-2 border-b border-slate-700/50 pb-2">{data.name || payload[0].name}</div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-3 mt-2">
        <div className="flex flex-col">
          <span className="text-[9px] text-slate-500 uppercase tracking-wider">Total Volume</span>
          <span className="text-sm font-bold text-blue-400">{fmtLakhs(data.value)}</span>
        </div>

        {data.totalBudget && (
          <div className="flex flex-col">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">% of UT Budget</span>
            <span className="text-sm font-bold text-blue-300">{fmtPct((data.value / data.totalBudget) * 100)}</span>
          </div>
        )}

        {exp !== undefined && (
          <div className="flex flex-col col-span-2">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Amount Utilized</span>
            <span className="text-sm font-bold text-emerald-400">{fmtLakhs(exp)}</span>
          </div>
        )}
      </div>

      {utilPct !== undefined && utilPct > 0 && (
        <div className="mt-3 pt-2 border-t border-slate-700/50">
          <div className="flex justify-between items-center mb-1">
            <span className="text-[9px] text-slate-500 uppercase tracking-wider">Absorption Rate</span>
            <span className="text-[10px] font-bold" style={{ color: utilPct >= 70 ? 'var(--accent-green)' : utilPct >= 40 ? 'var(--accent-gold)' : 'var(--accent-red)' }}>
              {fmtPct(utilPct)}
            </span>
          </div>
          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(utilPct, 100)}%`,
                background: utilPct >= 70 ? 'var(--accent-green)' : utilPct >= 40 ? 'var(--accent-gold)' : 'var(--accent-red)'
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Total budget → top departments → everything else. Only sourced figures are drawn: there is no
 * published Central-vs-UT funding split here yet, so none is shown (an earlier version guessed one).
 */
export default function BudgetSankey({ overview, departments }: BudgetSankeyProps) {
  const total = overview.total_budget_lakhs
  const officialTotal = overview.sources.total_budget_lakhs?.source_type === 'official'

  const data = useMemo(() => {
    if (total == null || total <= 0) return { nodes: [], links: [] }

    const known = departments.filter(d => d.budget_estimate_lakhs != null && d.budget_estimate_lakhs > 0)
    const topDepts = [...known].sort((a, b) => b.budget_estimate_lakhs! - a.budget_estimate_lakhs!).slice(0, 8)
    const topSum = topDepts.reduce((sum, d) => sum + d.budget_estimate_lakhs!, 0)
    const otherSum = Math.max(0, total - topSum)

    const nodes: any[] = [
      { name: officialTotal ? 'UT total (final grant)' : 'UT total', fill: 'var(--accent-gold)', type: 'Total', totalBudget: total },
    ]
    const links: any[] = []

    topDepts.forEach(d => {
      links.push({
        source: 0, target: nodes.length, value: d.budget_estimate_lakhs!,
        percentOfTotal: (d.budget_estimate_lakhs! / total) * 100,
      })
      nodes.push({
        name: d.name.split(' (')[0].substring(0, 25),
        fill: '#64748b',
        type: 'Department',
        // undefined (not 0) when utilisation is unknown, so the tooltip hides it
        expenditure: d.utilized_lakhs ?? undefined,
        utilizationPct: d.utilization_pct ?? undefined,
        totalBudget: total,
      })
    })

    if (otherSum > 0) {
      links.push({ source: 0, target: nodes.length, value: otherSum, percentOfTotal: (otherSum / total) * 100 })
      nodes.push({
        name: officialTotal ? 'Other grants' : 'Other departments',
        fill: '#475569',
        type: 'Aggregated Group',
        totalBudget: total,
      })
    }

    return { nodes, links }
  }, [total, officialTotal, departments])

  return (
    <div className="panel xl:col-span-3">
      <div className="flex items-center justify-between gap-2">
        <div className="panel-title">BUDGET FLOW: TOTAL TO DEPARTMENTS</div>
        <SourceBadge source={overview.sources.total_budget_lakhs} />
      </div>
      {data.links.length === 0 ? (
        <div className="h-40 flex items-center justify-center mono text-[10px] text-dim">
          No budget total for FY {overview.financial_year} in this view
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={400}>
            <Sankey
              data={data}
              node={{ stroke: 'var(--panel-border)', strokeWidth: 1 }}
              nodePadding={30}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              link={{ stroke: 'rgba(255,255,255,0.1)' }}
            >
              <Tooltip content={<CustomTooltip nodes={data.nodes} />} />
            </Sankey>
          </ResponsiveContainer>
          <div className="mono text-[9px] text-dim mt-1">
            Each department uses its own source (see the Departments page for badges). The funding split between
            Central transfers and J&amp;K&apos;s own revenue is not shown: no source for it has been loaded yet.
          </div>
        </>
      )}
    </div>
  )
}
