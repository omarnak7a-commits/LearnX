/**
 * LearnX API client — the single real fetch wrapper for the backend.
 *
 * - Base URL comes from `VITE_API_BASE_URL` (set at build time on Vercel
 *   to the Render backend URL). Falls back to same-origin for dev.
 * - Attaches the JWT from localStorage (`learnx_token`) as Bearer.
 * - Normalizes errors into `ApiError` with status + message.
 */

const BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

const TOKEN_KEY = 'learnx_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // storage unavailable — session only
  }
}

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${BASE_URL}${p}`
}

export interface RequestOptions {
  method?: string
  body?: unknown
  /** Raw FormData / Blob body — skips JSON serialization. */
  rawBody?: BodyInit
  headers?: Record<string, string>
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, rawBody, headers = {} } = opts
  const token = getToken()

  const h: Record<string, string> = {
    ...(rawBody ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...headers,
  }

  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: h,
      body: rawBody ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'Network error — backend unreachable.')
  }

  if (response.status === 401) {
    // Token invalid/expired — clear it so the app can re-authenticate.
    setToken(null)
  }

  const text = await response.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    const detail =
      (typeof data === 'object' && data !== null && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : undefined) ?? text ?? response.statusText
    throw new ApiError(response.status, detail)
  }

  return data as T
}
