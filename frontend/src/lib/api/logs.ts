import { API_BASE, ApiError, apiFetch } from './client'

export interface LogEntry {
  id: string
  timestamp: string
  campaign_id: string | null
  lead_id: string | null
  account_id: string | null
  action: string
  channel: string
  instagram_handle: string | null
  result: string
  error: string | null
  message_hash: string | null
  details: string | null
}

export interface DownloadLogsCsvParams {
  campaignId?: string
  today?: boolean
  result?: string
  limit?: number
}

export async function fetchLogs(): Promise<LogEntry[]> {
  return apiFetch<LogEntry[]>('/logs')
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null
  const match = /filename="([^"]+)"/i.exec(header)
  return match?.[1] ?? null
}

export async function downloadLogsCsv(
  params: DownloadLogsCsvParams = {},
): Promise<void> {
  const search = new URLSearchParams()
  if (params.campaignId) {
    search.set('campaign_id', params.campaignId)
  }
  if (params.today) {
    search.set('today', 'true')
  }
  if (params.result) {
    search.set('result', params.result)
  }
  if (params.limit !== undefined) {
    search.set('limit', String(params.limit))
  }
  const query = search.toString()

  const response = await fetch(
    `${API_BASE}/logs/export${query ? `?${query}` : ''}`,
    {
      headers: { Accept: 'text/csv' },
    },
  )

  if (!response.ok) {
    let errorBody: unknown
    try {
      errorBody = await response.json()
    } catch {
      errorBody = undefined
    }
    throw new ApiError(
      response.status,
      `Falha na requisição (status ${response.status})`,
      errorBody,
    )
  }

  const blob = await response.blob()
  const filename =
    filenameFromDisposition(response.headers.get('Content-Disposition')) ??
    'prospectai-logs.csv'
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
