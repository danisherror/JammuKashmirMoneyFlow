import clsx from 'clsx'
import type { FigureSource } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import SourceBadge from './SourceBadge'

interface Props {
  label: string
  value: string | number | null
  sub?: string
  direction?: 'up' | 'down' | 'neutral'
  format?: 'lakhs' | 'pct' | 'raw'
  className?: string
  /** Where the figure comes from; shows a source badge when given (todo.md 2.2a). */
  source?: FigureSource | null
}

export default function KpiCard({ label, value, sub, direction = 'neutral', format = 'raw', className, source }: Props) {
  const display =
    format === 'lakhs' ? fmtLakhs(value as number) :
    format === 'pct'   ? fmtPct(value as number) :
    value ?? '—'

  // Map direction to the new CSS variables
  const colorMap = {
    up: 'var(--accent-green)',
    down: 'var(--accent-red)',
    neutral: 'var(--accent-blue)',
  }
  
  const bgMap = {
    up: 'rgba(52, 211, 153, 0.05)',
    down: 'rgba(251, 113, 133, 0.05)',
    neutral: 'rgba(56, 189, 248, 0.05)',
  }

  const barColor = colorMap[direction]
  const bgColor = bgMap[direction]

  return (
    <div 
      className={clsx(
        'panel flex flex-col gap-2 overflow-hidden transition-all duration-300 hover:-translate-y-1', 
        className
      )}
      style={{ 
        background: `linear-gradient(to bottom right, var(--panel-bg), ${bgColor})`,
      }}
    >
      {/* Soft top glow line */}
      <div 
        className="absolute top-0 left-0 right-0 h-1" 
        style={{ 
          background: `linear-gradient(90deg, transparent, ${barColor}, transparent)`,
          opacity: 0.6
        }} 
      />
      
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-[10px] text-slate-400 tracking-widest uppercase">{label}</div>
        {source !== undefined && <SourceBadge source={source} />}
      </div>
      
      <div
        className="display text-4xl tracking-tight leading-none font-bold"
        style={{ 
          color: barColor, 
          textShadow: `0 4px 20px ${barColor}40` 
        }}
      >
        {display as string}
      </div>
      
      {sub && <div className="text-xs text-slate-500 font-medium mt-auto">{sub}</div>}
    </div>
  )
}
