/**
 * Rows of the audited original → final grant → spent → net chain (todo.md 2.2b). Pure, so it can
 * be unit-tested. Steps that are zero in every year they could appear (re-appropriation outside
 * 2021-22, excess, surrender) are left out to keep the chain short; the totals always show.
 */
import type { OfficialChain } from './api'

export interface ChainStep {
  key: keyof OfficialChain & string
  label: string
  sign: '' | '+' | '−' | '='
  value: number | null
  tone: 'base' | 'add' | 'total' | 'spent' | 'minus' | 'saving' | 'excess'
}

export function chainSteps(chain: OfficialChain): ChainStep[] {
  const steps: ChainStep[] = [
    { key: 'original_lakhs', label: 'Original grant', sign: '', value: chain.original_lakhs, tone: 'base' },
    { key: 'supplementary_lakhs', label: 'Supplementary', sign: '+', value: chain.supplementary_lakhs, tone: 'add' },
  ]
  if (chain.reappropriation_lakhs !== 0) {
    steps.push({ key: 'reappropriation_lakhs', label: 'Re-appropriation', sign: '+', value: chain.reappropriation_lakhs, tone: 'add' })
  }
  steps.push(
    { key: 'final_grant_lakhs', label: 'Final grant', sign: '=', value: chain.final_grant_lakhs, tone: 'total' },
    { key: 'gross_expenditure_lakhs', label: 'Gross expenditure', sign: '', value: chain.gross_expenditure_lakhs, tone: 'spent' },
    { key: 'saving_lakhs', label: 'Saving (unspent)', sign: '', value: chain.saving_lakhs, tone: 'saving' },
  )
  if (chain.excess_lakhs !== 0) {
    steps.push({ key: 'excess_lakhs', label: 'Excess over grant', sign: '', value: chain.excess_lakhs, tone: 'excess' })
  }
  if (chain.surrendered_lakhs !== 0) {
    steps.push({ key: 'surrendered_lakhs', label: 'Surrendered in year', sign: '', value: chain.surrendered_lakhs, tone: 'saving' })
  }
  steps.push(
    { key: 'recoveries_lakhs', label: 'Recoveries', sign: '−', value: chain.recoveries_lakhs, tone: 'minus' },
    { key: 'net_expenditure_lakhs', label: 'Net expenditure', sign: '=', value: chain.net_expenditure_lakhs, tone: 'spent' },
  )
  return steps
}
