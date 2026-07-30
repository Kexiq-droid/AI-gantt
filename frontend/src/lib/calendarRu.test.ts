import { describe, expect, it } from 'vitest'
import {
  buildCalendarSpans,
  formatDdMmYy,
  isNonWorkingDay,
  isRfHoliday,
  isWeekend,
  pad2,
  toIsoDate,
} from '../lib/calendarRu'

describe('calendarRu', () => {
  it('pad2 and date helpers', () => {
    expect(pad2(3)).toBe('03')
    expect(toIsoDate(new Date(2026, 6, 29))).toBe('2026-07-29')
    expect(formatDdMmYy(new Date(2026, 0, 5))).toBe('05-01-26')
  })

  it('weekends and RF holidays', () => {
    expect(isWeekend(new Date(2026, 6, 25))).toBe(true) // Sat
    expect(isWeekend(new Date(2026, 6, 27))).toBe(false) // Mon
    expect(isRfHoliday(new Date(2026, 0, 1))).toBe(true)
    expect(isNonWorkingDay(new Date(2026, 0, 1))).toBe(true)
    expect(isNonWorkingDay(new Date(2026, 6, 27))).toBe(false)
  })

  it('buildCalendarSpans covers range', () => {
    const min = new Date(2026, 6, 1)
    const { days, months, years } = buildCalendarSpans(min, 10)
    expect(days).toHaveLength(10)
    expect(days[0].label).toBe('01-07-26')
    expect(months.length).toBeGreaterThanOrEqual(1)
    expect(years.length).toBeGreaterThanOrEqual(1)
    expect(years[0].label).toContain('2026')
  })
})
