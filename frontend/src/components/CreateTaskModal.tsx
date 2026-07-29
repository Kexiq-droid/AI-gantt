import { useEffect, useMemo, useRef, useState } from 'react'
import { AssigneeInput } from './AssigneeInput'

export type CreateTaskContext = {
  parent_id: number | null
  after_task_id: number | null
  hint?: string
  /** ISO date YYYY-MM-DD — default start for the form */
  default_start?: string
}

function toIso(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function parseIso(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function addDaysIso(iso: string, days: number) {
  const d = parseIso(iso)
  d.setDate(d.getDate() + days)
  return toIso(d)
}

/** Same as backend: end = start + duration_days */
function durationFromDates(start: string, end: string) {
  const a = parseIso(start).getTime()
  const b = parseIso(end).getTime()
  return Math.max(1, Math.round((b - a) / 86400000))
}

type Props = {
  context: CreateTaskContext
  assigneeOptions: string[]
  onClose: () => void
  onCreate: (body: {
    title: string
    parent_id?: number | null
    after_task_id?: number | null
    assignee?: string
    duration_days?: number
    start_date?: string
  }) => Promise<void>
}

export function CreateTaskModal({ context, assigneeOptions, onClose, onCreate }: Props) {
  const initialStart = context.default_start || toIso(new Date())
  const [title, setTitle] = useState('')
  const [assignee, setAssignee] = useState('')
  const [startDate, setStartDate] = useState(initialStart)
  const [endDate, setEndDate] = useState(() => addDaysIso(initialStart, 5))
  const [saving, setSaving] = useState(false)
  const backdropPointerDown = useRef(false)

  const duration = useMemo(
    () => durationFromDates(startDate, endDate),
    [startDate, endDate],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const onStartChange = (value: string) => {
    if (!value) return
    setStartDate(value)
    setEndDate(addDaysIso(value, durationFromDates(startDate, endDate)))
  }

  const onEndChange = (value: string) => {
    if (!value) return
    if (parseIso(value).getTime() < parseIso(startDate).getTime()) {
      setEndDate(addDaysIso(startDate, 1))
      return
    }
    setEndDate(value)
  }

  const handleSave = async () => {
    const t = title.trim()
    if (!t || saving) return
    setSaving(true)
    try {
      await onCreate({
        title: t,
        parent_id: context.parent_id,
        after_task_id: context.after_task_id,
        assignee: assignee.trim(),
        duration_days: duration,
        start_date: startDate,
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onPointerDown={(e) => {
        backdropPointerDown.current = e.target === e.currentTarget
      }}
      onClick={(e) => {
        if (backdropPointerDown.current && e.target === e.currentTarget) onClose()
        backdropPointerDown.current = false
      }}
    >
      <form
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
        onPointerDown={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault()
          void handleSave()
        }}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-xl">Новая задача</h3>
            {context.hint && (
              <div className="mt-0.5 text-xs text-[var(--muted)]">{context.hint}</div>
            )}
          </div>
          <button type="button" className="text-[var(--muted)]" onClick={onClose}>
            ✕
          </button>
        </div>
        <label className="mb-3 block text-sm">
          <span className="text-[var(--muted)]">Название</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            required
          />
        </label>
        <label className="mb-3 block text-sm">
          <span className="text-[var(--muted)]">Исполнитель</span>
          <AssigneeInput
            value={assignee}
            onChange={setAssignee}
            options={assigneeOptions}
            listId="create-assignee-suggestions"
          />
        </label>
        <div className="mb-3 grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-[var(--muted)]">Дата начала</span>
            <input
              type="date"
              required
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
              value={startDate}
              onChange={(e) => onStartChange(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--muted)]">Дата конца</span>
            <input
              type="date"
              required
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
              value={endDate}
              min={startDate}
              onChange={(e) => onEndChange(e.target.value)}
            />
          </label>
        </div>
        <label className="mb-4 block text-sm">
          <span className="text-[var(--muted)]">Длительность, дни</span>
          <input
            type="number"
            readOnly
            tabIndex={-1}
            className="mt-1 w-full cursor-default rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 opacity-80"
            value={duration}
            title="Считается из дат начала и конца"
          />
          <div className="mt-1 text-[11px] text-[var(--muted)]">
            Считается автоматически: конец − начало
          </div>
        </label>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg px-3 py-2 text-sm text-[var(--muted)]"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={saving || !title.trim()}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {saving ? 'Создание…' : 'Создать'}
          </button>
        </div>
      </form>
    </div>
  )
}
