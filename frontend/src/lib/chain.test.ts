import { describe, expect, it } from 'vitest'
import type { OfficialChain } from './api'
import { chainSteps } from './chain'

// 2023-24 grant 36 (Co-operative), from the CAG Appropriation Accounts.
const chain: OfficialChain = {
  financial_year: '2023-24',
  grants: [36],
  original_lakhs: 9619.69,
  supplementary_lakhs: 405.34,
  reappropriation_lakhs: 0,
  final_grant_lakhs: 10025.03,
  surrendered_lakhs: 0,
  gross_expenditure_lakhs: 8233.02,
  saving_lakhs: 2031.88,
  excess_lakhs: 239.87,
  recoveries_lakhs: 0.13,
  recoveries_estimate_lakhs: 0,
  net_expenditure_lakhs: 8232.89,
  sources: {},
}

describe('chainSteps', () => {
  it('lists the steps in order and leaves out zero optional steps', () => {
    expect(chainSteps(chain).map(s => s.key)).toEqual([
      'original_lakhs', 'supplementary_lakhs', 'final_grant_lakhs', 'gross_expenditure_lakhs',
      'saving_lakhs', 'excess_lakhs', 'recoveries_lakhs', 'net_expenditure_lakhs',
    ])
  })

  it('shows re-appropriation and surrender when printed', () => {
    const keys = chainSteps({ ...chain, reappropriation_lakhs: -5, surrendered_lakhs: 12 }).map(s => s.key)
    expect(keys).toContain('reappropriation_lakhs')
    expect(keys).toContain('surrendered_lakhs')
  })

  it('keeps missing recoveries as null, never 0', () => {
    const steps = chainSteps({ ...chain, recoveries_lakhs: null, net_expenditure_lakhs: null })
    expect(steps.find(s => s.key === 'recoveries_lakhs')?.value).toBeNull()
    expect(steps.find(s => s.key === 'net_expenditure_lakhs')?.value).toBeNull()
  })
})
