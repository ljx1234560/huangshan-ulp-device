import { describe, expect, it } from 'vitest'
import { buildDateQuery } from '../src/index'
import { mockApi } from '../src/mock'

describe('mock API contracts', () => {
  it('keeps activity summary and trend data consistent', async () => {
    const summary = await mockApi.activity('week')
    expect(summary.points).toHaveLength(7)
    expect(summary.completionRate).toBeCloseTo(summary.todaySteps / summary.goal)
  })

  it('completes asynchronous mock pet jobs', async () => {
    const job = await mockApi.createPetJob({
      species: 'fox',
      color: 'lavender',
      style: 'celestial',
      personality: 'energetic',
      name: '露米',
      description: '',
    })
    expect(job.status).toBe('queued')
    expect(job.source).toBe('mock_asset')
  })

  it('passes explicit activity date filters to real API query strings', () => {
    const query = new URLSearchParams(buildDateQuery('month', {
      startDate: '2026-11-01',
      endDate: '2026-11-18',
    }))
    expect(query.get('range')).toBe('month')
    expect(query.get('start_date')).toBe('2026-11-01')
    expect(query.get('end_date')).toBe('2026-11-18')
  })

  it('keeps mock sync requests in persistent history', async () => {
    const created = await mockApi.syncDevice('VP-TEST')
    const history = await mockApi.syncHistory()
    expect(created.source).toBe('web_request')
    expect(created.status).toBe('pending')
    expect(history.some((item) => item.id === created.id)).toBe(true)
  })

  it('generates a structured coaching record and exposes its history', async () => {
    const generated = await mockApi.generateCoaching()
    const latest = await mockApi.latestCoaching()
    const history = await mockApi.coachingHistory()
    expect(generated.source).toBe('mock')
    expect(generated.dataSufficient).toBe(true)
    expect(generated.advice.length).toBeGreaterThanOrEqual(4)
    expect(latest[0]?.id).toBe(generated.advice[0]?.id)
    expect(history.some((item) => item.id === generated.id)).toBe(true)
  })
})
