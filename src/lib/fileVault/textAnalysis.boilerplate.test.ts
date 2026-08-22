/**
 * Regression tests for offline boilerplate filtering.
 *
 * The original production bug: a local offline quiz fallback generated
 * questions straight from PDF boilerplate, e.g.
 * "Copyright © 2020, _____ and/or its affiliates."
 *
 * That generator no longer exists — quizzes are built only by the backend,
 * which understands the document before writing anything. These tests pin:
 *   1. `isBoilerplateText` still flags boilerplate strings (EN + AR).
 *   2. `analyzeDocument` (summaries/concepts, not quizzes) stays clean.
 *   3. The client-side question generator stays deleted, so a future change
 *      cannot silently reintroduce the weak fallback.
 */

import { describe, expect, it } from 'vitest'
import type { FilePageText } from '../../types/fileVault'
import * as textAnalysis from './textAnalysis'
import { analyzeDocument, isBoilerplateText } from './textAnalysis'

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

describe('the weak client-side quiz generator stays removed', () => {
  it('does not export a client-side question generator', () => {
    // Requirement: a provider outage must never fall back to sentence
    // transformation. The strongest guarantee is that the function is gone.
    expect('generateQuestions' in textAnalysis).toBe(false)
  })

  it('exposes no other client-side quiz builder', () => {
    const quizLike = Object.keys(textAnalysis).filter((name) => /quiz|question/i.test(name))
    expect(quizLike).toEqual([])
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
