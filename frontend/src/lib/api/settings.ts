import { apiFetch } from './client'

export interface AppSettings {
  daily_dm_limit: number
  min_delay_seconds: number
  max_delay_seconds: number
  warmup_days: number
  proxy_rotation: boolean
}

export async function fetchSettings(): Promise<AppSettings> {
  return apiFetch<AppSettings>('/settings')
}
