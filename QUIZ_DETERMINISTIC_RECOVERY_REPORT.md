# Deterministic Fallback Recovery — Production Incident 075eb4af… (6-of-8 → 8-of-8)

**Status:** implemented and verified (backend 568 ✓, frontend 108 ✓, `tsc --noEmit` ✓, `vite build` ✓). No PR opened until verification completed.

## The production failure

`learnxDiagnoseExam("075eb4af-5813-41d0-9602-23065c1e4ddf", 8)` returned **HTTP 422** because the deterministic fallback produced **6 of 8** questions after the AI provider failed completely:

| Funnel counter | Value |
|---|---|
| provider_errors | 2 (understanding + writer), zero provider candidates, understanding_source=deterministic |
| deterministic_targets_writable | 10 |
| deterministic_candidates_attempted / returned / dropped | 14 / 6 / 8 |
| drop reasons | facet_answer_unavailable=2, no_answer_claim=4, false_statement_not_constructible=2 |
| grounding / quality / validation | 6 / 6 / 6 passed — **zero** gate rejections |
| plans / attempted / created / skipped | 22 / 22 / 8 / 14 (all skipped = duplicate_objective) |
| concepts / evidence_items / relationships | 12 / 15 / 3 |
| PDF | 32 pages, text_pages=30, image_only_pages=2, pages_dropped_in_cleaning=0 |
| final quiz | 6 deterministic: mcq=4, short-answer=1, fill-blank=1 |

## Root cause (Phase 1)

Three drop categories, each reproduced in isolation on HEAD (commit `22df029`):

1. **`false_statement_not_constructible` (2 in production)** — the misconception true/false writer calls `_true_statement`, which **refuses any base statement that is verbatim-equal to its evidence**. For evidence shaped like *"The X is responsible for Y"*, the facet frame produces exactly the evidence sentence, so `_true_statement` returned `None` and the misconception slot was dropped — even though the writer's very next step is to swap a *different* taught concept into that frame, which yields a genuinely different, false claim ("The query optimizer is responsible for caching frequently accessed pages."). The refusal was correct for a **true** question (the answer would be readable off the evidence) but wrong for the misconception path.

2. **`facet_answer_unavailable` (2)** — a facet clause too short to frame (2-word clause) and with no recoverable claim from the evidence tail. The planner's syntactic veto (`target_writable_types`) declared the target writable; the writer then dropped it mid-run.

3. **`no_answer_claim` (4)** — contentless claims ("…exists in two forms.") or concept names absent from the evidence. Same planner/writer disagreement.

**Why 6-of-8 instead of recovery:** the planner had already committed slots to all constructible-looking objectives (14 `duplicate_objective` skips), so once the writer dropped 8 slots the top-up rounds had no fresh objective to plan — the shortfall was permanent even though the document supported 8 defensible questions.

## The fix (smallest safe change)

Three coordinated edits — no gate is weakened, nothing is fabricated, and every new candidate passes the identical grounding / quality-judge / scoring / dedupe / final-validation path as before.

### 1. `backend/app/services/quiz_deterministic.py` — misconception writer may request the verbatim base (`allow_verbatim`)

- `_true_statement(blueprint, *, allow_verbatim: bool = False)`: the verbatim-vs-evidence refusal is now conditional. The **true** path still refuses verbatim statements (unchanged behavior).
- `_false_statement` calls `_true_statement(..., allow_verbatim=True)`: the base may be the evidence frame because the very next step swaps in a different taught concept, producing a distinct false claim. `_meaningful_true_false` and all downstream gates still apply — verified the swapped claim passes them.

### 2. `backend/app/services/quiz_deterministic.py` — writer-backed planning veto

- `writer_writable_types(target, allowed_types, *, understanding)`: runs the writer's own `_candidate_for` decision per syntactically-allowed type, so the planner only commits slots the writer can actually produce. This eliminates the `facet_answer_unavailable` / `no_answer_claim` waste at the source and stops `false_statement_not_constructible` slots from being planned for non-recoverable shapes (2-word clauses, contentless claims).
- MCQ is deliberately handled by the existing re-planner: `replan_unsafe_mcq_blueprints` already converts too-few-distractor MCQs to a safe selected type (short-answer first) before the writer runs, so an MCQ slot is never lost. Vetoing MCQ at plan time would push recognition targets to fill-blank, which then collides with the factual-recall fill-blank of the same concept in the (unchanged) near-duplicate gate. Only when the MCQ is the *only* approved type and the writer cannot build it is the whole target excluded.
- `writer_type_veto(understanding)`: memoised planner `type_filter` built on `writer_writable_types`.
- `replan_unsafe_mcq_blueprints` now uses `writer_writable_types` so its replacement selection agrees with the veto.

### 3. `backend/app/services/quiz_pipeline.py` — both deterministic planning sites use the veto

- The deterministic supplement in `generate_quiz` and every top-up round in `_top_up_candidates` now plan through `writer_veto = writer_type_veto(understanding)` (both the `build_question_blueprints` call and the diagnostics-only `_account_plan_skips` call), so planned slots and accounting agree.

## Verification

### Production-shaped regression fixture (2 concepts, "X is responsible for Y")

| Metric | HEAD (before) | After fix |
|---|---|---|
| Result | **422 available=6** | **200 with 8 questions** |
| deterministic candidates attempted | 10 | 8 |
| returned / dropped | 6 / 4 | 8 / 0 |
| drop reasons | false_statement_not_constructible=4 | {} |
| plans_skipped | 20 (duplicate_objective=14, application=6) | 2 (application=2) |
| final types | short-answer=4, fill-blank=2 | short-answer=4, true-false=2, fill-blank=2 |
| top-up | no_new_objectives → planner_returned_no_blueprints | pool_sufficient |
| provider_errors | 2 | 2 |

The 2 recovered questions are the misconception true/false pair — the same drop category as production (`false_statement_not_constructible`). The fixture reproduces the production funnel shape including **14 duplicate_objective skips** and **provider_errors=2** at HEAD.

### SQL18-shaped 32-page fixture (the production document shape)

| Metric | HEAD | After fix |
|---|---|---|
| accepted | 8/8 | 8/8 |
| deterministic candidates attempted / returned / dropped | 15 / 11 / 4 | 11 / 11 / **0** |
| plans_created | 16 | 16 |

The 4 previously-dropped false_statement candidates are now written; every planned slot returns a candidate.

### Truthfulness is preserved (never force 8)

- Thin 3-sentence document → still **422 available=3**, dropped=0 (the veto planned only what is constructible).
- Document with contentless claims ("…exists in two forms.") and a 2-word purpose clause → **422 available<8**, dropped=0, plans accounting shows the unconstructible targets vetoed (`all_types_vetoed_by_writer`).
- The true/false **true** path still refuses verbatim statements (asserted by a new unit test).

## Regression tests added (`backend/tests/test_quiz_deterministic_writer_regression.py`)

1. `test_provider_down_deterministic_recovers_to_full_quiz` — dead provider, requested=8, deterministic fallback, the production-shaped document: fixed result 8/8, dropped=0, 2 recovered true/false questions, provider_errors=2. (HEAD behavior documented in the test: 422 available=6.)
2. `test_sql18_shape_provider_down_deterministic_uses_every_plan` — 32-page fixture: 8/8, dropped=0, attempted==returned, plans_created==16.
3. `test_misconception_swaps_verbatim_frame_into_a_different_false_claim` — unit-level: the true path still refuses the verbatim base; the misconception path swaps a different concept into the frame.
4. `test_writer_veto_excludes_slots_the_writer_cannot_construct` — contentless / 2-word-clause targets are vetoed at plan time, dropped=0, quiz is exactly as long as the document supports.
5. `test_genuinely_thin_document_still_422s_after_recovery` — a 3-sentence document still fails honestly with available<8.

Also fixed a latent test bug exposed by the fix: `test_fill_blank_questions_carry_a_real_blank` called `is_valid_fill_blank(prompt)` with one argument; the function requires `(prompt, answer)`. At HEAD the test passed vacuously because deterministic quizzes never contained fill-blanks; after the fix fill-blanks genuinely appear, so the call now passes `question.correct_answer` and the assertion actually runs (and passes).

## Full verification

- Backend: `python -m pytest tests/ -q` → **568 passed** (563 at HEAD + 5 new).
- Frontend: `vitest run` → **108 passed** (7 files).
- TypeScript: `tsc --noEmit` → clean.
- Build: `vite build` → success (only the pre-existing chunk-size warning).
