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
  undo: () => request<import('./types').Plan>('/api/plans/current/undo', { method: 'POST' }),
  resetSeed: () =>
    request<import('./types').Plan>('/api/plans/current/reset-seed', { method: 'POST' }),
  exportExcel: async () => {
    const res = await fetch('/api/plans/current/export', { credentials: 'include' })
    if (!res.ok) throw new Error('Не удалось экспортировать')
    return res.blob()
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
  chat: (message: string) =>
    request<{ job_id: number }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
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
