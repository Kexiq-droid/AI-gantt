import { useState, type FormEvent } from 'react'
import { api } from './api'

type Props = { onLogin: () => void }

export function LoginPage({ onLogin }: Props) {
  const [login, setLogin] = useState('pm')
  const [password, setPassword] = useState('pm12345')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await api.login(login, password)
      onLogin()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-[var(--bg)] px-4">
      <div className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-[var(--shadow)]">
        <div className="mb-6">
          <div className="brand text-4xl text-[var(--accent)]">BioPlan</div>
          <p className="mt-2 text-sm text-[var(--muted)]">
            AI-планировщик R&D: Gantt, Excel и правки на естественном языке
          </p>
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-sm">
            Логин
            <input
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label className="block text-sm">
            Пароль
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-[var(--accent)] py-2.5 font-medium text-white disabled:opacity-60"
          >
            {loading ? 'Вход…' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}
