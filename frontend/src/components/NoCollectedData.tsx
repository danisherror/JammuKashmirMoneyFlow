import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { fetchSyncStatus } from '../lib/api'
import { emptyStateText, pickCollectors } from '../lib/collectors'

interface Props {
  /** collector_name of each collector whose rows the panel would show. */
  collectors: readonly string[]
  className?: string
}

/**
 * Empty state for a panel backed by portal collectors (todo.md 1.3): one line per collector,
 * e.g. "No data collected yet from jktenders.gov.in — last attempt failed: <reason>", instead of
 * a blank chart, 0 or 0.0%.
 */
export default function NoCollectedData({ collectors, className }: Props) {
  const { data, isError } = useQuery({ queryKey: ['sync-status'], queryFn: fetchSyncStatus, refetchInterval: 60_000 })
  const items = pickCollectors(data, collectors)

  return (
    <div className={clsx('mono text-[10px] text-dim leading-relaxed space-y-1', className)} role="status">
      {isError && <p>No data to show. The collector status is unavailable, so the reason is unknown.</p>}
      {!isError && items.length === 0 && <p>No data to show.</p>}
      {items.map(s => <p key={s.collector_name}>{emptyStateText(s)}</p>)}
      <p>
        <Link to="/sync" className="text-sky-300 hover:underline">Collector status →</Link>
      </p>
    </div>
  )
}
