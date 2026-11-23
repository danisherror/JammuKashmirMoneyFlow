import { describe, expect, it } from 'vitest'
import { difference, fmtCount, fmtLakhs, fmtPct, sumKnown } from './utils'

// todo.md 1.3: a real zero shows as zero; unknown (null) shows as "—".
describe('real zero vs unknown', () => {
  it('fmtLakhs', () => {
    expect(fmtLakhs(0)).toBe('₹0 L')
    expect(fmtLakhs(null)).toBe('—')
    expect(fmtLakhs(undefined)).toBe('—')
    expect(fmtLakhs(0.37)).toBe('₹0.37 L')
    expect(fmtLakhs(250)).toBe('₹2.5 Cr')
  })

  it('fmtPct', () => {
    expect(fmtPct(0)).toBe('0.0%')
    expect(fmtPct(null)).toBe('—')
    expect(fmtPct(Number.NaN)).toBe('—')
  })

  it('fmtCount', () => {
    expect(fmtCount(0)).toBe('0')
    expect(fmtCount(null)).toBe('—')
    expect(fmtCount(123456)).toBe('1,23,456')
  })

  it('difference is null when either side is unknown', () => {
    expect(difference(10, 4)).toBe(6)
    expect(difference(4, 4)).toBe(0)
    expect(difference(10, null)).toBeNull()
    expect(difference(null, 4)).toBeNull()
  })

  it('sumKnown skips unknowns and is null when nothing is known', () => {
    expect(sumKnown([1, null, 2])).toBe(3)
    expect(sumKnown([0, null])).toBe(0)
    expect(sumKnown([null, undefined])).toBeNull()
    expect(sumKnown([])).toBeNull()
  })
})
