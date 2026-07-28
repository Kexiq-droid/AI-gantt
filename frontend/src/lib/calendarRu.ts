/** Russian Federation non-working public holidays (fixed + known transfers). */
const RF_HOLIDAYS: ReadonlySet<string> = new Set([
  '2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04', '2025-01-05',
  '2025-01-06', '2025-01-07', '2025-01-08',
  '2025-02-23', '2025-03-08', '2025-05-01', '2025-05-09',
  '2025-06-12', '2025-11-04',
  '2026-01-01', '2026-01-02', '2026-01-03', '2026-01-04', '2026-01-05',
  '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09',
  '2026-02-23', '2026-03-08', '2026-03-09',
  '2026-05-01', '2026-05-09', '2026-05-11',
  '2026-06-12', '2026-11-04',
  '2027-01-01', '2027-01-02', '2027-01-03', '2027-01-04', '2027-01-05',
  '2027-01-06', '2027-01-07', '2027-01-08',
  '2027-02-23', '2027-03-08', '2027-05-01', '2027-05-09',
  '2027-06-12', '2027-11-04',
])

const WEEKDAYS_RU = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'] as const
const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
] as const

export function pad2(n: number) {
  return String(n).padStart(2, '0')
}

export function formatDdMmYy(d: Date) {
  const yy = String(d.getFullYear()).slice(-2)
  return `${pad2(d.getDate())}-${pad2(d.getMonth() + 1)}-${yy}`
}

export function toIsoDate(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export function isWeekend(d: Date) {
  const day = d.getDay()
  return day === 0 || day === 6
}

export function isRfHoliday(d: Date) {
  return RF_HOLIDAYS.has(toIsoDate(d))
}

export function isNonWorkingDay(d: Date) {
  return isWeekend(d) || isRfHoliday(d)
}

export function weekdayRu(d: Date) {
  return WEEKDAYS_RU[d.getDay()]
}

export type Span = { start: number; count: number; label: string }

export type DayCell = {
  offset: number
  date: Date
  label: string
  weekday: string
  nonWorking: boolean
  holiday: boolean
  weekend: boolean
}

/** Build contiguous year/month spans and day cells over [min, min+totalDays). */
export function buildCalendarSpans(min: Date, totalDays: number) {
  const years: Span[] = []
  const months: Span[] = []
  const days: DayCell[] = []

  let yearStart = 0
  let monthStart = 0
  let curYear = -1
  let curMonth = -1

  for (let i = 0; i < totalDays; i++) {
    const d = new Date(min.getFullYear(), min.getMonth(), min.getDate() + i)
    const y = d.getFullYear()
    const m = d.getMonth()

    if (i === 0) {
      curYear = y
      curMonth = m
      yearStart = 0
      monthStart = 0
    } else {
      if (y !== curYear) {
        years.push({ start: yearStart, count: i - yearStart, label: String(curYear) })
        curYear = y
        yearStart = i
      }
      if (m !== curMonth) {
        months.push({ start: monthStart, count: i - monthStart, label: MONTHS_RU[curMonth] })
        curMonth = m
        monthStart = i
      }
    }

    const weekend = isWeekend(d)
    const holiday = isRfHoliday(d)
    days.push({
      offset: i,
      date: d,
      label: formatDdMmYy(d),
      weekday: weekdayRu(d),
      nonWorking: weekend || holiday,
      holiday,
      weekend,
    })
  }

  if (totalDays > 0) {
    years.push({ start: yearStart, count: totalDays - yearStart, label: String(curYear) })
    months.push({ start: monthStart, count: totalDays - monthStart, label: MONTHS_RU[curMonth] })
  }

  return { years, months, days }
}
