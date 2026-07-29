import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AgentJournal } from './components/AgentJournal'
import { AssigneesModal } from './components/AssigneesModal'
import { ChatPanel } from './components/ChatPanel'
import { CreateTaskModal, type CreateTaskContext } from './components/CreateTaskModal'
import { GanttChart } from './components/GanttChart'
import { TaskModal } from './components/TaskModal'
import { LoginPage } from './LoginPage'
import type { Assignee, ChatMessage, Plan, Task, User } from './types'

function getTheme(): 'light' | 'dark' {
  const saved = localStorage.getItem('bioplan-theme')
  return saved === 'dark' ? 'dark' : 'light'
}

function applyTheme(theme: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('bioplan-theme', theme)
}

const CHAT_OPEN_KEY = 'bioplan-chat-open'
const CHAT_WIDTH_KEY = 'bioplan-chat-width'
const CHAT_MIN_WIDTH = 280
const CHAT_MAX_WIDTH = 720
const CHAT_DEFAULT_WIDTH = 360

function clampChatWidth(w: number) {
  return Math.min(CHAT_MAX_WIDTH, Math.max(CHAT_MIN_WIDTH, Math.round(w)))
}

function loadChatOpen() {
  const v = localStorage.getItem(CHAT_OPEN_KEY)
  if (v === null) return false
  return v === '1'
}

function loadChatWidth() {
  const n = Number(localStorage.getItem(CHAT_WIDTH_KEY))
  return Number.isFinite(n) && n > 0 ? clampChatWidth(n) : CHAT_DEFAULT_WIDTH
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selected, setSelected] = useState<Task | null>(null)
  const [createCtx, setCreateCtx] = useState<CreateTaskContext | null>(null)
  const [assignees, setAssignees] = useState<Assignee[]>([])
  const [assigneesOpen, setAssigneesOpen] = useState(false)
  const [highlight, setHighlight] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>(getTheme)
  const [journalOpen, setJournalOpen] = useState(false)
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)
  const [error, setError] = useState('')
  const [chatOpen, setChatOpen] = useState(loadChatOpen)
  const [chatWidth, setChatWidth] = useState(loadChatWidth)
  const fileRef = useRef<HTMLInputElement>(null)
  const knownJobs = useRef<Set<number>>(new Set())
  const resizingChat = useRef(false)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem(CHAT_OPEN_KEY, chatOpen ? '1' : '0')
  }, [chatOpen])

  useEffect(() => {
    localStorage.setItem(CHAT_WIDTH_KEY, String(chatWidth))
  }, [chatWidth])

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!resizingChat.current) return
      setChatWidth(clampChatWidth(window.innerWidth - e.clientX - 12))
    }
    function onUp() {
      if (!resizingChat.current) return
      resizingChat.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [])

  const refresh = useCallback(async () => {
    const [p, m, a] = await Promise.all([api.plan(), api.messages(), api.assignees()])
    setPlan(p)
    setMessages(m)
    setAssignees(a)
    return { p, m, a }
  }, [])

  const assigneeOptions = assignees.map((a) => a.name)

  useEffect(() => {
    api
      .me()
      .then(async (u) => {
        setUser(u)
        await refresh()
      })
      .catch(() => setUser(null))
      .finally(() => setBooting(false))
  }, [refresh])

  useEffect(() => {
    if (!user) return
    const t = window.setInterval(async () => {
      try {
        const runs = await api.runs()
        for (const job of runs) {
          if (
            (job.status === 'done' || job.status === 'failed') &&
            !knownJobs.current.has(job.id) &&
            job.finished_at
          ) {
            const finished = new Date(job.finished_at).getTime()
            if (Date.now() - finished < 60_000) {
              knownJobs.current.add(job.id)
              setToast(
                job.status === 'done'
                  ? `Ассистент завершил задачу #${job.id}`
                  : `Ассистент завершился с ошибкой #${job.id}`,
              )
              await refresh()
              if (job.changes?.length) {
                setHighlight(job.changes)
                window.setTimeout(() => setHighlight([]), 4500)
              }
            } else {
              knownJobs.current.add(job.id)
            }
          }
          if (job.status === 'queued' || job.status === 'running') {
            knownJobs.current.delete(job.id)
          }
        }
      } catch {
        /* ignore poll errors */
      }
    }, 4000)
    return () => clearInterval(t)
  }, [user, refresh])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(''), 4500)
    return () => clearTimeout(t)
  }, [toast])

  async function pollJob(jobId: number) {
    setBusy(true)
    try {
      for (let i = 0; i < 90; i++) {
        const job = await api.job(jobId)
        if (job.status === 'done' || job.status === 'failed') {
          knownJobs.current.add(jobId)
          await refresh()
          if (job.changes?.length) {
            setHighlight(job.changes)
            window.setTimeout(() => setHighlight([]), 4500)
          }
          if (job.status === 'failed') {
            setToast(job.error || 'Ошибка ассистента')
          }
          return
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    } finally {
      setBusy(false)
    }
  }

  if (booting) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--muted)]">Загрузка…</div>
    )
  }

  if (!user) {
    return (
      <LoginPage
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
        onLogin={async () => {
          const u = await api.me()
          setUser(u)
          await refresh()
        }}
      />
    )
  }

  const canEdit = user.role !== 'viewer'

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3">
        <div className="brand text-2xl text-[var(--accent)]">BioPlan</div>
        <div className="text-sm text-[var(--muted)]">
          /{user.login}
          {!canEdit && <span className="ml-2 text-[var(--accent)]">· просмотр</span>}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
            onClick={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}
          >
            {theme === 'light' ? 'Тёмная тема' : 'Светлая тема'}
          </button>
          {canEdit && (
            <>
              <button
                type="button"
                className={`header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm ${
                  !plan || plan.undo_count < 1 ? 'is-disabled' : ''
                }`}
                aria-disabled={!plan || plan.undo_count < 1}
                onClick={async () => {
                  if (!plan || plan.undo_count < 1) return
                  try {
                    setPlan(await api.undo())
                    setToast('Изменение отменено')
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Ошибка')
                  }
                }}
              >
                ← Отменить ({plan?.undo_count ?? 0})
              </button>
              <button
                type="button"
                className={`header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm ${
                  !plan || (plan.redo_count ?? 0) < 1 ? 'is-disabled' : ''
                }`}
                aria-disabled={!plan || (plan.redo_count ?? 0) < 1}
                onClick={async () => {
                  if (!plan || (plan.redo_count ?? 0) < 1) return
                  try {
                    setPlan(await api.redo())
                    setToast('Изменение повторено')
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Ошибка')
                  }
                }}
              >
                Повторить → ({plan?.redo_count ?? 0})
              </button>
              <button
                type="button"
                className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
                onClick={() => setAssigneesOpen(true)}
              >
                Исполнители
              </button>
              <button
                type="button"
                className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
                onClick={() => fileRef.current?.click()}
              >
                Импорт Excel
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (!file) return
                  try {
                    setPlan(await api.importExcel(file))
                    setToast('План импортирован')
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Импорт не удался')
                  }
                }}
              />
            </>
          )}
          <button
            type="button"
            className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
            onClick={async () => {
              const { blob, filename } = await api.exportExcel()
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = filename
              a.click()
              URL.revokeObjectURL(url)
            }}
          >
            Экспорт Excel
          </button>
          {canEdit && (
            <button
              type="button"
              className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
              onClick={() => setResetConfirmOpen(true)}
            >
              Очистить план
            </button>
          )}
          <button
            type="button"
            className="header-action rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
            onClick={() => setJournalOpen(true)}
          >
            Журнал ассистента
          </button>
          <button
            type="button"
            className="header-action rounded-lg px-3 py-1.5 text-sm text-[var(--muted)]"
            onClick={async () => {
              await api.logout()
              setUser(null)
              setPlan(null)
            }}
          >
            Выйти
          </button>
        </div>
      </header>

      {(toast || error) && (
        <div className="px-4 pt-2">
          {toast && (
            <div className="rounded-lg bg-[var(--accent-soft)] px-3 py-2 text-sm text-[var(--accent)]">
              {toast}
            </div>
          )}
          {error && (
            <div className="mt-1 rounded-lg bg-red-100 px-3 py-2 text-sm text-[var(--danger)]">
              {error}
              <button type="button" className="ml-2 underline" onClick={() => setError('')}>
                закрыть
              </button>
            </div>
          )}
        </div>
      )}

      <main className="flex min-h-0 flex-1 gap-0 p-3">
        <div className="min-h-0 min-w-0 flex-1">
          {plan ? (
            <GanttChart
              plan={plan}
              highlightCodes={highlight}
              onSelect={setSelected}
              onShiftTasks={async (taskIds, days) => {
                if (!canEdit || !days || taskIds.length === 0) return
                setPlan(await api.shiftTasks(taskIds, days))
              }}
              onRequestCreate={(ctx) => {
                if (!canEdit) return
                setError('')
                setCreateCtx({
                  ...ctx,
                  default_start: plan.start_date,
                })
              }}
              onDeleteTask={async (task) => {
                if (!canEdit) return
                setError('')
                if (task.has_children) {
                  setError(
                    `Нельзя удалить ${task.code}: есть дочерние задачи. Сначала удалите их.`,
                  )
                  return
                }
                if (!window.confirm(`Удалить задачу «${task.code} ${task.title}»?`)) return
                try {
                  setPlan(await api.deleteTask(task.id))
                  if (selected?.id === task.id) setSelected(null)
                  setToast(`Удалено: ${task.code}`)
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Ошибка удаления')
                }
              }}
              onReorderTasks={async (body) => {
                if (!canEdit) return
                setError('')
                try {
                  setPlan(await api.reorderTasks(body))
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Ошибка порядка')
                }
              }}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-[var(--muted)]">
              Нет плана
            </div>
          )}
        </div>

        {canEdit && chatOpen && (
          <>
            <div
              role="separator"
              aria-orientation="vertical"
              aria-label="Изменить ширину чата"
              title="Потяните, чтобы изменить ширину"
              className="mx-1 w-1.5 shrink-0 cursor-ew-resize rounded-full bg-transparent hover:bg-[var(--accent)]/35 active:bg-[var(--accent)]/55"
              onPointerDown={(e) => {
                e.preventDefault()
                resizingChat.current = true
                document.body.style.cursor = 'ew-resize'
                document.body.style.userSelect = 'none'
              }}
            />
            <div className="min-h-0 shrink-0" style={{ width: chatWidth }}>
              <ChatPanel
                messages={messages}
                busy={busy}
                onCollapse={() => setChatOpen(false)}
                onRated={(jobId, rating) => {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.role === 'assistant' && m.job_id === jobId
                        ? { ...m, meta: { ...(m.meta || {}), rating } }
                        : m,
                    ),
                  )
                }}
                onSend={async (text, file) => {
                  setError('')
                  try {
                    const { job_id } = await api.chat(text, file)
                    await refresh()
                    await pollJob(job_id)
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Ошибка чата')
                  }
                }}
              />
            </div>
          </>
        )}
      </main>

      {canEdit && !chatOpen && (
        <button
          type="button"
          aria-label="Открыть чат с ассистентом"
          title="Ассистент"
          className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-[var(--accent)] px-4 py-3 text-sm font-medium text-white shadow-lg transition hover:brightness-110"
          onClick={() => setChatOpen(true)}
        >
          <span aria-hidden>💬</span>
          Ассистент
          {busy && (
            <span className="ml-0.5 inline-block h-2 w-2 animate-pulse rounded-full bg-amber-300" />
          )}
        </button>
      )}

      {selected && (
        <TaskModal
          task={selected}
          assigneeOptions={assigneeOptions}
          readOnly={!canEdit}
          onClose={() => setSelected(null)}
          onSave={async (id, body) => {
            setPlan(await api.updateTask(id, body))
            setAssignees(await api.assignees())
          }}
        />
      )}
      {canEdit && createCtx && (
        <CreateTaskModal
          context={createCtx}
          assigneeOptions={assigneeOptions}
          onClose={() => setCreateCtx(null)}
          onCreate={async (body) => {
            setError('')
            try {
              const next = await api.createTask(body)
              setPlan(next)
              setAssignees(await api.assignees())
              const created = [...next.tasks].reverse().find((t) => t.title === body.title)
              if (created) {
                setSelected(created)
                setHighlight([created.code])
              }
              setToast('Задача создана')
            } catch (e) {
              setError(e instanceof Error ? e.message : 'Ошибка создания')
              throw e
            }
          }}
        />
      )}
      <AssigneesModal
        open={assigneesOpen && canEdit}
        assignees={assignees}
        onClose={() => setAssigneesOpen(false)}
        onCreate={async (name) => {
          await api.createAssignee(name)
          setAssignees(await api.assignees())
          setToast(`Добавлен: ${name}`)
        }}
        onDelete={async (id) => {
          await api.deleteAssignee(id)
          setAssignees(await api.assignees())
          setPlan(await api.plan())
          setToast('Исполнитель удалён')
        }}
      />
      <AgentJournal open={journalOpen} onClose={() => setJournalOpen(false)} />

      {resetConfirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={() => setResetConfirmOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-plan-title"
          >
            <h2 id="reset-plan-title" className="text-lg font-medium">
              Очистить план?
            </h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Все задачи будут удалены. Чат и журнал ассистента тоже очистятся.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg bg-[var(--surface-2)] px-3 py-1.5 text-sm"
                onClick={() => setResetConfirmOpen(false)}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm text-white"
                onClick={async () => {
                  setResetConfirmOpen(false)
                  try {
                    setPlan(await api.resetSeed())
                    setMessages([])
                    setToast('План очищен')
                    await refresh()
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Ошибка очистки')
                  }
                }}
              >
                Очистить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
