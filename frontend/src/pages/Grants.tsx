import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchGrants } from '../lib/api'
import { fmtLakhs, fmtPct } from '../lib/utils'
import { pct } from '../lib/grants'
import PageHeader from '../components/PageHeader'
import ErrorBox from '../components/ErrorBox'
import SourceBadge from '../components/SourceBadge'

/**
 * Every grant in the latest CAG Appropriation Accounts, mapped to a tracker department or not
 * (todo.md 2.2b), each linking to its breakdown.
 */
export default function Grants() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['grants', 'latest'], queryFn: () => fetchGrants() })

  return (
    <div>
      <PageHeader title="CAG GRANTS" subtitle="AUDITED APPROPRIATION ACCOUNTS — EVERY GRANT, LATEST LOADED YEAR" />
      <div className="p-6">
        {isLoading && <div className="panel h-40 flex items-center justify-center mono text-[10px] text-dim animate-pulse">Loading grants…</div>}
        {isError && <ErrorBox />}
        {data && data.length === 0 && (
          <div className="panel p-6 text-center mono text-[10px] text-dim">No CAG Appropriation Accounts loaded yet.</div>
        )}
        {data && data.length > 0 && (
          <div className="panel overflow-x-auto">
            <table className="w-full mono text-[10px]">
              <caption className="sr-only">Grants with final grant and gross expenditure, ₹</caption>
              <thead>
                <tr className="text-dim text-left">
                  <th className="py-1 pr-2 font-normal">No.</th>
                  <th className="py-1 pr-2 font-normal">Grant</th>
                  <th className="py-1 pr-2 font-normal text-right">Final grant</th>
                  <th className="py-1 pr-2 font-normal text-right">Gross expenditure</th>
                  <th className="py-1 pr-2 font-normal text-right">Spent</th>
                  <th className="py-1 pr-2 font-normal">Tracker department</th>
                  <th className="py-1 font-normal">Source</th>
                </tr>
              </thead>
              <tbody>
                {data.map(g => (
                  <tr key={g.grant_no} className="border-t" style={{ borderColor: '#1a2a3a' }}>
                    <td className="py-1.5 pr-2 text-dim">{g.grant_no}</td>
                    <td className="py-1.5 pr-2">
                      <Link to={`/grants/${g.grant_no}`} className="hover:text-white hover:underline">{g.name}</Link>
                    </td>
                    <td className="py-1.5 pr-2 text-right">{fmtLakhs(g.final_grant_lakhs)}</td>
                    <td className="py-1.5 pr-2 text-right">{fmtLakhs(g.gross_expenditure_lakhs)}</td>
                    <td className="py-1.5 pr-2 text-right">{fmtPct(pct(g.gross_expenditure_lakhs, g.final_grant_lakhs))}</td>
                    <td className="py-1.5">
                      {g.department_id != null
                        ? <Link to={`/departments/${g.department_id}`} className="text-sky-300 hover:underline">view</Link>
                        : <span className="text-dim">not mapped</span>}
                    </td>
                    <td className="py-1.5"><SourceBadge source={g.source} value={g.final_grant_lakhs} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
