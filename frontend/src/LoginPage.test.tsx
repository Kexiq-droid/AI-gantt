import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'

vi.mock('./api', () => ({
  api: {
    login: vi.fn(),
  },
}))

vi.mock('./components/ui/wavy-background', () => ({
  BIOPLAN_WAVE_COLORS: [],
  BIOPLAN_WAVE_COLORS_DARK: [],
  WavyBackground: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="wave">{children}</div>
  ),
}))

import { api } from './api'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.mocked(api.login).mockReset()
  })

  it('renders brand and default credentials', () => {
    render(
      <LoginPage onLogin={vi.fn()} theme="light" onToggleTheme={vi.fn()} />,
    )
    expect(screen.getByText('BioPlan')).toBeInTheDocument()
    expect(screen.getByDisplayValue('pm')).toBeInTheDocument()
    expect(screen.getByDisplayValue('pm12345')).toBeInTheDocument()
  })

  it('calls api.login and onLogin on success', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    vi.mocked(api.login).mockResolvedValue({ id: 1, login: 'pm', role: 'editor' })

    render(<LoginPage onLogin={onLogin} theme="light" onToggleTheme={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('pm', 'pm12345')
      expect(onLogin).toHaveBeenCalled()
    })
  })

  it('shows error when login fails', async () => {
    const user = userEvent.setup()
    vi.mocked(api.login).mockRejectedValue(new Error('Неверный логин или пароль'))

    render(<LoginPage onLogin={vi.fn()} theme="light" onToggleTheme={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByText('Неверный логин или пароль')).toBeInTheDocument()
  })

  it('toggles theme', async () => {
    const user = userEvent.setup()
    const onToggleTheme = vi.fn()
    render(
      <LoginPage onLogin={vi.fn()} theme="light" onToggleTheme={onToggleTheme} />,
    )
    await user.click(screen.getByRole('button', { name: 'Включить тёмную тему' }))
    expect(onToggleTheme).toHaveBeenCalled()
  })
})
