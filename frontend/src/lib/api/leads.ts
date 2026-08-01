import { apiFetch, apiUpload } from './client'

export interface Lead {
  id: string
  campaign_id: string
  nome: string
  empresa: string
  cargo: string
  instagram: string
  cidade: string | null
  observacoes: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface LeadCreate {
  campaign_id: string
  nome: string
  empresa: string
  cargo: string
  instagram: string
  cidade?: string | null
  observacoes?: string | null
}

export interface LeadUpdate {
  nome?: string
  empresa?: string
  cargo?: string
  instagram?: string
  cidade?: string | null
  observacoes?: string | null
  status?: string
}

export interface MessageResponse {
  detail: string
}

export interface ImportPreviewRow {
  row_number: number
  nome: string
  empresa: string
  cargo: string
  instagram: string
  cidade?: string | null
  observacoes?: string | null
}

export interface ImportRejectedRow {
  row_number: number
  raw: Record<string, string | null>
  reasons: string[]
}

export interface ImportPreviewResponse {
  campaign_id: string | null
  total_rows: number
  valid_count: number
  rejected_count: number
  duplicate_count: number
  preview: ImportPreviewRow[]
  rejected: ImportRejectedRow[]
}

export interface ImportConfirmLead {
  nome: string
  empresa: string
  cargo: string
  instagram: string
  cidade?: string | null
  observacoes?: string | null
}

export interface ImportConfirmResponse {
  campaign_id: string
  inserted: number
  skipped_duplicates: number
}

export interface FetchLeadsParams {
  campaignId?: string
  status?: string
  skip?: number
  limit?: number
}

export async function fetchLeads(
  params: FetchLeadsParams = {},
): Promise<Lead[]> {
  const search = new URLSearchParams()
  if (params.campaignId) {
    search.set('campaign_id', params.campaignId)
  }
  if (params.status) {
    search.set('status', params.status)
  }
  if (params.skip !== undefined) {
    search.set('skip', String(params.skip))
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  const query = search.toString()
  return apiFetch<Lead[]>(`/leads${query ? `?${query}` : ''}`)
}

export async function createLead(payload: LeadCreate): Promise<Lead> {
  return apiFetch<Lead>('/leads', {
    method: 'POST',
    body: payload,
  })
}

export async function updateLead(
  id: string,
  payload: LeadUpdate,
): Promise<Lead> {
  return apiFetch<Lead>(`/leads/${id}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function deleteLead(id: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/leads/${id}`, {
    method: 'DELETE',
  })
}

export async function previewImport(
  campaignId: string,
  file: File,
): Promise<ImportPreviewResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return apiUpload<ImportPreviewResponse>(
    `/leads/import/preview?campaign_id=${encodeURIComponent(campaignId)}`,
    formData,
  )
}

export async function confirmImport(
  campaignId: string,
  leads: ImportConfirmLead[],
): Promise<ImportConfirmResponse> {
  return apiFetch<ImportConfirmResponse>('/leads/import/confirm', {
    method: 'POST',
    body: {
      campaign_id: campaignId,
      leads,
    },
  })
}
