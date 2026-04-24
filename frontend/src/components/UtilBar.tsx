import { fmtPct } from '../lib/utils'

interface Props {
  allocated: number
  released?: number | null
  utilized: number | null
  showLabels?: boolean
}

export default function UtilBar({ allocated, released, utilized, showLabels = true }: Props) {
  const rel = released ?? 0
  const util = utilized ?? 0
  const relPct  = allocated > 0 ? Math.min((rel  / allocated) * 100, 100) : 0
  const utilPct = allocated > 0 ? Math.min((util / allocated) * 100, 100) : 0

  return (
    <div className="w-full">
      {showLabels && (
        <div className="flex justify-between mb-1 items-end">
          <span className="mono text-[8px] text-dim">ALLOCATED</span>
          {released != null && (
            <span className="mono text-[8px] text-purple">RELEASED</span>
          )}
          <span className="mono text-[8px]" style={{ color: utilPct >= 75 ? '#00ff88' : utilPct >= 40 ? '#ffd700' : '#ff3366' }}>
            {fmtPct(utilPct)} UTILIZED
          </span>
        </div>
      )}
      <div className="h-3 w-full relative" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid #1a2a3a' }}>
        {/* Released layer */}
        {released != null && (
          <div
            className="absolute top-0 left-0 h-full"
            style={{ width: `${relPct}%`, background: 'rgba(0,170,255,0.25)' }}
          />
        )}
        {/* Utilized layer */}
        <div
          className="absolute top-0 left-0 h-full transition-all duration-700"
          style={{
            width: `${utilPct}%`,
            background: utilPct >= 75 ? 'rgba(0,255,136,0.5)' : utilPct >= 40 ? 'rgba(255,215,0,0.5)' : 'rgba(255,51,102,0.4)',
            borderRight: utilPct > 0 ? `2px solid ${utilPct >= 75 ? '#00ff88' : utilPct >= 40 ? '#ffd700' : '#ff3366'}` : 'none',
          }}
        />
      </div>
    </div>
  )
}
