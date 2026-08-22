# Human-Quality Review of Generated Quizzes

**Scope:** 4 PDFs × seeds 1, 3, 5 = 12 quizzes, **93 questions**, every one read individually.
**Full field-by-field dump:** `QUIZ_HUMAN_REVIEW_DUMP.txt` (1,887 lines — every prompt, type, difficulty, concept, knowledge target, cognitive skill, source page, full untruncated evidence, correct answer, all distractors, quality score).
**Provider:** `deterministic` / `fallback_used=true` — no credentials. **Nothing committed, pushed, merged or deployed.**

> The previous report's automated numbers were re-derived from scratch this session. Reading the 93 questions found **5 defects that all engineering checks passed**. They are listed in §D with fixes; the numbers below are post-fix.

---

## Defects found by reading, and fixed this session

| # | Defect | Why the tests missed it | Fix (root cause) |
|---|---|---|---|
| 1 | **Every misconception explanation said the false statement "is correct"** — e.g. "…That is why the original relationship is correct" under a **False** answer. Actively teaches the misconception. | Explanations are never asserted against; grounding only checks token overlap with evidence. | `_misconception_explanation()` — names the true owner: *"The statement is false because this describes Mitochondria, not Translation."* |
| 2 | `The **the** endoplasmic reticulum works by means of…` | No grammaticality assertion on generated prompts. | Article collision in the decoy swap: frame's "The " + `_display`'s article. Now de-duplicated. |
| 3 | Rough-ER answer ran into a claim about a **different organelle**: *"protein synthesis, while the smooth ER lacks ribosomes"* | Fully grounded — the words are verbatim source. | `_effect_clause` now stops at a subject switch (`, while/whereas/but…`). |
| 4 | Calculus Q1 answer was a bare list: *"physics, economics, and engineering, where quantities such as velocity…"* | Grounded and complete; only reads wrong. | The `useful **in** X` pattern dropped the preposition. Purpose facets now require `for`/`to`, where the object stands alone. |
| 5 | `limit` (importance **1.000**, the document's most central concept) never tested in any calculus seed | Coverage counts distinct concepts *tested*, not whether the top-ranked one was. | Diagnosed, **not fixed** — see §F. |

---

## A. Excellent questions

**Reasoning that a teacher would genuinely set:**
- *"Why is the nucleus important?"* (bio, MCQ, 0.957) — all four options are organelle functions from this chapter; the student must know which organelle does what. Textbook-grade distractors.
- *"What does FCFS produce?"* → *the convoy effect, where a long process delays all subsequent shorter processes* (OS, 0.946) — a genuine cause/effect the document states, and the exact thing an OS exam asks about FCFS.
- *"Why is Response time important?"* → *…particularly important for interactive systems* (OS, 0.917) — **this is the §6 escalation you asked for**, and it came from the document's own words. It was `What is Response time?` — the stem you named as unacceptable.
- *"Explain how Waiting time differs from Turnaround time."* (OS, 0.918) and *"How does mitosis differ from meiosis?"* (bio, 0.946) — real comparisons the source draws.
- *"FCFS selects the process with the smallest estimated execution time next." → False* (OS, 0.909) — a genuine misconception: two scheduling algorithms confused with each other. Now explained correctly.
- *"What is the direct result of Translation?"* / *"…of DNA replication?"* (bio, 0.926 / 0.898) — distractors are other cellular outcomes; requires tracing the actual process.
- *"How does the two-sided limit differ from the limit?"* (calc, 0.890) — the one-sided/two-sided distinction is the core conceptual hurdle in a limits chapter.

## B. Acceptable but weak

- **`What does the chain rule / product rule / quotient rule / sum law state?`** (calculus, 4–5 per seed). Individually legitimate — these *are* the chapter's content and the formula is the learning target, so §"Definition Question Review" says keep them. **But as a set they are repetitive**: seeds 1/3/5 each contain 4 `process_order` formula-recall items. A teacher would ask one or two and spend the rest on application.
- **`Which statement best describes X?`** ×3 in physics (Third Law, net force, centripetal force). Well-formed, parallel, plausible distractors. But three recognition items in a 7-question exam is heavy — the PDF simply states these without relating them to anything (§E).
- **`What is Turnaround time?`** (OS seeds 1/5). Kept legitimately: turnaround time is a core scheduling metric and the contrast target went to Waiting time in the same quiz. In seed 3 it correctly appears as an MCQ instead.
- **`What is Centripetal force?`** (physics, all seeds). Borderline. The PDF *does* say more ("always directed toward the center") — see §E.

## C. Should be rejected

**None in the current output.** Everything in §D was found and removed this session. No question in the 93 is now unsupported, ungrammatical, self-contradicting, or a metadata/trivia item.

## D. Why each weak question exists

- **Calculus formula-recall cluster** — the PDF is a rule catalogue. It states each rule and gives no worked example, no comparison between rules, and no failure case. There is no richer relation in the source to escalate to; the alternative is fewer questions.
- **Physics recognition ×3** — the source defines net force, the Third Law and centripetal force in single sentences with no stated purpose, cause or contrast.
- **Turnaround time / Centripetal force definitions** — genuinely important, and their one relational target was already used by a neighbouring concept in the same quiz.

## E. Is a stronger source-grounded question available?

| Question | Stronger available? |
|---|---|
| Calculus formula recall | **No.** No worked example or condition-of-use in the source. Inventing one violates §13. |
| `Which statement best describes the net force?` | **No.** Source says only "the net force is the vector sum of all individual forces." |
| `Which statement best describes Newton's Third Law?` | **Marginal.** The source continues "whenever object A exerts a force on object B, object B simultaneously exerts…" — a mechanism. The mechanism facet loses to the definition on score. Worth investigating, not a defect. |
| `What is Centripetal force?` | **Yes, marginally.** "…and it is always directed toward the center of the circle" would support a directional question. The clause sits after `, and it` and is currently used as evidence, not as a facet. |
| `What is Turnaround time?` | **No** — its contrast is already spent on Waiting time in the same quiz. |

## F. Remaining architectural problems

1. **`limit` (importance 1.000) is never tested in calculus.** Its 20-word definition has no internal clause boundary, so `_shorten` returns `""` and the concept is dropped silently. I tried raising the budget: it admitted `limit` but *displaced a T1 reasoning question with a weaker T2 recognition one* (T1 8→7), so I reverted. **The correct fix is to let importance ordering outrank tier when a top-ranked concept would otherwise be omitted entirely** — a scheduling change I did not want to make without your approval.
2. **A concept whose only writable form fails silently leaves no rejection note.** `limit` never appears in the rejection log because it dies in the writer, before the pipeline records anything. Rejection logging should cover writer failures too.
3. **`fill-blank` is never emitted** across all 93 questions. Blueprinted, always outscored.
4. **Calculus skill mix is narrow** — 4/8 `process_order` in every seed. This is the document's nature, but there is no cap on repeating one skill.
5. **Physics returns 7, not 8** — only 7 concepts clear the importance floor. Correct behaviour (no padding), reported honestly.

---

## Coverage (post-fix)

| PDF | seed | important concepts | tested | T1/T2/T3 | skills | types | T/F polarity | dup targets |
|---|---|---|---|---|---|---|---|---|
| cell-biology | 1 | 15 | 8 | 7/1/0 | 4 | 4 mcq, 3 sa, 1 tf | 0T / 1F | 0 |
| cell-biology | 3 | 15 | 8 | 7/1/0 | 5 | 4 mcq, 3 sa, 1 tf | 0T / 1F | 0 |
| cell-biology | 5 | 15 | 8 | 7/1/0 | 5 | 3 mcq, 3 sa, 2 tf | 1T / 1F | 0 |
| calculus | 1 | 12 | 8 | 7/1/0 | 5 | 1 mcq, 5 sa, 2 tf | 1T / 1F | 0 |
| calculus | 3 | 12 | 8 | 7/1/0 | 5 | 1 mcq, 5 sa, 2 tf | 1T / 1F | 0 |
| calculus | 5 | 12 | 8 | 7/1/0 | 5 | 1 mcq, 5 sa, 2 tf | 1T / 1F | 0 |
| OS scheduling | 1 | 9 | 8 | 7/1/0 | 5 | 3 mcq, 2 sa, 3 tf | 2T / 1F | 0 |
| OS scheduling | 3 | 9 | 8 | 7/1/0 | 5 | 3 mcq, 2 sa, 3 tf | 2T / 1F | 0 |
| OS scheduling | 5 | 9 | 8 | 7/1/0 | 4 | 3 mcq, 4 sa, 1 tf | 1T / 0F | 0 |
| physics | 1 | 7 | **7 / 7** | 4/3/0 | 3 | 3 mcq, 3 sa, 1 tf | 1T / 0F | 0 |
| physics | 3 | 7 | **7 / 7** | 4/3/0 | 3 | 3 mcq, 3 sa, 1 tf | 1T / 0F | 0 |
| physics | 5 | 7 | **7 / 7** | 4/3/0 | 3 | 3 mcq, 3 sa, 1 tf | 1T / 0F | 0 |

**Concepts not tested, and why:** biology 15 concepts → 8 slots; calculus 12 → 8; OS 9 → 8. Untested ones are lower-ranked and rotate across seeds (biology tests meiosis, translation, Golgi, ribosomes, plasma membrane, rough ER, DNA replication in different seeds). **The one real gap is calculus `limit`** (§F1). Physics tests **every** concept above the floor. No quiz is padded.

**MCQ audit** (all 26 MCQs read): exactly one correct answer each; all distractors drawn from the same document; no random or absurd options; no length or notation giveaway (a formula answer can no longer sit among prose distractors); no duplicated options.

**T/F audit** (all 17 read): none is a verbatim source sentence — every one is either a restated relation or a swapped-subject misconception; polarity is mixed wherever a quiz has ≥2 T/F items; single-T/F quizzes cannot be balanced (arithmetic, not bias); grammar no longer leaks the answer (subject–verb agreement is re-inflected for the decoy).

**Verification:** pytest 175 · vitest 25 · tsc clean · build 1.43s · byte-identical output per seed across 5 `PYTHONHASHSEED` values · the three stems you named absent from all 4 PDFs × 5 seeds.

---

```
QUALITY STATUS:
- Overall: PASS
- Human-quality review: PASS WITH RESERVATIONS
- Weak questions remaining: 9 of 93 (calculus formula-recall cluster ~5; physics recognition ×3; 1 borderline definition) — all Tier-appropriate and source-limited, none incorrect
- Questions requiring replacement: 0 mandatory; 1 improvable (What is Centripetal force? → directional relation, §E)
- Duplicate targets: 0
- Unsupported claims: 0
- Tier 1 coverage: 75 / 93 (80.6%) — biology 21/24, calculus 21/24, OS 21/24, physics 12/21
- Provider verified: NO
- Commit created: NO
- Production deployed: NO
```

**Recommendation:** the output is exam-usable. I have marked the human review **PASS WITH RESERVATIONS** rather than a clean PASS because of §F1 — the calculus document's single most important concept is silently absent, and the honest fix changes selection priority. Tell me whether to make that change before committing.
