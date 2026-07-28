import { useEffect, useMemo, useRef, useState } from 'react'
import { buildCalendarSpans } from '../lib/calendarRu'
import type { Plan, Task } from '../types'

type Props = {
  plan: Plan
  highlightCodes: string[]
  onSelect: (task: Task) => void
  onShiftTasks: (taskIds: number[], days: number) => void
}

type Zoom = 'day' | 'week'

const HEADER_H = 72 // year 22 + month 22 + day 28

function parseDate(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function daysBetween(a: Date, b: Date) {
  const a0 = new Date(a.getFullYear(), a.getMonth(), a.getDate())
  const b0 = new Date(b.getFullYear(), b.getMonth(), b.getDate())
  return Math.round((b0.getTime() - a0.getTime()) / 86400000)
}

function addDays(d: Date, n: number) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
}

export function GanttChart({ plan, highlightCodes, onSelect, onShiftTasks }: Props) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [zoom, setZoom] = useState<Zoom>('day')
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const selectedRef = useRef<number[]>([])
  selectedRef.current = selectedIds

  const dragRef = useRef<{
    anchorId: number
    rootIds: number[]
    visualIds: number[]
    startX: number
    moved: boolean
    ctrlToggle: boolean
  } | null>(null)

  const rootRef = useRef<HTMLDivElement>(null)
  const tasksById = useMemo(() => new Map(plan.tasks.map((t) => [t.id, t])), [plan.tasks])

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

  const pxPerDay = zoom === 'day' ? 28 : 12
  const timelineWidth = range.total * pxPerDay

  const calendar = useMemo(
    () => buildCalendarSpans(range.min, range.total),
    [range.min, range.total],
  )

  const hasChildren = (id: number) => (childrenMap.get(id) || []).length > 0

  const subtreeIds = (rootId: number): number[] => {
    const out = [rootId]
    let i = 0
    while (i < out.length) {
      for (const c of childrenMap.get(out[i]) || []) out.push(c.id)
      i += 1
    }
    return out
  }

  const dedupeRoots = (ids: number[]): number[] => {
    const set = new Set(ids)
    return ids.filter((id) => {
      let p = tasksById.get(id)?.parent_id ?? null
      while (p != null) {
        if (set.has(p)) return false
        p = tasksById.get(p)?.parent_id ?? null
      }
      return true
    })
  }

  const visualIdsForRoots = (roots: number[]): number[] => {
    const all = new Set<number>()
    for (const r of roots) for (const id of subtreeIds(r)) all.add(id)
    return [...all]
  }

  useEffect(() => {
    const DRAG_THRESHOLD_PX = 5
    const setTranslate = (ids: number[], px: number) => {
      for (const id of ids) {
        const el = document.querySelector(`[data-bar-id="${id}"]`) as HTMLElement | null
        if (el) el.style.translate = px ? `${px}px 0` : ''
      }
    }
    const onMove = (e: PointerEvent) => {
      const drag = dragRef.current
      if (!drag || drag.ctrlToggle) return
      const deltaPx = e.clientX - drag.startX
      if (Math.abs(deltaPx) >= DRAG_THRESHOLD_PX) drag.moved = true
      if (!drag.moved) return
      const deltaDays = Math.round(deltaPx / pxPerDay)
      setTranslate(drag.visualIds, deltaDays * pxPerDay)
    }
    const onUp = (e: PointerEvent) => {
      const drag = dragRef.current
      if (!drag) return
      dragRef.current = null

      if (drag.ctrlToggle) {
        // handled on pointerdown
        return
      }

      const deltaPx = e.clientX - drag.startX
      const deltaDays = Math.round(deltaPx / pxPerDay)
      setTranslate(drag.visualIds, 0)

      if (drag.moved) {
        if (deltaDays !== 0) onShiftTasks(drag.rootIds, deltaDays)
        return
      }

      // plain click on a bar
      const task = tasksById.get(drag.anchorId)
      if (!task) return
      const wasSelected = selectedRef.current.includes(drag.anchorId)
      if (wasSelected && selectedRef.current.length === 1) {
        onSelect(task)
      } else if (!wasSelected) {
        // selection already cleared on pointerdown; open card
        onSelect(task)
      }
      // multi-select click without move: keep selection, no modal
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [onSelect, onShiftTasks, pxPerDay, tasksById])

  // Click anywhere except selected bars → clear selection
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      const target = e.target as HTMLElement | null
      const bar = target?.closest?.('[data-bar-id]') as HTMLElement | null
      if (bar) {
        const id = Number(bar.dataset.barId)
        if (selectedRef.current.includes(id)) return
        // unselected bar: selection cleared in bar handler
        return
      }
      if (rootRef.current?.contains(target)) {
        setSelectedIds([])
      }
    }
    // capture so we clear even when other handlers stopPropagation
    document.addEventListener('pointerdown', onDown, true)
    return () => document.removeEventListener('pointerdown', onDown, true)
  }, [])

  const nonWorkingBg = 'color-mix(in srgb, var(--danger) 14%, transparent)'
  const holidayBg = 'color-mix(in srgb, var(--danger) 22%, transparent)'
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  return (
    <div
      ref={rootRef}
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]"
    >
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--muted)]">План</div>
          <h2 className="text-lg leading-tight">{plan.title}</h2>
          {selectedIds.length > 0 && (
            <div className="mt-0.5 text-xs text-[var(--accent)]">
              Выделено: {selectedIds.length} · Ctrl+клик — добавить/убрать
            </div>
          )}
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

            <div
              className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--surface)]"
              style={{ height: HEADER_H }}
            >
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
              <div className="relative h-[28px]">
                {calendar.days.map((day) => {
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
                const isSelected = selectedSet.has(task.id)
                return (
                  <div
                    key={task.id}
                    className="relative h-10 border-b border-[var(--border)]"
                  >
                    <div
                      data-bar-id={task.id}
                      className={`absolute top-2 h-6 cursor-grab rounded-md active:cursor-grabbing ${hl ? 'bar-highlight' : ''}`}
                      style={{
                        left,
                        width,
                        background: isPhase ? 'var(--bar-phase)' : 'var(--bar)',
                        opacity: isPhase ? 0.85 : 1,
                        outline: isSelected ? '2px dashed var(--accent)' : undefined,
                        outlineOffset: isSelected ? 2 : undefined,
                        zIndex: isSelected ? 2 : 1,
                      }}
                      title={`${task.code}: ${task.start_date} → ${task.end_date}${isPhase ? ' (фаза: сдвиг с дочерними)' : ''}`}
                      onPointerDown={(e) => {
                        if (e.button !== 0) return
                        e.preventDefault()
                        e.stopPropagation()

                        if (e.ctrlKey || e.metaKey) {
                          setSelectedIds((prev) =>
                            prev.includes(task.id)
                              ? prev.filter((id) => id !== task.id)
                              : [...prev, task.id],
                          )
                          dragRef.current = {
                            anchorId: task.id,
                            rootIds: [],
                            visualIds: [],
                            startX: e.clientX,
                            moved: false,
                            ctrlToggle: true,
                          }
                          return
                        }

                        const already = selectedRef.current.includes(task.id)
                        let roots: number[]
                        if (already) {
                          roots = dedupeRoots(selectedRef.current)
                        } else {
                          setSelectedIds([])
                          roots = [task.id]
                        }
                        const visual = visualIdsForRoots(roots)
                        dragRef.current = {
                          anchorId: task.id,
                          rootIds: roots,
                          visualIds: visual,
                          startX: e.clientX,
                          moved: false,
                          ctrlToggle: false,
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
