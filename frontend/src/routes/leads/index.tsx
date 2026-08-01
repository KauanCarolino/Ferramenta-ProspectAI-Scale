import { useEffect, useId, useState } from 'react'
import { createFileRoute } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EmptyState } from '@/components/EmptyState'
import { ErrorState } from '@/components/ErrorState'
import { LoadingState } from '@/components/LoadingState'
import { PageHeader } from '@/components/PageHeader'
import { fetchCampaigns } from '@/lib/api/campaigns'
import { getApiErrorMessage } from '@/lib/api/client'
import {
  confirmImport,
  createLead,
  deleteLead,
  fetchLeads,
  previewImport,
  updateLead,
  type ImportPreviewResponse,
  type Lead,
} from '@/lib/api/leads'

export const Route = createFileRoute('/leads/')({
  component: LeadsPage,
})

const INPUT_CLASS =
  'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500'

function LeadEditModal({
  lead,
  open,
  onClose,
  onSaved,
}: {
  lead: Lead | null
  open: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const queryClient = useQueryClient()
  const nomeId = useId()
  const empresaId = useId()
  const cargoId = useId()
  const instagramId = useId()
  const cidadeId = useId()
  const observacoesId = useId()

  const [nome, setNome] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [cargo, setCargo] = useState('')
  const [instagram, setInstagram] = useState('')
  const [cidade, setCidade] = useState('')
  const [observacoes, setObservacoes] = useState('')

  useEffect(() => {
    if (!lead) return
    setNome(lead.nome)
    setEmpresa(lead.empresa)
    setCargo(lead.cargo)
    setInstagram(lead.instagram)
    setCidade(lead.cidade ?? '')
    setObservacoes(lead.observacoes ?? '')
  }, [lead])

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!lead) {
        throw new Error('Lead não selecionado')
      }
      return updateLead(lead.id, {
        nome: nome.trim(),
        empresa: empresa.trim(),
        cargo: cargo.trim(),
        instagram: instagram.trim(),
        cidade: cidade.trim() || null,
        observacoes: observacoes.trim() || null,
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['leads'] })
      onSaved()
      onClose()
    },
  })

  if (!open || !lead) return null

  function handleClose() {
    updateMutation.reset()
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center"
      role="presentation"
      onClick={handleClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lead-edit-dialog-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="lead-edit-dialog-title"
          className="text-lg font-semibold text-slate-900"
        >
          Editar lead
        </h2>
        <p className="mt-1 text-sm text-slate-500">@{lead.instagram}</p>

        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault()
            updateMutation.reset()
            updateMutation.mutate()
          }}
        >
          <div>
            <label
              htmlFor={nomeId}
              className="block text-sm font-medium text-slate-700"
            >
              Nome
            </label>
            <input
              id={nomeId}
              type="text"
              required
              maxLength={255}
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={empresaId}
              className="block text-sm font-medium text-slate-700"
            >
              Empresa
            </label>
            <input
              id={empresaId}
              type="text"
              required
              maxLength={255}
              value={empresa}
              onChange={(e) => setEmpresa(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={cargoId}
              className="block text-sm font-medium text-slate-700"
            >
              Cargo
            </label>
            <input
              id={cargoId}
              type="text"
              required
              maxLength={255}
              value={cargo}
              onChange={(e) => setCargo(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={instagramId}
              className="block text-sm font-medium text-slate-700"
            >
              Instagram
            </label>
            <input
              id={instagramId}
              type="text"
              required
              maxLength={150}
              value={instagram}
              onChange={(e) => setInstagram(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={cidadeId}
              className="block text-sm font-medium text-slate-700"
            >
              Cidade (opcional)
            </label>
            <input
              id={cidadeId}
              type="text"
              maxLength={150}
              value={cidade}
              onChange={(e) => setCidade(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>
          <div>
            <label
              htmlFor={observacoesId}
              className="block text-sm font-medium text-slate-700"
            >
              Observações (opcional)
            </label>
            <textarea
              id={observacoesId}
              rows={3}
              value={observacoes}
              onChange={(e) => setObservacoes(e.target.value)}
              className={INPUT_CLASS}
            />
          </div>

          {updateMutation.isError ? (
            <p className="text-sm text-red-600" role="alert">
              {getApiErrorMessage(updateMutation.error, 'Falha ao salvar lead')}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={
                updateMutation.isPending ||
                !nome.trim() ||
                !empresa.trim() ||
                !cargo.trim() ||
                !instagram.trim()
              }
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {updateMutation.isPending ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function LeadsPage() {
  const queryClient = useQueryClient()
  const campaignSelectId = useId()
  const createCampaignSelectId = useId()
  const filterSelectId = useId()
  const fileInputId = useId()
  const createNomeId = useId()
  const createEmpresaId = useId()
  const createCargoId = useId()
  const createInstagramId = useId()
  const createCidadeId = useId()
  const createObservacoesId = useId()

  const [importCampaignId, setImportCampaignId] = useState('')
  const [createCampaignId, setCreateCampaignId] = useState('')
  const [filterCampaignId, setFilterCampaignId] = useState('')
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [editLead, setEditLead] = useState<Lead | null>(null)
  const [listFeedback, setListFeedback] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createNome, setCreateNome] = useState('')
  const [createEmpresa, setCreateEmpresa] = useState('')
  const [createCargo, setCreateCargo] = useState('')
  const [createInstagram, setCreateInstagram] = useState('')
  const [createCidade, setCreateCidade] = useState('')
  const [createObservacoes, setCreateObservacoes] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const campaignsQuery = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
    retry: 1,
  })

  const leadsQuery = useQuery({
    queryKey: ['leads', filterCampaignId || 'all'],
    queryFn: () =>
      fetchLeads({
        campaignId: filterCampaignId || undefined,
        limit: 100,
      }),
    retry: 1,
  })

  useEffect(() => {
    if (
      campaignsQuery.data &&
      campaignsQuery.data.length > 0
    ) {
      const firstId = campaignsQuery.data[0].id
      if (!importCampaignId) setImportCampaignId(firstId)
      if (!createCampaignId) setCreateCampaignId(firstId)
    }
  }, [importCampaignId, createCampaignId, campaignsQuery.data])

  const previewMutation = useMutation({
    mutationFn: (file: File) => {
      if (!importCampaignId) {
        throw new Error('Selecione uma campanha')
      }
      return previewImport(importCampaignId, file)
    },
    onSuccess: (result) => {
      setPreview(result)
      setFeedback(null)
    },
  })

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!importCampaignId || !preview) {
        throw new Error('Faça o preview antes de confirmar')
      }
      const leads = preview.preview.map((row) => ({
        nome: row.nome,
        empresa: row.empresa,
        cargo: row.cargo,
        instagram: row.instagram,
        cidade: row.cidade ?? null,
        observacoes: row.observacoes ?? null,
      }))
      return confirmImport(importCampaignId, leads)
    },
    onSuccess: async (result) => {
      setFeedback(
        `Importação concluída: ${result.inserted} inseridos, ${result.skipped_duplicates} duplicados ignorados.`,
      )
      setPreview(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['leads'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
      ])
    },
  })

  const createMutation = useMutation({
    mutationFn: () => {
      if (!createCampaignId) {
        throw new Error('Selecione uma campanha')
      }
      return createLead({
        campaign_id: createCampaignId,
        nome: createNome.trim(),
        empresa: createEmpresa.trim(),
        cargo: createCargo.trim(),
        instagram: createInstagram.trim(),
        cidade: createCidade.trim() || null,
        observacoes: createObservacoes.trim() || null,
      })
    },
    onSuccess: async () => {
      setCreateNome('')
      setCreateEmpresa('')
      setCreateCargo('')
      setCreateInstagram('')
      setCreateCidade('')
      setCreateObservacoes('')
      setShowCreateForm(false)
      setListFeedback('Lead criado.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['leads'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
      ])
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteLead(id),
    onSuccess: async () => {
      setDeletingId(null)
      setListFeedback('Lead removido.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['leads'] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] }),
      ])
    },
    onError: () => {
      setDeletingId(null)
    },
  })

  const campaigns = campaignsQuery.data ?? []
  const campaignNameById = new Map(campaigns.map((c) => [c.id, c.name]))

  return (
    <>
      <PageHeader
        title="Leads"
        description="Criar, editar, excluir, filtrar e importar CSV/XLSX"
      />

      <section
        aria-label="Importar leads"
        className="mb-6 space-y-4 rounded-lg border border-slate-200 bg-white p-4"
      >
        <h2 className="text-sm font-semibold text-slate-900">Importar CSV/XLSX</h2>

        {campaignsQuery.isLoading ? (
          <LoadingState label="Carregando campanhas…" />
        ) : null}

        {campaignsQuery.isError ? (
          <ErrorState
            message={getApiErrorMessage(
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
            description="Crie uma campanha antes de importar leads."
          />
        ) : null}

        {campaigns.length > 0 ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <label
                htmlFor={campaignSelectId}
                className="block text-sm font-medium text-slate-700"
              >
                Campanha
              </label>
              <select
                id={campaignSelectId}
                value={importCampaignId}
                onChange={(e) => {
                  setImportCampaignId(e.target.value)
                  setPreview(null)
                  setFeedback(null)
                  previewMutation.reset()
                  confirmMutation.reset()
                }}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-0 flex-1">
              <label
                htmlFor={fileInputId}
                className="block text-sm font-medium text-slate-700"
              >
                Arquivo
              </label>
              <input
                id={fileInputId}
                type="file"
                accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                disabled={previewMutation.isPending || !importCampaignId}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (!file) return
                  setFeedback(null)
                  confirmMutation.reset()
                  previewMutation.reset()
                  previewMutation.mutate(file)
                }}
                className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-700 hover:file:bg-slate-200"
              />
            </div>
          </div>
        ) : null}

        {previewMutation.isPending ? (
          <LoadingState label="Gerando preview…" />
        ) : null}

        {previewMutation.isError ? (
          <p className="text-sm text-red-600" role="alert">
            {getApiErrorMessage(previewMutation.error, 'Falha no preview')}
          </p>
        ) : null}

        {preview ? (
          <div className="space-y-3 rounded-md border border-slate-100 bg-slate-50 p-3">
            <div className="flex flex-wrap gap-3 text-sm text-slate-700">
              <span>
                Total: <strong>{preview.total_rows}</strong>
              </span>
              <span>
                Válidos: <strong>{preview.valid_count}</strong>
              </span>
              <span>
                Rejeitados: <strong>{preview.rejected_count}</strong>
              </span>
              <span>
                Duplicados: <strong>{preview.duplicate_count}</strong>
              </span>
            </div>

            {preview.preview.length > 0 ? (
              <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">#</th>
                      <th className="px-3 py-2 font-medium">Nome</th>
                      <th className="px-3 py-2 font-medium">Empresa</th>
                      <th className="px-3 py-2 font-medium">Instagram</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {preview.preview.slice(0, 10).map((row) => (
                      <tr key={`${row.row_number}-${row.instagram}`}>
                        <td className="px-3 py-1.5 text-slate-500">
                          {row.row_number}
                        </td>
                        <td className="px-3 py-1.5 text-slate-900">{row.nome}</td>
                        <td className="px-3 py-1.5 text-slate-600">
                          {row.empresa}
                        </td>
                        <td className="px-3 py-1.5 text-slate-600">
                          @{row.instagram}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {preview.rejected.length > 0 ? (
              <div className="text-sm text-amber-900">
                <p className="font-medium">
                  Amostra de rejeitados ({preview.rejected.length}):
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {preview.rejected.slice(0, 5).map((row) => (
                    <li key={`rej-${row.row_number}`}>
                      Linha {row.row_number}: {row.reasons.join('; ')}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={
                  confirmMutation.isPending || preview.valid_count === 0
                }
                onClick={() => {
                  setFeedback(null)
                  confirmMutation.reset()
                  confirmMutation.mutate()
                }}
                className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {confirmMutation.isPending
                  ? 'Confirmando…'
                  : 'Confirmar importação'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setPreview(null)
                  previewMutation.reset()
                  confirmMutation.reset()
                }}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Limpar preview
              </button>
            </div>

            {confirmMutation.isError ? (
              <p className="text-sm text-red-600" role="alert">
                {getApiErrorMessage(
                  confirmMutation.error,
                  'Falha ao confirmar importação',
                )}
              </p>
            ) : null}
          </div>
        ) : null}

        {feedback ? (
          <p className="text-sm text-emerald-700" role="status">
            {feedback}
          </p>
        ) : null}
      </section>

      <section aria-label="Lista de leads" className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Leads</h2>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="sm:w-64">
              <label
                htmlFor={filterSelectId}
                className="block text-sm font-medium text-slate-700"
              >
                Filtrar por campanha
              </label>
              <select
                id={filterSelectId}
                value={filterCampaignId}
                onChange={(e) => setFilterCampaignId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Todas</option>
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={campaign.id}>
                    {campaign.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              disabled={campaigns.length === 0}
              onClick={() => {
                setShowCreateForm((open) => !open)
                createMutation.reset()
                setListFeedback(null)
              }}
              className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {showCreateForm ? 'Fechar formulário' : 'Novo lead'}
            </button>
          </div>
        </div>

        {showCreateForm && campaigns.length > 0 ? (
          <section
            aria-label="Novo lead"
            className="rounded-lg border border-slate-200 bg-white p-4"
          >
            <h3 className="text-sm font-semibold text-slate-900">Novo lead</h3>
            <form
              className="mt-4 space-y-3"
              onSubmit={(e) => {
                e.preventDefault()
                createMutation.reset()
                setListFeedback(null)
                createMutation.mutate()
              }}
            >
              <div>
                <label
                  htmlFor={createCampaignSelectId}
                  className="block text-sm font-medium text-slate-700"
                >
                  Campanha
                </label>
                <select
                  id={createCampaignSelectId}
                  value={createCampaignId}
                  onChange={(e) => setCreateCampaignId(e.target.value)}
                  required
                  className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {campaigns.map((campaign) => (
                    <option key={campaign.id} value={campaign.id}>
                      {campaign.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor={createNomeId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Nome
                  </label>
                  <input
                    id={createNomeId}
                    type="text"
                    required
                    maxLength={255}
                    value={createNome}
                    onChange={(e) => setCreateNome(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </div>
                <div>
                  <label
                    htmlFor={createEmpresaId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Empresa
                  </label>
                  <input
                    id={createEmpresaId}
                    type="text"
                    required
                    maxLength={255}
                    value={createEmpresa}
                    onChange={(e) => setCreateEmpresa(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </div>
                <div>
                  <label
                    htmlFor={createCargoId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Cargo
                  </label>
                  <input
                    id={createCargoId}
                    type="text"
                    required
                    maxLength={255}
                    value={createCargo}
                    onChange={(e) => setCreateCargo(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </div>
                <div>
                  <label
                    htmlFor={createInstagramId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Instagram
                  </label>
                  <input
                    id={createInstagramId}
                    type="text"
                    required
                    maxLength={150}
                    value={createInstagram}
                    onChange={(e) => setCreateInstagram(e.target.value)}
                    className={INPUT_CLASS}
                    placeholder="handle_sem_arroba"
                  />
                </div>
                <div>
                  <label
                    htmlFor={createCidadeId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Cidade (opcional)
                  </label>
                  <input
                    id={createCidadeId}
                    type="text"
                    maxLength={150}
                    value={createCidade}
                    onChange={(e) => setCreateCidade(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </div>
                <div>
                  <label
                    htmlFor={createObservacoesId}
                    className="block text-sm font-medium text-slate-700"
                  >
                    Observações (opcional)
                  </label>
                  <input
                    id={createObservacoesId}
                    type="text"
                    value={createObservacoes}
                    onChange={(e) => setCreateObservacoes(e.target.value)}
                    className={INPUT_CLASS}
                  />
                </div>
              </div>

              {createMutation.isError ? (
                <p className="text-sm text-red-600" role="alert">
                  {getApiErrorMessage(
                    createMutation.error,
                    'Falha ao criar lead',
                  )}
                </p>
              ) : null}

              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={
                    createMutation.isPending ||
                    !createCampaignId ||
                    !createNome.trim() ||
                    !createEmpresa.trim() ||
                    !createCargo.trim() ||
                    !createInstagram.trim()
                  }
                  className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Criando…' : 'Criar lead'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false)
                    createMutation.reset()
                  }}
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </section>
        ) : null}

        {listFeedback ? (
          <p className="text-sm text-emerald-700" role="status">
            {listFeedback}
          </p>
        ) : null}

        {deleteMutation.isError ? (
          <p className="text-sm text-red-600" role="alert">
            {getApiErrorMessage(deleteMutation.error, 'Falha ao remover lead')}
          </p>
        ) : null}

        {leadsQuery.isLoading ? <LoadingState /> : null}

        {leadsQuery.isError ? (
          <ErrorState
            message={getApiErrorMessage(
              leadsQuery.error,
              'Falha ao carregar leads',
            )}
            onRetry={() => {
              void leadsQuery.refetch()
            }}
          />
        ) : null}

        {!leadsQuery.isLoading &&
        !leadsQuery.isError &&
        (leadsQuery.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="Nenhum lead cadastrado"
            description="Crie um lead ou importe um CSV/XLSX para começar."
          />
        ) : null}

        {!leadsQuery.isLoading &&
        !leadsQuery.isError &&
        leadsQuery.data &&
        leadsQuery.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Instagram</th>
                  <th className="px-4 py-2 font-medium">Nome</th>
                  <th className="px-4 py-2 font-medium">Empresa</th>
                  <th className="px-4 py-2 font-medium">Campanha</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {leadsQuery.data.map((lead) => (
                  <tr key={lead.id}>
                    <td className="px-4 py-2 font-medium text-slate-900">
                      @{lead.instagram}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{lead.nome}</td>
                    <td className="px-4 py-2 text-slate-600">{lead.empresa}</td>
                    <td className="px-4 py-2 text-slate-600">
                      {campaignNameById.get(lead.campaign_id) ??
                        lead.campaign_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2 text-slate-600">{lead.status}</td>
                    <td className="px-4 py-2 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setListFeedback(null)
                            setEditLead(lead)
                          }}
                          className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          Editar
                        </button>
                        <button
                          type="button"
                          disabled={
                            deleteMutation.isPending && deletingId === lead.id
                          }
                          onClick={() => {
                            if (
                              !window.confirm(
                                `Remover o lead @${lead.instagram}?`,
                              )
                            ) {
                              return
                            }
                            setListFeedback(null)
                            deleteMutation.reset()
                            setDeletingId(lead.id)
                            deleteMutation.mutate(lead.id)
                          }}
                          className="rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          {deleteMutation.isPending && deletingId === lead.id
                            ? 'Removendo…'
                            : 'Excluir'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <LeadEditModal
        lead={editLead}
        open={Boolean(editLead)}
        onClose={() => setEditLead(null)}
        onSaved={() => setListFeedback('Lead atualizado.')}
      />
    </>
  )
}
