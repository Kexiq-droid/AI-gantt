import { useEffect, useState } from 'react'
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
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="text-xs text-[var(--muted)]">{task.code}</div>
            <h3 className="text-xl">Детали задачи</h3>
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
            <span className="text-[var(--muted)]">Длительность (дни)</span>
            <input
              type="number"
              min={1}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </label>
          <div className="grid grid-cols-2 gap-3 text-[var(--muted)]">
            <div>
              Старт: <span className="text-[var(--text)]">{task.start_date}</span>
            </div>
            <div>
              Конец: <span className="text-[var(--text)]">{task.end_date}</span>
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
                {task.last_changed_by === 'agent' ? 'агент' : 'пользователь'}
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
            type="button"
            disabled={saving}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm text-white disabled:opacity-60"
            onClick={async () => {
              setSaving(true)
              try {
                await onSave(task.id, {
                  title,
                  description,
                  assignee,
                  duration_days: duration,
                })
                onClose()
              } finally {
                setSaving(false)
              }
            }}
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  )
}
