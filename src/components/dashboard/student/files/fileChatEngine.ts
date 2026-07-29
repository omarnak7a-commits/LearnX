import type { VaultFile } from '../../../../types/fileVault'

/**
 * Generates chat answers strictly from the real extracted text of this
 * PDF (`file.pagesText`) plus its computed analysis — never from
 * hardcoded canned responses. A different PDF produces genuinely
 * different, content-grounded answers.
 */
export function answerAboutFile(question: string, file: VaultFile): string {
  const lower = question.toLowerCase()
  const analysis = file.analysis
  if (!analysis) return "I'm still analyzing this document — check back in a moment."

  const topic = analysis.keyConcepts[0] ?? file.title
  const struggle = analysis.difficultTopics[0]

  if (lower.includes('summar')) {
    return analysis.shortSummary
  }
  if (lower.includes('explain')) {
    const target = findClosestConcept(question, analysis.keyConcepts) ?? topic
    const def = analysis.definitions.find((d) =>
      d.term.toLowerCase().includes(target.toLowerCase())
    )
    if (def) return `${def.term}: ${def.definition} (page ${def.sourcePage})`
    return `Here's what "${file.title}" covers about ${target}: ${analysis.detailedSummary.slice(0, 280)}`
  }
  if (lower.includes('important') || lower.includes('topic')) {
    return `The most important topics in this document are: ${analysis.keyConcepts.slice(0, 5).join(', ')}.`
  }
  if (lower.includes('exam') || lower.includes('question')) {
    return analysis.importantQuestions[0]
      ? `Based on this document, a likely exam question is: "${analysis.importantQuestions[0]}"`
      : `This document's key exam-relevant topics are: ${analysis.keyConcepts.slice(0, 3).join(', ')}.`
  }
  if (lower.includes('difficult') || lower.includes('hard') || lower.includes('struggle')) {
    return struggle
      ? `The most challenging part of this document is: ${struggle}`
      : `This document is rated ${analysis.difficulty} difficulty overall — no single topic stands out as unusually hard.`
  }
  if (lower.includes('definition') || lower.includes('define')) {
    const def = analysis.definitions[0]
    return def
      ? `${def.term}: ${def.definition}`
      : 'No explicit definitions were detected in this document.'
  }
  if (lower.includes('formula')) {
    return analysis.formulas.length > 0
      ? `Key formulas in this document: ${analysis.formulas.join('; ')}`
      : 'No formulas were detected in this document.'
  }

  // Fallback: find the most relevant real sentence from the extracted text.
  const relevant = findRelevantSentence(question, file)
  return relevant ?? analysis.executiveSummary
}

function findClosestConcept(question: string, concepts: string[]): string | null {
  const qWords = question.toLowerCase().split(/\W+/)
  let best: string | null = null
  let bestScore = 0
  for (const concept of concepts) {
    const conceptWords = concept.toLowerCase().split(/\W+/)
    const score = conceptWords.filter((w) => qWords.includes(w)).length
    if (score > bestScore) {
      bestScore = score
      best = concept
    }
  }
  return best
}

function findRelevantSentence(question: string, file: VaultFile): string | null {
  const qWords = new Set(question.toLowerCase().match(/[a-z]{4,}/g) ?? [])
  if (qWords.size === 0) return null
  let best: { sentence: string; score: number; page: number } | null = null
  for (const page of file.pagesText) {
    const sentences = page.text.split(/(?<=[.!?])\s+/)
    for (const sentence of sentences) {
      const words = sentence.toLowerCase().match(/[a-z]{4,}/g) ?? []
      const score = words.filter((w) => qWords.has(w)).length
      if (score > 0 && (!best || score > best.score)) {
        best = { sentence, score, page: page.page }
      }
    }
  }
  return best ? `${best.sentence.trim()} (page ${best.page})` : null
}
