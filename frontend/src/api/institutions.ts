import { apiFetch } from './client'

export interface Institution {
  id: number
  name: string
  location: string
  preferred_sectors: string
  preferred_stages: string
  known_preferences: string
  contact_name: string
  contact_wechat: string
  fa_fee_note: string
  response_style: string
  track_updates: number
  website: string
  founded_year: string
  aum: string
  key_partners: string
}

export const institutionsApi = {
  list: () => apiFetch<Institution[]>('/api/institutions'),
  get: (id: number) => apiFetch<Institution>(`/api/institutions/${id}`),
  create: (d: Partial<Institution>) =>
    apiFetch<Institution & { scrape_job_id: string }>('/api/institutions', {
      method: 'POST',
      body: JSON.stringify(d)
    }),
  update: (id: number, d: Partial<Institution>) =>
    apiFetch<Institution>(`/api/institutions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(d)
    }),
  delete: (id: number) =>
    apiFetch<void>(`/api/institutions/${id}`, { method: 'DELETE' }),
  scrape: (id: number) =>
    apiFetch<{ job_id: string }>(`/api/institutions/${id}/scrape`, {
      method: 'POST'
    }),
  records: (id: number) =>
    apiFetch<unknown[]>(`/api/institutions/${id}/records`),
  importExcel: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return apiFetch<{ created: number }>('/api/institutions/import', {
      method: 'POST',
      body: fd,
      headers: {}
    })
  }
}
