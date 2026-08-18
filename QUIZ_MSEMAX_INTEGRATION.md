# MSEMAX integration

MSEMAX is an **optional** generation layer. The deterministic engine remains
the source of truth and the reproducible baseline; MSEMAX has to earn its place
through the existing quality gates.

Status: **implemented, disabled by default, benchmark pending credentials.**

---

## 1. Where it sits

```
PDF / TXT
    ↓
deterministic document understanding      quiz_understanding.py
    ↓  concepts + evidence + facets
knowledge targets                         quiz_knowledge_targets.py
    ↓
question blueprints                       quiz_blueprints.py
    ↓  concept, skill, evidence, facet, question type, difficulty are now FIXED
deterministic candidate writing           quiz_deterministic.py
    ↓
MSEMAX phrasing layer  (optional)         quiz_msemax.py      ← the only new stage
    ↓
_collect_records  → grounding / shape / dedup / history       quiz_pipeline.py
_score_and_filter → importance, grounding, clarity, conceptual, distractors
select_diverse    → skill/concept/polarity balance
    ↓
final quiz
```

The seam is `quiz_pipeline.generate_quiz`, immediately after
`deterministic_candidates(...)` and **before** `_collect_records(...)`.

Two consequences follow from that placement, and they are the whole design:

1. **MSEMAX cannot bypass a single validator.** Its candidates enter the same
   list, in the same shape, as deterministic ones, and every downstream gate
   runs unchanged.
2. **MSEMAX cannot reduce coverage.** It is given the blueprints that already
   have deterministic candidates and returns a `{blueprint_id: candidate}` map.
   A blueprint it declines simply keeps its deterministic question.

## 2. What MSEMAX is and is not allowed to decide

| Decision | Owner |
|---|---|
| which concepts matter | deterministic understanding |
| which evidence sentence grounds the question | deterministic understanding |
| facet / relationship type | deterministic understanding |
| knowledge target and cognitive skill | deterministic planner |
| question type and difficulty | deterministic planner |
| source pages, provenance | blueprint |
| **the wording of stem, options, answer, explanation** | **MSEMAX** |

`_to_candidate()` rebuilds every non-prose field from the blueprint, so the
model has no channel through which to change the target, the pages, or the
evidence even if it tried.

## 3. Grounding contract

`validate_generation()` runs before the shared pipeline gates. It rejects, with
a specific stated reason:

- empty / too-short stem (the model is instructed to decline, not invent)
- meta references ("the document", "the passage", …)
- verbatim copies of a source sentence
- a stem that does not mention the planned concept
- a stem that does not express the planned skill (a comparison answered with a
  definition is a silent skill swap that no other gate would catch)
- content tokens in the stem, answer, or explanation that are absent from the
  evidence — i.e. invented facts
- MCQ: wrong option count, duplicate options, out-of-range index, answer-length
  giveaway
- true/false: options that are not exactly True and False
- short answer: missing or over-long answer

The unsupported-token check is morphology-tolerant (`partitions` is supported
by `partition`) so natural rephrasing — the entire point of using a model — is
not punished, while invented facts are still caught.

## 4. Failure handling

Everything is a **structured failure**, never a silent drop:

| Failure | Result |
|---|---|
| provider timeout / 5xx / transport error | `MsemaxRejection(reason="provider error: …")` |
| malformed or non-conforming JSON | handled by `AIService.complete_structured`, then `"malformed output"` |
| constraint violation | `MsemaxRejection` naming the violated constraint |
| MSEMAX enabled, no credentials | `MsemaxConfigurationError` raised at run time |

Every rejection is appended to `result.rejections` with
`stage="msemax_generation"`, so a declined generation is visible in exactly the
same place as any other rejected candidate. Per-run counters live in
`result.msemax_stats` (`None` when MSEMAX did not participate — distinct from
"participated and produced nothing").

**No fake backend exists anywhere in the implementation.** Deterministic text is
labelled `origin="deterministic"` before MSEMAX runs, so it can never be
reported as model output.

## 5. Configuration

```bash
MSEMAX_ENABLED=false   # default: deterministic only, fully reproducible
MSEMAX_ENABLED=true    # requires GEMINI_API_KEY or GROQ_API_KEY
```

The flag is parsed from a raw string: `MSEMAX_ENABLED=""` and malformed values
degrade to *off* rather than crashing the API at import time. It reuses the
existing `AIService` (Gemini primary, Groq fallback, configured timeout, JSON
schema enforcement, retry) — there is no second HTTP client.

`generate_quiz(..., msemax_enabled=True|False)` overrides the setting per call,
which is how the A/B harness runs both arms in one process without mutating
global configuration.

## 5b. Running STEP 9 against Vercel-side credentials (batched)

The offline harness needs ~485 sequential provider calls. That cannot run in one
Vercel invocation (10s default, 300s ceiling even on Pro) and a serverless
filesystem is ephemeral, so a second execution path exists for measuring
against the credentials that already live in Vercel — without copying them
anywhere.

**Unit of work.** One `(document, seed)` pair (40 units), but a unit is *not*
completed in one request. `vercel.json` uses the legacy `builds` property, which
cannot carry a `functions.maxDuration` override, so the platform default applies
(10s Hobby / 15s Pro). A single provider call may take up to
`AI_TIMEOUT_SECONDS` (25s) on its own, and a unit needs up to 16 calls — so a
whole unit can never fit.

Each request therefore phrases at most `BENCHMARK_MAX_CALLS_PER_REQUEST` (3)
blueprints, and stops starting new calls after `BENCHMARK_PHRASING_BUDGET` (6s).
Every phrasing is committed immediately to `benchmark_phrasings`, so an
invocation killed mid-flight loses at most the one call in progress. Once every
blueprint of a unit is cached, a final request replays that prose through the
identical pipeline and scores both arms **making zero provider calls**.

That keeps the methodology unchanged — same blueprints, same prose, same
validators, same scanner — while fitting each request inside the limit.

**State.** `benchmark_runs` / `benchmark_batches` / `benchmark_phrasings` in the Postgres database the
project already uses (`app.models.benchmark`). No new dependency, no filesystem
state. A `UNIQUE(run_id, document, seed)` constraint makes duplicate measurement
impossible at the database level rather than by convention, and
`UNIQUE(batch_id, blueprint_id)` gives the same guarantee at blueprint
granularity so no provider call is ever paid for twice.

**Endpoints** (`app/api/benchmark.py`), mounted **only** when `BENCHMARK_TOKEN`
is set — otherwise they do not exist and return 404:

| route | purpose |
|---|---|
| `POST /benchmark/runs` | create a run and materialise all 40 batches |
| `POST /benchmark/runs/{id}/next` | execute the next outstanding batch |
| `GET  /benchmark/runs/{id}` | progress and per-batch status |
| `GET  /benchmark/runs/{id}/report` | final report, once every batch completed |

**Driving it** (no provider key on the client):

```bash
export BENCHMARK_TOKEN=…        # NOT a provider key
python backend/scripts/run_remote_benchmark.py --base-url https://…
```

**Guarantees.** Batches are claimed with `FOR UPDATE SKIP LOCKED`, so concurrent
or repeated calls advance the run instead of racing. Only `pending`/`failed`
batches are eligible, so a completed pair is never re-measured. A provider
outage marks its batch failed with an error category and leaves it retryable —
the run is never corrupted, and `build_report` refuses to emit an A/B comparison
until all 40 batches have genuinely completed.

**Credentials.** `BENCHMARK_TOKEN` authorises *triggering* a benchmark and
grants no access to the provider keys. The benchmark modules never read
`gemini_api_key`/`groq_api_key`; AIService reads them from the environment at
call time. Nothing is written to the database or returned in a response except
provider/model **names**.

## 6. A/B benchmark

```bash
# arm A only — always runnable, no network
.venv/bin/python backend/scripts/msemax_ab.py --baseline-only

# both arms — needs a real provider key
MSEMAX_ENABLED=true GEMINI_API_KEY=… .venv/bin/python backend/scripts/msemax_ab.py
```

Both arms use identical documents (4 demo PDFs + 4 cross-domain text fixtures),
identical seeds (1, 3, 5, 7, 11), identical question counts, and — importantly
— the identical scanner: `adversarial_scan.inspect_quiz()` was extracted so
there is one definition of "defect" rather than two.

Measured per arm: questions, unique concepts, Tier-1 count, candidate survival,
silent candidate loss, rejections by stage, scanner defects and warnings by
kind, MSEMAX valid rate and rejection reasons, and latency. Results are written
to `QUIZ_MSEMAX_AB.json` plus a printed summary.

Without credentials the MSEMAX arm reports
`{"status": "not_executed", "reason": "provider credentials missing…"}`.
It does not substitute canned responses and does not invent numbers.

### Measured so far

| metric | baseline (MSEMAX off) | MSEMAX arm |
|---|---|---|
| questions (8 docs × 5 seeds) | 298 | not executed |
| unique concepts | 68 | not executed |
| Tier-1 questions | 194 | not executed |
| candidate survival | 0.671 | not executed |
| silent candidate loss | **0** | not executed |
| scanner defects | 7 | not executed |
| scanner warnings | 18 | not executed |
| unit tests | 218 passed | — |

The MSEMAX arm is **pending real provider credentials**. No estimated or
illustrative figures are given for it.

### Isolation proof

The claim "disabled MSEMAX is bit-for-bit the previous engine" was verified by
construction, not by inspection: the MSEMAX seam was physically deleted from
`quiz_pipeline.py`, the full corpus regenerated, and every question (prompt,
answer, sorted options; 8 documents × 5 seeds = 298 questions) hashed.

```
MSEMAX code absent  : md5 1e0bbdfb6aefa7089b80a99e1902ed1d
MSEMAX code present : md5 1e0bbdfb6aefa7089b80a99e1902ed1d   (flag off)
```

Identical. The same run reproduced 7 defects / 18 warnings with the layer
absent, which is what establishes the remaining history-ww1 defects as
pre-existing rather than MSEMAX-induced.

### Failure-path verification (no network required)

Running the harness with a configured-but-invalid provider key exercises the
real provider path and the real failure handling end to end:

| | baseline | MSEMAX, provider unreachable |
|---|---|---|
| questions | 59 | 59 |
| scanner defects | 1 | 1 |
| Tier-1 | 38 | 38 |
| silent candidate loss | 0 | **0** |
| MSEMAX generations requested | — | 97 |
| MSEMAX generations accepted | — | 0 |
| provider errors logged | — | **97** |

Every one of the 97 failed generations produced a `msemax_generation`
rejection note, and output was identical to baseline. This is the fallback
contract holding under genuine provider failure — it is *not* an A/B result and
says nothing about MSEMAX quality.


## 7. Verdict rule (STEP 10)

Not yet decided, by design — the decision requires measurement.

MSEMAX may be promoted from optional to preferred **only if**, on the same
fixtures and seeds:

- scanner defects do not increase, **and**
- questions, unique concepts and Tier-1 coverage do not decrease, **and**
- silent candidate loss stays at 0, **and**
- the valid-generation rate is high enough that latency and cost are justified.

More natural-sounding wording is explicitly **not** sufficient.
