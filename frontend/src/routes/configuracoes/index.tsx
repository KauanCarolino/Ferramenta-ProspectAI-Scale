import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { fetchSettings } from '@/lib/api/settings'

export const Route = createFileRoute('/configuracoes/')({
  component: SettingsPage,
})

function SettingsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    retry: 1,
  })

  return (
    <>
      <PageHeader
        title="Configurações"
        description="Rate limits, delays, warm-up e proxies"
      />

      {isLoading ? <LoadingState /> : null}

      {isError ? (
        <ErrorState
          message={
            error instanceof Error
              ? error.message
              : 'Falha ao carregar configurações'
          }
          onRetry={() => {
            void refetch()
          }}
        />
      ) : null}

      {data ? (
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <dt className="text-sm text-slate-500">Limite diário de DMs</dt>
            <dd className="mt-1 text-xl font-semibold">{data.daily_dm_limit}</dd>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <dt className="text-sm text-slate-500">Delay (segundos)</dt>
            <dd className="mt-1 text-xl font-semibold">
              {data.min_delay_seconds}–{data.max_delay_seconds}
            </dd>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <dt className="text-sm text-slate-500">Dias de warm-up</dt>
            <dd className="mt-1 text-xl font-semibold">{data.warmup_days}</dd>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <dt className="text-sm text-slate-500">Rotação de proxies</dt>
            <dd className="mt-1 text-xl font-semibold">
              {data.proxy_rotation ? 'Ativa' : 'Desativada'}
            </dd>
          </div>
        </dl>
      ) : null}

      {!isLoading && !isError && !data ? (
        <p className="text-sm text-slate-500">
          Nenhuma configuração retornada pela API.
        </p>
      ) : null}
    </>
  )
}
