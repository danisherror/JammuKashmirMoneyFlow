import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { fetchSyncStatus } from '../lib/api'
import { fetchedText, pickCollectors } from '../lib/collectors'

interface Props {
  /** collector_name of each collector whose rows the panel shows. */
  collectors: readonly string[]
  className?: string
}

/**
 * "Source: jktenders.gov.in · fetched 22 Nov 2026" for panels backed by portal collectors
 * (todo.md 1.3). With several collectors each one is listed with its own name. Uses the same
 * cached `sync-status` query as the freshness strip, so it costs no extra request.
 */
export default function CollectorSource({ collectors, className }: Props) {
  const { data, isError } = useQuery({ queryKey: ['sync-status'], queryFn: fetchSyncStatus, refetchInterval: 60_000 })
  const items = pickCollectors(data, collectors)
  const many = items.length > 1

  return (
    <span className={clsx('mono text-[9px] text-dim font-normal', className)}>
      Source:{' '}
      {isError && 'unknown (status unavailable)'}
      {!isError && items.length === 0 && '…'}
      {items.map((s, i) => (
        <span key={s.collector_name}>
          {i > 0 && '; '}
          {many && `${s.label}: `}
          {s.source_url
            ? <a href={s.source_url} target="_blank" rel="noreferrer" className="text-sky-300 hover:underline">{s.source_name}</a>
            : <span className="text-amber-300">{s.source_name}</span>}
          {' · '}{fetchedText(s)}
        </span>
      ))}
    </span>
  )
}
