import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPanel } from '../components/ChatPanel'
import type { ChatMessage } from '../types'

vi.mock('../api', () => ({
  api: { rate: vi.fn() },
}))

vi.mock('../components/MarkdownMessage', () => ({
  MarkdownMessage: ({ text }: { text: string }) => <div>{text}</div>,
}))

function msg(partial: Partial<ChatMessage> & Pick<ChatMessage, 'id' | 'content'>): ChatMessage {
  return {
    role: 'user',
    job_id: null,
    meta: null,
    created_at: '2026-07-29T12:00:00Z',
    ...partial,
  }
}

describe('ChatPanel', () => {
  it('shows empty hint when no messages', () => {
    render(
      <ChatPanel
        messages={[]}
        busy={false}
        onSend={vi.fn()}
        onRated={vi.fn()}
        onCollapse={vi.fn()}
      />,
    )
    expect(screen.getByText(/добавь задачу/i)).toBeInTheDocument()
  })

  it('hides UI action messages from the list', () => {
    render(
      <ChatPanel
        messages={[
          msg({ id: 1, content: 'Видимое', meta: null }),
          msg({
            id: 2,
            content: '[UI_ACTION] {}',
            meta: { hidden: true, source: 'ui' },
          }),
        ]}
        busy={false}
        onSend={vi.fn()}
        onRated={vi.fn()}
        onCollapse={vi.fn()}
      />,
    )
    expect(screen.getByText('Видимое')).toBeInTheDocument()
    expect(screen.queryByText(/UI_ACTION/)).not.toBeInTheDocument()
  })

  it('sends trimmed text and clears input', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn().mockResolvedValue(undefined)
    render(
      <ChatPanel
        messages={[]}
        busy={false}
        onSend={onSend}
        onRated={vi.fn()}
        onCollapse={vi.fn()}
      />,
    )
    const box = screen.getByPlaceholderText(/что изменить в плане/i)
    await user.type(box, '  Сдвинь P1 на 1 день  ')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(onSend).toHaveBeenCalledWith('Сдвинь P1 на 1 день', null)
    expect(box).toHaveValue('')
  })

  it('does not send while busy', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(
      <ChatPanel
        messages={[]}
        busy
        onSend={onSend}
        onRated={vi.fn()}
        onCollapse={vi.fn()}
      />,
    )
    expect(screen.getByText(/Ассистент думает/i)).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText(/что изменить в плане/i), 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(onSend).not.toHaveBeenCalled()
  })
})
