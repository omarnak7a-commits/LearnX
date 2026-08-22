# AI Quiz Generation — Architecture

## The rule

**The system must understand what the PDF is teaching before it writes a single
question.**

Questions are never derived from sentences, headings, page numbers, or word
frequency. They are derived from a *semantic study map* of the document.

## Pipeline

```
PDF
 ↓  ai_documents.py            extract complete educational content
 ↓  quiz_boilerplate.py        strip headers/footers/legal/page furniture
 ↓  quiz_understanding.py      DOCUMENT UNDERSTANDING  ← the critical step
 ↓                             → DocumentUnderstanding (the study map)
 ↓  quiz_understanding.py      important concept selection (educational importance)
 ↓                             → knowledge relationships, learning objectives
 ↓  quiz_knowledge_targets.py  KNOWLEDGE TARGETS
 ↓  quiz_blueprints.py         QUIZ BLUEPRINT (the assessment plan)
 ↓  quiz_pipeline.py           large candidate pool (provider prose)
 ↓  quiz_deterministic.py        …or the provider-free study-map writer
 ↓  quiz_pipeline.py           validation against the study map (hard gates)
 ↓  quiz_pipeline.py           semantic deduplication (by knowledge target)
 ↓  quiz_scoring.py            eight-factor quality scoring
 ↓  quiz_scoring.py            cognitive diversity selection
 → final quiz (unchanged API response contract)
```

## Modules

| Module | Responsibility |
| --- | --- |
| `quiz_grounding.py` | Is this text really in the source? Is it a heading, layout trivia, or teaching prose? |
| `quiz_concepts.py` | Page splitting and the educational-content sufficiency check. |
| `quiz_boilerplate.py` | Deterministic boilerplate detection and source cleaning. |
| `quiz_understanding.py` | **The study map.** Subject, summary, topics, concepts, relationships, objectives — all grounded, all ranked by educational importance. |
| `quiz_knowledge_targets.py` | Converts concepts into testable knowledge targets, only where the source supports them. |
| `quiz_blueprints.py` | Plans the quiz: which concept, which target, which skill, which type. |
| `quiz_deterministic.py` | Writes questions from the study map when no provider is available. |
| `quiz_pipeline.py` | Orchestration, hard gates, deduplication, selection. |
| `quiz_scoring.py` | Quality scoring, diversity selection, answer randomization. |

## Importance is not frequency

`quiz_understanding.IMPORTANCE_WEIGHTS` contains **no frequency term**. A
concept is important because of:

- **knowledge type** — a mechanism or causal relationship outranks a bare fact
- **explanatory depth** — is it actually explained, and how thoroughly
- **centrality** — do other taught concepts depend on it
- **teaching emphasis** — is it flagged as important or tied to an objective
- **prerequisite role** — is it required to understand something else
- **topic spread** — is it developed across the document

Intrinsic signals (type, depth) carry 85% of the weight; structural signals
carry a bounded 15% bonus, so a short handout's central definition is not
penalised for lacking cross-references it structurally cannot have.

A term mentioned twenty times but never explained cannot outrank a mechanism
explained once. `ConceptNode.mention_count` exists only for diagnostics.

## Semantic deduplication

Two questions are duplicates when they test the same **knowledge target**,
regardless of wording. Identity is `concept_id::cognitive_skill`, so:

- "What is the function of mitochondria?"
- "Which role does the mitochondrion perform?"
- "Why are mitochondria important?"

are one question, not three. Selection then prefers *breadth*: an eight-question
quiz covers eight concepts whenever the document offers eight.

## Provider unavailability

There is no sentence-transformation fallback anywhere — the client-side
generator was deleted outright (see `src/lib/fileVault/textAnalysis.ts`).

When Gemini/Groq are unavailable the pipeline:

1. builds the study map deterministically from explanatory sentences only,
2. plans blueprints restricted to skills the deterministic writer can express
   honestly (never `application`, which would require inventing a scenario),
3. runs that prose through the **same** gates, deduplication, and scoring,
4. reports `provider="deterministic"` and `fallbackUsed=true` so the result is
   never passed off as provider-backed,
5. and raises `AIUnavailableError` if the result still cannot clear the bar.

Arabic has no deterministic writer by design: awkward machine-assembled Arabic
would be worse than an honest "unavailable".

## Traceability

Every final question carries a `QuestionProvenance`: `concept_id`,
`knowledge_target_id`, `cognitive_skill`, `knowledge_type`, `source_pages`,
`quality_score`, `blueprint_id`.

## Inspecting a real PDF

```bash
python backend/scripts/inspect_quiz.py public/demo-files/cell-biology-ch3.pdf --seed 7
```

Prints the document summary, main topics, important concepts (with their
importance signals), knowledge targets, quiz blueprint, and the selected
questions with full provenance.
