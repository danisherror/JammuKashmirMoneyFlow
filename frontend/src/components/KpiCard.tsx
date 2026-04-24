import clsx from 'clsx'
import { fmtLakhs, fmtPct } from '../lib/utils'

interface Props {
  label: string
  value: string | number | null
  sub?: string
  direction?: 'up' | 'down' | 'neutral'
  format?: 'lakhs' | 'pct' | 'raw'
  className?: string
}

export default function KpiCard({ label, value, sub, direction = 'neutral', format = 'raw', className }: Props) {
  const display =
    format === 'lakhs' ? fmtLakhs(value as number) :
    format === 'pct'   ? fmtPct(value as number) :
    value ?? '—'

  const barColor =
    direction === 'up'   ? '#00ff88' :
    direction === 'down' ? '#ff3366' : '#ffd700'

  return (
    <div className={clsx('panel flex flex-col gap-1 cursor-default', className)}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: barColor }} />
      <div className="mono text-[8px] text-dim tracking-widest uppercase">{label}</div>
      <div
        className="display text-2xl tracking-wide leading-none"
        style={{ color: barColor, textShadow: `0 0 16px ${barColor}66` }}
      >
        {display as string}
      </div>
      {sub && <div className="mono text-[9px] text-dim">{sub}</div>}
    </div>
  )
}
