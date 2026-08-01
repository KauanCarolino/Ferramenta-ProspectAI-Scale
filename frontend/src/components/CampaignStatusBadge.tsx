import { cn } from '@/lib/utils'
import type { CampaignStatus } from '@/lib/api/campaigns'

const STATUS_LABELS: Record<string, string> = {
  draft: 'Rascunho',
  active: 'Ativa',
  paused: 'Pausada',
  completed: 'Concluída',
  cancelled: 'Cancelada',
  auto_paused: 'Pausa automática',
}

interface CampaignStatusBadgeProps {
  status: CampaignStatus | string
  className?: string
}

export function campaignStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

export function CampaignStatusBadge({
  status,
  className,
}: CampaignStatusBadgeProps) {
  const isAutoPaused = status === 'auto_paused'

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        status === 'active' && 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-600/20',
        status === 'draft' && 'bg-slate-100 text-slate-700 ring-1 ring-slate-500/10',
        status === 'paused' && 'bg-amber-50 text-amber-900 ring-1 ring-amber-600/20',
        isAutoPaused && 'bg-orange-100 text-orange-900 ring-1 ring-orange-600/30 font-semibold',
        status === 'cancelled' && 'bg-slate-100 text-slate-500 ring-1 ring-slate-400/20',
        status === 'completed' && 'bg-sky-50 text-sky-800 ring-1 ring-sky-600/20',
        !['active', 'draft', 'paused', 'auto_paused', 'cancelled', 'completed'].includes(
          status,
        ) && 'bg-slate-100 text-slate-700 ring-1 ring-slate-500/10',
        className,
      )}
    >
      {campaignStatusLabel(status)}
    </span>
  )
}
