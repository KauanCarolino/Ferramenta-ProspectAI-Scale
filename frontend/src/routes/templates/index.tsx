import { useEffect, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { fetchCampaigns } from '@/lib/api/campaigns'
import { ApiError } from '@/lib/api/client'
import {
  TEMPLATE_STAGES,
  createTemplate,
  fetchTemplates,
  previewTemplate,
  updateTemplate,
  type Template,
  type TemplateStage,
} from '@/lib/api/templates'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/templates/')({
  component: TemplatesPage,
})

const STAGE_LABELS: Record<TemplateStage, string> = {
  d1: 'D1 — Dia 1',
  d4: 'D4 — Dia 4',
  d8: 'D8 — Dia 8',
}

const VARIABLE_HINTS = [
  '{{nome}}',
  '{{empresa}}',
  '{{cargo}}',
  '{{cidade}}',
  '{{observacoes}}',
  '{{instagram}}',
] as const

const VARIABLE_KEYS = [
  'nome',
  'empresa',
  'cargo',
  'cidade',
  'observacoes',
  'instagram',
] as const

type VariableKey = (typeof VARIABLE_KEYS)[number]

const DEFAULT_PREVIEW_VARS: Record<VariableKey, string> = {
  nome: 'Maria Silva',
  empresa: 'Acme Ltda',
  cargo: 'Gerente Comercial',
  cidade: 'São Paulo',
  observacoes: 'Interessada em automação',
  instagram: 'mariasilva',
}

function stageLabel(stage: string): string {
  if (stage === 'd1' || stage === 'd4' || stage === 'd8') {
    return STAGE_LABELS[stage]
  }
  return stage.toUpperCase()
}

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = error.body
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return fallback
}

function findStageTemplate(
  templates: Template[] | undefined,
  stage: TemplateStage,
): Template | undefined {
  return templates?.find((t) => t.stage === stage)
}

function TemplatesPage() {
  const queryClient = useQueryClient()

  const [campaignId, setCampaignId] = useState('')
  const [activeStage, setActiveStage] = useState<TemplateStage>('d1')
  const [name, setName] = useState('')
  const [body, setBody] = useState('')
  const [previewVars, setPreviewVars] =
    useState<Record<VariableKey, string>>(DEFAULT_PREVIEW_VARS)
  const [previewSeed, setPreviewSeed] = useState('')
  const [rendered, setRendered] = useState<string | null>(null)
  const [saveFeedback, setSaveFeedback] = useState<string | null>(null)

  const campaignsQuery = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
    retry: 1,
  })

  const templatesQuery = useQuery({
    queryKey: ['templates', campaignId],
    queryFn: () => fetchTemplates(campaignId),
    enabled: Boolean(campaignId),
    retry: 1,
  })

  useEffect(() => {
    if (!campaignId && campaignsQuery.data && campaignsQuery.data.length > 0) {
      setCampaignId(campaignsQuery.data[0].id)
    }
  }, [campaignId, campaignsQuery.data])

  useEffect(() => {
    const existing = findStageTemplate(templatesQuery.data, activeStage)
    setName(existing?.name ?? '')
    setBody(existing?.body ?? '')
  }, [activeStage, campaignId, templatesQuery.data])

  useEffect(() => {
    setRendered(null)
    setSaveFeedback(null)
  }, [activeStage, campaignId])

  const previewMutation = useMutation({
    mutationFn: previewTemplate,
    onSuccess: (result) => {
      setRendered(result.rendered)
    },
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!campaignId) {
        throw new Error('Selecione uma campanha')
      }
      const trimmedBody = body.trim()
      if (!trimmedBody) {
        throw new Error('O corpo do template é obrigatório')
      }
      const trimmedName = name.trim()
      const existing = findStageTemplate(templatesQuery.data, activeStage)
      if (existing) {
        return updateTemplate(existing.id, {
          body: trimmedBody,
          name: trimmedName || null,
        })
      }
      return createTemplate({
        campaign_id: campaignId,
        stage: activeStage,
        body: trimmedBody,
        name: trimmedName || null,
      })
    },
    onSuccess: async () => {
      setSaveFeedback('Template salvo com sucesso')
      await queryClient.invalidateQueries({ queryKey: ['templates', campaignId] })
    },
  })

  function handlePreview() {
    previewMutation.reset()
    previewMutation.mutate({
      body,
      variables: { ...previewVars },
      seed: previewSeed.trim() || undefined,
    })
  }

  function handleSave() {
    setSaveFeedback(null)
    saveMutation.reset()
    saveMutation.mutate()
  }

  const campaigns = campaignsQuery.data ?? []
  const templates = templatesQuery.data ?? []
  const existingForStage = findStageTemplate(templates, activeStage)

  return (
    <>
      <PageHeader
        title="Templates"
        description="Editor D1 / D4 / D8 com preview Spintax"
      />

      {campaignsQuery.isLoading ? <LoadingState label="Carregando campanhas…" /> : null}

      {campaignsQuery.isError ? (
        <ErrorState
          message={errorMessage(
            campaignsQuery.error,
            'Falha ao carregar campanhas',
          )}
          onRetry={() => {
            void campaignsQuery.refetch()
          }}
        />
      ) : null}

      {!campaignsQuery.isLoading &&
      !campaignsQuery.isError &&
      campaigns.length === 0 ? (
        <EmptyState
          title="Nenhuma campanha"
          description="Crie uma campanha antes de editar templates."
        />
      ) : null}

      {!campaignsQuery.isLoading &&
      !campaignsQuery.isError &&
      campaigns.length > 0 ? (
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <label
              htmlFor="campaign-select"
              className="block text-sm font-medium text-slate-700"
            >
              Campanha
            </label>
            <select
              id="campaign-select"
              value={campaignId}
              onChange={(e) => {
                setCampaignId(e.target.value)
                setActiveStage('d1')
                previewMutation.reset()
                saveMutation.reset()
              }}
              className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 sm:max-w-md"
            >
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </select>
          </div>

          {templatesQuery.isLoading ? (
            <LoadingState label="Carregando templates…" />
          ) : null}

          {templatesQuery.isError ? (
            <ErrorState
              message={errorMessage(
                templatesQuery.error,
                'Falha ao carregar templates',
              )}
              onRetry={() => {
                void templatesQuery.refetch()
              }}
            />
          ) : null}

          {campaignId && !templatesQuery.isLoading && !templatesQuery.isError ? (
            <>
              <div
                role="tablist"
                aria-label="Etapas do template"
                className="flex flex-wrap gap-2"
              >
                {TEMPLATE_STAGES.map((stage) => {
                  const hasTemplate = Boolean(
                    findStageTemplate(templates, stage),
                  )
                  return (
                    <button
                      key={stage}
                      type="button"
                      role="tab"
                      aria-selected={activeStage === stage}
                      onClick={() => {
                        setActiveStage(stage)
                        previewMutation.reset()
                        saveMutation.reset()
                      }}
                      className={cn(
                        'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                        activeStage === stage
                          ? 'bg-brand-600 text-white'
                          : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                      )}
                    >
                      {STAGE_LABELS[stage]}
                      {hasTemplate ? (
                        <span className="ml-1.5 text-xs opacity-80">●</span>
                      ) : null}
                    </button>
                  )
                })}
              </div>

              <section
                aria-label={`Editor ${STAGE_LABELS[activeStage]}`}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Editor — {STAGE_LABELS[activeStage]}
                  </h2>
                  <p className="text-xs text-slate-500">
                    {existingForStage
                      ? 'Template existente — salvar atualiza'
                      : 'Sem template nesta etapa — salvar cria'}
                  </p>
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <label
                      htmlFor="template-name"
                      className="block text-sm font-medium text-slate-700"
                    >
                      Nome (opcional)
                    </label>
                    <input
                      id="template-name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder={`Follow-up ${activeStage.toUpperCase()}`}
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 sm:max-w-md"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="template-body"
                      className="block text-sm font-medium text-slate-700"
                    >
                      Corpo da mensagem
                    </label>
                    <textarea
                      id="template-body"
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      rows={10}
                      placeholder="{Olá|Oi|E aí} {{nome}}, tudo bem? Vi que você trabalha na {{empresa}}…"
                      className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      Variáveis:{' '}
                      {VARIABLE_HINTS.map((hint, i) => (
                        <span key={hint}>
                          {i > 0 ? ' ' : null}
                          <code className="rounded bg-slate-100 px-1 py-0.5">
                            {hint}
                          </code>
                        </span>
                      ))}
                      {' · '}
                      Spintax:{' '}
                      <code className="rounded bg-slate-100 px-1 py-0.5">
                        {'{A|B|C}'}
                      </code>
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handlePreview}
                      disabled={!body.trim() || previewMutation.isPending}
                      className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {previewMutation.isPending ? 'Gerando preview…' : 'Preview'}
                    </button>
                    <button
                      type="button"
                      onClick={handleSave}
                      disabled={!body.trim() || saveMutation.isPending}
                      className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {saveMutation.isPending ? 'Salvando…' : 'Salvar'}
                    </button>
                  </div>

                  {saveMutation.isError ? (
                    <p className="text-sm text-red-700" role="alert">
                      {errorMessage(saveMutation.error, 'Falha ao salvar')}
                    </p>
                  ) : null}
                  {saveFeedback ? (
                    <p className="text-sm text-emerald-700" role="status">
                      {saveFeedback}
                    </p>
                  ) : null}
                </div>
              </section>

              <section
                aria-label="Preview Spintax"
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <h2 className="text-sm font-semibold text-slate-900">
                  Variáveis de exemplo
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Usadas no Preview. Seed opcional torna o Spintax reprodutível.
                </p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {VARIABLE_KEYS.map((key) => (
                    <div key={key}>
                      <label
                        htmlFor={`var-${key}`}
                        className="block text-xs font-medium uppercase tracking-wide text-slate-500"
                      >
                        {key}
                      </label>
                      <input
                        id={`var-${key}`}
                        type="text"
                        value={previewVars[key]}
                        onChange={(e) =>
                          setPreviewVars((prev) => ({
                            ...prev,
                            [key]: e.target.value,
                          }))
                        }
                        className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                  ))}
                  <div>
                    <label
                      htmlFor="preview-seed"
                      className="block text-xs font-medium uppercase tracking-wide text-slate-500"
                    >
                      seed (opcional)
                    </label>
                    <input
                      id="preview-seed"
                      type="text"
                      value={previewSeed}
                      onChange={(e) => setPreviewSeed(e.target.value)}
                      placeholder="lead-id-d1"
                      className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                </div>

                {previewMutation.isError ? (
                  <p className="mt-4 text-sm text-red-700" role="alert">
                    {errorMessage(
                      previewMutation.error,
                      'Falha ao gerar preview',
                    )}
                  </p>
                ) : null}

                {rendered !== null ? (
                  <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Texto renderizado
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-slate-900">
                      {rendered}
                    </p>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">
                    Clique em Preview para ver o texto com variáveis e Spintax
                    resolvidos.
                  </p>
                )}
              </section>

              <section aria-label="Templates da campanha">
                <h2 className="mb-3 text-sm font-semibold text-slate-900">
                  Templates desta campanha
                </h2>
                {templates.length === 0 ? (
                  <EmptyState
                    title="Nenhum template ainda"
                    description="Edite D1, D4 ou D8 acima e salve para criar o primeiro."
                  />
                ) : (
                  <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {templates.map((template) => (
                      <li key={template.id}>
                        <button
                          type="button"
                          onClick={() => {
                            if (
                              template.stage === 'd1' ||
                              template.stage === 'd4' ||
                              template.stage === 'd8'
                            ) {
                              setActiveStage(template.stage)
                              previewMutation.reset()
                              saveMutation.reset()
                            }
                          }}
                          className={cn(
                            'h-full w-full rounded-lg border bg-white p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/40',
                            template.stage === activeStage
                              ? 'border-brand-400 ring-1 ring-brand-200'
                              : 'border-slate-200',
                          )}
                        >
                          <p className="text-xs font-semibold uppercase tracking-wide text-brand-600">
                            {stageLabel(template.stage)}
                          </p>
                          <p className="mt-1 font-medium text-slate-900">
                            {template.name ??
                              `Template ${String(template.stage).toUpperCase()}`}
                          </p>
                          <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-sm text-slate-600">
                            {template.body}
                          </p>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          ) : null}
        </div>
      ) : null}
    </>
  )
}
