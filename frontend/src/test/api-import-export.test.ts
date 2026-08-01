import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api/client'
import { downloadLogsCsv } from '@/lib/api/logs'
import { confirmImport, previewImport } from '@/lib/api/leads'
import { pollInbox } from '@/lib/api/accounts'

describe('downloadLogsCsv', () => {
  const originalCreateObjectURL = URL.createObjectURL
  const originalRevokeObjectURL = URL.revokeObjectURL

  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
  })

  it('faz fetch do CSV e dispara download', async () => {
    const blob = new Blob(['a,b\n1,2'], { type: 'text/csv' })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => blob,
      headers: {
        get: (name: string) =>
          name === 'Content-Disposition'
            ? 'attachment; filename="prospectai-logs-20260801.csv"'
            : null,
      },
    })
    vi.stubGlobal('fetch', fetchMock)

    const click = vi.fn()
    const remove = vi.fn()
    const appendChild = vi
      .spyOn(document.body, 'appendChild')
      .mockImplementation((node) => {
        const el = node as HTMLAnchorElement
        Object.defineProperty(el, 'click', { value: click })
        Object.defineProperty(el, 'remove', { value: remove })
        return node
      })

    await downloadLogsCsv({ today: true, result: 'error', limit: 50 })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/logs/export?'),
      expect.objectContaining({ headers: { Accept: 'text/csv' } }),
    )
    const calledUrl = String(fetchMock.mock.calls[0]?.[0])
    expect(calledUrl).toContain('today=true')
    expect(calledUrl).toContain('result=error')
    expect(calledUrl).toContain('limit=50')
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')

    appendChild.mockRestore()
  })

  it('lança ApiError em resposta HTTP de erro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'boom' }),
      }),
    )

    await expect(downloadLogsCsv()).rejects.toBeInstanceOf(ApiError)
  })
})

describe('leads import API', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('previewImport envia FormData sem Content-Type JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        campaign_id: 'camp-1',
        total_rows: 1,
        valid_count: 1,
        rejected_count: 0,
        duplicate_count: 0,
        preview: [],
        rejected: [],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const file = new File(['nome,empresa\nA,B'], 'leads.csv', {
      type: 'text/csv',
    })
    await previewImport('camp-1', file)

    expect(fetchMock).toHaveBeenCalled()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/leads/import/preview?campaign_id=camp-1')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const headers = init.headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
  })

  it('confirmImport envia JSON com campaign_id e leads', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        campaign_id: 'camp-1',
        inserted: 2,
        skipped_duplicates: 1,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await confirmImport('camp-1', [
      {
        nome: 'Ana',
        empresa: 'Acme',
        cargo: 'CEO',
        instagram: 'ana',
      },
    ])

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({
      campaign_id: 'camp-1',
      leads: [
        {
          nome: 'Ana',
          empresa: 'Acme',
          cargo: 'CEO',
          instagram: 'ana',
        },
      ],
    })
  })
})

describe('pollInbox', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('chama POST /accounts/inbox-poll com account_id opcional', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        accounts_polled: 1,
        replies_seen: 2,
        leads_matched: 1,
        errors: 0,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await pollInbox('acc-1')
    expect(result.replies_seen).toBe(2)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/accounts/inbox-poll?account_id=acc-1')
    expect(init.method).toBe('POST')
  })
})
