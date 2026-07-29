async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || d).join('; ')
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : 'Ошибка запроса')
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res as unknown as T
}

export const api = {
  login: (login: string, password: string) =>
    request<import('./types').User>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login, password }),
    }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request<import('./types').User>('/api/auth/me'),
  plan: () => request<import('./types').Plan>('/api/plans/current'),
  updateTask: (id: number, body: Record<string, unknown>) =>
    request<import('./types').Plan>(`/api/plans/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  createTask: (body: {
    title: string
    parent_id?: number | null
    after_task_id?: number | null
    description?: string
    assignee?: string
    duration_days?: number
    start_date?: string
    code?: string
  }) =>
    request<import('./types').Plan>('/api/plans/tasks', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  assignees: () => request<import('./types').Assignee[]>('/api/plans/assignees'),
  createAssignee: (name: string) =>
    request<import('./types').Assignee>('/api/plans/assignees', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  deleteAssignee: (id: number) =>
    request<{ ok: boolean }>(`/api/plans/assignees/${id}`, { method: 'DELETE' }),
  deleteTask: (id: number) =>
    request<import('./types').Plan>(`/api/plans/tasks/${id}`, { method: 'DELETE' }),
  reorderTasks: (body: {
    task_id: number
    before_task_id?: number | null
    after_task_id?: number | null
  }) =>
    request<import('./types').Plan>('/api/plans/tasks/reorder', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  shiftTasks: (taskIds: number[], days: number) =>
    request<import('./types').Plan>('/api/plans/tasks/shift', {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds, days }),
    }),
  undo: () => request<import('./types').Plan>('/api/plans/current/undo', { method: 'POST' }),
  redo: () => request<import('./types').Plan>('/api/plans/current/redo', { method: 'POST' }),
  resetSeed: () =>
    request<import('./types').Plan>('/api/plans/current/reset-seed', { method: 'POST' }),
  exportExcel: async () => {
    const res = await fetch('/api/plans/current/export', { credentials: 'include' })
    if (!res.ok) throw new Error('Не удалось экспортировать')
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const utf = /filename\*=UTF-8''([^;]+)/i.exec(cd)
    const plain = /filename="?([^";]+)"?/i.exec(cd)
    let filename = 'BioPlan.xlsx'
    if (utf?.[1]) {
      try {
        filename = decodeURIComponent(utf[1])
      } catch {
        filename = utf[1]
      }
    } else if (plain?.[1]) {
      filename = plain[1]
    }
    return { blob, filename }
  },
  importExcel: async (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<import('./types').Plan>('/api/plans/current/import', {
      method: 'POST',
      body: fd,
      headers: {},
    })
  },
  chat: (message: string, file?: File | null) => {
    const fd = new FormData()
    fd.append('message', message)
    if (file) fd.append('file', file)
    return request<{ job_id: number }>('/api/chat', {
      method: 'POST',
      body: fd,
      headers: {},
    })
  },
  messages: () => request<import('./types').ChatMessage[]>('/api/chat/messages'),
  job: (id: number) => request<import('./types').AgentJob>(`/api/jobs/${id}`),
  runs: () => request<import('./types').AgentJob[]>('/api/agent/runs'),
  stats: () => request<import('./types').AgentStats>('/api/agent/stats'),
  rate: (id: number, rating: 'up' | 'down') =>
    request<import('./types').AgentJob>(`/api/jobs/${id}/rating`, {
      method: 'POST',
      body: JSON.stringify({ rating }),
    }),
  health: () => request<{ status: string; db: string; llm: string }>('/api/health'),
}
