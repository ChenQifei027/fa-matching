import { apiFetch } from './client'

export interface MatchResult {
  id: number
  name: string
  score: number
  reason: string
  preferred_sectors: string
  preferred_stages: string
}

export const matchingApi = {
  projectToInstitutions: (projectId: number) =>
    apiFetch<MatchResult[]>('/api/matching/project-to-institutions', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId })
    }),
  institutionToProjects: (institutionId: number) =>
    apiFetch<MatchResult[]>('/api/matching/institution-to-projects', {
      method: 'POST',
      body: JSON.stringify({ institution_id: institutionId })
    })
}
