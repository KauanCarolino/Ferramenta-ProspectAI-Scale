import { apiFetch } from './client'

export type TemplateStage = 'd1' | 'd4' | 'd8'

export const TEMPLATE_STAGES = ['d1', 'd4', 'd8'] as const

export interface Template {
  id: string
  campaign_id: string
  stage: TemplateStage | string
  name: string | null
  body: string
  created_at: string
  updated_at: string
}

export interface TemplateCreatePayload {
  campaign_id: string
  stage: TemplateStage
  body: string
  name?: string | null
}

export interface TemplateUpdatePayload {
  body?: string
  name?: string | null
  stage?: TemplateStage
}

export interface TemplatePreviewPayload {
  body: string
  variables?: Record<string, string>
  seed?: string
}

export interface TemplatePreviewResult {
  rendered: string
  variables_used?: string[]
  spintax_groups?: number
}

export async function fetchTemplates(
  campaignId?: string,
): Promise<Template[]> {
  const params = new URLSearchParams()
  if (campaignId) {
    params.set('campaign_id', campaignId)
  }
  const query = params.toString()
  return apiFetch<Template[]>(`/templates${query ? `?${query}` : ''}`)
}

export async function createTemplate(
  payload: TemplateCreatePayload,
): Promise<Template> {
  return apiFetch<Template>('/templates', {
    method: 'POST',
    body: payload,
  })
}

export async function updateTemplate(
  id: string,
  payload: TemplateUpdatePayload,
): Promise<Template> {
  return apiFetch<Template>(`/templates/${id}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function previewTemplate(
  payload: TemplatePreviewPayload,
): Promise<TemplatePreviewResult> {
  return apiFetch<TemplatePreviewResult>('/templates/preview', {
    method: 'POST',
    body: payload,
  })
}
