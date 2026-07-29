import { useEffect, useRef, useState } from 'react'
import type { Assignee } from '../types'

type Props = {
  open: boolean
  assignees: Assignee[]
  onClose: () => void
  onCreate: (name: string) => Promise<void>
  onDelete: (id: number) => Promise<void>
}

export function AssigneesModal({ open, assignees, onClose, onCreate, onDelete }: Props) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const backdropPointerDown = useRef(false)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const handleAdd = async () => {
    const n = name.trim()
    if (!n || busy) return
    setBusy(true)
    setError('')
    try {
      await onCreate(n)
      setName('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка')
    } finally {
      setBusy(false)
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
      <div
        className="flex max-h-[80vh] w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
        onPointerDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-xl">Исполнители</h3>
            <div className="mt-0.5 text-xs text-[var(--muted)]">
              Справочник для подсказок в задачах
            </div>
          </div>
          <button type="button" className="text-[var(--muted)]" onClick={onClose}>
            ✕
          </button>
        </div>

        <form
          className="mb-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            void handleAdd()
          }}
        >
          <input
            className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm"
            placeholder="Новый исполнитель"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button
            type="submit"
            disabled={busy || !name.trim()}
            className="shrink-0 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            Добавить
          </button>
        </form>

        {error && (
          <div className="mb-3 rounded-lg bg-red-100 px-3 py-2 text-sm text-[var(--danger)]">
            {error}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-auto">
          {assignees.length === 0 ? (
            <div className="py-6 text-center text-sm text-[var(--muted)]">Пока никого нет</div>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {assignees.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2 py-2.5">
                  <span className="truncate text-sm">{a.name}</span>
                  <button
                    type="button"
                    className="shrink-0 text-sm text-[var(--danger)] hover:underline"
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `Удалить «${a.name}»? У задач с этим исполнителем поле очистится.`,
                        )
                      ) {
                        return
                      }
                      setError('')
                      try {
                        await onDelete(a.id)
                      } catch (e) {
                        setError(e instanceof Error ? e.message : 'Ошибка удаления')
                      }
                    }}
                  >
                    Удалить
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
