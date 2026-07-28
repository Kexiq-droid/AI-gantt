export type Task = {
  id: number
  code: string
  parent_id: number | null
  parent_code: string | null
  title: string
  description: string
  assignee: string
  duration_days: number
  start_date: string
  end_date: string
  sort_order: number
  last_changed_by: string
  predecessor_codes: string[]
}

export type Plan = {
  id: number
  title: string
  start_date: string
  tasks: Task[]
  dependencies: {
    id: number
    predecessor_task_id: number
    successor_task_id: number
    predecessor_code: string
    successor_code: string
  }[]
  undo_count: number
}

export type User = { id: number; login: string }

export type ChatMessage = {
  id: number
  role: string
  content: string
  job_id: number | null
  meta: { changes?: string[]; tool_calls?: unknown[]; rating?: 'up' | 'down' } | null
  created_at: string
}

export type AgentJob = {
  id: number
  status: string
  request_text: string
  result_summary: string | null
  error: string | null
  changes: string[]
  provider: string | null
  model: string | null
  latency_ms: number | null
  validate_ok: boolean | null
  validate_errors: string[]
  tool_calls: unknown[]
  undone_within_5m: boolean
  rating: string | null
  created_at: string
  finished_at: string | null
}

export type AgentStats = {
  total: number
  success_rate: number
  validate_fail_rate: number
  undo_after_agent_rate: number
  avg_latency_ms: number | null
  ratings_up: number
  ratings_down: number
}
