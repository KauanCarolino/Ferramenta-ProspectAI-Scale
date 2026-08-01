import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { fetchLogs } from '@/lib/api/logs'

export const Route = createFileRoute('/logs/')({
  component: LogsPage,
})

function LogsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['logs'],
    queryFn: fetchLogs,
    retry: 1,
  })

  return (
    <>
      <PageHeader
        title="Logs"
        description="Auditoria de ações — filtros e export CSV"
      />

      {isLoading ? <LoadingState /> : null}

      {isError ? (
        <ErrorState
          message={
            error instanceof Error ? error.message : 'Falha ao carregar logs'
          }
          onRetry={() => {
            void refetch()
          }}
        />
      ) : null}

      {!isLoading && !isError && (data?.length ?? 0) === 0 ? (
        <EmptyState
          title="Nenhum log registrado"
          description="Os eventos do sistema aparecerão aqui conforme as campanhas rodarem"
        />
      ) : null}

      {!isLoading && !isError && data && data.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Resultado</th>
                <th className="px-4 py-2 font-medium">Ação</th>
                <th className="px-4 py-2 font-medium">Detalhe</th>
                <th className="px-4 py-2 font-medium">Campanha</th>
                <th className="px-4 py-2 font-medium">Quando</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((entry) => (
                <tr key={entry.id}>
                  <td className="px-4 py-2 font-medium text-slate-900">
                    {entry.result}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{entry.action}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {entry.error ?? entry.details ?? entry.instagram_handle ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {entry.campaign_id ?? '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {entry.timestamp
                      ? new Date(entry.timestamp).toLocaleString('pt-BR')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  )
}
