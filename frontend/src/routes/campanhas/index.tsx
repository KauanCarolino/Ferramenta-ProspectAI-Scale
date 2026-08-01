import { useId, useState } from 'react'
import { Link, createFileRoute, useNavigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CampaignStatusBadge } from '@/components/CampaignStatusBadge'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { getApiErrorMessage } from '@/lib/api/client'
import {
  createCampaign,
  fetchCampaigns,
  pauseCampaign,
  resumeCampaign,
  startCampaign,
  type Campaign,
} from '@/lib/api/campaigns'

export const Route = createFileRoute('/campanhas/')({
  component: CampaignsPage,
})

const INPUT_CLASS =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500'

const DEFAULT_CREATE = {
  name: '',
  description: '',
  messages_per_day: 150,
  duration_days: 10,
  window_start: '09:00',
  window_end: '18:00',
  min_interval_sec: 120,
  max_interval_sec: 300,
} as const

function CampaignQuickActions({ campaign }: { campaign: Campaign }) {
  const queryClient = useQueryClient()

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
      queryClient.invalidateQueries({ queryKey: ['campaigns', campaign.id] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
    ])
  }

  const startMutation = useMutation({
    mutationFn: () => startCampaign(campaign.id),
    onSuccess: invalidate,
  })
  const pauseMutation = useMutation({
    mutationFn: () => pauseCampaign(campaign.id),
    onSuccess: invalidate,
  })
  const resumeMutation = useMutation({
    mutationFn: () => resumeCampaign(campaign.id),
    onSuccess: invalidate,
  })

  const busy =
    startMutation.isPending ||
    pauseMutation.isPending ||
    resumeMutation.isPending

  const error =
    startMutation.error ?? pauseMutation.error ?? resumeMutation.error

  const { status } = campaign

  if (
    status === 'cancelled' ||
    status === 'completed' ||
    (status !== 'draft' &&
      status !== 'active' &&
      status !== 'paused' &&
      status !== 'auto_paused')
  ) {
    return (
      <Link
        to="/campanhas/$id"
        params={{ id: campaign.id }}
        className="text-sm font-medium text-brand-600 hover:text-brand-700"
      >
        Ver detalhe
      </Link>
    )
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap justify-end gap-2">
        {status === 'draft' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              startMutation.reset()
              startMutation.mutate()
            }}
            className="rounded-md bg-brand-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Iniciar
          </button>
        ) : null}
        {status === 'active' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              pauseMutation.reset()
              pauseMutation.mutate()
            }}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Pausar
          </button>
        ) : null}
        {status === 'paused' || status === 'auto_paused' ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              resumeMutation.reset()
              resumeMutation.mutate()
            }}
            className="rounded-md bg-brand-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Retomar
          </button>
        ) : null}
        <Link
          to="/campanhas/$id"
          params={{ id: campaign.id }}
          className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          Detalhe
        </Link>
      </div>
      {error ? (
        <p className="max-w-xs text-right text-xs text-red-600" role="alert">
          {getApiErrorMessage(error, 'Falha na ação')}
        </p>
      ) : null}
    </div>
  )
}

function CampaignsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const nameId = useId()
  const descriptionId = useId()
  const messagesId = useId()
  const durationId = useId()
  const windowStartId = useId()
  const windowEndId = useId()
  const minIntervalId = useId()
  const maxIntervalId = useId()

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState(DEFAULT_CREATE.name)
  const [description, setDescription] = useState(DEFAULT_CREATE.description)
  const [messagesPerDay, setMessagesPerDay] = useState(
    DEFAULT_CREATE.messages_per_day,
  )
  const [durationDays, setDurationDays] = useState(DEFAULT_CREATE.duration_days)
  const [windowStart, setWindowStart] = useState(DEFAULT_CREATE.window_start)
  const [windowEnd, setWindowEnd] = useState(DEFAULT_CREATE.window_end)
  const [minIntervalSec, setMinIntervalSec] = useState(
    DEFAULT_CREATE.min_interval_sec,
  )
  const [maxIntervalSec, setMaxIntervalSec] = useState(
    DEFAULT_CREATE.max_interval_sec,
  )
  const [formFeedback, setFormFeedback] = useState<string | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
    retry: 1,
  })

  function resetForm() {
    setName(DEFAULT_CREATE.name)
    setDescription(DEFAULT_CREATE.description)
    setMessagesPerDay(DEFAULT_CREATE.messages_per_day)
    setDurationDays(DEFAULT_CREATE.duration_days)
    setWindowStart(DEFAULT_CREATE.window_start)
    setWindowEnd(DEFAULT_CREATE.window_end)
    setMinIntervalSec(DEFAULT_CREATE.min_interval_sec)
    setMaxIntervalSec(DEFAULT_CREATE.max_interval_sec)
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createCampaign({
        name: name.trim(),
        channel: 'instagram',
        messages_per_day: messagesPerDay,
        duration_days: durationDays,
        window_start: windowStart,
        window_end: windowEnd,
        min_interval_sec: minIntervalSec,
        max_interval_sec: maxIntervalSec,
        description: description.trim() || null,
      }),
    onSuccess: async (campaign) => {
      setFormFeedback('Campanha criada com sucesso.')
      resetForm()
      setShowForm(false)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
      ])
      await navigate({
        to: '/campanhas/$id',
        params: { id: campaign.id },
      })
    },
  })

  return (
    <>
      <PageHeader
        title="Campanhas"
        description="Criar, pausar, retomar e cancelar campanhas"
      />

      <div className="mb-6">
        <button
          type="button"
          onClick={() => {
            setShowForm((open) => !open)
            setFormFeedback(null)
            createMutation.reset()
          }}
          className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {showForm ? 'Fechar formulário' : 'Nova campanha'}
        </button>
      </div>

      {showForm ? (
        <section
          aria-label="Nova campanha"
          className="mb-6 rounded-lg border border-slate-200 bg-white p-4"
        >
          <h2 className="text-sm font-semibold text-slate-900">Nova campanha</h2>
          <p className="mt-1 text-xs text-slate-500">
            Canal Instagram · defaults do produto: 150 msgs/dia × 10 dias
          </p>
          <form
            className="mt-4 space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              setFormFeedback(null)
              createMutation.reset()
              createMutation.mutate()
            }}
          >
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
                  placeholder="Campanha Q3 — Clínica XYZ"
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
                  onChange={(e) =>
                    setDurationDays(Number(e.target.value) || 1)
                  }
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
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={createMutation.isPending || !name.trim()}
                className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Criando…' : 'Criar campanha'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  createMutation.reset()
                }}
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </button>
            </div>
            {createMutation.isError ? (
              <p className="text-sm text-red-600" role="alert">
                {getApiErrorMessage(
                  createMutation.error,
                  'Falha ao criar campanha',
                )}
              </p>
            ) : null}
            {formFeedback ? (
              <p className="text-sm text-emerald-700" role="status">
                {formFeedback}
              </p>
            ) : null}
          </form>
        </section>
      ) : null}

      {isLoading ? <LoadingState /> : null}

      {isError ? (
        <ErrorState
          message={getApiErrorMessage(error, 'Falha ao carregar campanhas')}
          onRetry={() => {
            void refetch()
          }}
        />
      ) : null}

      {!isLoading && !isError && (data?.length ?? 0) === 0 ? (
        <EmptyState
          title="Nenhuma campanha ainda"
          description="Crie a primeira campanha com o botão Nova campanha."
        />
      ) : null}

      {!isLoading && !isError && data && data.length > 0 ? (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {data.map((campaign) => (
            <li
              key={campaign.id}
              className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to="/campanhas/$id"
                    params={{ id: campaign.id }}
                    className="font-medium text-slate-900 hover:text-brand-700"
                  >
                    {campaign.name}
                  </Link>
                  <CampaignStatusBadge status={campaign.status} />
                </div>
                <p className="text-xs text-slate-500">
                  {campaign.channel} · {campaign.messages_per_day}/dia ·{' '}
                  {campaign.duration_days} dias
                </p>
              </div>
              <CampaignQuickActions campaign={campaign} />
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}
