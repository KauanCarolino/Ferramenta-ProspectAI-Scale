import { apiFetch } from './client'

export interface DashboardSummary {
  campaign_id: string | null
  enviadas_hoje: number
  respostas_hoje: number
  falhas_hoje: number
  progresso_pct: number
  leads_totais: number
  leads_restantes: number
  leads_enviados: number
  campanhas_ativas: number
  status_campanha: string | null
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/dashboard/summary')
}
