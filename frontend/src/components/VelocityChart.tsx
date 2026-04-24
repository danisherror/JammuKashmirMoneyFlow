import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid, Legend,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import type { SchemeVelocity } from '../lib/api'

interface VelocityChartProps {
  velocity: SchemeVelocity
}

const VERDICT_CONFIG = {
  'ON TRACK':  { color: '#00ff88', bg: 'rgba(0,255,136,0.1)',  border: 'rgba(0,255,136,0.3)',  icon: '✓' },
  'AT RISK':   { color: '#ffd700', bg: 'rgba(255,215,0,0.1)',  border: 'rgba(255,215,0,0.3)',  icon: '⚠' },
  'CRITICAL':  { color: '#ff3366', bg: 'rgba(255,51,102,0.1)', border: 'rgba(255,51,102,0.3)', icon: '✕' },
  'NO DATA':   { color: '#5a7a9a', bg: 'rgba(90,122,154,0.1)', border: 'rgba(90,122,154,0.3)', icon: '—' },
}

function fmtLakhs(n: number | null | undefined) {
  if (n == null) return '—'
  if (n >= 100) return `₹${(n / 100).toFixed(1)} Cr`
  return `₹${n.toLocaleString('en-IN')} L`
}

export default function VelocityChart({ velocity }: VelocityChartProps) {
  const cfg = VERDICT_CONFIG[velocity.verdict] ?? VERDICT_CONFIG['NO DATA']

  // Build chart data: historical points + a projected endpoint
  const chartData = velocity.history.map(h => ({
    date: h.snapshot_date,
    label: format(parseISO(h.snapshot_date), 'dd MMM'),
    utilized: h.funds_utilized_lakhs,
    allocated: h.funds_allocated_lakhs,
    projected: null as number | null,
  }))

  // Append the projected endpoint at Mar 31
  if (velocity.projected_utilized_lakhs != null && velocity.total_allocated_lakhs != null) {
    const fy = velocity.financial_year.split('-')[0]
    chartData.push({
      date: `${parseInt(fy) + 1}-03-31`,
      label: '31 Mar',
      utilized: null as any,
      allocated: velocity.total_allocated_lakhs,
      projected: velocity.projected_utilized_lakhs,
    })
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="mono text-[9px] p-3 space-y-1"
        style={{ background: '#0d1520', border: '1px solid #1a2a3a', minWidth: 180 }}>
        <div className="text-dim tracking-widest mb-2">{label}</div>
        {payload.map((p: any) => (
          p.value != null && (
            <div key={p.name} className="flex justify-between gap-4">
              <span style={{ color: p.color }}>{p.name.toUpperCase()}</span>
              <span className="text-white">{fmtLakhs(p.value)}</span>
            </div>
          )
        ))}
      </div>
    )
  }

  return (
    <div className="panel space-y-4">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="panel-title mb-0">SPENDING VELOCITY & PROJECTION</div>
        {/* Verdict badge */}
        <div
          className="mono text-[10px] font-bold px-4 py-2 flex items-center gap-2"
          style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color }}
        >
          <span style={{ fontSize: 14 }}>{cfg.icon}</span>
          {velocity.verdict}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'DAYS ELAPSED',    val: `${velocity.days_elapsed} days`,         color: '#5a7a9a' },
          { label: 'DAYS REMAINING',  val: `${velocity.days_remaining} days`,        color: '#00aaff' },
          { label: 'DAILY RUN RATE',  val: fmtLakhs(velocity.daily_run_rate_lakhs), color: '#ffd700' },
          { label: 'PROJECTED (Mar 31)', val: fmtLakhs(velocity.projected_utilized_lakhs), color: cfg.color },
        ].map(({ label, val, color }) => (
          <div key={label} className="p-3" style={{ background: '#060a0f', border: '1px solid #1a2a3a' }}>
            <div className="mono text-[7px] text-dim tracking-widest mb-1">{label}</div>
            <div className="mono text-[11px] font-bold" style={{ color }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Surrender risk notice */}
      {velocity.surrender_risk_lakhs != null && velocity.surrender_risk_lakhs > 0 && (
        <div className="mono text-[9px] p-3 flex items-center gap-3"
          style={{ background: 'rgba(255,51,102,0.07)', border: '1px solid rgba(255,51,102,0.25)' }}>
          <span className="text-red text-base">⚠</span>
          <span className="text-dim">
            At current run-rate, approximately{' '}
            <span className="text-white font-bold">{fmtLakhs(velocity.surrender_risk_lakhs)}</span>
            {' '}may be surrendered (unspent) by March 31st if spending pace doesn't accelerate.
          </span>
        </div>
      )}

      {/* Chart */}
      {chartData.length > 1 ? (
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="utilGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#00ff88" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#00ff88" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="projGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={cfg.color} stopOpacity={0.2} />
                <stop offset="95%" stopColor={cfg.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="label"
              tick={{ fill: '#5a7a9a', fontSize: 8, fontFamily: 'Space Mono' }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: '#5a7a9a', fontSize: 8, fontFamily: 'Space Mono' }}
              tickFormatter={v => v >= 100 ? `${(v/100).toFixed(0)}Cr` : `${v}L`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontFamily: 'Space Mono', fontSize: 8, color: '#5a7a9a' }}
            />
            {/* Allocated ceiling line */}
            {velocity.total_allocated_lakhs && (
              <ReferenceLine
                y={velocity.total_allocated_lakhs}
                stroke="#00aaff"
                strokeDasharray="6 3"
                label={{ value: 'ALLOCATED', fill: '#00aaff', fontSize: 8, fontFamily: 'Space Mono' }}
              />
            )}
            {/* Actual utilized */}
            <Area
              type="monotone"
              dataKey="utilized"
              name="Utilized"
              stroke="#00ff88"
              strokeWidth={2}
              fill="url(#utilGrad)"
              connectNulls={false}
              dot={false}
            />
            {/* Projected */}
            <Area
              type="monotone"
              dataKey="projected"
              name="Projected"
              stroke={cfg.color}
              strokeWidth={2}
              strokeDasharray="6 3"
              fill="url(#projGrad)"
              connectNulls={true}
              dot={{ fill: cfg.color, r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="mono text-[9px] text-dim text-center py-8">
          Not enough historical snapshots yet. The chart will populate after the next few weekly runs.
        </div>
      )}
    </div>
  )
}
