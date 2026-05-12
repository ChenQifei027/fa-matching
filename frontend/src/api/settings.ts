import { apiFetch } from './client'

export interface Settings {
  anthropic_api_key: string
  model: string
  db_path: string
}

export const settingsApi = {
  get: () => apiFetch<Settings>('/api/settings'),
  update: (d: Partial<Settings>) =>
    apiFetch<{ ok: boolean }>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(d)
    }),
  verifyLlm: () =>
    apiFetch<{ configured: boolean }>('/api/settings/verify-llm'),
  syncCookies: () =>
    apiFetch<{ synced: number }>('/api/settings/sync-cookies', {
      method: 'POST'
    })
}
