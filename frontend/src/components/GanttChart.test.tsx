import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { GanttChart } from '../components/GanttChart'
import type { Plan } from '../types'

const emptyPlan: Plan = {
  id: 1,
  title: 'Новый проект',
  start_date: '2026-07-29',
  tasks: [],
  dependencies: [],
  undo_count: 0,
  redo_count: 0,
}

const miniPlan: Plan = {
  id: 1,
  title: 'VAX-B demo',
  start_date: '2026-07-01',
  tasks: [
    {
      id: 1,
      code: 'P1',
      parent_id: null,
      parent_code: null,
      title: 'Discovery',
      description: '',
      assignee: '',
      duration_days: 10,
      progress_pct: 0,
      start_date: '2026-07-01',
      end_date: '2026-07-11',
      sort_order: 10,
      last_changed_by: 'user',
      predecessor_codes: [],
      has_children: false,
    },
  ],
  dependencies: [],
  undo_count: 0,
  redo_count: 0,
}

const noop = {
  onSelect: vi.fn(),
  onShiftTasks: vi.fn(),
  onRequestCreate: vi.fn(),
  onDeleteTask: vi.fn(),
  onReorderTasks: vi.fn(),
}

describe('GanttChart', () => {
  it('shows empty-project hint when there are no tasks', () => {
    render(<GanttChart plan={emptyPlan} highlightCodes={[]} {...noop} />)
    expect(screen.getByText('Новый проект')).toBeInTheDocument()
    expect(screen.getByText(/Пустой проект/i)).toBeInTheDocument()
  })

  it('renders task code and title', () => {
    render(<GanttChart plan={miniPlan} highlightCodes={['P1']} {...noop} />)
    expect(screen.getByText('VAX-B demo')).toBeInTheDocument()
    expect(screen.getByText('P1')).toBeInTheDocument()
    expect(screen.getByText('Discovery')).toBeInTheDocument()
  })
})
