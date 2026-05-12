import { apiFetch } from './client'

export interface Project {
  id: number
  name: string
  file_path: string
  sector: string
  sub_sector: string
  stage: string
  location: string
  description: string
  highlights: string
  financing_need: string
  report_json: string | null
  report_generated_at: string | null
  research_json: string | null
  research_generated_at: string | null
}

export interface ParsedBP {
  name?: string
  sector?: string
  sub_sector?: string
  stage?: string
  location?: string
  description?: string
  highlights?: string
  financing_need?: string
  file_path: string
  default_name: string
}

export const projectsApi = {
  list: () => apiFetch<Project[]>('/api/projects'),
  get: (id: number) => apiFetch<Project>(`/api/projects/${id}`),
  create: (d: Partial<Project>) =>
    apiFetch<Project>('/api/projects', { method: 'POST', body: JSON.stringify(d) }),
  update: (id: number, d: Partial<Project>) =>
    apiFetch<Project>(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(d) }),
  delete: (id: number) =>
    apiFetch<void>(`/api/projects/${id}`, { method: 'DELETE' }),
  parse: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return apiFetch<ParsedBP>('/api/projects/parse', {
      method: 'POST',
      body: fd,
      headers: {}
    })
  },
  startReport: (id: number) =>
    apiFetch<{ job_id: string }>(`/api/projects/${id}/report`, { method: 'POST' }),
  startResearch: (id: number) =>
    apiFetch<{ job_id: string }>(`/api/projects/${id}/research`, { method: 'POST' }),
  fundingRounds: (id: number) =>
    apiFetch<unknown[]>(`/api/projects/${id}/funding-rounds`)
}
