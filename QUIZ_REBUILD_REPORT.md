# LearnX AI Quiz Generation — Rebuild Report

**Branch:** `arena/01a00ba8-learnx` · **Baseline:** `a09e6e4` · **Status:** uncommitted (no commit/push/PR/deploy performed)
**Provider:** `deterministic` (`fallback_used=true`) — no credentials present, see §Provider

---

## A. Before / After

Every pair below was verified by regenerating the quiz, not by reading code.

| # | Before | After | Root cause fixed |
|---|--------|-------|------------------|
| 1 | `What is Response time?` | `Why is Response time important?` | Non-restrictive `, which` clause re-anchors to the main subject, so the document's own reason ("particularly important for interactive systems") became a purpose facet |
| 2 | `What is the cell?` | `Which statement best describes the cell?` + 7 reasoning questions | Concept now competes on tier, not on ease of generation |
| 3 | `What is the net force?` | `Which statement best describes the net force?` | Same |
| 4 | `Newton's First Law works by means of an unbalanced external force → True` (**inverts the law**) | dropped | "states that" negation exemption anchored at the quote marker |
| 5 | `The net force … is equal to the mass of the object → True` (**truncated into a falsehood**) | dropped | `_OPEN_RELATION` guard inside the walk-back branch |
| 6 | `How does the nucleus differ from cell?` (prokaryote answer) | dropped | Subject attribution (`_states_claim_about`) on graph-edge evidence |
| 7 | `The sum law works by means of lim x->a …` (not English) | `What does the sum law state?` | `_EQUATION` — notation counts as a proposition |
| 8 | `…differs from limit` / `…differs from the meiosis` | `…differs from the limit` / `…differs from meiosis` | Article read from the source, via the real concept name (casing was destroyed by the normalised clause) |
| 9 | Two questions asserting one fact (inertial mass / friction) | one retained | Claim-signature dedup at Jaccard ≥ 0.70 |
| 10 | `Translation result in …`, `The chain rule are responsible …` | `Translation results in …`, `The chain rule is responsible …` | Verb re-inflected for the swapped-in decoy subject |
| 11 | Answers ending `with respect`, `without necessarily ever`, `…f(x)/g(x) =`, `the operating system decides` | full clauses | `_shorten` no longer invents a boundary the source lacks; only real punctuation/conjunctions end a clause |
| 12 | Distractor `constant, the direction of velocity is continuously changing` | gone | Concept no longer named from inside a concessive clause |
| 13 | Distractor `between force, mass, and acceleration and is one of…` | gone | A predicate starting on a preposition with no finite verb is not a claim |
| 14 | Distractor `…where quantities such as velocity, marginal cost` | gone | Open `such as` enumeration detected as unfinished |
| 15 | `Centripetal force … , and it` (evidence truncated by page break) | full sentence | Sentences rejoined across page breaks; grounding verifies the join |
| 16 | **Every T/F answer `True`** in all 20 runs | balanced | Misconception targets were being deleted by clause-dedup |
| 17 | Then **every T/F answer `False`** | balanced | First-T/F tie-break so polarity settles on merit |

---

## B. Final question sets (seed 3)

### physics-newtonian-mechanics.pdf — 7 questions / 7 concepts
1. `short-answer` **What does Newton's Second Law state?** — *the net force acting on an object is equal to the mass of the object multiplied by its acceleration, expressed by the formula F = ma* · process_order · T1
2. `mcq` **Why does Friction matter?** — *opposes relative motion or the tendency toward relative motion between two surfaces in contact* · cause_effect · T1
3. `short-answer` **What is Centripetal force?** — *the net force required to keep an object moving in a circular path* · understanding · T2
4. `short-answer` **What does Newton's First Law state?** — *an object at rest stays at rest and an object in motion stays in motion … unless acted upon by an unbalanced external force* · process_order · T1
5. `mcq` **Which statement best describes Newton's Third Law?** — *for every action there is an equal and opposite reaction* · understanding · T2
6. `true-false` **The free body diagram is responsible for correctly applying Newton's Second Law…** → True · cause_effect · T1
7. `mcq` **Which statement best describes the net force?** — *the vector sum of all individual forces* · understanding · T2

### calculus-limits-derivatives.pdf — 8 questions / 8 concepts / T1 = 8
1. **Why is the derivative important?** · cause_effect
2. **What does L'Hopital's Rule state?** · process_order
3. **How does the two-sided limit differ from the limit?** · comparison
4. **Critical points are responsible for locating local maxima and local minima…** → True · cause_effect
5. **L'Hopital's Rule states that lim x->a [f(x) * g(x)] = …** → False · misconception
6. **What does the chain rule state?** · process_order
7. **What does the quotient rule state?** · process_order
8. **What does the sum law state?** · process_order

### cell-biology-ch3.pdf — 8 questions / 8 concepts / T1 = 7
Nucleus, Mitosis, cell, Meiosis, Transcription, DNA replication, nucleolus, Mitochondria — one question each, skills `cause_effect · comparison · misconception · process_order · understanding`.

### operating-systems-scheduling.pdf — 8 questions / 8 concepts / T1 = 7
Multilevel queue, FCFS convoy effect, Waiting vs Turnaround time, Turnaround time, **Why is Response time important?**, Shortest Job First, Round Robin, CPU scheduling.

---

## C. Coverage statistics (seed 3)

| document | Q | concepts | dup targets | T1 | T2 | T3 | skills |
|---|---|---|---|---|---|---|---|
| calculus-limits-derivatives | 8 | 8 / 8 | 0 | 8 | 0 | 0 | 4 |
| cell-biology-ch3 | 8 | 8 / 8 | 0 | 7 | 1 | 0 | 5 |
| operating-systems-scheduling | 8 | 8 / 8 | 0 | 7 | 1 | 0 | 5 |
| physics-newtonian-mechanics | 7 | 7 / 7 | 0 | 4 | 3 | 0 | 4 |

Every question maps to a distinct concept. **Zero duplicate targets, zero Tier-3 questions, zero unsupported claims** in all 20 seed runs.

## D. Rejection statistics (seed 3)

calculus 5 · biology 6 · OS 5 · physics 2. Representative reasons, all logged with stage and cause:

- `[validation] chain-rule/process_order — failed grounding/shape/type validation` (formula answer vs prose distractors, `distractor_quality 0.40 < 0.55`)
- `[diversity_selection] derivative/understanding — valid (score 0.95) but not selected: concept/skill already covered`
- `[diversity_selection] product-law/misconception — valid (score 0.88) but quiz full`

## E. Seed variation (1, 3, 5, 7, 11)

All 20 runs: full concept coverage, 0 duplicate targets, 0 Tier 3. Tier-1 counts stable per document (calculus 8/8/8/8/8; biology 7×5; OS 7×5; physics 4×5). Important concepts appear in every seed; variation is confined to comparably-scored candidates.

**Determinism:** same seed → byte-identical quiz, verified across 5 different `PYTHONHASHSEED` values on all four PDFs (1 variant each). Two real non-determinism bugs were found and fixed here:
- RNG draws happened only for non-skipped candidates, so set-iteration order changed the jitter sequence → jitter is now derived from `blake2b(seed, candidate.id)`.
- `max(set(types), …)` broke value ties by hash order, so `process` vs `cause_effect` (both 0.95) flipped between runs → stable final sort key.

## F. Test results

`pytest 175 passed` · `vitest 25 passed (3 files)` · `tsc --noEmit` clean · `vite build` ✓ 1.14s

> Note: `.venv` and `node_modules` are excluded from workspace snapshots and were missing at the start of this session. They were rebuilt before any of the numbers above were measured; an earlier "clean" fragment scan had silently passed because the interpreter was absent.

## G. Remaining weaknesses

1. **physics returns 7, not 8.** Honest under-supply, not padding.
2. **Inertial mass excluded at importance 0.583** (floor 0.60). It has a definition plus one correlative sentence; seven concepts genuinely outrank it.
3. **Three T2 "which statement best describes X" questions in physics.** The PDF defines centripetal force, net force and the Third Law without relating them to anything.
4. **`fill-blank` is never emitted.** Blueprinted but always loses; no §11-valid blank survives.
5. **Single-T/F quizzes cannot show polarity balance** (physics: 1 True; biology seeds 1/3: 1 False).

## H. Why each remaining weakness is unavoidable

1–2. Physics teaches 7 concepts above the floor. Forcing an 8th means either a second question on a covered concept or promoting a concept the document does not develop — both explicitly forbidden. The gap is reported, not filled.
3. Escalating these would require inventing a reason the PDF never states. Fix #1 shows the pipeline *does* escalate whenever the document supplies the reason.
4. A blank is only valid if the term is meaningful and its definition is not still visible. Where these PDFs define a term they define it in the same sentence, so every candidate blank is self-answering.
5. Arithmetic, not bias: one T/F question cannot be balanced. Where two or more exist, the split is 1–1 or 2–1.

---

## Provider

No `.env`; all provider keys empty. Every run reports `provider=deterministic, model=learnx-study-map-v1, fallback_used=true`. **The Gemini/Groq path was never executed and no claim is made about its output quality.** The deterministic path is source-grounded and passes all gates on its own.

## Preserved contracts

`AIProviderMetadata.provider` literal, `AIQuizQuestion` (`extra="forbid"`), route `backend/app/api/ai.py:297`, PDF viewer, auth, quiz runner, `src/lib/ai/apiClient.ts:15` — all untouched.

---

```
QUALITY STATUS:
- Overall: PASS
- Weak questions remaining: 3 (physics T2 recognition items — the source states no relationship for those concepts)
- Duplicate targets: 0
- Unsupported claims: 0
- Tier 1 coverage: 26 / 31 questions (calculus 8/8, biology 7/8, OS 7/8, physics 4/7)
- Provider verified: NO
- Commit created: NO
- Production deployed: NO
```
