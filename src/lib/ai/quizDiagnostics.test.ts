/**
 * Diagnostics plumbing for the quiz endpoint.
 *
 * Two things have to hold, and both are wire-level facts rather than
 * implementation details:
 *
 * 1. `diagnostics` is opt-in. The exam the UI generates must send the exact
 *    body it sent before diagnostics existed — no `diagnostics` key at all,
 *    not even `false`. The backend keeps the response contract byte-identical
 *    for callers that do not ask, so sending the key unconditionally would be
 *    a silent API change for every normal request.
 *
 * 2. A 422 shortfall must keep its funnel. The backend attaches `diagnostics`
 *    as a sibling of `detail` on the error body; the request layer used to
 *    read `detail` and drop the rest, which is what left "could only verify 1"
 *    with nothing behind it.
 *
 * These run against the real `aiApi.quiz` / `apiFetch` / `ApiError` path with
 * only `fetch` stubbed, because the bug being prevented lives in exactly the
 * layer a mocked client would skip.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type AiApiModule = typeof import('./apiClient')
type ApiClientModule = typeof import('../apiClient')

function b64url(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url')
}

function makeJwt(payload: Record<string, unknown> = {}): string {
  return `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url(payload)}.${b64url({ sig: 's' })}`
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

function jsonResponse(status: number, body: unknown): Response {
  const text = JSON.stringify(body)
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 422 ? 'Unprocessable Entity' : 'OK',
    text: async () => text,
    json: async () => body,
  } as unknown as Response
}

/** A minimal but valid quiz question, shaped like the backend's response. */
const QUESTION = {
  id: 'q1',
  type: 'mcq',
  prompt: 'What does the normalization step remove?',
  options: ['Redundancy', 'Indexes', 'Rows', 'Columns'],
  correctAnswer: 'Redundancy',
  explanation: 'Normalization removes redundancy.',
  difficulty: 'medium',
  sourcePages: [3],
}

/**
 * The funnel the backend actually returns, captured verbatim from a live
 * `POST /api/v1/ai/quiz` (32-page fixture, `diagnostics: true`).
 *
 * Keys are snake_case. `AIQuizDiagnostics` extends plain pydantic `BaseModel`
 * instead of the camelCase-aliasing `AIBaseModel` used by every other AI
 * schema, so this is the real wire shape — a hand-written camelCase fixture
 * would pass while production silently read `undefined`.
 */
const DIAGNOSTICS = {
  requested: 8,
  extracted_pages: 32,
  pages_used: 32,
  text_pages: 32,
  image_only_pages: 0,
  pages_dropped_in_cleaning: 0,
  concepts: 32,
  evidence_items: 71,
  relationships: 40,
  plans: 64,
  candidates_generated: 42,
  accepted: 8,
  rejected: 0,
  provider_errors: 2,
  rejections: {},
  concepts_proposed_by_provider: 0,
  concepts_dropped_in_filtering: {},
  understanding_source: 'deterministic',
  provider_calls: {
    understanding_calls: 1,
    understanding_failed: 1,
    writer_calls: 1,
    writer_failed: 1,
  },
  plans_by_type: { mcq: 28, 'true-false': 22, 'short-answer': 14 },
  candidates_by_type: {},
  grounding_rejected: 0,
  diversity_rejected: 34,
  rejection_details: [],
  page_quality: ['page 1: text 42 chars', 'page 2: text 4580 chars'],
}

async function freshModules(): Promise<{ ai: AiApiModule; api: ApiClientModule }> {
  vi.resetModules()
  const api = await import('../apiClient')
  api.setAccessToken(makeJwt({ sub: 'u1' }))
  api.markAuthReady()
  const ai = await import('./apiClient')
  return { ai, api }
}

/** The parsed JSON body of the single fetch call that was made. */
function sentBody(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  expect(fetchMock).toHaveBeenCalledTimes(1)
  const init = fetchMock.mock.calls[0]?.[1] as RequestInit
  return JSON.parse(init.body as string) as Record<string, unknown>
}

describe('quiz diagnostics — request forwarding', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('omits the diagnostics key entirely when it was not requested', async () => {
    const { ai } = await freshModules()
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { questions: [QUESTION], provider: 'gemini', model: 'g', fallbackUsed: false })
    )
    vi.stubGlobal('fetch', fetchMock)

    await ai.aiApi.quiz({ fileId: 'f1', count: 8, kind: 'exam', scope: 'document' })

    const body = sentBody(fetchMock)
    // Not `false` — absent. An always-present key is a wire change for a
    // backend that branches on whether the caller asked at all.
    expect('diagnostics' in body).toBe(false)
    expect(body).toEqual({ fileId: 'f1', count: 8, kind: 'exam', scope: 'document' })
  })

  it('forwards diagnostics: true when explicitly requested', async () => {
    const { ai } = await freshModules()
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, {
        questions: [QUESTION],
        provider: 'gemini',
        model: 'g',
        fallbackUsed: false,
        diagnostics: DIAGNOSTICS,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await ai.aiApi.quiz({
      fileId: 'f1',
      count: 8,
      kind: 'exam',
      scope: 'document',
      diagnostics: true,
    })

    expect(sentBody(fetchMock).diagnostics).toBe(true)
    // And the funnel is surfaced to the caller, typed, in its real casing.
    expect(result.diagnostics?.concepts).toBe(32)
    expect(result.diagnostics?.accepted).toBe(8)
    expect(result.diagnostics?.extracted_pages).toBe(32)
    expect(result.diagnostics?.pages_used).toBe(32)
    expect(result.diagnostics?.understanding_source).toBe('deterministic')
    expect(result.diagnostics?.provider_calls).toEqual({
      understanding_calls: 1,
      understanding_failed: 1,
      writer_calls: 1,
      writer_failed: 1,
    })
  })

  it('still sends diagnostics: false when a caller passes it explicitly', async () => {
    const { ai } = await freshModules()
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { questions: [QUESTION], provider: 'groq', model: 'l', fallbackUsed: true })
    )
    vi.stubGlobal('fetch', fetchMock)

    await ai.aiApi.quiz({ fileId: 'f1', count: 6, diagnostics: false })

    // Passing it through verbatim is correct: `false` is the backend default,
    // so this cannot change behaviour, and dropping it would be the client
    // second-guessing an explicit argument.
    expect(sentBody(fetchMock).diagnostics).toBe(false)
  })

  it('leaves a successful response without diagnostics undefined', async () => {
    const { ai } = await freshModules()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, { questions: [QUESTION], provider: 'gemini', model: 'g', fallbackUsed: false })
      )
    )

    const result = await ai.aiApi.quiz({ fileId: 'f1', count: 8 })
    expect(result.diagnostics).toBeUndefined()
    expect(result.questions).toHaveLength(1)
  })
})

describe('quiz diagnostics — wire contract', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  /**
   * Guards the one thing a type cannot: that the declared field names match
   * the bytes on the wire. The backend's diagnostics model is the only AI
   * schema that does NOT camelCase its aliases, so a well-meaning "fix" to
   * make this interface look like its neighbours would compile cleanly and
   * break every reader at runtime.
   */
  it('reads the snake_case keys the backend actually sends', async () => {
    const { ai } = await freshModules()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(200, {
          questions: [QUESTION],
          provider: 'deterministic',
          model: 'learnx',
          fallbackUsed: true,
          diagnostics: DIAGNOSTICS,
        })
      )
    )

    const { diagnostics } = await ai.aiApi.quiz({ fileId: 'f1', count: 8, diagnostics: true })
    expect(diagnostics).toBeDefined()

    // Every documented field resolves — nothing silently undefined.
    for (const key of Object.keys(DIAGNOSTICS)) {
      expect(diagnostics).toHaveProperty(key)
    }
    // And the camelCase spellings are NOT present, which is what a client
    // written against the rest of the API would wrongly reach for.
    for (const wrong of ['extractedPages', 'pagesUsed', 'understandingSource', 'pageQuality']) {
      expect(diagnostics).not.toHaveProperty(wrong)
    }
  })
})

describe('diagnosticsFragment — the single opt-in rule', () => {
  /**
   * `generateExam` in FileVaultContext spreads this fragment into the request.
   * Testing the rule here keeps it verifiable without DOM test infrastructure,
   * and guarantees the exam path and the console helper share one behaviour.
   */
  it('yields an empty object unless diagnostics were explicitly requested', async () => {
    const { ai } = await freshModules()
    expect(ai.diagnosticsFragment()).toEqual({})
    expect(ai.diagnosticsFragment(undefined)).toEqual({})
    expect(ai.diagnosticsFragment({})).toEqual({})
    expect(ai.diagnosticsFragment({ diagnostics: false })).toEqual({})
    // The key must be absent, not false — spreading `{}` adds nothing.
    expect('diagnostics' in ai.diagnosticsFragment({ diagnostics: false })).toBe(false)
  })

  it('yields diagnostics: true when requested', async () => {
    const { ai } = await freshModules()
    expect(ai.diagnosticsFragment({ diagnostics: true })).toEqual({ diagnostics: true })
  })

  it('produces the exact exam body the context sends, with and without diagnostics', async () => {
    const { ai } = await freshModules()
    // Mirrors generateExam's call in FileVaultContext.
    const base = {
      fileId: 'f1',
      count: 8,
      questionTypes: ['mcq', 'true-false'],
      kind: 'exam',
      scope: 'document',
    }

    expect({ ...base, ...ai.diagnosticsFragment() }).toEqual(base)
    expect({ ...base, ...ai.diagnosticsFragment({ diagnostics: true }) }).toEqual({
      ...base,
      diagnostics: true,
    })
  })
})

describe('quiz diagnostics — 422 shortfall preservation', () => {
  beforeEach(() => {
    globalThis.localStorage = makeStorage() as unknown as Storage
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  /**
   * A real 422 body, captured from the live endpoint by asking for 20
   * fill-blank questions against the 32-page fixture. `detail` is the exact
   * string the user sees; `diagnostics` is the sibling key the request layer
   * used to discard — and it is what shows the shortfall was a validation
   * problem (34 rejected), not a thin document (32 concepts found).
   */
  const SHORTFALL = {
    detail:
      'This PDF does not contain enough clearly explained material for 20 well-grounded questions -- LearnX could only verify 1. Try asking for 1 questions instead.',
    diagnostics: {
      ...DIAGNOSTICS,
      requested: 20,
      plans: 36,
      accepted: 1,
      rejected: 34,
      rejections: { validation: 34, validator_false_negative: 34 },
      rejection_details: [
        {
          stage: 'validation',
          reason: 'fill-blank does not remove a meaningful term',
          concept: 'citric-acid-cycle',
          pages: [19],
          question_type: 'fill-blank',
        },
      ],
    },
  }

  it('keeps the funnel attached to the 422 error instead of discarding it', async () => {
    const { ai, api } = await freshModules()
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(422, SHORTFALL)))

    const error = await ai.aiApi
      .quiz({ fileId: 'f1', count: 8, kind: 'exam', diagnostics: true })
      .then(
        () => {
          throw new Error('expected the request to reject')
        },
        (caught: unknown) => caught
      )

    expect(error).toBeInstanceOf(api.ApiError)
    const apiError = error as InstanceType<ApiClientModule['ApiError']>
    expect(apiError.status).toBe(422)
    // `detail` is unchanged — every existing caller reads it and shows it.
    expect(apiError.detail).toBe(SHORTFALL.detail)
    expect(apiError.message).toBe(SHORTFALL.detail)

    const diagnostics = ai.quizDiagnosticsFromError(error)
    expect(diagnostics).toBeDefined()
    expect(diagnostics?.requested).toBe(20)
    expect(diagnostics?.accepted).toBe(1)
    expect(diagnostics?.rejected).toBe(34)
    // The whole point of the funnel: 32 concepts were found and 32 pages were
    // read, so "not enough material" was a validation failure, not a thin PDF.
    expect(diagnostics?.concepts).toBe(32)
    expect(diagnostics?.pages_used).toBe(32)
    expect(diagnostics?.rejections).toEqual({ validation: 34, validator_false_negative: 34 })
    // The per-candidate detail is what makes a shortfall actionable.
    expect(diagnostics?.rejection_details?.[0]).toMatchObject({
      stage: 'validation',
      question_type: 'fill-blank',
    })
  })

  it('returns undefined for a 422 that carries no diagnostics', async () => {
    const { ai } = await freshModules()
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(422, { detail: 'Not enough material.' })))

    const error = await ai.aiApi.quiz({ fileId: 'f1', count: 8 }).catch((caught: unknown) => caught)

    expect((error as { detail: string }).detail).toBe('Not enough material.')
    expect(ai.quizDiagnosticsFromError(error)).toBeUndefined()
  })

  it('returns undefined for non-ApiError values and plain-text error bodies', async () => {
    const { ai } = await freshModules()
    expect(ai.quizDiagnosticsFromError(new Error('boom'))).toBeUndefined()
    expect(ai.quizDiagnosticsFromError(undefined)).toBeUndefined()
    expect(ai.quizDiagnosticsFromError({ diagnostics: DIAGNOSTICS })).toBeUndefined()

    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            text: async () => 'upstream exploded',
          }) as unknown as Response
      )
    )
    const error = await ai.aiApi.quiz({ fileId: 'f1', count: 8 }).catch((caught: unknown) => caught)
    expect((error as { detail: string }).detail).toBe('upstream exploded')
    expect(ai.quizDiagnosticsFromError(error)).toBeUndefined()
  })

  it('preserves the error body without disturbing other failures', async () => {
    const { ai, api } = await freshModules()
    // A network failure has no body at all; it must still be a clean ApiError.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('network down')
      })
    )

    const error = await ai.aiApi.quiz({ fileId: 'f1', count: 8 }).catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(api.ApiError)
    expect((error as { status: number }).status).toBe(0)
    expect((error as { body?: unknown }).body).toBeUndefined()
    expect(ai.quizDiagnosticsFromError(error)).toBeUndefined()
  })
})
