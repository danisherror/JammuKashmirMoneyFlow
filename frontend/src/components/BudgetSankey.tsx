import React, { useMemo } from 'react'
import { Sankey, Tooltip, ResponsiveContainer } from 'recharts'
import { BudgetOverview, DepartmentSummary, SchemeSummary } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'

interface BudgetSankeyProps {
  overview: BudgetOverview
  departments: DepartmentSummary[]
  schemes: SchemeSummary[]
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null
  const data = payload[0].payload
  
  if (data.source !== undefined && data.target !== undefined) {
    // It's a link
    return (
      <div className="panel mono text-[10px] p-3" style={{ minWidth: 160, background: '#0d1520', border: '1px solid #1a2a3a' }}>
        <div className="text-dim mb-1 tracking-widest text-[8px]">FUND FLOW</div>
        <div className="text-[#c8d8e8] mb-1">
          {data.source.name} → {data.target.name}
        </div>
        <div className="text-[#00aaff] font-bold">
          {fmtLakhs(data.value)}
        </div>
        {data.percentOfTotal && (
          <div className="text-[#00ff88] mt-1 text-[9px]">
            {fmtPct(data.percentOfTotal)} of UT Budget
          </div>
        )}
      </div>
    )
  }
  
  // It's a node
  return (
    <div className="panel mono text-[10px] p-3" style={{ minWidth: 140, background: '#0d1520', border: '1px solid #1a2a3a' }}>
      <div className="text-dim mb-1 tracking-widest text-[8px]">NODE</div>
      <div className="text-[#c8d8e8] mb-1 font-bold">{data.name}</div>
      <div className="text-[#00aaff]">
        {fmtLakhs(data.value)}
      </div>
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
    const nodes = [
      { name: 'Central Govt', fill: '#00aaff' }, // 0
      { name: 'J&K Tax Revenue', fill: '#00ff88' }, // 1
      { name: 'J&K Finance Dept', fill: '#ffb300' }, // 2
    ]
    
    topDepts.forEach(d => {
      nodes.push({ name: d.name.split(' (')[0].substring(0, 25), fill: '#5a7a9a' })
    })
    nodes.push({ name: 'Other Departments', fill: '#3a4a5a' }) // The last node

    // 4. Build Links
    const links = [
      { 
        source: 0, target: 2, value: centralGrants, 
        percentOfTotal: (centralGrants / overview.total_budget_lakhs) * 100 
      },
      { 
        source: 1, target: 2, value: utRevenue, 
        percentOfTotal: (utRevenue / overview.total_budget_lakhs) * 100 
      }
    ]

    let targetIndex = 3
    topDepts.forEach(d => {
      links.push({
        source: 2,
        target: targetIndex,
        value: d.budget_estimate_lakhs,
        percentOfTotal: (d.budget_estimate_lakhs / overview.total_budget_lakhs) * 100
      })
      targetIndex++
    })

    if (otherDeptsSum > 0) {
      links.push({
        source: 2,
        target: targetIndex,
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
          node={{ stroke: '#0d1520', strokeWidth: 2 }}
          nodePadding={50}
          margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
          link={{ stroke: 'rgba(255,255,255,0.1)' }}
        >
          <Tooltip content={<CustomTooltip />} />
        </Sankey>
      </ResponsiveContainer>
    </div>
  )
}
