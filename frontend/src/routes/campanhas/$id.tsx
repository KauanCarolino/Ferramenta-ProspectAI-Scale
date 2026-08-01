import { useEffect, useId, useState } from 'react'
import { Link, createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CampaignStatusBadge } from '@/components/CampaignStatusBadge'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { getApiErrorMessage } from '@/lib/api/client'
import {
  cancelCampaign,
  fetchCampaign,
  fetchCampaignJobs,
  pauseCampaign,
  resumeCampaign,
  startCampaign,
  updateCampaign,
  type Campaign,
} from '@/lib/api/campaigns'

export const Route = createFileRoute('/campanhas/$id')({
  component: CampaignDetailPage,
})

const INPUT_CLASS =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-slate-50 disabled:text-slate-500'

function isLiveStatus(status: string): boolean {
  return status === 'active' || status === 'auto_paused'
}

function isEditableStatus(status: string): boolean {
  return (
    status === 'draft' ||
    status === 'active' ||
    status === 'paused' ||
    status === 'auto_paused'
  )
}

function toTimeInputValue(value: string): string {
  return String(value).slice(0, 5)
}

function CampaignActions({
  campaign,
  busy,
  onStart,
  onPause,
  onResume,
  onCancel,
}: {
  campaign: Campaign
  busy: boolean
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onCancel: () => void
}) {
  const { status } = campaign

  if (status === 'cancelled' || status === 'completed') {
    return (
      <p className="text-sm text-slate-500">
        Campanha encerrada — somente leitura.
      </p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {status === 'draft' ? (
        <button
          type="button"
          disabled={busy}
          onClick={onStart}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Iniciar
        </button>
      ) : null}

      {status === 'active' ? (
        <button
          type="button"
          disabled={busy}
          onClick={onPause}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Pausar
        </button>
      ) : null}

      {status === 'paused' || status === 'auto_paused' ? (
        <button
          type="button"
          disabled={busy}
          onClick={onResume}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Retomar
        </button>
      ) : null}

      {status === 'active' ||
      status === 'paused' ||
      status === 'auto_paused' ? (
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
        >
          Cancelar
        </button>
      ) : null}
    </div>
  )
}

function CampaignEditForm({ campaign }: { campaign: Campaign }) {
  const queryClient = useQueryClient()
  const nameId = useId()
  const descriptionId = useId()
  const messagesId = useId()
  const durationId = useId()
  const windowStartId = useId()
  const windowEndId = useId()
  const minIntervalId = useId()
  const maxIntervalId = useId()

  const editable = isEditableStatus(campaign.status)

  const [name, setName] = useState(campaign.name)
  const [description, setDescription] = useState(campaign.description ?? '')
  const [messagesPerDay, setMessagesPerDay] = useState(
    campaign.messages_per_day,
  )
  const [durationDays, setDurationDays] = useState(campaign.duration_days)
  const [windowStart, setWindowStart] = useState(
    toTimeInputValue(campaign.window_start),
  )
  const [windowEnd, setWindowEnd] = useState(
    toTimeInputValue(campaign.window_end),
  )
  const [minIntervalSec, setMinIntervalSec] = useState(
    campaign.min_interval_sec,
  )
  const [maxIntervalSec, setMaxIntervalSec] = useState(
    campaign.max_interval_sec,
  )
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    setName(campaign.name)
    setDescription(campaign.description ?? '')
    setMessagesPerDay(campaign.messages_per_day)
    setDurationDays(campaign.duration_days)
    setWindowStart(toTimeInputValue(campaign.window_start))
    setWindowEnd(toTimeInputValue(campaign.window_end))
    setMinIntervalSec(campaign.min_interval_sec)
    setMaxIntervalSec(campaign.max_interval_sec)
    setFeedback(null)
  }, [campaign])

  const updateMutation = useMutation({
    mutationFn: () =>
      updateCampaign(campaign.id, {
        name: name.trim(),
        description: description.trim() || null,
        messages_per_day: messagesPerDay,
        duration_days: durationDays,
        window_start: windowStart,
        window_end: windowEnd,
        min_interval_sec: minIntervalSec,
        max_interval_sec: maxIntervalSec,
      }),
    onSuccess: async () => {
      setFeedback('Campanha atualizada.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['campaigns', campaign.id] }),
        queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
      ])
    },
  })

  return (
    <section
      aria-label="Editar campanha"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-sm font-semibold text-slate-900">
          Configuração da campanha
        </h2>
        {!editable ? (
          <p className="text-xs text-slate-500">Somente leitura</p>
        ) : null}
      </div>

      <form
        className="mt-4 space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (!editable) return
          setFeedback(null)
          updateMutation.reset()
          updateMutation.mutate()
        }}
      >
        <fieldset disabled={!editable} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label
                htmlFor={nameId}
                className="block text-sm font-medium text-slate-700"
              >
                Nome
              </label>
              <input
                id={nameId}
                type="text"
                required
                maxLength={255}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
            <div className="sm:col-span-2">
              <label
                htmlFor={descriptionId}
                className="block text-sm font-medium text-slate-700"
              >
                Descrição (opcional)
              </label>
              <textarea
                id={descriptionId}
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={messagesId}
                className="block text-sm font-medium text-slate-700"
              >
                Mensagens / dia
              </label>
              <input
                id={messagesId}
                type="number"
                required
                min={1}
                max={500}
                value={messagesPerDay}
                onChange={(e) =>
                  setMessagesPerDay(Number(e.target.value) || 1)
                }
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={durationId}
                className="block text-sm font-medium text-slate-700"
              >
                Duração (dias)
              </label>
              <input
                id={durationId}
                type="number"
                required
                min={1}
                max={90}
                value={durationDays}
                onChange={(e) => setDurationDays(Number(e.target.value) || 1)}
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={windowStartId}
                className="block text-sm font-medium text-slate-700"
              >
                Janela início
              </label>
              <input
                id={windowStartId}
                type="time"
                required
                value={windowStart}
                onChange={(e) => setWindowStart(e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={windowEndId}
                className="block text-sm font-medium text-slate-700"
              >
                Janela fim
              </label>
              <input
                id={windowEndId}
                type="time"
                required
                value={windowEnd}
                onChange={(e) => setWindowEnd(e.target.value)}
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={minIntervalId}
                className="block text-sm font-medium text-slate-700"
              >
                Intervalo mín. (seg)
              </label>
              <input
                id={minIntervalId}
                type="number"
                required
                min={30}
                value={minIntervalSec}
                onChange={(e) =>
                  setMinIntervalSec(Number(e.target.value) || 30)
                }
                className={INPUT_CLASS}
              />
            </div>
            <div>
              <label
                htmlFor={maxIntervalId}
                className="block text-sm font-medium text-slate-700"
              >
                Intervalo máx. (seg)
              </label>
              <input
                id={maxIntervalId}
                type="number"
                required
                min={60}
                value={maxIntervalSec}
                onChange={(e) =>
                  setMaxIntervalSec(Number(e.target.value) || 60)
                }
                className={INPUT_CLASS}
              />
            </div>
          </div>
        </fieldset>

        {editable ? (
          <button
            type="submit"
            disabled={updateMutation.isPending || !name.trim()}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Salvando…' : 'Salvar alterações'}
          </button>
        ) : null}

        {updateMutation.isError ? (
          <p className="text-sm text-red-600" role="alert">
            {getApiErrorMessage(
              updateMutation.error,
              'Falha ao atualizar campanha',
            )}
          </p>
        ) : null}
        {feedback ? (
          <p className="text-sm text-emerald-700" role="status">
            {feedback}
          </p>
        ) : null}
      </form>
    </section>
  )
}

function CampaignDetailPage() {
  const { id } = Route.useParams()
  const queryClient = useQueryClient()

  const campaignQuery = useQuery({
    queryKey: ['campaigns', id],
    queryFn: () => fetchCampaign(id),
    retry: 1,
  })

  const status = campaignQuery.data?.status
  const jobsLive = status ? isLiveStatus(status) : false

  const jobsQuery = useQuery({
    queryKey: ['campaigns', id, 'jobs'],
    queryFn: () => fetchCampaignJobs(id, { limit: 50, status: 'pending' }),
    enabled: Boolean(campaignQuery.data),
    retry: 1,
    refetchInterval: jobsLive ? 12_000 : false,
  })

  async function invalidateCampaign() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['campaigns', id] }),
      queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
      queryClient.invalidateQueries({ queryKey: ['campaigns', id, 'jobs'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
    ])
  }

  const startMutation = useMutation({
    mutationFn: () => startCampaign(id),
    onSuccess: invalidateCampaign,
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseCampaign(id),
    onSuccess: invalidateCampaign,
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeCampaign(id),
    onSuccess: invalidateCampaign,
  })
  const cancelMutation = useMutation({
    mutationFn: () => cancelCampaign(id),
    onSuccess: invalidateCampaign,
  })

  const actionBusy =
    startMutation.isPending ||
    pauseMutation.isPending ||
    resumeMutation.isPending ||
    cancelMutation.isPending

  const actionError =
    startMutation.error ??
    pauseMutation.error ??
    resumeMutation.error ??
    cancelMutation.error

  const actionSuccess =
    startMutation.isSuccess ||
    pauseMutation.isSuccess ||
    resumeMutation.isSuccess ||
    cancelMutation.isSuccess

  function handleCancel() {
    const confirmed = window.confirm(
      'Cancelar esta campanha? Jobs pendentes serão cancelados. Esta ação não pode ser desfeita.',
    )
    if (!confirmed) return
    cancelMutation.reset()
    cancelMutation.mutate()
  }

  return (
    <>
      <div className="mb-4">
        <Link
          to="/campanhas"
          className="text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          ← Voltar às campanhas
        </Link>
      </div>

      {campaignQuery.isLoading ? (
        <>
          <PageHeader title="Campanha" />
          <LoadingState />
        </>
      ) : null}

      {campaignQuery.isError ? (
        <ErrorState
          message={getApiErrorMessage(
            campaignQuery.error,
            'Falha ao carregar campanha',
          )}
          onRetry={() => {
            void campaignQuery.refetch()
          }}
        />
      ) : null}

      {campaignQuery.data ? (
        <div className="space-y-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <PageHeader
              title={campaignQuery.data.name}
              description={`Canal: ${campaignQuery.data.channel}`}
            />
            <CampaignStatusBadge
              status={campaignQuery.data.status}
              className="self-start"
            />
          </div>

          {campaignQuery.data.status === 'auto_paused' ? (
            <div
              role="alert"
              className="rounded-lg border border-orange-300 bg-orange-50 px-4 py-3 text-sm text-orange-950"
            >
              <p className="font-semibold">Pausa automática</p>
              <p className="mt-1">
                A campanha foi pausada automaticamente (anti-ban / falhas).
                Revise contas e logs antes de retomar.
              </p>
            </div>
          ) : null}

          <CampaignActions
            campaign={campaignQuery.data}
            busy={actionBusy}
            onStart={() => {
              startMutation.reset()
              startMutation.mutate()
            }}
            onPause={() => {
              pauseMutation.reset()
              pauseMutation.mutate()
            }}
            onResume={() => {
              resumeMutation.reset()
              resumeMutation.mutate()
            }}
            onCancel={handleCancel}
          />

          {actionError ? (
            <p className="text-sm text-red-600" role="alert">
              {getApiErrorMessage(actionError, 'Falha na ação da campanha')}
            </p>
          ) : null}

          {actionSuccess && !actionBusy && !actionError ? (
            <p className="text-sm text-emerald-700" role="status">
              Ação concluída com sucesso.
            </p>
          ) : null}

          <CampaignEditForm campaign={campaignQuery.data} />

          <section aria-label="Próximos envios">
            <div className="mb-3 flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-900">
                Próximos jobs
              </h2>
              {jobsQuery.isFetching && !jobsQuery.isLoading ? (
                <span className="text-xs text-slate-400">Atualizando…</span>
              ) : null}
            </div>

            {jobsQuery.isLoading ? <LoadingState label="Carregando fila…" /> : null}

            {jobsQuery.isError ? (
              <ErrorState
                message={getApiErrorMessage(
                  jobsQuery.error,
                  'Falha ao carregar jobs',
                )}
                onRetry={() => {
                  void jobsQuery.refetch()
                }}
              />
            ) : null}

            {!jobsQuery.isLoading &&
            !jobsQuery.isError &&
            (jobsQuery.data?.length ?? 0) === 0 ? (
              <EmptyState
                title="Nenhum job pendente"
                description="A fila de envios aparece aqui quando houver jobs agendados."
              />
            ) : null}

            {!jobsQuery.isLoading &&
            !jobsQuery.isError &&
            jobsQuery.data &&
            jobsQuery.data.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Stage</th>
                      <th className="px-4 py-2 font-medium">Agendado</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Canal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {jobsQuery.data.map((job) => (
                      <tr key={job.id}>
                        <td className="px-4 py-2 font-medium text-slate-900">
                          {job.stage.toUpperCase()}
                        </td>
                        <td className="px-4 py-2 text-slate-600">
                          {new Date(job.scheduled_at).toLocaleString('pt-BR')}
                        </td>
                        <td className="px-4 py-2 text-slate-600">{job.status}</td>
                        <td className="px-4 py-2 text-slate-600">{job.channel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </>
  )
}
