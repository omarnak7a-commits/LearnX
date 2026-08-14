/**
 * Deterministic, extractive "AI" text-analysis engine.
 *
 * There is no LLM/backend call here — everything below is computed
 * directly from the real text extracted from the student's uploaded PDF
 * (see `pdfEngine.ts`) using classic, explainable NLP techniques:
 * sentence segmentation, stop-word-filtered term frequency, pattern-based
 * definition/formula detection, and frequency-weighted extractive
 * summarization. It is genuinely driven by file content — a different PDF
 * produces genuinely different output — while remaining fully client-side
 * and reproducible (a seeded PRNG, not `Math.random()`, drives any
 * question-distractor shuffling so results are stable per file).
 */

import type {
  FileAiAnalysis,
  FileDifficulty,
  FilePageText,
  VaultDefinition,
  VaultFlashcard,
  VaultMindMapNode,
  VaultQuizQuestion,
  VaultTimelineEntry,
} from '../../types/fileVault'

const STOPWORDS = new Set(
  (
    'a an the of to in and is are was were be been being for on with as by at from that this ' +
    'these those it its into or not no can may might will would should could shall must ' +
    'do does did has have had than then so such but if while when where which who whom whose ' +
    'what how why also because between within without about above below over under again ' +
    'further once here there all any both each few more most other some own same too very s t ' +
    'just don now i we you they he she him her his their our your my me us them'
  )
    .split(/\s+/)
    .filter(Boolean)
)

/** Generic academic scaffolding words that are too common across every document to be a
 * meaningful "key concept" even though they aren't grammatical stopwords. */
const GENERIC_ACADEMIC_WORDS = new Set([
  'defined',
  'define',
  'definition',
  'process',
  'review',
  'question',
  'questions',
  'chapter',
  'section',
  'summary',
  'example',
  'examples',
  'concept',
  'concepts',
  'topic',
  'topics',
  'exam',
  'tip',
  'student',
  'students',
  'following',
  'introduction',
])

/**
 * Deterministic PDF-boilerplate detector — the offline mirror of the backend
 * `quiz_boilerplate` layer. Copyright notices, legal/publisher text, ISBNs,
 * DOIs, URLs, e-mail addresses, page folios, and Arabic equivalents must
 * never become quiz questions, even when the backend is unreachable and the
 * local fallback engine generates the exam.
 */
const BOILERPLATE_SYMBOL_RE = /©|®|™|Ⓒ|ⓒ/
const BOILERPLATE_URL_RE = /https?:\/\/\S+|www\.\S+/i
const BOILERPLATE_EMAIL_RE = /\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/i
const BOILERPLATE_ISBN_RE = /\bisbn[:\s]*[\d\-x]{8,}\b/i
const BOILERPLATE_DOI_RE = /\b10\.\d{4,9}\/[-._;()/:a-z0-9]+\b/i
const BOILERPLATE_WORD_RES: RegExp[] = [
  /\bcopyright\b/i,
  /all rights reserved/i,
  /\btrademarks?\b/i,
  /\bregistered marks?\b/i,
  /\bisbn\b/i,
  /\bdoi\b/i,
  /\bissn\b/i,
  /\bpublish(ed|er|ers|ing|es)?\b/i,
  /\blicen[cs]e(d|ing)?\b/i,
  /\bpermission of\b/i,
  /\bterms of (use|service)\b/i,
  /\bprivacy policy\b/i,
  /\blegal notice\b/i,
  /\bunauthorized\b/i,
  /\bproprietary\b/i,
  /\bconfidential\b/i,
  /\bdo not (copy|distribute|sell)\b/i,
  /\bmay not be (reproduced|copied|distributed)\b/i,
  /\bno part of this\b/i,
  /\bpages?\s*\d+(\s*[-–]\s*\d+)?\b/i,
  /\bpage\s*\d+\s+of\s+\d+\b/i,
  /حقوق النشر|حقوق الطبع|جميع الحقوق محفوظ[ةه]|كل الحقوق محفوظ[ةه]|الطبع والنشر|دار النشر|الناشر|رقم الإيداع|رقم الايداع|ترخيص|علام[ةه] تجاري[ةه]/i,
]

/**
 * True when the text contains deterministic PDF-boilerplate markers.
 * Used both to clean source lines and to filter generated questions.
 */
export function isBoilerplateText(text: string): boolean {
  if (!text) return false
  if (BOILERPLATE_SYMBOL_RE.test(text)) return true
  if (BOILERPLATE_URL_RE.test(text) || BOILERPLATE_EMAIL_RE.test(text)) return true
  if (BOILERPLATE_ISBN_RE.test(text) || BOILERPLATE_DOI_RE.test(text)) return true
  return BOILERPLATE_WORD_RES.some((re) => re.test(text))
}

/** Line-level detection for source cleaning (stricter: only flags lines that ARE boilerplate). */
function isBoilerplateLine(line: string): boolean {
  const s = line.trim()
  if (!s || /^\W+$/.test(s)) return true
  if (BOILERPLATE_SYMBOL_RE.test(s) || BOILERPLATE_URL_RE.test(s) || BOILERPLATE_EMAIL_RE.test(s))
    return true
  if (
    BOILERPLATE_ISBN_RE.test(s) ||
    BOILERPLATE_DOI_RE.test(s) ||
    /\bissn[:\s]*\d{4}/i.test(s)
  )
    return true
  if (/^\d{1,5}$/.test(s)) return true
  if (/^(page|صفحة|صفحه)\s*\d+(\s+(of|من)\s*\d+)?$/i.test(s)) return true
  if (
    /all rights reserved|جميع الحقوق محفوظ|حقوق النشر|حقوق الطبع|may not be (reproduced|copied|distributed)|no part of this|do not (copy|distribute|sell)|unauthorized (use|reproduction)|trademarks? of/i.test(
      s
    )
  )
    return true
  if (
    /^(published by|publisher|printed (in|by)|printing|for more information|visit (us|our)|call us|terms of use|privacy policy|legal notice|copyright|©|®|™|confidential|proprietary|internal use only|دار النشر|الناشر|طبع|رقم الإيداع|رقم الايداع|إيداع|ايداع)/i.test(
      s
    )
  )
    return true
  return false
}

/** Digit-insensitive key for comparing the same header/footer line across pages. */
function lineKeyOf(line: string): string {
  return line.replace(/\d+/g, '#').replace(/\s+/g, ' ').trim().toLowerCase()
}

/**
 * Removes boilerplate lines from every page, then removes repeated
 * headers/footers: short lines that appear (digit-insensitively) on two or
 * more distinct pages, e.g. "Page 3 of 12" or a publisher's footer line.
 */
function stripRepeatedHeadersFooters(pages: FilePageText[]): FilePageText[] {
  const counts = new Map<string, number>()
  if (pages.length >= 2) {
    for (const page of pages) {
      const seen = new Set<string>()
      for (const line of page.text.split('\n')) {
        const key = lineKeyOf(line)
        if (key.length < 2 || seen.has(key)) continue
        seen.add(key)
        counts.set(key, (counts.get(key) ?? 0) + 1)
      }
    }
  }
  const repeated = new Set(
    [...counts.entries()].filter(([, count]) => count >= 2).map(([key]) => key)
  )
  return pages.map((page) => ({
    ...page,
    text: page.text
      .split('\n')
      .filter((line) => {
        if (isBoilerplateLine(line)) return false
        const key = lineKeyOf(line)
        if (key.length < 2) return false
        const words = line.trim().split(/\s+/).length
        if (repeated.has(key) && words <= 15) return false
        return true
      })
      .join('\n'),
  }))
}

function cleanPages(pages: FilePageText[]): FilePageText[] {
  return stripRepeatedHeadersFooters(pages)
}

/** True when ANY field of a generated question carries boilerplate. */
function isBoilerplateQuestion(q: VaultQuizQuestion): boolean {
  return (
    isBoilerplateText(q.prompt) ||
    isBoilerplateText(q.correctAnswer) ||
    isBoilerplateText(q.explanation) ||
    (q.options ?? []).some((option) => isBoilerplateText(option))
  )
}

/** Tiny seeded PRNG (mulberry32) so quiz distractor order is deterministic per file, not random each render. */
function seededRandom(seed: number): () => number {
  let a = seed >>> 0 || 1
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function hashString(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  return h
}

function splitSentences(text: string): string[] {
  return text
    .replace(/\s+/g, ' ')
    .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter((s) => s.length > 12)
}

/**
 * PDF text extraction concatenates a page's content with no paragraph or
 * line breaks preserved, so a section heading like "3.1 Introduction to
 * Cell Structure" runs directly into the following sentence ("The cell is
 * defined as..."). Left alone, that confuses both sentence splitting and
 * the definition-term regexes (which end up capturing the tail of the
 * heading as part of the "term"). Insert an explicit sentence boundary
 * right after every detected heading so downstream analysis treats each
 * heading as its own (short, filtered-out) sentence.
 */
const SENTENCE_STARTER_WORDS = new Set([
  'the',
  'a',
  'an',
  'this',
  'these',
  'those',
  'it',
  'in',
  'on',
  'at',
  'we',
  'you',
  'they',
  'each',
  'every',
  'many',
  'most',
  'some',
  'because',
  'when',
  'while',
  'if',
  'although',
  'students',
  'a\u00a0key',
])

/** Lowercase "glue" words that are allowed inside a heading (e.g. "Cell Structure and Function"). */
const HEADING_GLUE_WORDS = new Set(['and', 'or', 'of', 'to', 'in', 'for', 'the', 'a', 'an'])
const HEADING_INTERROGATIVE_WORDS = new Set(['what', 'why', 'how', 'when', 'where'])
const HEADING_COPULA_WORDS = new Set(['is', 'are'])

interface DetectedHeading {
  heading: string
  start: number
  end: number
}

/**
 * Walks the words following a "N.N " chapter-numbering marker and collects
 * a run of Title-Case words (allowing a few lowercase "glue" words like
 * "and"/"of"/"to") as the heading text, stopping as soon as it hits a
 * lowercase content word — which marks the start of the following
 * sentence. PDF text extraction concatenates a page with no paragraph
 * breaks, so a heading like "3.1 Introduction to Cell Structure" runs
 * directly into "The cell is defined as..." with no punctuation between
 * them; naive regexes end up swallowing "The" (itself capitalized, since
 * it starts a sentence) into the heading. This walker additionally trims
 * a single trailing common sentence-starter word (The/A/An/This/...) off
 * the collected heading, since that word almost always belongs to the
 * next sentence rather than the heading itself.
 */
function detectHeadings(text: string): DetectedHeading[] {
  const headings: DetectedHeading[] = []
  const markerPattern = /\d+\.\d+\s+/g
  let match: RegExpExecArray | null
  while ((match = markerPattern.exec(text)) !== null) {
    const markerStart = match.index
    let cursor = markerPattern.lastIndex
    const words: string[] = []
    const wordPattern = /\S+/g
    wordPattern.lastIndex = cursor
    let lastWordEnd = cursor
    let iterations = 0
    let sawInterrogative = false
    let sawContentWordAfterInterrogative = false
    while (iterations < 10) {
      wordPattern.lastIndex = cursor
      const wordMatch = wordPattern.exec(text)
      if (!wordMatch || wordMatch.index !== cursor) break
      const rawWord = wordMatch[0]
      const cleanWord = rawWord.replace(/[.,;:!?]+$/, '')
      const lower = cleanWord.toLowerCase()
      const isTitleCase = /^[A-Z][a-z'-]*$/.test(cleanWord) || /^[A-Z]+$/.test(cleanWord)
      const isGlue = HEADING_GLUE_WORDS.has(lower)
      // "What is a Process?" style headings: allow a leading interrogative
      // word, then its copula ("is"/"are") and article, until the first
      // real content (title-case) word is reached -- after that, revert to
      // strict mode so a *later* "is" (starting the next sentence, e.g.
      // "Process is defined as...") correctly terminates the heading.
      const isLeadingInterrogative = words.length === 0 && HEADING_INTERROGATIVE_WORDS.has(lower)
      const isCopulaAfterInterrogative =
        sawInterrogative && !sawContentWordAfterInterrogative && HEADING_COPULA_WORDS.has(lower)
      if (!isTitleCase && !isGlue && !isLeadingInterrogative && !isCopulaAfterInterrogative) break
      if (isLeadingInterrogative) sawInterrogative = true
      if (sawInterrogative && isTitleCase && !isLeadingInterrogative) {
        sawContentWordAfterInterrogative = true
      }
      // A title-case word that already appeared earlier in this same
      // heading run is a strong signal that the heading has ended and the
      // next sentence is restating one of its terms as its own subject
      // (e.g. heading "...Mitosis and Meiosis" followed by the sentence
      // "Mitosis is defined as..."). Stop before the repeat.
      if (isTitleCase && words.some((w) => w.toLowerCase() === lower)) {
        break
      }
      words.push(cleanWord)
      lastWordEnd = wordMatch.index + rawWord.length
      cursor = lastWordEnd + 1
      iterations++
      if (/[.!?]$/.test(rawWord)) break
    }
    // Drop a trailing common sentence-starter word — it belongs to the next sentence.
    while (words.length > 1 && SENTENCE_STARTER_WORDS.has(words[words.length - 1].toLowerCase())) {
      words.pop()
    }
    if (words.length >= 1) {
      const heading = `${text.slice(markerStart, match.index + match[0].length).trim()} ${words.join(' ')}`
      headings.push({ heading, start: markerStart, end: lastWordEnd })
    }
  }
  return headings
}

function normalizeHeadingBoundaries(text: string): string {
  const headings = detectHeadings(text)
  if (headings.length === 0) return text
  let result = ''
  let cursor = 0
  for (const h of headings) {
    result += text.slice(cursor, h.end)
    result += '. '
    cursor = h.end
    // Skip whitespace immediately following the heading in the source text.
    while (cursor < text.length && /\s/.test(text[cursor])) cursor++
  }
  result += text.slice(cursor)
  return result
}

function normalizePages(pages: FilePageText[]): FilePageText[] {
  return pages.map((p) => ({ ...p, text: normalizeHeadingBoundaries(p.text) }))
}

function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z][a-z'-]{2,}/g) ?? []).filter((w) => !STOPWORDS.has(w))
}

function termFrequencies(tokens: string[]): Map<string, number> {
  const freq = new Map<string, number>()
  for (const t of tokens) freq.set(t, (freq.get(t) ?? 0) + 1)
  return freq
}

/** Extracts candidate key phrases: the most frequent 2-3 word noun-ish n-grams, plus capitalized single terms. */
function extractKeyConcepts(pages: FilePageText[], limit = 10): string[] {
  const freq = new Map<string, number>()
  const properNounFreq = new Map<string, number>()

  for (const page of pages) {
    const words = page.text.split(/\s+/)
    for (let i = 0; i < words.length; i++) {
      const w = words[i].replace(/[^A-Za-z-]/g, '')
      if (
        w.length > 3 &&
        /^[A-Z][a-z-]+$/.test(w) &&
        !STOPWORDS.has(w.toLowerCase()) &&
        !GENERIC_ACADEMIC_WORDS.has(w.toLowerCase())
      ) {
        properNounFreq.set(w, (properNounFreq.get(w) ?? 0) + 1)
      }
    }
    const tokens = tokenize(page.text)
    for (let i = 0; i < tokens.length - 1; i++) {
      if (GENERIC_ACADEMIC_WORDS.has(tokens[i]) || GENERIC_ACADEMIC_WORDS.has(tokens[i + 1]))
        continue
      const bigram = `${tokens[i]} ${tokens[i + 1]}`
      freq.set(bigram, (freq.get(bigram) ?? 0) + 1)
    }
  }

  const bigramTop = [...freq.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([term]) => titleCase(term))

  const properTop = [...properNounFreq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([term]) => term)

  const merged = [...new Set([...bigramTop, ...properTop])].slice(0, limit)
  return merged.length > 0 ? merged : ['General Overview']
}

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase())
}

/** Finds "X is defined as Y." / "X refers to Y." style sentences and extracts (term, definition) pairs. */
/** Finds "X is defined as Y." / "X refers to Y." style sentences and extracts (term, definition) pairs. */
function extractDefinitions(pages: FilePageText[], limit = 8): VaultDefinition[] {
  const results: VaultDefinition[] = []
  const patterns = [
    /\b([A-Z][A-Za-z0-9 '-]{2,40}?)\s+is defined as\s+([^.]+\.)/g,
    /\b([A-Z][A-Za-z0-9 '-]{2,40}?)\s+are defined as\s+([^.]+\.)/g,
    /\b([A-Z][A-Za-z0-9 '-]{2,40}?)\s+refers to\s+([^.]+\.)/g,
  ]
  for (const page of pages) {
    for (const pattern of patterns) {
      pattern.lastIndex = 0
      let match: RegExpExecArray | null
      while ((match = pattern.exec(page.text)) !== null && results.length < limit * 2) {
        const term = match[1].trim().replace(/^(The|A|An)\s+/i, '')
        const definition = match[2].trim()
        if (term.length < 60 && term.length > 1 && definition.length > 10) {
          results.push({ term, definition, sourcePage: page.page })
        }
      }
    }
  }
  const seen = new Set<string>()
  const deduped = results.filter((d) => {
    const key = d.term.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  return deduped.slice(0, limit)
}

/** Finds formula-like lines: contain an '=' with surrounding alphanumeric/operator tokens. */
function extractFormulas(pages: FilePageText[], limit = 8): string[] {
  const results: string[] = []
  const pattern = /\b([A-Za-z0-9_]+(?:\s*[-+*/^]\s*[A-Za-z0-9_().]+)*\s*=\s*[^.;,]{2,40})/g
  for (const page of pages) {
    let match: RegExpExecArray | null
    pattern.lastIndex = 0
    while ((match = pattern.exec(page.text)) !== null && results.length < limit * 2) {
      const candidate = match[1].trim()
      // Filter out plain-English false positives ("is equal to" style noise) by requiring a digit or operator.
      if (/[0-9^*/+-]/.test(candidate) && candidate.length < 60) {
        results.push(candidate)
      }
    }
  }
  return [...new Set(results)].slice(0, limit)
}

/** Sentences that read like exam guidance ("exam tip", "frequently tested", "commonly asked"). */
function extractExamTips(sentences: string[], limit = 6): string[] {
  const markers =
    /exam tip|frequently tested|commonly (asked|tested)|key exam|on the exam|likely to (appear|be tested)/i
  return sentences.filter((s) => markers.test(s)).slice(0, limit)
}

/** Sentences that explicitly read as review/practice questions, or end with '?'. */
function extractQuestionsFromText(sentences: string[], limit = 8): string[] {
  const explicit = sentences.filter((s) => /review question[:.]?/i.test(s))
  const cleaned = explicit.map((s) => s.replace(/.*?review question[:.]?\s*/i, '').trim())
  const questionMarks = sentences.filter((s) => s.trim().endsWith('?'))
  return [...new Set([...cleaned, ...questionMarks])].slice(0, limit)
}

/** Sentences flagging conceptual difficulty ("difficult", "students struggle", "common misconception"). */
function extractDifficultTopics(sentences: string[], limit = 5): string[] {
  const markers =
    /difficult|struggle|misconception|frequently confused|hardest|challenging|commonly (misunderstood|confused)/i
  return sentences.filter((s) => markers.test(s)).slice(0, limit)
}

/** Section headings look like "3.1 Some Heading" or "1.2 Title Case Words" in our academic PDFs. */
function extractHeadingsWithPages(pages: FilePageText[]): Array<{ heading: string; page: number }> {
  const headings: Array<{ heading: string; page: number }> = []
  for (const page of pages) {
    for (const h of detectHeadings(page.text)) {
      headings.push({ heading: h.heading, page: page.page })
    }
  }
  return headings
}

/** Scores each sentence by sum of term frequency of its (non-stopword) tokens — classic extractive summarization. */
function scoreSentences(
  sentences: string[],
  freq: Map<string, number>
): Array<{ sentence: string; score: number }> {
  return sentences.map((sentence) => {
    const tokens = tokenize(sentence)
    const score =
      tokens.reduce((sum, t) => sum + (freq.get(t) ?? 0), 0) / Math.max(1, tokens.length)
    return { sentence, score }
  })
}

function estimateDifficulty(fullText: string, formulaCount: number): FileDifficulty {
  const sentences = splitSentences(fullText)
  const avgWordsPerSentence =
    sentences.reduce((sum, s) => sum + s.split(/\s+/).length, 0) / Math.max(1, sentences.length)
  const uniqueWords = new Set(tokenize(fullText)).size
  const totalWords = tokenize(fullText).length
  const lexicalDensity = totalWords > 0 ? uniqueWords / totalWords : 0

  let score = 0
  if (avgWordsPerSentence > 22) score += 1
  if (lexicalDensity > 0.45) score += 1
  if (formulaCount >= 3) score += 1
  if (avgWordsPerSentence > 28) score += 1

  if (score >= 3) return 'hard'
  if (score >= 1) return 'medium'
  return 'easy'
}

function buildMindMap(
  title: string,
  headings: Array<{ heading: string; page: number }>,
  keyConcepts: string[]
): VaultMindMapNode {
  const children: VaultMindMapNode[] = headings.slice(0, 8).map((h, i) => ({
    id: `mm-h-${i}`,
    label: h.heading,
    sourcePage: h.page,
    children: keyConcepts
      .slice(i, i + 2)
      .map((c, j) => ({ id: `mm-h-${i}-c-${j}`, label: c, children: [] })),
  }))
  return { id: 'mm-root', label: title, children }
}

function buildTimeline(
  headings: Array<{ heading: string; page: number }>,
  totalPages: number
): VaultTimelineEntry[] {
  if (headings.length === 0) {
    return [{ id: 'tl-0', label: 'Full document', startPage: 1, endPage: totalPages }]
  }
  return headings.map((h, i) => ({
    id: `tl-${i}`,
    label: h.heading,
    startPage: h.page,
    endPage: headings[i + 1]?.page ?? totalPages,
  }))
}

function buildFlashcards(
  definitions: VaultDefinition[],
  topSentences: Array<{ sentence: string; page: number }>,
  limit = 10
): VaultFlashcard[] {
  const fromDefs: VaultFlashcard[] = definitions.map((d, i) => ({
    id: `fc-def-${i}`,
    question: `What is ${d.term}?`,
    answer: d.definition,
    sourcePage: d.sourcePage,
    masteredLevel: 0,
  }))
  const remaining = Math.max(0, limit - fromDefs.length)
  const fromSentences: VaultFlashcard[] = topSentences.slice(0, remaining).map((s, i) => ({
    id: `fc-sent-${i}`,
    question: `Explain the concept described on page ${s.page}:`,
    answer: s.sentence,
    sourcePage: s.page,
    masteredLevel: 0,
  }))
  return [...fromDefs, ...fromSentences].slice(0, limit)
}

/** Attributes a sentence/definition to the page it was extracted from, for question sourcing. */
function sentencesWithPages(pages: FilePageText[]): Array<{ sentence: string; page: number }> {
  const result: Array<{ sentence: string; page: number }> = []
  for (const page of pages) {
    for (const s of splitSentences(page.text)) {
      result.push({ sentence: s, page: page.page })
    }
  }
  return result
}

/**
 * Generates quiz/exam questions ONLY from the provided page range — this
 * is what enforces "never generate questions from unread sections" and
 * "questions must come only from the uploaded PDF" from the spec.
 */
export function generateQuestions(
  rawPages: FilePageText[],
  allowedPages: Set<number>,
  seed: number,
  count = 8
): VaultQuizQuestion[] {
  // Boilerplate lines and repeated headers/footers are stripped BEFORE any
  // question is built, so copyright/legal/publisher text can never feed the
  // offline generator.
  const pages = cleanPages(normalizePages(rawPages))
  const scopedPages = pages.filter((p) => allowedPages.has(p.page))
  if (scopedPages.length === 0) return []

  const definitions = extractDefinitions(scopedPages, 12)
  const swp = sentencesWithPages(scopedPages)
  const rand = seededRandom(seed)
  const questions: VaultQuizQuestion[] = []

  // MCQ from definitions: correct answer = real definition, distractors = other real definitions from this doc.
  const allDefTexts = definitions.map((d) => d.definition)
  for (let i = 0; i < definitions.length && questions.length < count; i++) {
    const d = definitions[i]
    const distractorPool = allDefTexts.filter((t) => t !== d.definition)
    const distractors = shuffle(distractorPool, rand).slice(0, 3)
    if (distractors.length < 2) continue
    const options = shuffle([d.definition, ...distractors], rand)
    questions.push({
      id: `q-mcq-${i}`,
      type: 'mcq',
      prompt: `Which of the following best defines "${d.term}"?`,
      options,
      correctAnswer: d.definition,
      explanation: `"${d.term}" is defined as: ${d.definition}`,
      difficulty: 'medium',
      sourcePages: [d.sourcePage],
    })
  }

  // True/False from definitions: sometimes swap the term with another to create a false statement.
  for (let i = 0; i < definitions.length && questions.length < count; i++) {
    const d = definitions[i]
    const makeFalse = rand() > 0.5 && definitions.length > 1
    const swapWith = makeFalse ? definitions[(i + 1) % definitions.length] : null
    const statement = swapWith
      ? `${d.term} is defined as: ${swapWith.definition}`
      : `${d.term} is defined as: ${d.definition}`
    questions.push({
      id: `q-tf-${i}`,
      type: 'true-false',
      prompt: statement,
      options: ['True', 'False'],
      correctAnswer: swapWith ? 'False' : 'True',
      explanation: `The correct definition of "${d.term}" is: ${d.definition}`,
      difficulty: 'easy',
      sourcePages: [d.sourcePage],
    })
  }

  // Fill-in-the-blank: pick a key sentence, blank out its most frequent non-stopword term.
  const freq = termFrequencies(tokenize(scopedPages.map((p) => p.text).join(' ')))
  const scoredSentences = scoreSentences(
    swp.map((s) => s.sentence),
    freq
  )
    .map((s, i) => ({ ...s, page: swp[i].page }))
    .sort((a, b) => b.score - a.score)

  for (let i = 0; i < scoredSentences.length && questions.length < count; i++) {
    const { sentence, page } = scoredSentences[i]
    // Never blank out a boilerplate sentence (copyright footers etc.).
    if (isBoilerplateText(sentence)) continue
    const tokens = tokenize(sentence)
    if (tokens.length === 0) continue
    const target = [...tokens].sort((a, b) => (freq.get(b) ?? 0) - (freq.get(a) ?? 0))[0]
    if (!target || target.length < 4) continue
    const re = new RegExp(`\\b${escapeRegExp(target)}\\b`, 'i')
    if (!re.test(sentence)) continue
    const blanked = sentence.replace(re, '_____').slice(0, 220)
    questions.push({
      id: `q-fb-${i}`,
      type: 'fill-blank',
      prompt: blanked,
      correctAnswer: target,
      explanation: `The missing word is "${target}" — full sentence: ${sentence}`,
      difficulty: 'medium',
      sourcePages: [page],
    })
  }

  // Short answer: from explicit review-question sentences within the allowed pages.
  const questionSentences = swp.filter((s) => /review question[:.]?/i.test(s.sentence))
  for (let i = 0; i < questionSentences.length && questions.length < count; i++) {
    const cleaned = questionSentences[i].sentence.replace(/.*?review question[:.]?\s*/i, '').trim()
    questions.push({
      id: `q-sa-${i}`,
      type: 'short-answer',
      prompt: cleaned,
      correctAnswer: '(open-ended — reviewed manually or against the source material)',
      explanation: `This question is drawn directly from the review section on page ${questionSentences[i].page}.`,
      difficulty: 'hard',
      sourcePages: [questionSentences[i].page],
    })
  }

  // Final deterministic gate: any question that still carries boilerplate in
  // any field is dropped, mirroring the backend's scoring rejection.
  return questions.filter((q) => !isBoilerplateQuestion(q)).slice(0, count)
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function shuffle<T>(arr: T[], rand: () => number): T[] {
  const copy = [...arr]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

/**
 * Runs the full analysis pipeline against the real extracted text of a
 * document and produces every AI artifact the spec requires, generated
 * automatically (no button press) immediately after upload.
 */
export function analyzeDocument(
  _fileId: string,
  title: string,
  rawPages: FilePageText[]
): FileAiAnalysis {
  const pages = cleanPages(normalizePages(rawPages))
  const fullText = pages.map((p) => p.text).join('\n\n')
  const sentences = splitSentences(fullText)
  const freq = termFrequencies(tokenize(fullText))
  const scored = scoreSentences(sentences, freq).sort((a, b) => b.score - a.score)

  const keyConcepts = extractKeyConcepts(pages, 10)
  const definitions = extractDefinitions(pages, 8)
  const formulas = extractFormulas(pages, 8)
  const examTips = extractExamTips(sentences, 6)
  const importantQuestions = extractQuestionsFromText(sentences, 8)
  const difficultTopics = extractDifficultTopics(sentences, 5)
  const headings = extractHeadingsWithPages(pages)
  const difficulty = estimateDifficulty(fullText, formulas.length)

  const topSentenceTexts = scored.slice(0, 12).map((s) => s.sentence)
  const shortSummary =
    topSentenceTexts.slice(0, 3).join(' ') ||
    'No summary could be generated from this document yet.'
  const detailedSummary = topSentenceTexts.slice(0, 8).join(' ') || shortSummary
  const executiveSummary =
    `${title} covers ${headings.length > 0 ? headings.length : keyConcepts.length} main ` +
    `${headings.length > 0 ? 'sections' : 'topics'}, spanning ${pages.length} pages. ` +
    `Core focus areas include ${keyConcepts.slice(0, 3).join(', ') || 'general subject material'}.`

  const learningObjectives = keyConcepts
    .slice(0, 5)
    .map((c) => `Understand and explain the concept of ${c}.`)

  const revisionNotes = topSentenceTexts.slice(0, 10)

  const swp = sentencesWithPages(pages)
  const topWithPages = scored.slice(0, 12).map((s) => {
    const match = swp.find((x) => x.sentence === s.sentence)
    return { sentence: s.sentence, page: match?.page ?? 1 }
  })

  const flashcards = buildFlashcards(definitions, topWithPages, 10)
  const mindMap = buildMindMap(title, headings, keyConcepts)
  const timeline = buildTimeline(headings, pages.length || 1)

  const contentDensityScore = Math.min(
    100,
    Math.round(
      definitions.length * 8 +
        formulas.length * 6 +
        keyConcepts.length * 4 +
        importantQuestions.length * 5 +
        Math.min(pages.length, 10) * 2
    )
  )

  return {
    ready: true,
    executiveSummary,
    shortSummary,
    detailedSummary,
    keyConcepts,
    definitions,
    formulas,
    examTips:
      examTips.length > 0 ? examTips : ['No explicit exam guidance detected in this document.'],
    importantQuestions:
      importantQuestions.length > 0
        ? importantQuestions
        : keyConcepts.slice(0, 3).map((c) => `Explain the significance of ${c} in this material.`),
    learningObjectives,
    difficultTopics:
      difficultTopics.length > 0
        ? difficultTopics
        : [
            'No specific difficulty markers detected — pace your review evenly across all sections.',
          ],
    revisionNotes,
    flashcards,
    mindMap,
    timeline,
    difficulty,
    contentDensityScore,
  }
}

export {
  splitSentences,
  tokenize,
  extractKeyConcepts,
  sentencesWithPages,
  hashString,
  seededRandom,
  normalizeHeadingBoundaries,
  detectHeadings,
}
