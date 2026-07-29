import { useEffect, useMemo, useRef, useState } from 'react'
import type { Task } from '../types'
import { AssigneeInput } from './AssigneeInput'

type Props = {
  task: Task
  assigneeOptions: string[]
  readOnly?: boolean
  onClose: () => void
  onSave: (id: number, body: Record<string, unknown>) => Promise<void>
}

export function TaskModal({ task, assigneeOptions, readOnly = false, onClose, onSave }: Props) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [assignee, setAssignee] = useState(task.assignee)
  const [startDate, setStartDate] = useState(task.start_date)
  const [endDate, setEndDate] = useState(task.end_date)
  const [progress, setProgress] = useState(task.progress_pct ?? 0)
  const [saving, setSaving] = useState(false)
  const isPhase = Boolean(task.has_children)
  // Close only on a full click that both starts and ends on the backdrop
  // (not when drag starts inside the dialog and ends outside).
  const backdropPointerDown = useRef(false)

  const duration = useMemo(() => {
    const [ys, ms, ds] = startDate.split('-').map(Number)
    const [ye, me, de] = endDate.split('-').map(Number)
    const a = new Date(ys, ms - 1, ds).getTime()
    const b = new Date(ye, me - 1, de).getTime()
    return Math.max(1, Math.round((b - a) / 86400000))
  }, [startDate, endDate])

  useEffect(() => {
    setTitle(task.title)
    setDescription(task.description)
    setAssignee(task.assignee)
    setStartDate(task.start_date)
    setEndDate(task.end_date)
    setProgress(task.progress_pct ?? 0)
  }, [task])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const onStartChange = (value: string) => {
    if (!value) return
    const prevDur = duration
    setStartDate(value)
    const [y, m, d] = value.split('-').map(Number)
    const next = new Date(y, m - 1, d)
    next.setDate(next.getDate() + prevDur)
    const yy = next.getFullYear()
    const mm = String(next.getMonth() + 1).padStart(2, '0')
    const dd = String(next.getDate()).padStart(2, '0')
    setEndDate(`${yy}-${mm}-${dd}`)
  }

  const onEndChange = (value: string) => {
    if (!value) return
    const [ys, ms, ds] = startDate.split('-').map(Number)
    const [ye, me, de] = value.split('-').map(Number)
    if (new Date(ye, me - 1, de) < new Date(ys, ms - 1, ds)) {
      const next = new Date(ys, ms - 1, ds)
      next.setDate(next.getDate() + 1)
      const yy = next.getFullYear()
      const mm = String(next.getMonth() + 1).padStart(2, '0')
      const dd = String(next.getDate()).padStart(2, '0')
      setEndDate(`${yy}-${mm}-${dd}`)
      return
    }
    setEndDate(value)
  }

  const handleSave = async () => {
    if (readOnly || saving) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        title,
        description,
        assignee,
        duration_days: duration,
        start_date: startDate,
      }
      if (!isPhase) body.progress_pct = progress
      await onSave(task.id, body)
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
        className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
        onPointerDown={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault()
          if (!readOnly) void handleSave()
        }}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="text-xs text-[var(--muted)]">{task.code}</div>
            <h3 className="text-xl">{readOnly ? 'Задача (просмотр)' : 'Задача'}</h3>
          </div>
          <button type="button" className="text-[var(--muted)]" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-[var(--muted)]">Название</span>
            <input
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-70"
              value={title}
              disabled={readOnly}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Описание</span>
            <textarea
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-70"
              rows={3}
              value={description}
              disabled={readOnly}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => {
                if (readOnly) return
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void handleSave()
                }
              }}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Исполнитель</span>
            <AssigneeInput
              value={assignee}
              onChange={setAssignee}
              options={assigneeOptions}
              disabled={readOnly}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-70"
              listId="edit-assignee-suggestions"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[var(--muted)]">Дата начала</span>
              <input
                type="date"
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-70"
                value={startDate}
                disabled={readOnly}
                onChange={(e) => onStartChange(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-[var(--muted)]">Дата конца</span>
              <input
                type="date"
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-70"
                value={endDate}
                min={startDate}
                disabled={readOnly}
                onChange={(e) => onEndChange(e.target.value)}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-[var(--muted)]">Длительность, дни</span>
            <input
              type="number"
              readOnly
              tabIndex={-1}
              className="mt-1 w-full cursor-default rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 opacity-80"
              value={duration}
              title="Считается из дат начала и конца"
            />
            <div className="mt-1 text-[11px] text-[var(--muted)]">
              Считается автоматически: конец − начало
            </div>
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">
              Прогресс, %{isPhase ? ' (считается по подзадачам)' : ''}
            </span>
            <input
              type="number"
              min={0}
              max={100}
              disabled={isPhase || readOnly}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-60"
              value={progress}
              onFocus={(e) => e.currentTarget.select()}
              onClick={(e) => e.currentTarget.select()}
              onChange={(e) => setProgress(Math.max(0, Math.min(100, Number(e.target.value))))}
            />
          </label>
          <div className="grid grid-cols-2 gap-3 text-[var(--muted)]">
            <div>
              Родитель: <span className="text-[var(--text)]">{task.parent_code || '—'}</span>
            </div>
            <div>
              Предшественники:{' '}
              <span className="text-[var(--text)]">
                {task.predecessor_codes.join(', ') || '—'}
              </span>
            </div>
            <div className="col-span-2">
              Последнее изменение:{' '}
              <span className="text-[var(--text)]">
                {task.last_changed_by === 'agent' ? 'ассистент' : 'пользователь'}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg px-3 py-2 text-sm text-[var(--muted)]"
            onClick={onClose}
          >
            {readOnly ? 'Закрыть' : 'Отмена'}
          </button>
          {!readOnly && (
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm text-white disabled:opacity-60"
            >
              Сохранить
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
