import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { useAppStore } from '../store'
import { VIEWS, parseView, searchWithView } from '../lib/sources'
import type { View } from '../lib/api'

/**
 * Live / Official / Combined switch (todo.md 2.2a), kept in the URL as `?view=` so links can be shared.
 *
 * - A URL with `?view=` sets the view (shared link, Back/Forward).
 * - A URL without it (an in-app link, a bare address) gets the current view added, replacing the
 *   history entry, so moving between pages keeps the view.
 */
export default function ViewSwitch() {
  const view = useAppStore((s) => s.view)
  const setView = useAppStore((s) => s.setView)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const raw = new URLSearchParams(location.search).get('view')
    if (raw === null) {
      navigate({ pathname: location.pathname, search: searchWithView(location.search, view), hash: location.hash }, { replace: true })
      return
    }
    const fromUrl = parseView(raw)
    if (fromUrl !== view) setView(fromUrl)
    if (raw !== fromUrl) {
      // An unknown value: rewrite it to the view actually shown (the default).
      navigate({ pathname: location.pathname, search: searchWithView(location.search, fromUrl), hash: location.hash }, { replace: true })
    }
    // Only react to URL changes; `view` changes go through choose(), which updates the URL.
  }, [location.pathname, location.search])

  const choose = (next: View) => {
    if (next === view) return
    setView(next)
    navigate({ pathname: location.pathname, search: searchWithView(location.search, next), hash: location.hash })
  }

  return (
    <div className="flex items-center gap-3" role="group" aria-label="Data view">
      <span className="text-[10px] font-bold text-slate-400 tracking-widest uppercase">View</span>
      <div className="flex rounded-lg border border-slate-700/60 overflow-hidden">
        {VIEWS.map(({ value, label, hint }) => (
          <button
            key={value}
            type="button"
            onClick={() => choose(value)}
            title={hint}
            aria-pressed={view === value}
            className={clsx(
              'px-3 py-1.5 text-[11px] font-semibold tracking-wide transition-colors',
              view === value
                ? value === 'official'
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : value === 'live'
                    ? 'bg-sky-500/15 text-sky-300'
                    : 'bg-blue-500/20 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="hidden lg:inline text-[10px] text-slate-500">
        {VIEWS.find((v) => v.value === view)?.hint}
      </span>
    </div>
  )
}
