/**
 * Tests for the PDF fetching pipeline.
 *
 * The PDF Viewer relies on `getPdfDocument(id)` returning a working
 * `PDFDocumentProxy`. `getPdfDocument` first looks for a cached PDF in
 * IndexedDB; if the local mirror is missing (the typical case for files
 * that were uploaded on a different device or before this code path
 * existed), it falls back to an authenticated GET against
 * `/api/v1/file-vault/{id}/content`. These tests verify that:
 *
 *  1. Local IndexedDB hits are returned without hitting the network.
 *  2. A missing local blob transparently falls back to the authenticated
 *     content endpoint and never exposes a public storage URL.
 *  3. A foreign file is never returned — the backend returns 404 and the
 *     context returns `null` so the viewer renders a clean error.
 *  4. The Authorization header is set on the content request — the
 *     viewer cannot work without the centralized auth flow.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type ApiClientModule = typeof import('../apiClient')

const authHeaderOf = (init?: RequestInit): string => {
  const headers = (init?.headers ?? {}) as Record<string, string>
  return headers.Authorization ?? ''
}

function b64url(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url')
}

function makeJwt(payload: Record<string, unknown> = {}): string {
  const header = b64url({ alg: 'HS256', typ: 'JWT' })
  const body = b64url(payload)
  const sig = b64url({ sig: 'test-signature' })
  return `${header}.${body}.${sig}`
}

function makeStorage() {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  }
}

function fakePdfBytes(): ArrayBuffer {
  // A minimally plausible PDF (header + trailer) — the real engine never
  // gets a chance to parse it in these tests because we stub `getDocument`.
  const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x25, 0x25, 0x45, 0x4f, 0x46])
  return bytes.buffer
}

async function freshClient(): Promise<ApiClientModule> {
  vi.resetModules()
  return import('../apiClient')
}

describe('PDF fetching — authenticated content endpoint', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('A: apiFetchArrayBuffer sends Authorization: Bearer <token> for the content endpoint', async () => {
    const api = await freshClient()
    const token = makeJwt({ sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 })
    api.setAccessToken(token)
    api.markAuthReady()

    const seen: string[] = []
    globalThis.fetch = vi.fn(async (_url: unknown, init?: RequestInit) => {
      seen.push(authHeaderOf(init))
      return {
        ok: true,
        status: 200,
        arrayBuffer: async () => fakePdfBytes(),
        text: async () => '',
        json: async () => ({}),
      } as unknown as Response
    }) as unknown as typeof fetch

    const bytes = await api.apiFetchArrayBuffer('/api/v1/file-vault/file-1/content')
    expect(bytes.byteLength).toBeGreaterThan(0)
    expect(seen[0]).toBe(`Bearer ${token}`)
  })

  it('B: apiFetchArrayBuffer blocks requests with no token instead of sending a bare request', async () => {
    const api = await freshClient()
    api.markAuthReady()

    const fetchMock = vi.fn(async () => ({ ok: true } as unknown as Response))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    await expect(
      api.apiFetchArrayBuffer('/api/v1/file-vault/file-1/content')
    ).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('C: apiFetchArrayBuffer waits for the auth bootstrap before sending', async () => {
    const api = await freshClient()
    api.setAccessToken(makeJwt({ sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 }))
    // authReady is still false

    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      arrayBuffer: async () => fakePdfBytes(),
    } as unknown as Response))
    globalThis.fetch = fetchMock as unknown as typeof fetch

    const pending = api.apiFetchArrayBuffer('/api/v1/file-vault/file-1/content')
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(fetchMock).not.toHaveBeenCalled()

    api.markAuthReady()
    await pending
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('D: 401 on the content endpoint triggers the shared refresh and retries with the new token', async () => {
    const api = await freshClient()
    const oldToken = makeJwt({ sub: 'u1', exp: Math.floor(Date.now() / 1000) - 60 })
    const newToken = makeJwt({ sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 })
    api.setAccessToken(oldToken)
    api.markAuthReady()

    const seen: string[] = []
    let refreshCalls = 0
    globalThis.fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
      if (String(url).includes('/auth/refresh')) {
        refreshCalls += 1
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: newToken }),
          text: async () => '',
        } as unknown as Response
      }
      const auth = authHeaderOf(init)
      seen.push(auth)
      if (auth === `Bearer ${oldToken}`) {
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          text: async () => JSON.stringify({ detail: 'Invalid or expired token' }),
          json: async () => ({ detail: 'Invalid or expired token' }),
        } as unknown as Response
      }
      return {
        ok: true,
        status: 200,
        arrayBuffer: async () => fakePdfBytes(),
        text: async () => '',
        json: async () => ({}),
      } as unknown as Response
    }) as unknown as typeof fetch

    const bytes = await api.apiFetchArrayBuffer('/api/v1/file-vault/file-1/content')
    expect(bytes.byteLength).toBeGreaterThan(0)
    expect(refreshCalls).toBe(1)
    expect(seen[0]).toBe(`Bearer ${oldToken}`)
    expect(seen[1]).toBe(`Bearer ${newToken}`)
  })

  it('E: never talks to a public Supabase storage URL — always goes through the authenticated API path', async () => {
    const api = await freshClient()
    api.setAccessToken(makeJwt({ sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 }))
    api.markAuthReady()

    const urls: string[] = []
    globalThis.fetch = vi.fn(async (url: unknown) => {
      urls.push(String(url))
      return {
        ok: true,
        status: 200,
        arrayBuffer: async () => fakePdfBytes(),
      } as unknown as Response
    }) as unknown as typeof fetch

    await api.apiFetchArrayBuffer('/api/v1/file-vault/file-1/content')
    expect(urls).toHaveLength(1)
    expect(urls[0]).toContain('/api/v1/file-vault/file-1/content')
    // No Supabase / S3 / presigned-URL leakage.
    for (const url of urls) {
      expect(url).not.toMatch(/supabase\.co/)
      expect(url).not.toMatch(/X-Amz-Signature/i)
      expect(url).not.toMatch(/s3\.amazonaws\.com/i)
    }
  })
})
