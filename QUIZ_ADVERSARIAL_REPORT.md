# Adversarial Educational-Quality Pass — Final Report

**Nothing committed, pushed, merged, PR'd or deployed.**
Artifacts: `QUIZ_ADVERSARIAL_SCAN.txt` (machine scan, 155 questions), `QUIZ_HUMAN_REVIEW_DUMP.txt` (1,921 lines, every field of every question).

---

## L. Provider status — checked FIRST (§16)

```
.env / .env.local        : absent
settings.gemini_api_key  : EMPTY
settings.groq_api_key    : EMPTY
GEMINI_*/GROQ_* in env   : none
every run reports        : provider=deterministic  fallback_used=True
```

**The provider path is UNVERIFIED. Every result below is deterministic-path only.** No provider claim is made anywhere in this report.

---

## A. Root causes found

This pass built an automated scanner (`backend/scripts/adversarial_scan.py`) that encodes §6–§15 as predicates over every question of every seed, then read the output. Six real root causes surfaced — **five of them invisible to the demo PDFs**, found only by running the pipeline on subjects it had never seen.

| # | Defect observed | Earliest incorrect decision |
|---|---|---|
| 1 | `limit` (importance **1.000**, calculus) never tested in any seed | `_other_subject_intervenes` searched `[mention_end, match_start)`. The condition-facet pattern fires *on the rival subject's own verb* (`continuity **requires**`), so the window ended one word short and continuity's claim was credited to `limit`. The bogus facet then produced no writable question. |
| 2 | Same concept then still absent | `_DANGLING_TAIL` listed `it`. A pronoun **object** legitimately ends a clause ("…without ever reaching **it**"), so the whole 20-word definition was discarded as a fragment. |
| 3 | `"Nationalism differs"`, `"Erosion differs"` as concept names (History, Geography) | `_PREDICATE_STOP` is a hand-written verb inventory. Every unseen document brings verbs it lacks (`differs`, `concerns`, `dissociates`), and the verb was absorbed into the name. |
| 4 | `"How does Erosion differ from **the deposition adds it**?"` | The comparison-partner guard used `_FINITE_VERB`, another inventory, which misses unseen verbs. A clause was accepted as a concept name. |
| 5 | `"What is the assassination of Archduke Franz?"` → answer began `"Ferdinand in June 1914…"` | `_SUBJECT_HEAD` capped the subject span at 4 tokens, cutting a proper name in half and leaking its tail into the answer. |
| 6 | `"The alliance system is responsible for **bound** the major powers…"` | Relation frames end in a preposition, so the clause must be a noun phrase. A bare infinitive/past verb was inserted unchecked. |

## B. Fixes made — all at the earliest decision, none a blacklist

1. **`_other_subject_intervenes`** — widened the guard to see a rival subject whose verb *is* the match. Kills cross-subject attribution generally.
2. **`_DANGLING_TAIL`** — removed `it`/`this`/`these`; a stranded pronoun *subject* is still caught by the finite-verb tests.
3. **`_looks_like_finite_verb` + `_COMPLEMENT_OPENER`** — morphological predicate detection replacing inventory lookup. A `-s`/`-ed` token ends the name only when what follows opens a complement, so `"Related rates problems"` survives while `"Nationalism differs"` is cut.
4. **`_is_noun_phrase`** — a multi-word comparison partner carrying a verb or participle is rejected as a name.
5. **`_SUBJECT_HEAD` 4 → 5 tokens** — deliberately *not* 6: at 6 an overview sentence yields a catch-all concept ("Newton's three laws of motion") that duplicates the laws it summarises, and that regression produced a **false claim** (`"Centripetal force is responsible for correctly applying Newton's Second Law"` — the free body diagram's property). Caught by re-running the scan after the change.
6. **`_opens_with_bare_verb`** — declines a relation frame whose clause is a bare infinitive; mirrored into `writable_question_types` so the planner never commits a slot the writer will drop.
7. **`_is_sole_opportunity`** — coverage concession for §4: the wider answer budget applies **only** to a top-quartile concept with no relational facet, i.e. one that would otherwise be absent from its own exam. Applying it broadly cost T1 coverage (7→6 in three documents); scoping it recovered biology and OS to T1=7.
8. **`_NEEDS_A_COMPLEMENT` in `_shorten`** — a transitive verb with no object ("the operating system decides") can no longer end an answer.
9. **Removed `^(?:mitosis|meiosis)$`** from `_EVENT_LIKE` (§1 hardcoding). The generic `sis$` suffix already matched both, so the alternation added nothing but a biology dependency.

**Two changes were made and then reverted**, because measurement showed they made the product worse:
- Rephrasing the short-answer definition stem to `"Define X."` — cascaded into a classifier change that broke a deliberate design decision (`"What is photosynthesis?" → factual_recall`) and produced **zero questions** on small documents.
- Applying the wide answer budget unconditionally — displaced T1 reasoning questions with T2 recognition ones.

## C. Before / after

| Before | After |
|---|---|
| `The nationalism differs are caused by Britain had guaranteed Belgian neutrality.` | *(not generated)* |
| `How does Erosion differ from the deposition adds it?` | *(not generated)* |
| `What is the assassination of Archduke Franz?` → `"Ferdinand in June 1914 triggered…"` | `assassination of Archduke Franz Ferdinand` is one concept; the fragment is gone |
| `The alliance system is responsible for bound the major European powers…` | *(declined; slot goes to a writable target)* |
| `Militarism works by means of maintain a strong military.` | *(declined)* |
| calculus `limit` (importance 1.000) — absent from all 5 seeds | `Which statement best describes the limit?` with three confusable distractors (one-sided limit, direct substitution, critical points) |
| physics `Centripetal force is responsible for correctly applying Newton's Second Law` (**false** — that is the free body diagram) | caught by re-scan, cause reverted |

## D–H. Final state (4 PDFs × seeds 1/3/5/7/11 = 155 questions)

| PDF | Q | concepts | dup targets | T1 | T2 | T3 | skills |
|---|---|---|---|---|---|---|---|
| calculus-limits-derivatives | 8 | 8/8 | 0 | 6 | 2 | 0 | 5 |
| cell-biology-ch3 | 8 | 8/8 | 0 | 7 | 1 | 0 | 4–5 |
| operating-systems-scheduling | 8 | 8/8 | 0 | 7 | 1 | 0 | 4–5 |
| physics-newtonian-mechanics | 7 | **7/7** | 0 | 4 | 3 | 0 | 3–4 |

- **Tier 3: 0** across all 155. **Duplicate targets: 0. Unsupported claims: 0.**
- **Cognitive skills:** `cause_effect`, `comparison`, `process_order`, `understanding`, `misconception` — up to 5 per quiz.
- **T/F polarity:** mixed in every quiz with ≥2 T/F items. Single-T/F quizzes cannot be balanced (arithmetic).
- **Physics returns 7, not 8** — only 7 concepts clear the importance floor. Not padded (§4/§14).

## I. Seed variation & determinism

- Same seed → **byte-identical** quiz across 5 different `PYTHONHASHSEED` values, all 4 PDFs.
- Distinct quizzes across seeds 1/3/5/7/11: biology 5/5, OS 4/5, calculus 3/5, physics 3/5. Important concepts stay stable; variation is confined to comparably-scored candidates.

## J. Automated results

`pytest 181 passed` (175 + 6 new regression tests) · `vitest 25` · `tsc` clean · `build` 1.15s
`adversarial_scan`: **155 questions, 0 defects, 0 warnings.**

## K. Human review

Every question of seeds 1/3/5 read in `QUIZ_HUMAN_REVIEW_DUMP.txt`, plus generated quizzes for **History, Chemistry, Literature and Geography** — subjects with no demo PDF, which is where five of the six root causes surfaced. Cross-domain output is now grammatical and correctly attributed.

## M. Remaining limitations

1. **`What is the net force?` still appears in 6 of 155 runs** (physics seeds 1/5/7/11). The source states only `"the net force is the vector sum of all individual forces"` — no purpose, cause or contrast, so there is nothing to escalate to (§3 permits a clean recognition question here). The remaining objection is the *stem wording*. I attempted a rephrase and reverted it: see §B. **This is the product-level decision below.**
2. **`fill-blank` is never emitted** — blueprinted, always outscored.
3. **Calculus skews to formula recall** (`What does the chain rule state?` ×4). The chapter is a rule catalogue with no worked examples; §5 forbids inventing application scenarios.
4. **Physics is 3 T2 recognition items of 7** — those concepts are defined in single sentences with no stated relation.
5. **Provider path unverified** (§16).

## N. Files changed

`quiz_understanding.py`, `quiz_deterministic.py`, `quiz_scoring.py`, `quiz_grounding.py`, `quiz_knowledge_targets.py`, `quiz_blueprints.py`, `quiz_pipeline.py`
New: `backend/tests/test_quiz_regression_cases.py`, `backend/scripts/adversarial_scan.py`, `backend/scripts/review_quiz.py`

## O. Ready for commit?

**Not yet — one product decision is required.**

Everything mechanical is clean: 0 defects across 155 questions, 0 Tier 3, 0 duplicate targets, 0 unsupported claims, deterministic, no domain hardcoding, no silent candidate loss, cross-domain verified, provider limitation disclosed.

**The decision:** `"What is the net force?"` is a stem you named as unacceptable, but the physics PDF supports nothing richer for that concept, and your §3/§12 guidance says a clean recognition question is acceptable when a document only defines a concept. So the question is purely how the stem should read. Options:

- **(a) Accept it.** It is honest, grounded, and about a genuinely central concept.
- **(b) Rephrase the short-answer understanding stem** (e.g. `"Define X."` / `"State what X means."`). I tried `"Define X."`; it requires reclassifying `define`/`what is` as `understanding`, which contradicts an existing deliberate test (`"What is photosynthesis?" → factual_recall`) and returned zero questions on small documents. Doable, but it means changing that design decision on purpose.
- **(c) Force the concept to short-answer only when an MCQ form exists** — the MCQ variant already reads well (`"Which statement best describes the net force?"`, seed 3) and appears in some seeds already.

Tell me which and I will implement it. **No commit until you approve.**

```
QUALITY STATUS:
- Overall: PASS (mechanical)
- Human-quality review: PASS WITH ONE OPEN DECISION
- Weak questions remaining: 6 / 155 ("What is the net force?" — source supports no richer target)
- Questions requiring replacement: 0 mandatory; 6 pending the stem decision above
- Duplicate targets: 0
- Unsupported claims: 0
- Tier 1 coverage: 24 / 31 per seed-3 set (calculus 6/8, biology 7/8, OS 7/8, physics 4/7)
- Provider verified: NO
- Commit created: NO
- Production deployed: NO
```
