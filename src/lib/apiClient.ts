/**
 * LearnX API client — the single real fetch wrapper for the backend, plus the
 * central access-token manager.
 *
 * - Base URL comes from `VITE_API_BASE_URL` (set at build time on Vercel to the
 *   Render backend URL). Falls back to same-origin for dev.
 * - `memoryToken` below is the ONE source of truth for the access token.
 *   `localStorage` is used only as persistent hydration (page refresh) and as a
 *   mirror; every read of the current token goes through `getAccessToken()` and
 *   every write goes through `setAccessToken()` / `clearAccessToken()`.
 * - Protected requests wait for the auth bootstrap to complete, refuse to send
 *   when no valid token exists, and share a single refresh promise so that N
 *   concurrent 401s trigger exactly ONE `/auth/refresh` call.
 */

const BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

// `learnx_access_token` is the current AuthContext key. Keep the legacy key
// synchronized so the existing feature API clients and both auth flows share
// one authenticated session.
const TOKEN_KEY = 'learnx_access_token'
const LEGACY_TOKEN_KEY = 'learnx_token'

// Endpoints that are unauthenticated by design. These neither require a token,
// wait for the auth bootstrap, nor trigger a refresh on 401.
const NO_AUTH_PATHS = new Set([
  '/api/v1/auth/refresh',
  '/api/v1/auth/login',
  '/api/v1/auth/register',
  '/api/v1/auth/logout',
  '/api/v1/auth/logout-all',
  '/api/v1/auth/forgot-password',
  '/api/v1/auth/reset-password',
  '/api/v1/auth/verify-email',
  '/api/v1/auth/resend-verification',
  '/api/v1/auth/google',
  '/api/v1/auth/google/callback',
  '/api/v1/auth/google/complete-signup',
])

// ────────────────────────────────────────────────────────────────────────────
// Single source of truth: in-memory access token.
// ────────────────────────────────────────────────────────────────────────────

// Authoritative in-memory copy. Authenticated calls never depend on React
// state or on a synchronous localStorage read alone.
let memoryToken: string | null = null

// Set to true once we have either hydrated from storage or performed an
// explicit set/clear. Prevents a stale localStorage value from being
// resurrected after `clearAccessToken()`.
let storageHydrated = false

// Monotonic counter bumped on every set/clear. A refresh that began against an
// older generation must not clobber a token that was set while it was running.
let tokenGeneration = 0

// Shared refresh lock: exactly one refresh runs at a time; every concurrent
// caller awaits this same promise instead of starting its own refresh.
let refreshPromise: Promise<string | null> | null = null

// ────────────────────────────────────────────────────────────────────────────
// Auth bootstrap gate.
// ────────────────────────────────────────────────────────────────────────────

// Set by AuthProvider once the initial hydration/validation pass has finished.
// Protected requests wait for this before being sent, so a request can never
// fire in the window where the session is still being restored.
let authReady = false
let authReadyWaiters: Array<() => void> = []

// Development-only auth diagnostics. NEVER logs the JWT or any header value.
const DEBUG_AUTH =
  typeof import.meta !== 'undefined' && (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV === true

function authDebug(info: Record<string, unknown>): void {
  if (!DEBUG_AUTH) return
  try {
    // eslint-disable-next-line no-console
    console.debug('[AUTH DEBUG]', JSON.stringify(info))
  } catch {
    // Debug output must never break the request path.
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Token normalization + validation.
// ────────────────────────────────────────────────────────────────────────────

export function normalizeAccessToken(raw: string | null | undefined): string | null {
  if (!raw) return null
  let token = raw.trim().replace(/^["']+|["']+$/g, '')
  while (/^bearer\s+/i.test(token)) {
    token = token.replace(/^bearer\s+/i, '').trim().replace(/^["']+|["']+$/g, '')
  }
  return token || null
}

function isWellFormedJwt(token: string): boolean {
  if (!token || typeof token !== 'string') return false
  const parts = token.split('.')
  if (parts.length !== 3) return false
  const base64url = /^[A-Za-z0-9_-]+$/
  return parts.every((part) => part.length > 0 && base64url.test(part))
}

/** Returns true for a non-empty, structurally valid JWT (never for "null", "", whitespace, etc.). */
export function isValidAccessToken(token: string | null | undefined): boolean {
  if (!token) return false
  const cleaned = normalizeAccessToken(token)
  return cleaned !== null && cleaned !== '' && isWellFormedJwt(cleaned)
}

function base64UrlDecode(segment: string): string {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  if (typeof atob === 'function') return atob(padded)
  if (typeof Buffer !== 'undefined') return Buffer.from(base64, 'base64').toString('utf8')
  throw new Error('No base64url decoder available')
}

function jwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split('.')[1]
    if (!part) return null
    return JSON.parse(base64UrlDecode(part)) as Record<string, unknown>
  } catch {
    return null
  }
}

/**
 * Structural expiry check used only to avoid a needless (and concurrency-
 * unsafe) refresh rotation on boot. `skewSeconds` guards against clock skew.
 * A token we cannot decode is treated as not-expired and left to the backend.
 */
export function isAccessTokenExpired(token: string, skewSeconds = 30): boolean {
  const payload = jwtPayload(token)
  if (!payload || typeof payload.exp !== 'number') return false
  return payload.exp <= Math.floor(Date.now() / 1000) + skewSeconds
}

// ────────────────────────────────────────────────────────────────────────────
// Public token-manager API (single source of truth).
// ────────────────────────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (memoryToken && isValidAccessToken(memoryToken)) return memoryToken

  if (!storageHydrated) {
    storageHydrated = true
    try {
      const stored = normalizeAccessToken(
        localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY),
      )
      if (stored && isValidAccessToken(stored)) {
        memoryToken = stored
        return stored
      }
    } catch {
      // storage unavailable — fall through, memory remains authoritative
    }
  }

  return memoryToken && isValidAccessToken(memoryToken) ? memoryToken : null
}

/** Atomically update the in-memory token AND localStorage. */
export function setAccessToken(token: string | null): void {
  const cleaned = normalizeAccessToken(token)
  memoryToken = cleaned && isValidAccessToken(cleaned) ? cleaned : null
  storageHydrated = true
  tokenGeneration++

  try {
    if (memoryToken) {
      localStorage.setItem(TOKEN_KEY, memoryToken)
      localStorage.setItem(LEGACY_TOKEN_KEY, memoryToken)
    } else {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(LEGACY_TOKEN_KEY)
    }
  } catch {
    // storage unavailable — session only (memoryToken is still authoritative)
  }
}

/** Atomically clear the in-memory token AND localStorage. */
export function clearAccessToken(): void {
  memoryToken = null
  storageHydrated = true
  tokenGeneration++

  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(LEGACY_TOKEN_KEY)
  } catch {
    // storage unavailable
  }
}

// Backward-compatible aliases used by AuthContext / Google callback / App.
export function getToken(): string | null {
  return getAccessToken()
}

export function setToken(token: string | null): void {
  setAccessToken(token)
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken()
  if (!token) return { ...extra }
  return {
    Authorization: `Bearer ${token}`,
    'X-Access-Token': token,
    ...extra,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Auth bootstrap gate (public).
// ────────────────────────────────────────────────────────────────────────────

export function isAuthReady(): boolean {
  return authReady
}

export function markAuthReady(): void {
  if (authReady) return
  authReady = true
  const waiters = authReadyWaiters
  authReadyWaiters = []
  for (const resolve of waiters) resolve()
}

/**
 * Resolve once the auth bootstrap completes. Protected requests await this so
 * they are never sent while the session is still being restored. Falls back to
 * a controlled timeout rather than hanging forever if bootstrap stalls.
 */
export function waitForAuthReady(timeoutMs = 20000): Promise<void> {
  if (authReady) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new ApiError(0, 'Authentication initialization timed out.'))
    }, timeoutMs)
    authReadyWaiters.push(() => {
      clearTimeout(timer)
      resolve()
    })
  })
}

// ────────────────────────────────────────────────────────────────────────────
// Errors + helpers.
// ────────────────────────────────────────────────────────────────────────────

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

function isPublicPath(path: string): boolean {
  const normalized = path.split('?')[0] ?? path
  return NO_AUTH_PATHS.has(normalized)
}

// ────────────────────────────────────────────────────────────────────────────
// Concurrency-safe refresh.
// ────────────────────────────────────────────────────────────────────────────

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise

  const generationAtStart = tokenGeneration
  authDebug({ event: 'refresh_start', refreshInProgress: true })

  refreshPromise = (async () => {
    try {
      const response = await fetch(apiUrl('/api/v1/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({}),
      })
      if (!response.ok) return null
      const data = (await response.json()) as { access_token?: string }
      const next = normalizeAccessToken(data?.access_token)
      if (!next || !isValidAccessToken(next)) return null

      // Discard a stale refresh result: if a newer token was set while this
      // refresh was in flight (e.g. a fresh login), keep the newer token.
      if (tokenGeneration === generationAtStart) {
        setAccessToken(next)
      }
      return getAccessToken()
    } catch {
      return null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

// ────────────────────────────────────────────────────────────────────────────
// Request layer.
// ────────────────────────────────────────────────────────────────────────────

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  return requestJson<T>(path, opts, true)
}

/**
 * Authenticated binary download — same JWT / refresh / bootstrap semantics
 * as `apiFetch`, but the response body is read as raw bytes. Used by the
 * PDF Viewer to load a real PDF into `pdfjsLib.getDocument` without
 * exposing the storage URL or bypassing auth.
 */
export async function apiFetchArrayBuffer(path: string, opts: RequestOptions = {}): Promise<ArrayBuffer> {
  return requestArrayBuffer(path, opts, true)
}

async function requestArrayBuffer(
  path: string,
  opts: RequestOptions,
  allowRefresh: boolean,
): Promise<ArrayBuffer> {
  const { method = 'GET', body, rawBody, headers = {} } = opts
  const isPublic = isPublicPath(path)

  if (!isPublic) {
    await waitForAuthReady()
  }

  const token = isPublic ? null : getAccessToken()

  if (!isPublic && !token) {
    throw new ApiError(401, 'Authentication required — please sign in again.')
  }

  const h: Record<string, string> = {
    ...(rawBody ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}`, 'X-Access-Token': token } : {}),
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

  if (response.status === 401 && allowRefresh && !isPublic) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      return requestArrayBuffer(path, opts, false)
    }
    clearAccessToken()
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const text = await response.text()
      if (text) {
        try {
          const parsed = JSON.parse(text) as { detail?: unknown }
          if (parsed && typeof parsed.detail === 'string') {
            detail = parsed.detail
          } else {
            detail = text
          }
        } catch {
          detail = text
        }
      }
    } catch {
      // ignore secondary read errors
    }
    throw new ApiError(response.status, detail)
  }

  return response.arrayBuffer()
}

async function requestJson<T>(
  path: string,
  opts: RequestOptions,
  allowRefresh: boolean,
): Promise<T> {
  const { method = 'GET', body, rawBody, headers = {} } = opts
  const isPublic = isPublicPath(path)

  // Protected requests must not run until the auth bootstrap has completed.
  if (!isPublic) {
    await waitForAuthReady()
  }

  // Obtain the current token immediately before sending. Never capture a stale
  // token when the request function is created, and never rely on React state.
  const token = isPublic ? null : getAccessToken()

  if (!isPublic && !token) {
    authDebug({
      event: 'blocked_missing_token',
      request: path,
      hasToken: false,
      tokenValid: false,
      authReady: authReady,
      refreshInProgress: refreshPromise !== null,
    })
    // Do NOT send the request — return a controlled authentication error.
    throw new ApiError(401, 'Authentication required — please sign in again.')
  }

  // Construct Authorization immediately before the request is sent, fresh per
  // request. A previous request must never affect this one.
  const h: Record<string, string> = {
    ...(rawBody ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}`, 'X-Access-Token': token } : {}),
    ...headers,
  }

  authDebug({
    request: path,
    hasToken: token !== null,
    tokenValid: token !== null,
    authReady: authReady,
    refreshInProgress: refreshPromise !== null,
  })

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

  if (response.status === 401 && allowRefresh && !isPublic) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      return requestJson<T>(path, opts, false)
    }
    // Refresh definitively failed — clear auth state once and let the 401
    // surface as a clean error. Do not retry indefinitely.
    clearAccessToken()
    authDebug({
      event: 'refresh_failed',
      request: path,
      hasToken: false,
      tokenValid: false,
      authReady: authReady,
      refreshInProgress: false,
    })
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
