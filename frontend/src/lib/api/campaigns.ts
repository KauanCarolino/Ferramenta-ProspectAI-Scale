import { apiFetch } from './client'

export type CampaignStatus =
  | 'draft'
  | 'active'
  | 'paused'
  | 'completed'
  | 'cancelled'
  | 'auto_paused'

export interface Campaign {
  id: string
  name: string
  status: CampaignStatus | string
  channel: string
  messages_per_day: number
  duration_days: number
  window_start: string
  window_end: string
  min_interval_sec: number
  max_interval_sec: number
  description: string | null
  created_at: string
  updated_at: string
}

export interface CampaignCreate {
  name: string
  channel?: string
  messages_per_day?: number
  duration_days?: number
  window_start?: string
  window_end?: string
  min_interval_sec?: number
  max_interval_sec?: number
  description?: string | null
}

export interface CampaignUpdate {
  name?: string
  messages_per_day?: number
  duration_days?: number
  window_start?: string
  window_end?: string
  min_interval_sec?: number
  max_interval_sec?: number
  description?: string | null
  status?: CampaignStatus
}

export interface ScheduledJob {
  id: string
  campaign_id: string
  lead_id: string
  account_id: string | null
  stage: string
  scheduled_at: string
  status: string
  channel: string
  created_at: string
  updated_at: string
}

export interface FetchCampaignJobsParams {
  limit?: number
  status?: string | null
}

export async function fetchCampaigns(): Promise<Campaign[]> {
  return apiFetch<Campaign[]>('/campaigns')
}

export async function fetchCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}`)
}

export async function createCampaign(
  payload: CampaignCreate,
): Promise<Campaign> {
  return apiFetch<Campaign>('/campaigns', {
    method: 'POST',
    body: payload,
  })
}

export async function updateCampaign(
  id: string,
  payload: CampaignUpdate,
): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function startCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}/start`, { method: 'POST' })
}

export async function pauseCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}/pause`, { method: 'POST' })
}

export async function resumeCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}/resume`, { method: 'POST' })
}

export async function cancelCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}/cancel`, { method: 'POST' })
}

export async function fetchCampaignJobs(
  id: string,
  params: FetchCampaignJobsParams = {},
): Promise<ScheduledJob[]> {
  const search = new URLSearchParams()
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  if (params.status !== undefined && params.status !== null) {
    search.set('status', params.status)
  }
  const query = search.toString()
  return apiFetch<ScheduledJob[]>(
    `/campaigns/${id}/jobs${query ? `?${query}` : ''}`,
  )
}
