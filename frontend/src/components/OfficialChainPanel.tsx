import type { OfficialChain } from '../lib/api'
import { fmtLakhs } from '../lib/utils'
import { chainSteps } from '../lib/chain'
import SourceBadge from './SourceBadge'

interface Props {
  chain: OfficialChain
  /** Shown under the title, e.g. "Grant 16" or "All 36 grants". */
  scope: string
}

const TONE: Record<string, string> = {
  base: '#5a7a9a',
  add: '#38bdf8',
  total: '#00ff88',
  spent: '#ffd700',
  minus: '#f97316',
  saving: '#94a3b8',
  excess: '#ff3366',
}

/**
 * The audited original → final grant → spent → net chain (todo.md 2.2b), one row per step with a
 * bar scaled to the largest amount and a source badge pointing at the PDF page.
 */
export default function OfficialChainPanel({ chain, scope }: Props) {
  const steps = chainSteps(chain)
  const max = Math.max(...steps.map(s => Math.abs(s.value ?? 0)), 1)

  return (
    <div className="panel">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="panel-title">HOW THE GRANT WAS USED — AUDITED {chain.financial_year}</div>
        <div className="mono text-[9px] text-dim">{scope}</div>
      </div>
      <table className="w-full mono text-[10px]">
        <caption className="sr-only">
          Original grant to net expenditure, CAG Appropriation Accounts {chain.financial_year}, ₹ lakhs
        </caption>
        <tbody>
          {steps.map(step => (
            <tr key={step.key} className="border-t" style={{ borderColor: '#1a2a3a' }}>
              <th scope="row" className="text-left font-normal py-2 pr-3 text-dim whitespace-nowrap">
                <span className="inline-block w-4 text-center" aria-hidden>{step.sign}</span>
                {step.label}
              </th>
              <td className="py-2 pr-3 w-1/2 hidden sm:table-cell">
                <div className="h-2" style={{
                  width: `${Math.max(Math.abs(step.value ?? 0) / max * 100, step.value ? 0.5 : 0)}%`,
                  background: TONE[step.tone],
                }} />
              </td>
              <td className="py-2 pr-3 text-right whitespace-nowrap" style={{ color: TONE[step.tone] }}>
                {step.value === null ? 'No data' : fmtLakhs(step.value)}
              </td>
              <td className="py-2 text-right"><SourceBadge source={chain.sources[step.key]} value={step.value} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mono text-[9px] text-dim mt-3 leading-relaxed">
        Audited annual accounts, not current spending. The original grant is what was passed with the
        budget; it has not been checked against the Budget Estimates in the budget documents.
      </p>
    </div>
  )
}
