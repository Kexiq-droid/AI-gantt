import { useEffect, useRef, useState } from 'react'
import type { Task } from '../types'

type Props = {
  task: Task
  onClose: () => void
  onSave: (id: number, body: Record<string, unknown>) => Promise<void>
}

export function TaskModal({ task, onClose, onSave }: Props) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description)
  const [assignee, setAssignee] = useState(task.assignee)
  const [duration, setDuration] = useState(task.duration_days)
  const [progress, setProgress] = useState(task.progress_pct ?? 0)
  const [saving, setSaving] = useState(false)
  const isPhase = Boolean(task.has_children)
  // Close only on a full click that both starts and ends on the backdrop
  // (not when drag starts inside the dialog and ends outside).
  const backdropPointerDown = useRef(false)

  useEffect(() => {
    setTitle(task.title)
    setDescription(task.description)
    setAssignee(task.assignee)
    setDuration(task.duration_days)
    setProgress(task.progress_pct ?? 0)
  }, [task])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleSave = async () => {
    if (saving) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        title,
        description,
        assignee,
        duration_days: duration,
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
          void handleSave()
        }}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="text-xs text-[var(--muted)]">{task.code}</div>
            <h3 className="text-xl">Задача</h3>
          </div>
          <button type="button" className="text-[var(--muted)]" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-[var(--muted)]">Название</span>
            <input
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Описание</span>
            <textarea
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void handleSave()
                }
              }}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Исполнитель</span>
            <input
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">Длительность, дни</span>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={duration}
              onFocus={(e) => e.currentTarget.select()}
              onClick={(e) => e.currentTarget.select()}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </label>
          <label className="block">
            <span className="text-[var(--muted)]">
              Прогресс, %{isPhase ? ' (считается по подзадачам)' : ''}
            </span>
            <input
              type="number"
              min={0}
              max={100}
              disabled={isPhase}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 disabled:opacity-60"
              value={progress}
              onFocus={(e) => e.currentTarget.select()}
              onClick={(e) => e.currentTarget.select()}
              onChange={(e) => setProgress(Math.max(0, Math.min(100, Number(e.target.value))))}
            />
          </label>
          <div className="grid grid-cols-2 gap-3 text-[var(--muted)]">
            <div>
              Начало: <span className="text-[var(--text)]">{task.start_date}</span>
            </div>
            <div>
              Окончание: <span className="text-[var(--text)]">{task.end_date}</span>
            </div>
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
            Отмена
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            Сохранить
          </button>
        </div>
      </form>
    </div>
  )
}
