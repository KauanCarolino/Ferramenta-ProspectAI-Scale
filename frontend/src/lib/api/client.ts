export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface ApiFetchOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

async function throwApiError(response: Response): Promise<never> {
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

export function getApiErrorMessage(
  error: unknown,
  fallback = 'Ocorreu um erro',
): string {
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

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { body, headers, ...rest } = options

  const response = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    await throwApiError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

/** Multipart upload — do not set Content-Type (browser sets boundary). */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: Omit<RequestInit, 'body'> = {},
): Promise<T> {
  const { headers, ...rest } = options

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    ...rest,
    headers: {
      Accept: 'application/json',
      ...headers,
    },
    body: formData,
  })

  if (!response.ok) {
    await throwApiError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
