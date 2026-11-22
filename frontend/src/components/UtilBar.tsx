import { fmtPct } from '../lib/utils'

interface Props {
  /** null when unknown: the bar stays empty rather than inventing a ratio. */
  allocated: number | null
  released?: number | null
  utilized: number | null
  showLabels?: boolean
}

export default function UtilBar({ allocated, released, utilized, showLabels = true }: Props) {
  const alloc = allocated ?? 0
  const rel = released ?? 0
  const util = utilized ?? 0
  const relPct  = alloc > 0 ? Math.min((rel  / alloc) * 100, 100) : 0
  const utilPct = alloc > 0 ? Math.min((util / alloc) * 100, 100) : 0
  const known = alloc > 0 && utilized != null

  return (
    <div className="w-full">
      {showLabels && (
        <div className="flex justify-between mb-1.5 items-end">
          <span className="text-[9px] font-semibold text-slate-500 tracking-widest uppercase">Allocated</span>
          {released != null && (
            <span className="text-[9px] font-semibold text-blue-400 tracking-widest uppercase">Released</span>
          )}
          <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: utilPct >= 75 ? 'var(--accent-green)' : utilPct >= 40 ? 'var(--accent-gold)' : 'var(--accent-red)' }}>
            {known ? `${fmtPct(utilPct)} Utilized` : 'No data'}
          </span>
        </div>
      )}
      <div className="h-2.5 w-full relative rounded-full overflow-hidden bg-slate-800/50 shadow-inner">
        {/* Released layer */}
        {released != null && (
          <div
            className="absolute top-0 left-0 h-full rounded-full transition-all duration-700"
            style={{ width: `${relPct}%`, background: 'rgba(56, 189, 248, 0.3)' }}
          />
        )}
        {/* Utilized layer */}
        <div
          className="absolute top-0 left-0 h-full rounded-full transition-all duration-700 shadow-[0_0_10px_rgba(255,255,255,0.1)]"
          style={{
            width: `${utilPct}%`,
            background: utilPct >= 75 ? 'linear-gradient(90deg, rgba(52,211,153,0.6), rgba(52,211,153,1))' : 
                        utilPct >= 40 ? 'linear-gradient(90deg, rgba(251,191,36,0.6), rgba(251,191,36,1))' : 
                        'linear-gradient(90deg, rgba(251,113,133,0.6), rgba(251,113,133,1))',
          }}
        />
      </div>
    </div>
  )
}
