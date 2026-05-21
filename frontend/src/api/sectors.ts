import { apiFetch, ApiError } from './client'

export interface SectorCompany {
  name: string
  desc: string
}

export interface SectorExplanation {
  name: string
  description: string
  industry_overview: string
  top_companies: SectorCompany[]
  synonyms: string[]
  generated_at: string
  generated_by: string
}

export const sectorsApi = {
  /** 拿缓存。命中返完整数据;未命中返 null(不抛错)。 */
  async get(name: string): Promise<SectorExplanation | null> {
    try {
      return await apiFetch<SectorExplanation>(`/api/sectors/${encodeURIComponent(name)}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }
  },

  /** 触发后台生成。返回 job_id。如果已存在且未 force,会抛 409。 */
  async generate(name: string, force = false): Promise<{ job_id: string }> {
    const qs = force ? '?force=true' : ''
    return apiFetch(`/api/sectors/${encodeURIComponent(name)}${qs}`, { method: 'POST' })
  },
}
