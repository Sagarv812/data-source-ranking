import { getAuthToken } from '../app/auth-client'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: await requestHeaders(),
  })
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  return response.json() as Promise<T>
}

export async function apiPost<TResponse, TBody extends object>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: await requestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  return response.json() as Promise<TResponse>
}

async function requestHeaders(init?: HeadersInit) {
  const headers = new Headers(init)
  const token = await getAuthToken()
  if (token) {
    headers.set('Authorization', token)
  }
  return headers
}

async function errorMessage(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    return typeof payload.detail === 'string' ? payload.detail : response.statusText
  } catch {
    return response.statusText
  }
}
