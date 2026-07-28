import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AgentJob, AgentStats } from '../types'

type Props = { open: boolean; onClose: () => void }

function statusLabel(status: string) {
  switch (status) {
    case 'done':
      return 'Готово'
    case 'failed':
      return 'Ошибка'
    case 'running':
      return 'В работе'
    case 'queued':
      return 'В очереди'
    default:
      return status
  }
}

export function AgentJournal({ open, onClose }: Props) {
  const [runs, setRuns] = useState<AgentJob[]>([])
  const [stats, setStats] = useState<AgentStats | null>(null)
  const [selected, setSelected] = useState<AgentJob | null>(null)

  useEffect(() => {
    if (!open) return
    Promise.all([api.runs(), api.stats()]).then(([r, s]) => {
      setRuns(r)
      setStats(s)
    })
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-xl flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-lg">Журнал ассистента</h2>
          <button type="button" onClick={onClose}>
            ✕
          </button>
        </div>
        {stats && (
          <div className="grid grid-cols-2 gap-2 border-b border-[var(--border)] p-4 text-sm">
            <div>Запросов: {stats.total}</div>
            <div>Успешно: {(stats.success_rate * 100).toFixed(0)}%</div>
            <div>Ошибки проверки: {(stats.validate_fail_rate * 100).toFixed(0)}%</div>
            <div>Отменено за 5 мин: {(stats.undo_after_agent_rate * 100).toFixed(0)}%</div>
            <div>👍 {stats.ratings_up}</div>
            <div>👎 {stats.ratings_down}</div>
            <div className="col-span-2 text-[var(--muted)]">
              Среднее время:{' '}
              {stats.avg_latency_ms != null ? `${Math.round(stats.avg_latency_ms)} мс` : '—'}
            </div>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[var(--surface-2)] text-xs text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2">ID</th>
                <th className="px-3 py-2">Статус</th>
                <th className="px-3 py-2">мс</th>
                <th className="px-3 py-2">Проверка</th>
                <th className="px-3 py-2">Отмена</th>
                <th className="px-3 py-2">Оценка</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr
                  key={r.id}
                  className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--surface-2)]"
                  onClick={() => setSelected(r)}
                >
                  <td className="px-3 py-2">{r.id}</td>
                  <td className="px-3 py-2">{statusLabel(r.status)}</td>
                  <td className="px-3 py-2">{r.latency_ms ?? '—'}</td>
                  <td className="px-3 py-2">
                    {r.validate_ok == null ? '—' : r.validate_ok ? 'ок' : 'ошибка'}
                  </td>
                  <td className="px-3 py-2">{r.undone_within_5m ? 'да' : ''}</td>
                  <td className="px-3 py-2">
                    {r.rating === 'up' ? '👍' : r.rating === 'down' ? '👎' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selected && (
          <div className="max-h-64 overflow-auto border-t border-[var(--border)] p-4 text-xs">
            <div className="mb-2 font-medium">Запрос #{selected.id}</div>
            <div className="mb-2 text-[var(--muted)]">{selected.request_text}</div>
            <pre className="whitespace-pre-wrap">{JSON.stringify(selected, null, 2)}</pre>
          </div>
        )}
      </aside>
    </div>
  )
}
