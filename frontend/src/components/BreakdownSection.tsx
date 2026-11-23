import { useQuery } from '@tanstack/react-query'
import type { GrantBreakdown } from '../lib/api'
import GrantBreakdownPanel from './GrantBreakdownPanel'
import ErrorBox from './ErrorBox'

interface Props {
  /** Query key prefix and fetcher; the fetcher gets the year, or undefined for the latest loaded year. */
  queryKey: unknown[]
  fetch: (financialYear?: string) => Promise<GrantBreakdown>
  financialYear: string
}

const hasPages = (b: GrantBreakdown | undefined) => !!b && b.section_blocks.length > 0

/**
 * Loads a breakdown for the selected year. The CAG accounts trail by about a year, so when the
 * selected year has no grant pages it falls back to the latest audited year and says so.
 */
export default function BreakdownSection({ queryKey, fetch, financialYear }: Props) {
  const selected = useQuery({ queryKey: [...queryKey, financialYear], queryFn: () => fetch(financialYear) })
  const needsLatest = selected.isSuccess && !hasPages(selected.data)
  const latest = useQuery({
    queryKey: [...queryKey, 'latest'],
    queryFn: () => fetch(undefined),
    enabled: needsLatest,
  })

  if (selected.isLoading) {
    return <div className="panel h-24 flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading breakdown…</div>
  }
  if (selected.isError) return <ErrorBox />
  if (hasPages(selected.data)) return <GrantBreakdownPanel breakdown={selected.data!} />
  if (needsLatest && latest.isLoading) {
    return <div className="panel h-24 flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading latest audited year…</div>
  }
  if (needsLatest && hasPages(latest.data) && latest.data!.financial_year !== financialYear) {
    return (
      <GrantBreakdownPanel
        breakdown={latest.data!}
        yearNote={`FY ${financialYear} has no audited accounts yet; showing the latest audited year, ${latest.data!.financial_year}.`}
      />
    )
  }
  return (
    <div className="panel p-6 text-center mono text-[10px] text-dim">
      No breakdown: {selected.data?.note ?? 'no CAG grant pages for this year'}.
    </div>
  )
}
