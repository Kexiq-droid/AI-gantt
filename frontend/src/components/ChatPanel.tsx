import { Fragment, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../types'
import { api } from '../api'
import { MarkdownMessage } from './MarkdownMessage'

type Props = {
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string, file?: File | null) => Promise<void>
  onRated: (jobId: number, rating: 'up' | 'down') => void
  onCollapse: () => void
}

const MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
] as const

function dayKey(d: Date) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

function formatTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function formatDayLabel(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((today.getTime() - msgDay.getTime()) / 86_400_000)
  if (diffDays === 0) return 'Сегодня'
  if (diffDays === 1) return 'Вчера'
  const base = `${d.getDate()} ${MONTHS_GENITIVE[d.getMonth()]}`
  return d.getFullYear() === now.getFullYear() ? base : `${base} ${d.getFullYear()}`
}

export function ChatPanel({ messages, busy, onSend, onRated, onCollapse }: Props) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [ratings, setRatings] = useState<Record<number, 'up' | 'down'>>({})
  const [pending, setPending] = useState<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  useEffect(() => {
    const next: Record<number, 'up' | 'down'> = {}
    for (const m of messages) {
      if (m.job_id && (m.meta?.rating === 'up' || m.meta?.rating === 'down')) {
        next[m.job_id] = m.meta.rating
      }
    }
    setRatings((prev) => ({ ...prev, ...next }))
  }, [messages])

  async function rate(jobId: number, value: 'up' | 'down') {
    if (pending === jobId) return
    setPending(jobId)
    setRatings((prev) => ({ ...prev, [jobId]: value }))
    try {
      await api.rate(jobId, value)
      onRated(jobId, value)
    } catch {
      setRatings((prev) => {
        const copy = { ...prev }
        delete copy[jobId]
        const msg = messages.find((m) => m.job_id === jobId)
        if (msg?.meta?.rating === 'up' || msg?.meta?.rating === 'down') {
          copy[jobId] = msg.meta.rating
        }
        return copy
      })
    } finally {
      setPending(null)
    }
  }

  async function submit() {
    if (busy) return
    const msg = text.trim()
    if (!msg && !file) return
    const attached = file
    setText('')
    setFile(null)
    if (fileRef.current) fileRef.current.value = ''
    await onSend(msg || (attached ? `Импортируй план из файла «${attached.name}»` : ''), attached)
  }

  let lastDay = ''

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]">
      <div className="flex items-start gap-2 border-b border-[var(--border)] px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-wide text-[var(--muted)]">Ассистент</div>
          <h2 className="text-lg leading-tight">Чат с планом</h2>
        </div>
        <button
          type="button"
          title="Свернуть"
          aria-label="Свернуть чат"
          className="rounded-md px-2 py-1 text-sm text-[var(--muted)] hover:bg-[var(--surface-2)]"
          onClick={onCollapse}
        >
          −
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto px-4 py-3">
        {messages.length === 0 && (
          <p className="text-sm text-[var(--muted)]">
            Например: «Сдвинь всю доклинику на 10 дней…» / «назначь Иванова на CMC» или прикрепите Excel VAX-B
            «импортируй».
          </p>
        )}
        {messages.filter((m) => !(m.meta?.hidden || m.meta?.source === 'ui')).map((m) => {
          const selected = m.job_id ? ratings[m.job_id] : undefined
          const d = new Date(m.created_at)
          const key = Number.isNaN(d.getTime()) ? '' : dayKey(d)
          const showDay = Boolean(key) && key !== lastDay
          if (key) lastDay = key
          const time = formatTime(m.created_at)
          const isUser = m.role === 'user'

          return (
            <Fragment key={m.id}>
              {showDay && (
                <div className="flex justify-center py-1">
                  <span className="rounded-full bg-[var(--surface-2)] px-3 py-0.5 text-xs text-[var(--muted)]">
                    {formatDayLabel(m.created_at)}
                  </span>
                </div>
              )}
              <div
                className={`max-w-[95%] rounded-xl px-3 pt-2 pb-1.5 text-sm ${
                  isUser ? 'ml-auto bg-[var(--accent)] text-white' : 'bg-[var(--surface-2)]'
                }`}
              >
                {m.meta?.attachment_name && (
                  <div
                    className={`mb-1.5 inline-flex max-w-full items-center gap-1.5 rounded-lg px-2 py-1 text-xs ${
                      isUser ? 'bg-white/15' : 'bg-[var(--bg)]'
                    }`}
                  >
                    <span aria-hidden>📎</span>
                    <span className="truncate">{m.meta.attachment_name}</span>
                  </div>
                )}
                {m.role === 'assistant' ? (
                  <MarkdownMessage content={m.content} />
                ) : (
                  <div className="whitespace-pre-wrap">{m.content}</div>
                )}
                {m.meta?.changes && m.meta.changes.length > 0 && (
                  <div className="mt-2 text-xs opacity-80">
                    Изменения: {m.meta.changes.join(', ')}
                  </div>
                )}
                {m.role === 'assistant' && m.job_id && (
                  <div className="mt-2 flex items-center gap-1.5">
                    <button
                      type="button"
                      title="Полезно"
                      disabled={pending === m.job_id}
                      aria-pressed={selected === 'up'}
                      className={`rounded-md px-1.5 py-0.5 text-base transition ${
                        selected === 'up'
                          ? 'scale-110 bg-emerald-500/25 opacity-100 ring-1 ring-emerald-400/60'
                          : 'opacity-40 hover:opacity-80'
                      }`}
                      onClick={() => rate(m.job_id!, 'up')}
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      title="Не полезно"
                      disabled={pending === m.job_id}
                      aria-pressed={selected === 'down'}
                      className={`rounded-md px-1.5 py-0.5 text-base transition ${
                        selected === 'down'
                          ? 'scale-110 bg-rose-500/25 opacity-100 ring-1 ring-rose-400/60'
                          : 'opacity-40 hover:opacity-80'
                      }`}
                      onClick={() => rate(m.job_id!, 'down')}
                    >
                      👎
                    </button>
                  </div>
                )}
                {m.meta?.tool_calls && (m.meta.tool_calls as unknown[]).length > 0 && (
                  <details className="mt-2 text-xs opacity-80">
                    <summary>Вызовы инструментов</summary>
                    <pre className="mt-1 overflow-auto whitespace-pre-wrap">
                      {JSON.stringify(m.meta.tool_calls, null, 2)}
                    </pre>
                  </details>
                )}
                {time && (
                  <div
                    className={`mt-1 text-right text-[10px] leading-none ${
                      isUser ? 'text-white/55' : 'text-[var(--muted)]'
                    }`}
                  >
                    {time}
                  </div>
                )}
              </div>
            </Fragment>
          )
        })}
        {busy && (
          <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--muted)]">
            Ассистент думает…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="border-t border-[var(--border)] p-3"
        onSubmit={async (e) => {
          e.preventDefault()
          await submit()
        }}
      >
        {file && (
          <div className="mb-2 flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs">
            <span aria-hidden>📎</span>
            <span className="min-w-0 flex-1 truncate">{file.name}</span>
            <button
              type="button"
              className="text-[var(--muted)] hover:text-[var(--danger)]"
              aria-label="Убрать файл"
              onClick={() => {
                setFile(null)
                if (fileRef.current) fileRef.current.value = ''
              }}
            >
              ✕
            </button>
          </div>
        )}
        <textarea
          className="mb-2 w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm"
          rows={3}
          placeholder="Напишите, что изменить в плане…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void submit()
            }
          }}
        />
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] || null
              setFile(f)
            }}
          />
          <button
            type="button"
            title="Прикрепить Excel"
            aria-label="Прикрепить Excel"
            disabled={busy}
            className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm disabled:opacity-50"
            onClick={() => fileRef.current?.click()}
          >
            📎
          </button>
          <button
            type="submit"
            disabled={busy || (!text.trim() && !file)}
            className="flex-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Отправить
          </button>
        </div>
      </form>
    </div>
  )
}
