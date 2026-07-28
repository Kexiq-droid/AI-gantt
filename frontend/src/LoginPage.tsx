import { useState, type FormEvent } from 'react'
import { api } from './api'
import {
  BIOPLAN_WAVE_COLORS,
  BIOPLAN_WAVE_COLORS_DARK,
  WavyBackground,
} from './components/ui/wavy-background'

type Props = {
  onLogin: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}

export function LoginPage({ onLogin, theme, onToggleTheme }: Props) {
  const [login, setLogin] = useState('pm')
  const [password, setPassword] = useState('pm12345')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const dark = theme === 'dark'

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
    <div className="relative h-full min-h-full">
      <button
        type="button"
        onClick={onToggleTheme}
        className="absolute top-4 right-4 z-20 rounded-xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_55%,transparent)] px-3 py-2 text-sm text-[var(--text)] shadow-[var(--shadow)] backdrop-blur-xl transition hover:bg-[color-mix(in_srgb,var(--surface)_75%,transparent)]"
        title={dark ? 'Светлая тема' : 'Тёмная тема'}
        aria-label={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      >
        {dark ? 'Светлая' : 'Тёмная'}
      </button>

      <WavyBackground
        key={theme}
        containerClassName="min-h-full w-full px-4"
        className="w-full max-w-md"
        colors={dark ? BIOPLAN_WAVE_COLORS_DARK : BIOPLAN_WAVE_COLORS}
        backgroundFill={dark ? '#12181a' : '#f6f3ee'}
        blur={14}
        speed="slow"
        waveOpacity={dark ? 0.55 : 0.4}
      >
        <div
          className={[
            'w-full rounded-2xl border p-8 shadow-[var(--shadow)]',
            'backdrop-blur-2xl backdrop-saturate-150',
            dark
              ? 'border-white/10 bg-[color-mix(in_srgb,#1a2226_42%,transparent)]'
              : 'border-white/50 bg-[color-mix(in_srgb,#fffcf8_48%,transparent)]',
          ].join(' ')}
        >
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
                className={[
                  'mt-1 w-full rounded-lg border px-3 py-2',
                  dark
                    ? 'border-white/10 bg-[color-mix(in_srgb,#12181a_55%,transparent)] backdrop-blur-md'
                    : 'border-[var(--border)]/80 bg-[color-mix(in_srgb,#f6f3ee_55%,transparent)] backdrop-blur-md',
                ].join(' ')}
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                autoComplete="username"
              />
            </label>
            <label className="block text-sm">
              Пароль
              <input
                type="password"
                className={[
                  'mt-1 w-full rounded-lg border px-3 py-2',
                  dark
                    ? 'border-white/10 bg-[color-mix(in_srgb,#12181a_55%,transparent)] backdrop-blur-md'
                    : 'border-[var(--border)]/80 bg-[color-mix(in_srgb,#f6f3ee_55%,transparent)] backdrop-blur-md',
                ].join(' ')}
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
      </WavyBackground>
    </div>
  )
}
