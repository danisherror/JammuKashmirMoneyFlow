import { describe, expect, it } from 'vitest'
import type { FigureSource, GrantBreakdown, HeadNode, HeadRowItem } from './api'
import { biggestUnspent, categoryLabel, countFlags, flagLabel, flattenRows, nodeTotal, pdfPageUrl, unspentLakhs } from './breakdown'

const source: FigureSource = {
  source_type: 'official', label: 'Official · Appropriation Accounts 2023-24, p.20', measure: null,
  source_url: 'https://cag.gov.in/a.pdf', snapshot_id: 1, page: 20, fetched_at: null, provisional: false, mismatch: null,
}

const row = (over: Partial<HeadRowItem>): HeadRowItem => ({
  grant_no: 1, section: 'revenue', kind: 'voted', note_number: 1, category: 'saving',
  reasons_not_communicated: false, head_code: '2052.090.0099.0518', head_name: 'GAD',
  head_path: [{ level: 'major', code: '2052', name: 'Secretariat' }],
  original_lakhs: null, supplementary_lakhs: null, reappropriation_lakhs: null,
  final_grant_lakhs: null, expenditure_lakhs: null, saving_lakhs: null, excess_lakhs: null,
  remark: '', printed_error: null, source, ...over,
})

const saving = row({ head_code: 'a', final_grant_lakhs: 6213.35, expenditure_lakhs: 4252.59, saving_lakhs: 1960.76 })
const unused = row({ head_code: 'b', category: 'unutilised', final_grant_lakhs: 650 })
const excess = row({ head_code: 'c', category: 'excess', final_grant_lakhs: 668.25, expenditure_lakhs: 732.37, saving_lakhs: 0, excess_lakhs: 64.12 })
const noProvision = row({ head_code: 'd', category: 'without_provision', expenditure_lakhs: 148.43 })

const tree: HeadNode[] = [{
  level: 'major', code: '2052', name: 'Secretariat', head_code: '2052', section: 'revenue', grant_no: 1,
  rows: [saving],
  children: [{
    level: 'minor', code: '090', name: 'Secretariat', head_code: '2052.090', section: 'revenue', grant_no: 1,
    rows: [unused, excess, noProvision], children: [],
  }],
}]

const breakdown: GrantBreakdown = {
  financial_year: '2023-24', department_id: 1, grants: [], section_blocks: [], tree, notes: [], issues: [], flags: [], note: null,
}

describe('breakdown helpers', () => {
  it('flattens the tree depth-first', () => {
    expect(flattenRows(tree).map(r => r.head_code)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('counts savings and wholly unspent provisions, not excesses', () => {
    expect(unspentLakhs(saving)).toBe(1960.76)
    expect(unspentLakhs(unused)).toBe(650)
    expect(unspentLakhs(excess)).toBeNull()
    expect(unspentLakhs(noProvision)).toBeNull()
  })

  it('ranks the biggest unspent items', () => {
    expect(biggestUnspent(breakdown).map(x => [x.row.head_code, x.unspent])).toEqual([['a', 1960.76], ['b', 650]])
    expect(biggestUnspent(breakdown, 1)).toHaveLength(1)
  })

  it('sums printed amounts only, null when none are printed', () => {
    expect(nodeTotal(tree[0], 'expenditure_lakhs')).toBe(5133.39)
    expect(nodeTotal(tree[0].children[0], 'final_grant_lakhs')).toBe(1318.25)
    expect(nodeTotal({ ...tree[0], rows: [unused], children: [] }, 'expenditure_lakhs')).toBeNull()
  })

  it('links to the PDF page', () => {
    expect(pdfPageUrl(source)).toBe('https://cag.gov.in/a.pdf#page=20')
    expect(pdfPageUrl({ ...source, page: null })).toBe('https://cag.gov.in/a.pdf')
    expect(pdfPageUrl(null)).toBeNull()
  })

  it('labels categories', () => {
    expect(categoryLabel('unutilised')).toBe('Entire provision unspent')
  })
})

describe('flag helpers', () => {
  it('counts flags per kind in a fixed order, zeros included', () => {
    const flag = { kind: 'fully_unutilised', financial_year: '2023-24', grant_no: 1, grant_name: 'GAD',
      department_id: null, section: null, block_kind: null, head_code: null, head_name: null,
      amount_lakhs: 650, share_pct: null, detail: '', source } as const
    const counts = countFlags([flag, { ...flag }, { ...flag, kind: 'excess_over_grant' }])
    expect(counts.map(c => [c.kind, c.count])).toEqual([
      ['excess_over_grant', 1], ['savings_not_surrendered', 0], ['supplementary_not_needed', 0],
      ['fully_unutilised', 2], ['reasons_not_communicated', 0],
    ])
    expect(flagLabel('savings_not_surrendered')).toBe('Savings not surrendered')
  })
})
