import React, { useMemo } from 'react'
import { Sankey, Tooltip, ResponsiveContainer } from 'recharts'
import { BudgetOverview, DepartmentSummary, SchemeSummary } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'

interface BudgetSankeyProps {
  overview: BudgetOverview
  departments: DepartmentSummary[]
  schemes: SchemeSummary[]
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

export default function BudgetSankey({ overview, departments, schemes }: BudgetSankeyProps) {
  const data = useMemo(() => {
    if (!overview || !departments || !schemes) return { nodes: [], links: [] }

    // 1. Calculate Central vs UT Revenue using scheme types
    // We sum up the total_outlay_lakhs for CSS and CENTRAL schemes to represent Central Grants
    // The rest of the total_budget_lakhs is treated as J&K Tax / Own Revenue
    let centralGrants = 0
    schemes.forEach(s => {
      if ((s.scheme_type === 'css' || s.scheme_type === 'central') && s.total_outlay_lakhs) {
        centralGrants += s.total_outlay_lakhs
      }
    })

    // Fallback if no schemes found or central grants exceed total budget
    if (centralGrants === 0) centralGrants = overview.total_budget_lakhs * 0.68
    if (centralGrants > overview.total_budget_lakhs) centralGrants = overview.total_budget_lakhs * 0.8

    const utRevenue = Math.max(0, overview.total_budget_lakhs - centralGrants)

    // 2. Identify top departments and group others
    const topDeptsCount = 8
    const sortedDepts = [...departments].sort((a, b) => b.budget_estimate_lakhs - a.budget_estimate_lakhs)
    const topDepts = sortedDepts.slice(0, topDeptsCount)

    const topDeptsSum = topDepts.reduce((sum, d) => sum + d.budget_estimate_lakhs, 0)
    const otherDeptsSum = Math.max(0, overview.total_budget_lakhs - topDeptsSum)

    // 3. Build Nodes
    const nodes: any[] = [
      { name: 'Central Govt', fill: 'var(--accent-blue)', type: 'Funding Source', totalBudget: overview.total_budget_lakhs }, // 0
      { name: 'J&K Tax Revenue', fill: 'var(--accent-green)', type: 'Funding Source', totalBudget: overview.total_budget_lakhs }, // 1
      { name: 'J&K Finance Dept', fill: 'var(--accent-gold)', type: 'Distributor', totalBudget: overview.total_budget_lakhs }, // 2
    ]

    topDepts.forEach(d => {
      nodes.push({
        name: d.name.split(' (')[0].substring(0, 25),
        fill: '#64748b',
        type: 'Department',
        expenditure: d.total_expenditure_lakhs,
        utilizationPct: d.budget_estimate_lakhs > 0 ? (d.total_expenditure_lakhs / d.budget_estimate_lakhs) * 100 : 0,
        totalBudget: overview.total_budget_lakhs
      })
    })

    if (otherDeptsSum > 0) {
      nodes.push({
        name: 'Other Departments',
        fill: '#475569',
        type: 'Aggregated Group',
        totalBudget: overview.total_budget_lakhs
      })
    }

    // 4. Build Links
    const links = []

    if (centralGrants > 0) {
      links.push({
        source: 0, target: 2, value: centralGrants,
        percentOfTotal: (centralGrants / overview.total_budget_lakhs) * 100
      })
    }

    if (utRevenue > 0) {
      links.push({
        source: 1, target: 2, value: utRevenue,
        percentOfTotal: (utRevenue / overview.total_budget_lakhs) * 100
      })
    }

    let targetIndex = 3
    topDepts.forEach(d => {
      if (d.budget_estimate_lakhs > 0) {
        links.push({
          source: 2,
          target: targetIndex,
          value: d.budget_estimate_lakhs,
          percentOfTotal: (d.budget_estimate_lakhs / overview.total_budget_lakhs) * 100
        })
      }
      targetIndex++
    })

    if (otherDeptsSum > 0) {
      links.push({
        source: 2,
        target: targetIndex, // This will correctly point to the 'Other Departments' node
        value: otherDeptsSum,
        percentOfTotal: (otherDeptsSum / overview.total_budget_lakhs) * 100
      })
    }

    return { nodes, links }
  }, [overview, departments, schemes])

  if (data.nodes.length === 0) return null

  return (
    <div className="panel xl:col-span-3">
      <div className="panel-title">BUDGET FLOW: SOURCE TO ALLOCATION</div>
      <ResponsiveContainer width="100%" height={400}>
        <Sankey
          data={data}
          node={{ stroke: 'var(--panel-border)', strokeWidth: 1 }}
          nodePadding={50}
          margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          link={{ stroke: 'rgba(255,255,255,0.1)' }}
        >
          <Tooltip content={<CustomTooltip nodes={data.nodes} />} />
        </Sankey>
      </ResponsiveContainer>
    </div>
  )
}
