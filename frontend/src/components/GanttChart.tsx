import { useEffect, useMemo, useRef, useState } from 'react'
import { buildCalendarSpans } from '../lib/calendarRu'
import type { Plan, Task } from '../types'

type Props = {
  plan: Plan
  highlightCodes: string[]
  onSelect: (task: Task) => void
  onShiftTask: (taskId: number, newStart: string) => void
}

type Zoom = 'day' | 'week'

const HEADER_H = 72 // year 22 + month 22 + day 28

function parseDate(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function fmt(d: Date) {
  const yy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

function addDays(d: Date, n: number) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
}

function daysBetween(a: Date, b: Date) {
  const a0 = new Date(a.getFullYear(), a.getMonth(), a.getDate())
  const b0 = new Date(b.getFullYear(), b.getMonth(), b.getDate())
  return Math.round((b0.getTime() - a0.getTime()) / 86400000)
}

export function GanttChart({ plan, highlightCodes, onSelect, onShiftTask }: Props) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [zoom, setZoom] = useState<Zoom>('day')
  const dragRef = useRef<{ id: number; startX: number; origStart: string } | null>(null)

  const childrenMap = useMemo(() => {
    const m = new Map<number | null, Task[]>()
    for (const t of plan.tasks) {
      const key = t.parent_id
      if (!m.has(key)) m.set(key, [])
      m.get(key)!.push(t)
    }
    for (const [, arr] of m) arr.sort((a, b) => a.sort_order - b.sort_order)
    return m
  }, [plan.tasks])

  const flat = useMemo(() => {
    const out: { task: Task; depth: number }[] = []
    const walk = (parentId: number | null, depth: number) => {
      for (const t of childrenMap.get(parentId) || []) {
        out.push({ task: t, depth })
        if (!collapsed[t.code]) walk(t.id, depth + 1)
      }
    }
    walk(null, 0)
    return out
  }, [childrenMap, collapsed])

  const range = useMemo(() => {
    let min = parseDate(plan.start_date)
    let max = addDays(min, 30)
    for (const t of plan.tasks) {
      const s = parseDate(t.start_date)
      const e = parseDate(t.end_date)
      if (s < min) min = s
      if (e > max) max = e
    }
    max = addDays(max, 7)
    return { min, max, total: Math.max(daysBetween(min, max), 14) }
  }, [plan])

  // Day mode: weekday + dd
  const pxPerDay = zoom === 'day' ? 28 : 12
  const timelineWidth = range.total * pxPerDay

  const calendar = useMemo(
    () => buildCalendarSpans(range.min, range.total),
    [range.min, range.total],
  )

  const hasChildren = (id: number) => (childrenMap.get(id) || []).length > 0

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!dragRef.current) return
      const deltaPx = e.clientX - dragRef.current.startX
      const deltaDays = Math.round(deltaPx / pxPerDay)
      const el = document.querySelector(`[data-bar-id="${dragRef.current.id}"]`) as HTMLElement | null
      if (el) el.style.translate = `${deltaDays * pxPerDay}px 0`
    }
    const onUp = (e: PointerEvent) => {
      if (!dragRef.current) return
      const deltaPx = e.clientX - dragRef.current.startX
      const deltaDays = Math.round(deltaPx / pxPerDay)
      const { id, origStart } = dragRef.current
      dragRef.current = null
      const el = document.querySelector(`[data-bar-id="${id}"]`) as HTMLElement | null
      if (el) el.style.translate = ''
      if (deltaDays !== 0) {
        onShiftTask(id, fmt(addDays(parseDate(origStart), deltaDays)))
      }
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [onShiftTask, pxPerDay])

  const nonWorkingBg = 'color-mix(in srgb, var(--danger) 14%, transparent)'
  const holidayBg = 'color-mix(in srgb, var(--danger) 22%, transparent)'

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--muted)]">План</div>
          <h2 className="text-lg leading-tight">{plan.title}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: nonWorkingBg }} />
            выходной
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: holidayBg }} />
            праздник РФ
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm ${zoom === 'day' ? 'bg-[var(--accent)] text-white' : 'bg-[var(--surface-2)]'}`}
              onClick={() => setZoom('day')}
            >
              Дни
            </button>
            <button
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm ${zoom === 'week' ? 'bg-[var(--accent)] text-white' : 'bg-[var(--surface-2)]'}`}
              onClick={() => setZoom('week')}
            >
              Недели
            </button>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        <div className="flex min-w-max">
          <div className="sticky left-0 z-20 w-[280px] shrink-0 border-r border-[var(--border)] bg-[var(--surface)]">
            <div
              className="flex items-end border-b border-[var(--border)] px-3 pb-2 text-xs text-[var(--muted)]"
              style={{ height: HEADER_H }}
            >
              Задача
            </div>
            {flat.map(({ task, depth }) => (
              <div
                key={task.id}
                className="flex h-10 items-center gap-1 border-b border-[var(--border)] px-2 text-sm"
              >
                <button
                  type="button"
                  className="w-5 text-[var(--muted)]"
                  onClick={() =>
                    hasChildren(task.id) &&
                    setCollapsed((c) => ({ ...c, [task.code]: !c[task.code] }))
                  }
                >
                  {hasChildren(task.id) ? (collapsed[task.code] ? '▸' : '▾') : ''}
                </button>
                <button
                  type="button"
                  className="truncate text-left hover:text-[var(--accent)]"
                  style={{ paddingLeft: depth * 12 }}
                  onClick={() => onSelect(task)}
                  title={task.code}
                >
                  <span className="mr-1 text-xs text-[var(--muted)]">{task.code}</span>
                  {task.title}
                </button>
              </div>
            ))}
          </div>

          <div className="relative" style={{ width: timelineWidth }}>
            {/* Non-working day vertical bands behind bars */}
            <div
              className="pointer-events-none absolute left-0 z-0"
              style={{ top: HEADER_H, width: timelineWidth, height: flat.length * 40 }}
            >
              {calendar.days.map((day) =>
                day.nonWorking ? (
                  <div
                    key={`bg-${day.offset}`}
                    className="absolute top-0 h-full"
                    style={{
                      left: day.offset * pxPerDay,
                      width: pxPerDay,
                      background: day.holiday ? holidayBg : nonWorkingBg,
                    }}
                  />
                ) : null,
              )}
            </div>

            {/* 3-level header: year / month / weekday+dd-mm-yy */}
            <div
              className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface)]"
              style={{ height: HEADER_H }}
            >
              {/* Years */}
              <div className="relative h-[22px] border-b border-[var(--border)]">
                {calendar.years.map((y) => (
                  <div
                    key={`y-${y.start}`}
                    className="absolute top-0 flex h-full items-center justify-center overflow-hidden border-l border-[var(--border)] text-[11px] font-semibold text-[var(--text)]"
                    style={{ left: y.start * pxPerDay, width: y.count * pxPerDay }}
                    title={y.label}
                  >
                    {y.label}
                  </div>
                ))}
              </div>
              {/* Months */}
              <div className="relative h-[22px] border-b border-[var(--border)]">
                {calendar.months.map((m) => (
                  <div
                    key={`m-${m.start}`}
                    className="absolute top-0 flex h-full items-center justify-center overflow-hidden border-l border-[var(--border)] text-[10px] font-medium text-[var(--muted)]"
                    style={{ left: m.start * pxPerDay, width: m.count * pxPerDay }}
                    title={m.label}
                  >
                    <span className="truncate px-1">{m.label}</span>
                  </div>
                ))}
              </div>
              {/* Days: weekday + dd-mm-yy */}
              <div className="relative h-[28px]">
                {calendar.days.map((day) => {
                  // In week zoom show every 7th day label to avoid clutter
                  const showLabel = zoom === 'day' || day.offset % 7 === 0
                  return (
                    <div
                      key={`d-${day.offset}`}
                      className="absolute top-0 flex h-full flex-col items-center justify-center border-l border-[var(--border)] leading-none"
                      style={{
                        left: day.offset * pxPerDay,
                        width: pxPerDay,
                        background: day.holiday
                          ? holidayBg
                          : day.weekend
                            ? nonWorkingBg
                            : undefined,
                        color: day.nonWorking ? 'var(--danger)' : 'var(--muted)',
                      }}
                      title={`${day.weekday}, ${day.label}${day.holiday ? ' · праздник РФ' : day.weekend ? ' · выходной' : ''}`}
                    >
                      {showLabel && (
                        <>
                          <span className="text-[9px] font-semibold">{day.weekday}</span>
                          <span className="mt-0.5 text-[10px] tabular-nums tracking-tight">
                            {String(day.date.getDate()).padStart(2, '0')}
                          </span>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            <svg
              className="pointer-events-none absolute left-0 z-[1]"
              style={{ top: HEADER_H }}
              width={timelineWidth}
              height={flat.length * 40}
            >
              {plan.dependencies.map((d) => {
                const pred = flat.findIndex((f) => f.task.id === d.predecessor_task_id)
                const succ = flat.findIndex((f) => f.task.id === d.successor_task_id)
                if (pred < 0 || succ < 0) return null
                const pTask = flat[pred].task
                const sTask = flat[succ].task
                const x1 = daysBetween(range.min, parseDate(pTask.end_date)) * pxPerDay
                const y1 = pred * 40 + 20
                const x2 = daysBetween(range.min, parseDate(sTask.start_date)) * pxPerDay
                const y2 = succ * 40 + 20
                return (
                  <path
                    key={d.id}
                    d={`M ${x1} ${y1} C ${x1 + 20} ${y1}, ${x2 - 20} ${y2}, ${x2} ${y2}`}
                    fill="none"
                    stroke="var(--muted)"
                    strokeWidth="1.2"
                    opacity="0.55"
                  />
                )
              })}
            </svg>

            <div className="relative z-[1]" style={{ marginTop: 0 }}>
              {flat.map(({ task }, idx) => {
                const left = daysBetween(range.min, parseDate(task.start_date)) * pxPerDay
                const width = Math.max(task.duration_days * pxPerDay, 8)
                const isPhase = hasChildren(task.id)
                const hl = highlightCodes.includes(task.code)
                return (
                  <div
                    key={task.id}
                    className="relative h-10 border-b border-[var(--border)]"
                  >
                    <div
                      data-bar-id={task.id}
                      className={`absolute top-2 h-6 cursor-grab rounded-md ${hl ? 'bar-highlight' : ''}`}
                      style={{
                        left,
                        width,
                        background: isPhase ? 'var(--bar-phase)' : 'var(--bar)',
                        opacity: isPhase ? 0.85 : 1,
                      }}
                      title={`${task.code}: ${task.start_date} → ${task.end_date}`}
                      onClick={() => onSelect(task)}
                      onPointerDown={(e) => {
                        if (isPhase) return
                        e.preventDefault()
                        dragRef.current = {
                          id: task.id,
                          startX: e.clientX,
                          origStart: task.start_date,
                        }
                      }}
                    />
                    <span className="sr-only">{idx}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
