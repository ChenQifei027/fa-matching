import { apiFetch } from './client'

export interface Job {
  status: 'pending' | 'running' | 'completed' | 'failed'
  result: unknown
  error: string | null
}

export function pollJob(
  jobId: string,
  onDone: (j: Job) => void,
  onError: (j: Job) => void
): () => void {
  const id = setInterval(async () => {
    try {
      const job = await apiFetch<Job>(`/api/jobs/${jobId}`)
      if (job.status === 'completed') {
        clearInterval(id)
        onDone(job)
      }
      if (job.status === 'failed') {
        clearInterval(id)
        onError(job)
      }
    } catch (_e: unknown) {
      clearInterval(id)
      onError({ status: 'failed', result: null, error: 'Network error' })
    }
  }, 2000)
  return () => clearInterval(id)
}
