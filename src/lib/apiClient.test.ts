/**
 * Concurrency + intermittent-behaviour regression tests for the access-token
 * manager and request layer (src/lib/apiClient.ts).
 *
 * These tests exercise the exact failure modes behind the intermittent
 * "Missing bearer token" bug: concurrent requests, a shared refresh lock,
 * refresh failure, auth bootstrap gating, and stale-refresh overwrites.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type ApiClientModule = typeof import('./apiClient')

function b64url(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url')
}

/** Build a structurally valid JWT (3 base64url segments) with the given claims. */
function makeJwt(payload: Record<string, unknown> = {}): string {
  const header = b64url({ alg: 'HS256', typ: 'JWT' })
  const body = b64url(payload)
  const sig = b64url({ sig: 'test-signature' })
  return `${header}.${body}.${sig}`
}

const NOW = Math.floor(Date.now() / 1000)

function makeStorage() {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

function jsonResponse(status: number, body: unknown): Response {
  const text = JSON.stringify(body)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => body,
  } as unknown as Response
}

async function freshClient(): Promise<ApiClientModule> {
  vi.resetModules()
  return import('./apiClient')
}

function authHeaderOf(init?: RequestInit): string {
  const headers = (init?.headers ?? {}) as Record<string, string>
  return headers.Authorization ?? ''
}

describe('access token manager — single source of truth', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('getAccessToken never returns null/undefined/""/"null"/whitespace/malformed', async () => {
    const mod = await freshClient()
    // nothing set → null
    expect(mod.getAccessToken()).toBeNull()

    for (const junk of ['', '   ', 'null', 'undefined', '"null"', '"undefined"', 'not-a-jwt', 'a.b', '..']) {
      mod.setAccessToken(junk)
      expect(mod.getAccessToken()).toBeNull()
    }

    const token = makeJwt({ sub: 'u1' })
    mod.setAccessToken(token)
    expect(mod.getAccessToken()).toBe(token)
    expect(mod.isValidAccessToken(token)).toBe(true)
    expect(mod.isValidAccessToken('null')).toBe(false)
    expect(mod.isValidAccessToken('')).toBe(false)
  })

  it('normalizes quoted + repeated "Bearer " prefixes', async () => {
    const mod = await freshClient()
    const token = makeJwt({ sub: 'u1' })
    expect(mod.normalizeAccessToken(`Bearer ${token}`)).toBe(token)
    expect(mod.normalizeAccessToken(`Bearer Bearer ${token}`)).toBe(token)
    expect(mod.normalizeAccessToken(`"${token}"`)).toBe(token)
    expect(mod.normalizeAccessToken(null)).toBeNull()
  })

  it('setAccessToken atomically writes memory AND localStorage', async () => {
    const mod = await freshClient()
    const token = makeJwt({ sub: 'u1' })
    mod.setAccessToken(token)
    expect(mod.getAccessToken()).toBe(token)
    expect(globalThis.localStorage.getItem('learnx_access_token')).toBe(token)
    expect(globalThis.localStorage.getItem('learnx_token')).toBe(token)
  })

  it('clearAccessToken atomically clears memory AND localStorage', async () => {
    const mod = await freshClient()
    const token = makeJwt({ sub: 'u1' })
    mod.setAccessToken(token)
    mod.clearAccessToken()
    expect(mod.getAccessToken()).toBeNull()
    expect(globalThis.localStorage.getItem('learnx_access_token')).toBeNull()
    expect(globalThis.localStorage.getItem('learnx_token')).toBeNull()
  })

  it('does not resurrect a cleared token from stale localStorage', async () => {
    const storage = makeStorage()
    storage.setItem('learnx_access_token', makeJwt({ sub: 'u1' }))
    globalThis.localStorage = storage as unknown as Storage

    const mod = await freshClient()
    // hydrate
    expect(mod.getAccessToken()).toBeTruthy()
    // clear explicitly
    mod.clearAccessToken()
    expect(mod.getAccessToken()).toBeNull()
  })
})

describe('concurrent requests', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('A: 10 concurrent requests with a valid token all carry Authorization and succeed', async () => {
    const mod = await freshClient()
    const token = makeJwt({ sub: 'u1', exp: NOW + 3600 })
    mod.setAccessToken(token)
    mod.markAuthReady()

    const seen: string[] = []
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      seen.push(authHeaderOf(init))
      return jsonResponse(200, { answer: 'ok' })
    }) as unknown as typeof fetch

    const results = await Promise.all(
      Array.from({ length: 10 }, () =>
        mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } }),
      ),
    )

    expect(results).toHaveLength(10)
    expect(seen).toHaveLength(10)
    for (const auth of seen) {
      expect(auth).toBe(`Bearer ${token}`)
    }
  })

  it('B: 10 concurrent 401s trigger EXACTLY ONE refresh and all retry with the new token', async () => {
    const mod = await freshClient()
    const oldToken = makeJwt({ sub: 'u1', exp: NOW - 60 }) // expired
    const newToken = makeJwt({ sub: 'u1', exp: NOW + 3600 })
    mod.setAccessToken(oldToken)
    mod.markAuthReady()

    let refreshCalls = 0
    let chatCalls = 0
    globalThis.fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
      const u = String(url)
      if (u.includes('/auth/refresh')) {
        refreshCalls += 1
        return jsonResponse(200, { access_token: newToken })
      }
      chatCalls += 1
      const auth = authHeaderOf(init)
      if (auth === `Bearer ${oldToken}`) return jsonResponse(401, { detail: 'Invalid or expired token' })
      if (auth === `Bearer ${newToken}`) return jsonResponse(200, { answer: 'ok' })
      return jsonResponse(401, { detail: 'Missing bearer token' })
    }) as unknown as typeof fetch

    const results = await Promise.all(
      Array.from({ length: 10 }, () =>
        mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } }),
      ),
    )

    expect(results).toHaveLength(10)
    expect(refreshCalls).toBe(1)
    expect(chatCalls).toBe(20) // 10 initial (401) + 10 retries (200)
    expect(mod.getAccessToken()).toBe(newToken)
  })

  it('C: refresh failure clears the token and all requests fail cleanly (no infinite retry)', async () => {
    const mod = await freshClient()
    mod.setAccessToken(makeJwt({ sub: 'u1', exp: NOW - 60 }))
    mod.markAuthReady()

    let refreshCalls = 0
    globalThis.fetch = vi.fn(async (url: unknown) => {
      if (String(url).includes('/auth/refresh')) {
        refreshCalls += 1
        return jsonResponse(401, { detail: 'No refresh token provided.' })
      }
      return jsonResponse(401, { detail: 'Invalid or expired token' })
    }) as unknown as typeof fetch

    const results = await Promise.allSettled(
      Array.from({ length: 10 }, () =>
        mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } }),
      ),
    )

    expect(refreshCalls).toBe(1)
    expect(mod.getAccessToken()).toBeNull()
    for (const r of results) {
      expect(r.status).toBe('rejected')
      if (r.status === 'rejected') {
        expect((r.reason as { status?: number }).status).toBe(401)
      }
    }
  })

  it('D: page refresh hydrates a valid JWT from localStorage before sending', async () => {
    const storage = makeStorage()
    const token = makeJwt({ sub: 'u1', exp: NOW + 3600 })
    storage.setItem('learnx_access_token', token)
    globalThis.localStorage = storage as unknown as Storage

    const mod = await freshClient() // fresh module — in-memory token empty
    mod.markAuthReady()

    const seen: string[] = []
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      seen.push(authHeaderOf(init))
      return jsonResponse(200, { answer: 'ok' })
    }) as unknown as typeof fetch

    await mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } })
    expect(seen[0]).toBe(`Bearer ${token}`)
  })

  it('E: a protected request is NOT sent before the auth bootstrap completes', async () => {
    const mod = await freshClient()
    mod.setAccessToken(makeJwt({ sub: 'u1', exp: NOW + 3600 }))
    // authReady is still false — bootstrap has not completed

    const fetchMock = vi.fn(async () => jsonResponse(200, { answer: 'ok' }))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const pending = mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } })
    await new Promise((r) => setTimeout(r, 20))
    expect(fetchMock).not.toHaveBeenCalled()

    mod.markAuthReady()
    await pending
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('F: token stored (Google OAuth path) is sent on the immediate next request', async () => {
    const mod = await freshClient()
    const token = makeJwt({ sub: 'u1', exp: NOW + 3600 })
    mod.setAccessToken(token) // mirrors GoogleCallbackPage.completeAuth
    mod.markAuthReady()

    const seen: string[] = []
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      seen.push(authHeaderOf(init))
      return jsonResponse(200, { answer: 'ok' })
    }) as unknown as typeof fetch

    await mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } })
    expect(seen[0]).toBe(`Bearer ${token}`)
  })

  it('G: a stale refresh must NOT overwrite a newer token set while it was in flight', async () => {
    const mod = await freshClient()
    const expired = makeJwt({ sub: 'u1', exp: NOW - 60 })
    const refreshedToken = makeJwt({ sub: 'u1', exp: NOW + 3600, src: 'refresh' })
    const newerToken = makeJwt({ sub: 'u1', exp: NOW + 7200, src: 'login' })
    mod.setAccessToken(expired)
    mod.markAuthReady()

    let resolveRefresh!: (r: Response) => void
    const refreshGate = new Promise<Response>((res) => {
      resolveRefresh = res
    })

    globalThis.fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
      if (String(url).includes('/auth/refresh')) return refreshGate
      const auth = authHeaderOf(init)
      if (auth === `Bearer ${expired}`) return jsonResponse(401, { detail: 'Invalid or expired token' })
      return jsonResponse(200, { answer: 'ok' })
    }) as unknown as typeof fetch

    const pending = mod.apiFetch('/api/v1/ai/chat', { method: 'POST', body: { message: 'hi' } })

    // Wait until the refresh call is actually in flight.
    await vi.waitFor(() => {
      expect((globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBeGreaterThanOrEqual(2)
    })

    // A fresh login lands while the (older) refresh is still pending.
    mod.setAccessToken(newerToken)

    // Let the stale refresh finish with the older token.
    resolveRefresh(jsonResponse(200, { access_token: refreshedToken }))

    await pending
    expect(mod.getAccessToken()).toBe(newerToken)
  })

  it('H: never sends Authorization: Bearer null/undefined/"" — blocked before fetch', async () => {
    const mod = await freshClient()
    mod.markAuthReady()

    const seen: string[] = []
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      seen.push(authHeaderOf(init))
      return jsonResponse(200, { answer: 'ok' })
    }) as unknown as typeof fetch

    // No token at all → controlled auth error, no request sent.
    await expect(mod.apiFetch('/api/v1/ai/chat', { method: 'POST' })).rejects.toMatchObject({
      status: 401,
    })
    expect(seen).toHaveLength(0)

    // Junk tokens are normalized to "no token", never sent as a header.
    for (const junk of ['null', 'undefined', '', '   ', '"null"']) {
      mod.setAccessToken(junk)
      expect(mod.getAccessToken()).toBeNull()
    }
    await expect(mod.apiFetch('/api/v1/ai/chat', { method: 'POST' })).rejects.toMatchObject({
      status: 401,
    })
    expect(seen).toHaveLength(0)
  })
})
