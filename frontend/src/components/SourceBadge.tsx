import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { format, parseISO } from 'date-fns'
import { ExternalLink } from 'lucide-react'
import clsx from 'clsx'
import type { FigureSource } from '../lib/api'
import { badgeText, measureLabel, mismatchText, pageRef, sourceKind, type SourceKind } from '../lib/sources'

const STYLES: Record<SourceKind, string> = {
  official: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30',
  live: 'text-sky-300 bg-sky-500/10 border-sky-500/30',
  flagged: 'text-amber-300 bg-amber-500/15 border-amber-500/50',
  unsourced: 'text-orange-300 bg-orange-500/10 border-orange-500/40',
  none: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
}

interface Props {
  source: FigureSource | null | undefined
  /** The figure itself, so a value with no recorded source shows "Unsourced" rather than "No data". */
  value?: number | null
  className?: string
}

/**
 * Small badge saying where a figure comes from (todo.md 2.2a). Hover or tap shows the full label,
 * what the number measures, the fetch date and a link to the source document. A flagged figure
 * (portal and audited accounts differ by > 2%) shows both numbers.
 */
export default function SourceBadge({ source, value, className }: Props) {
  const kind = sourceKind(source, value)
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const popRef = useRef<HTMLDivElement>(null)

  // Position the popover with fixed coordinates so table/panel overflow can't clip it.
  useLayoutEffect(() => {
    if (!open || !btnRef.current) return
    const r = btnRef.current.getBoundingClientRect()
    const width = 288
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8))
    setPos({ top: r.bottom + 6, left })
  }, [open])

  // A tapped (pinned) popover closes on an outside tap, Escape or scroll.
  useEffect(() => {
    if (!pinned) return
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== 'Escape') return
      const target = e.target as Node
      if (e.type === 'pointerdown' && (btnRef.current?.contains(target) || popRef.current?.contains(target))) return
      setPinned(false)
      setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    window.addEventListener('scroll', close, true)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [pinned])

  const mismatch = mismatchText(source)
  const measure = measureLabel(source)
  const page = pageRef(source)
  const fetched = source?.fetched_at ? format(parseISO(source.fetched_at), 'd MMM yyyy, HH:mm') : null

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={(e) => {
          // Badges sit inside clickable cards; don't navigate.
          e.stopPropagation()
          const next = !pinned
          setPinned(next)
          setOpen(next)
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => !pinned && setOpen(false)}
        aria-expanded={open}
        aria-label={`Source: ${source?.label ?? 'no data'}`}
        className={clsx(
          'inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-semibold tracking-wide uppercase leading-none whitespace-nowrap align-middle',
          STYLES[kind],
          className,
        )}
      >
        {badgeText(source, value)}
        {source?.provisional && kind === 'live' && <span className="normal-case font-normal opacity-80">· prov.</span>}
      </button>

      {open && pos && createPortal(
        <div
          ref={popRef}
          role="tooltip"
          onClick={(e) => e.stopPropagation()}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => !pinned && setOpen(false)}
          className="fixed z-[1000] w-72 rounded-lg border border-slate-700 bg-slate-900/95 backdrop-blur p-3 shadow-2xl text-left normal-case tracking-normal"
          style={{ top: pos.top, left: pos.left }}
        >
          <div className="text-[11px] font-semibold text-slate-100 leading-snug">{source?.label ?? 'No data'}</div>
          {mismatch && (
            <div className="mt-2 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-[11px] text-amber-200 leading-snug">
              ⚑ {mismatch}. The audited figure is shown.
            </div>
          )}
          <dl className="mt-2 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-[10px]">
            {measure && (<><dt className="text-slate-500">Measures</dt><dd className="text-slate-300">{measure}</dd></>)}
            {page && (<><dt className="text-slate-500">Page</dt><dd className="text-slate-300">{page}</dd></>)}
            {fetched && (<><dt className="text-slate-500">Fetched</dt><dd className="text-slate-300">{fetched}</dd></>)}
            {source?.provisional && (<><dt className="text-slate-500">Status</dt><dd className="text-slate-300">Provisional: may change once audited</dd></>)}
          </dl>
          {source?.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-[10px] font-semibold text-sky-400 hover:text-sky-300"
            >
              <ExternalLink size={10} /> Open source document{page ? ` (${page})` : ''}
            </a>
          )}
        </div>,
        document.body,
      )}
    </>
  )
}
