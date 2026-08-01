import { useQuery } from '@tanstack/react-query'
import {
  fetchDashboardSummary,
  type DashboardSummary,
} from '@/lib/api/dashboard'

export const DASHBOARD_SUMMARY_QUERY_KEY = ['dashboard', 'summary'] as const

/** Placeholder usado quando a API ainda não está disponível. */
export const DASHBOARD_PLACEHOLDER: DashboardSummary = {
  campaign_id: null,
  enviadas_hoje: 0,
  respostas_hoje: 0,
  falhas_hoje: 0,
  progresso_pct: 0,
  leads_totais: 0,
  leads_restantes: 0,
  leads_enviados: 0,
  campanhas_ativas: 0,
  status_campanha: null,
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: DASHBOARD_SUMMARY_QUERY_KEY,
    queryFn: fetchDashboardSummary,
    retry: 1,
    staleTime: 10_000,
    refetchInterval: 10_000,
  })
}
