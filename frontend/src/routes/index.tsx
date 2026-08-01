import { Link, createFileRoute } from '@tanstack/react-router'
import { CampaignStatusBadge } from '@/components/CampaignStatusBadge'
import { ErrorState } from '@/components/ErrorState'
import { KpiCard } from '@/components/KpiCard'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import {
  DASHBOARD_PLACEHOLDER,
  useDashboardSummary,
} from '@/hooks/useDashboardSummary'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/')({
  component: DashboardPage,
})

function formatNumber(value: number | undefined | null): string {
  return (value ?? 0).toLocaleString('pt-BR')
}

function DashboardPage() {
  const { data, isLoading, isError, error, refetch, isFetching } =
    useDashboardSummary()

  if (isLoading) {
    return (
      <>
        <PageHeader
          title="Dashboard"
          description="KPIs em tempo real da prospecção"
        />
        <LoadingState label="Carregando resumo…" />
      </>
    )
  }

  const summary = data ?? DASHBOARD_PLACEHOLDER
  const usingPlaceholder = isError || !data
  const isAutoPaused = summary.status_campanha === 'auto_paused'
  const hasFailures = (summary.falhas_hoje ?? 0) > 0

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="KPIs em tempo real da prospecção"
      />

      {usingPlaceholder ? (
        <div className="mb-4">
          <ErrorState
            message={
              error instanceof Error
                ? `${error.message} — exibindo placeholders até a API responder.`
                : 'API indisponível — exibindo placeholders.'
            }
            onRetry={() => {
              void refetch()
            }}
          />
        </div>
      ) : null}

      {isAutoPaused ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-orange-300 bg-orange-50 px-4 py-3 text-sm text-orange-950"
        >
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">Campanha em pausa automática</p>
            <CampaignStatusBadge status="auto_paused" />
          </div>
          <p className="mt-1">
            Revise contas e logs antes de retomar.{' '}
            <Link
              to="/campanhas"
              className="font-medium text-orange-900 underline hover:text-orange-950"
            >
              Ver campanhas
            </Link>
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Enviadas hoje"
          value={formatNumber(summary.enviadas_hoje)}
          hint={isFetching && !isLoading ? 'Atualizando…' : undefined}
        />
        <KpiCard
          label="Progresso"
          value={`${(summary.progresso_pct ?? 0).toFixed(1)}%`}
          hint={`${formatNumber(summary.leads_enviados)} de ${formatNumber(summary.leads_totais)} leads`}
        />
        <KpiCard
          label="Leads restantes"
          value={formatNumber(summary.leads_restantes)}
          hint="Fila + follow-ups"
        />
        <KpiCard
          label="Respostas hoje"
          value={formatNumber(summary.respostas_hoje)}
          hint={
            summary.campanhas_ativas > 0
              ? `${summary.campanhas_ativas} campanha(s) ativa(s)`
              : 'Nenhuma campanha ativa'
          }
        />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <article
          className={cn(
            'rounded-lg border bg-white p-4 shadow-sm',
            hasFailures
              ? 'border-red-300 ring-1 ring-red-200'
              : 'border-slate-200',
          )}
        >
          <p className="text-sm font-medium text-slate-500">Falhas hoje</p>
          <p
            className={cn(
              'mt-2 text-2xl font-semibold tracking-tight',
              hasFailures ? 'text-red-700' : 'text-slate-900',
            )}
          >
            {formatNumber(summary.falhas_hoje)}
          </p>
          {hasFailures ? (
            <p className="mt-1 text-xs text-red-600">
              Há falhas — confira{' '}
              <Link to="/logs" className="underline hover:text-red-800">
                logs
              </Link>
              .
            </p>
          ) : (
            <p className="mt-1 text-xs text-slate-400">Sem falhas registradas</p>
          )}
        </article>

        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Status campanha</p>
          <div className="mt-2">
            {summary.status_campanha ? (
              <CampaignStatusBadge status={summary.status_campanha} />
            ) : (
              <p className="text-2xl font-semibold text-slate-400">—</p>
            )}
          </div>
          {summary.campaign_id ? (
            <p className="mt-2 text-xs text-slate-500">
              <Link
                to="/campanhas/$id"
                params={{ id: summary.campaign_id }}
                className="font-medium text-brand-600 hover:text-brand-700"
              >
                Abrir campanha
              </Link>
            </p>
          ) : null}
        </article>

        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Campanhas ativas</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            {formatNumber(summary.campanhas_ativas)}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            <Link
              to="/campanhas"
              className="font-medium text-brand-600 hover:text-brand-700"
            >
              Gerenciar campanhas
            </Link>
          </p>
        </article>
      </div>
    </>
  )
}
