/**
 * LearnX API client — the single real fetch wrapper for the backend.
 *
 * - Base URL comes from `VITE_API_BASE_URL` (set at build time on Vercel
 *   to the Render backend URL). Falls back to same-origin for dev.
 * - Attaches the JWT from localStorage as Bearer + X-Access-Token.
 * - Silently refreshes an expired access token via the HttpOnly cookie.
 * - Normalizes errors into `ApiError` with status + message.
 */

const BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

// `learnx_access_token` is the current AuthContext key. Keep the legacy key
// synchronized so the existing feature API clients and both auth flows share
// one authenticated session.
const TOKEN_KEY = 'learnx_access_token'
const LEGACY_TOKEN_KEY = 'learnx_token'

const NO_REFRESH_PATHS = new Set([
  '/api/v1/auth/refresh',
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/logout',
  '/api/v1/auth/logout-all',
  '/api/v1/auth/forgot-password',
  '/api/v1/auth/reset-password',
  '/api/v1/auth/google',
  '/api/v1/auth/google/callback',
  '/api/v1/auth/google/complete-signup',
])

let refreshInFlight: Promise<boolean> | null = null

// In-memory copy of the access token. Guarantees authenticated calls keep
// working even when localStorage is unavailable (private browsing, blocked
// storage, etc.) — without it, a cookie-based refresh succeeds but the
// retried request still goes out without a bearer token.
let memoryToken: string | null = null

export function normalizeAccessToken(raw: string | null | undefined): string | null {
  if (!raw) return null
  let token = raw.trim().replace(/^["']+|["']+$/g, '')
  while (/^bearer\s+/i.test(token)) {
    token = token.replace(/^bearer\s+/i, '').trim().replace(/^["']+|["']+$/g, '')
  }
  return token || null
}

export function getToken(): string | null {
  try {
    const stored = normalizeAccessToken(
      localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY),
    )
    if (stored) return stored
  } catch {
    // storage unavailable — fall through to the in-memory token
  }
  return memoryToken
}

export function setToken(token: string | null): void {
  const cleaned = normalizeAccessToken(token)
  memoryToken = cleaned
  try {
    if (cleaned) {
      localStorage.setItem(TOKEN_KEY, cleaned)
      localStorage.setItem(LEGACY_TOKEN_KEY, cleaned)
    } else {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(LEGACY_TOKEN_KEY)
    }
  } catch {
    // storage unavailable — session only (memoryToken still holds it)
  }
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken()
  if (!token) return { ...extra }
  return {
    Authorization: `Bearer ${token}`,
    'X-Access-Token': token,
    ...extra,
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

function shouldAttemptRefresh(path: string): boolean {
  const normalized = path.split('?')[0] ?? path
  return !NO_REFRESH_PATHS.has(normalized)
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const response = await fetch(apiUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({}),
      })
      if (!response.ok) return false
      const data = (await response.json()) as { access_token?: string }
      if (!data.access_token) return false
      setToken(data.access_token)
      return true
    } catch {
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, opts, true)
}

async function requestJson<T>(
  path: string,
  opts: RequestOptions,
  allowRefresh: boolean,
): Promise<T> {
  const { method = 'GET', body, rawBody, headers = {} } = opts

  const h: Record<string, string> = {
    ...(rawBody ? {} : { 'Content-Type': 'application/json' }),
    ...authHeaders(),
    ...headers,
  }

  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      method,
      headers: h,
      credentials: 'include',
      body: rawBody ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'Network error — backend unreachable.')
  }

  if (response.status === 401 && allowRefresh && shouldAttemptRefresh(path)) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      return requestJson<T>(path, opts, false)
    }
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
