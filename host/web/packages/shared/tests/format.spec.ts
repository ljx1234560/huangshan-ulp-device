import { describe, expect, it } from 'vitest'
import { clampPercent, formatPercent } from '../src'

describe('shared format helpers', () => {
  it('clamps progress into a safe display range', () => {
    expect(clampPercent(-10)).toBe(0)
    expect(clampPercent(48.6)).toBe(49)
    expect(clampPercent(130)).toBe(100)
  })

  it('formats API ratios as percentages', () => {
    expect(formatPercent(0.876)).toContain('88')
  })
})
