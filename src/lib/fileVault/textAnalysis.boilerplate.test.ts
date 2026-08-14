/**
 * Regression tests for offline boilerplate filtering.
 *
 * The production bug: the local offline quiz fallback could generate
 * questions straight from PDF boilerplate, e.g.
 * "Copyright © 2020, _____ and/or its affiliates."
 *
 * These tests pin the deterministic filters in `textAnalysis.ts`:
 *   1. `isBoilerplateText` flags boilerplate strings (EN + AR).
 *   2. Repeated headers/footers and boilerplate lines are stripped before
 *      question generation.
 *   3. No generated question may carry boilerplate in ANY field.
 *   4. Real educational content still produces questions.
 */

import { describe, expect, it } from 'vitest'
import type { FilePageText } from '../../types/fileVault'
import { analyzeDocument, generateQuestions, isBoilerplateText } from './textAnalysis'

const FOOTER = 'Copyright © 2020, Oracle and/or its affiliates. All rights reserved.'

function page(n: number, text: string): FilePageText {
  return { page: n, text, wordCount: text.split(/\s+/).length }
}

const BIO = [
  page(
    1,
    '1.1 Introduction to Photosynthesis\nPhotosynthesis is defined as the process by which green plants convert light energy into chemical energy.\n'
  ),
  page(
    2,
    '2.1 The Light Reactions\nThe light reactions are defined as the stage in which chlorophyll absorbs light energy and splits water molecules.\n'
  ),
  page(
    3,
    '3.1 The Calvin Cycle\nThe Calvin cycle is defined as the set of reactions that fix carbon dioxide into glucose.\n'
  ),
]

function withFooters(pages: FilePageText[]): FilePageText[] {
  return pages.map((p) => ({
    ...p,
    text: `Oracle Database Documentation\n${p.text}${FOOTER}\nPage ${p.page} of ${pages.length}\n`,
  }))
}

function anyBoilerplateField(q: {
  prompt: string
  correctAnswer: string
  explanation: string
  options?: string[]
}): boolean {
  return (
    isBoilerplateText(q.prompt) ||
    isBoilerplateText(q.correctAnswer) ||
    isBoilerplateText(q.explanation) ||
    (q.options ?? []).some((o) => isBoilerplateText(o))
  )
}

describe('isBoilerplateText', () => {
  it('flags the exact production bug string', () => {
    expect(isBoilerplateText('Copyright © 2020, _____ and/or its affiliates.')).toBe(true)
    expect(isBoilerplateText(FOOTER)).toBe(true)
  })

  it('flags legal/publisher/metadata markers', () => {
    expect(isBoilerplateText('All rights reserved.')).toBe(true)
    expect(isBoilerplateText('ISBN 978-0-12-345678-9')).toBe(true)
    expect(isBoilerplateText('Visit https://example.com/docs for more information.')).toBe(true)
    expect(isBoilerplateText('Contact support@example.com for help.')).toBe(true)
    expect(isBoilerplateText('Published by Oxford University Press.')).toBe(true)
    expect(isBoilerplateText('Page 3 of 12')).toBe(true)
  })

  it('flags Arabic legal boilerplate', () => {
    expect(isBoilerplateText('جميع الحقوق محفوظة للناشر')).toBe(true)
    expect(isBoilerplateText('حقوق الطبع والنشر محفوظة لدار النشر')).toBe(true)
  })

  it('does not flag educational content', () => {
    expect(
      isBoilerplateText('Photosynthesis converts light energy into chemical energy.')
    ).toBe(false)
    expect(isBoilerplateText('The cell membrane is selectively permeable.')).toBe(false)
    // "do not reproduce" is legitimate biology, not a legal notice.
    expect(isBoilerplateText('Bacteria do not reproduce by mitosis.')).toBe(false)
  })
})

describe('generateQuestions boilerplate filtering', () => {
  it('never generates questions from a document that is only boilerplate', () => {
    const pages = [page(1, FOOTER), page(2, `${FOOTER}\nAll rights reserved.`)]
    const questions = generateQuestions(pages, new Set([1, 2]), 7, 8)
    expect(questions).toHaveLength(0)
  })

  it('repeated headers/footers do not leak into questions', () => {
    const allowed = new Set([1, 2, 3])
    const questions = generateQuestions(withFooters(BIO), allowed, 42, 8)
    expect(questions.length).toBeGreaterThan(0)
    for (const q of questions) {
      expect(anyBoilerplateField(q)).toBe(false)
    }
    const joined = questions
      .map((q) => `${q.prompt} ${q.correctAnswer} ${q.explanation} ${(q.options ?? []).join(' ')}`)
      .join(' | ')
    expect(joined.toLowerCase()).not.toContain('copyright')
    expect(joined).not.toContain('Oracle')
    expect(joined).not.toContain('©')
  })

  it('still generates questions from the real educational content', () => {
    const allowed = new Set([1, 2, 3])
    const questions = generateQuestions(withFooters(BIO), allowed, 42, 8)
    const joined = questions.map((q) => `${q.prompt} ${q.explanation}`).join(' | ')
    expect(/photosynthesis|calvin|light reactions/i.test(joined)).toBe(true)
  })

  it('preserves educational content when pdf.js flattened a footer into the same line', () => {
    // This reproduces the production failure exactly. extractPdf previously
    // joined every text item with a space, so each page was one physical line.
    // One © marker then caused source cleaning to discard the entire page.
    const flattened = BIO.map((p) =>
      page(p.page, `${p.text.replace(/\n/g, ' ')} ${FOOTER} Page ${p.page} of ${BIO.length}`)
    )
    const questions = generateQuestions(flattened, new Set([1, 2, 3]), 5, 8)
    expect(questions.length).toBeGreaterThan(0)
    expect(questions.some((q) => /photosynthesis|calvin|chlorophyll/i.test(q.prompt))).toBe(true)
    for (const q of questions) expect(anyBoilerplateField(q)).toBe(false)
  })

  it('a footer sentence is never used as a fill-in-the-blank', () => {
    const pages = [
      page(1, `${BIO[0].text}${FOOTER}`),
      page(2, `${BIO[1].text}${FOOTER}`),
    ]
    const questions = generateQuestions(pages, new Set([1, 2]), 5, 8)
    for (const q of questions) {
      expect(anyBoilerplateField(q)).toBe(false)
      if (q.type === 'fill-blank') {
        expect(q.prompt).not.toContain('©')
        expect(q.prompt.toLowerCase()).not.toContain('copyright')
      }
    }
  })

  it('short but meaningful educational text still generates a question', () => {
    const pages = [page(1, 'Mitosis produces two genetically identical daughter cells.')]
    const questions = generateQuestions(pages, new Set([1]), 9, 6)
    expect(questions.length).toBeGreaterThan(0)
    expect(questions[0].prompt).toContain('_____')
  })

  it('metadata-only pages are rejected', () => {
    const pages = [page(1, `${FOOTER}\nOxford University Press\nThird Edition\nISBN 978-0-12-345678-9`)]
    expect(generateQuestions(pages, new Set([1]), 4, 6)).toEqual([])
  })

  it('does not return repeated or near-identical prompts', () => {
    const questions = generateQuestions(BIO, new Set([1, 2, 3]), 42, 20)
    const normalized = questions.map((q) => q.prompt.toLowerCase().replace(/\W+/g, ' ').trim())
    expect(new Set(normalized).size).toBe(questions.length)
  })
})

describe('analyzeDocument boilerplate filtering', () => {
  it('boilerplate never becomes key concepts or summaries', () => {
    const analysis = analyzeDocument('file-1', 'Biology Chapter', withFooters(BIO))
    const concepts = analysis.keyConcepts.join(' | ')
    expect(concepts).not.toContain('Oracle')
    expect(concepts.toLowerCase()).not.toContain('copyright')
    expect(analysis.executiveSummary).not.toContain('Oracle')
    expect(analysis.executiveSummary).not.toContain('©')
  })
})
