import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CreateTaskModal } from '../components/CreateTaskModal'

describe('CreateTaskModal', () => {
  it('requires title before create', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn()
    render(
      <CreateTaskModal
        context={{ parent_id: null, after_task_id: null, default_start: '2026-07-01' }}
        assigneeOptions={['Иванов']}
        onClose={vi.fn()}
        onCreate={onCreate}
      />,
    )
    await user.click(screen.getByRole('button', { name: /создать/i }))
    expect(onCreate).not.toHaveBeenCalled()
  })

  it('submits title, dates and duration', async () => {
    const user = userEvent.setup()
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(
      <CreateTaskModal
        context={{ parent_id: 10, after_task_id: 11, default_start: '2026-07-01' }}
        assigneeOptions={[]}
        onClose={vi.fn()}
        onCreate={onCreate}
      />,
    )
    await user.type(screen.getByLabelText(/название/i), 'Новая задача')
    await user.click(screen.getByRole('button', { name: /создать/i }))
    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Новая задача',
        parent_id: 10,
        after_task_id: 11,
        start_date: '2026-07-01',
        duration_days: 5,
      }),
    )
  })
})
