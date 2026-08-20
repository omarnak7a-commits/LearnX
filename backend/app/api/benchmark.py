"""Protected STEP 9 benchmark control endpoints.

These exist so the MSEMAX A/B benchmark can use the provider credentials that
already live in the Vercel environment, without copying them anywhere. The
server reads them exactly as it does for normal AI traffic; the benchmark
caller never sees, sends, or needs them.

Security posture
----------------
* The router is registered ONLY when ``BENCHMARK_TOKEN`` is configured. With no
  token set -- the default, including today's production -- these routes do not
  exist at all and return 404.
* Every request must present that token in ``X-Benchmark-Token``, compared with
  ``secrets.compare_digest`` to avoid a timing side channel.
* ``BENCHMARK_TOKEN`` is a separate credential. It is never a provider key, and
  the provider keys are never read, returned, or logged here.
* Nothing is exposed to the frontend: no UI, no unauthenticated route, and the
  responses contain only measurement metadata.

Why endpoints instead of one long request
-----------------------------------------
The full benchmark is ~485 provider calls. A single invocation cannot survive
that inside Vercel's limits, so work advances one ``(document, seed)`` batch at
a time -- worst case 16 provider calls -- with progress in Postgres.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.models.benchmark import BATCH_COMPLETED, BenchmarkBatch, BenchmarkRun
from app.services.ai_service import AIService, get_ai_service
from app.services.benchmark_runner import (
    DEFAULT_COUNT,
    DEFAULT_SEEDS,
    BenchmarkError,
    build_report,
    create_run,
    run_batch,
    run_progress,
)
from app.services.quiz_msemax import MsemaxConfigurationError

router = APIRouter(prefix="/benchmark", tags=["benchmark"])

#: Contract version of the provider-check response. Returned on every call so
#: an operator can prove which revision production is serving. Bump whenever
#: the provider-check payload gains or changes a field.
#:   1 = initial pre-flight (ok/category/diagnosis)
#:   2 = adds degraded/primary_failures/primary_failure_category,
#:       gemini_thinking_budget and this marker
#:   3 = adds selected_gemini_model, gemini_model_available and the
#:       /benchmark/gemini-models discovery endpoint
PROVIDER_CHECK_VERSION = 3


def require_benchmark_token(
    x_benchmark_token: str = Header(default=""),
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    """Authorise a benchmark request.

    Accepts the token either as ``X-Benchmark-Token`` or as a standard
    ``Authorization: Bearer <token>`` header. The second form exists purely for
    client convenience -- it is what curl/PowerShell users reach for by default
    -- and carries exactly the same value; it is not a second credential.

    Deliberately strict: an unset token means the feature is off, not open.
    """
    expected = (getattr(settings, "benchmark_token", "") or "").strip()
    if not expected:
        # Should be unreachable (the router is not mounted), but a defence in
        # depth against a future refactor accidentally exposing it.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    provided = (x_benchmark_token or "").strip()
    if not provided:
        header = (authorization or "").strip()
        if header.lower().startswith("bearer "):
            provided = header[7:].strip()

    # compare_digest needs equal-length inputs to be meaningful; the emptiness
    # check keeps a missing header from being compared at all.
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or missing benchmark token"
        )


class StartRequest(BaseModel):
    """Methodology is fixed by default; overriding it starts a *different* run."""

    seeds: list[int] = Field(default_factory=lambda: list(DEFAULT_SEEDS))
    count: int = DEFAULT_COUNT


@router.post("/runs", dependencies=[Depends(require_benchmark_token)])
def start_run(
    payload: StartRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Create a run and materialise its full batch matrix."""
    body = payload or StartRequest()
    try:
        run = create_run(
            db,
            settings=settings,
            seeds=tuple(body.seeds),
            count=body.count,
        )
    except BenchmarkError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return run_progress(db, run)


def _load_run(db: Session, run_id: str) -> BenchmarkRun:
    run = db.query(BenchmarkRun).filter(BenchmarkRun.id == run_id).first()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benchmark run not found")
    return run


@router.post("/runs/{run_id}/next", dependencies=[Depends(require_benchmark_token)])
def advance_run(
    run_id: str,
    db: Session = Depends(get_db),
    service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    """Execute the next outstanding batch.

    Idempotent by construction: batches are claimed under a row lock and only
    ``pending``/``failed`` ones are eligible, so calling this repeatedly (or
    concurrently) advances the run without ever re-measuring a completed pair.
    """
    run = _load_run(db, run_id)
    try:
        batch = run_batch(db, run, service=service)
    except MsemaxConfigurationError as exc:
        # Provider not configured for this deployment: an operator error.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    progress = run_progress(db, run)
    if batch is None:
        if run.status != BATCH_COMPLETED:
            run.status = "completed"
            db.commit()
        return {"batch": None, "progress": progress, "message": "no batches remaining"}

    return {
        "batch": {
            "id": batch.id,
            "document": batch.document,
            "seed": batch.seed,
            "status": batch.status,
            "attempts": batch.attempts,
            "phrased_count": batch.phrased_count,
            "blueprint_count": batch.blueprint_count,
            "baseline_questions": batch.baseline_questions,
            "msemax_questions": batch.msemax_questions,
            "generations_requested": batch.generations_requested,
            "generations_accepted": batch.generations_accepted,
            "provider_errors": batch.provider_errors,
            "error": batch.error,
        },
        "progress": progress,
    }


@router.get("/runs/{run_id}", dependencies=[Depends(require_benchmark_token)])
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Progress plus per-batch status; no A/B numbers until the run finishes."""
    run = _load_run(db, run_id)
    batches = (
        db.query(BenchmarkBatch)
        .filter(BenchmarkBatch.run_id == run.id)
        .order_by(BenchmarkBatch.document, BenchmarkBatch.seed)
        .all()
    )
    return {
        "progress": run_progress(db, run),
        "batches": [
            {
                "document": batch.document,
                "seed": batch.seed,
                "status": batch.status,
                "attempts": batch.attempts,
                "error": batch.error,
            }
            for batch in batches
        ],
    }


@router.get("/runs/{run_id}/report", dependencies=[Depends(require_benchmark_token)])
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The STEP 9 report, once every batch has genuinely completed."""
    run = _load_run(db, run_id)
    return build_report(db, run)


def _recommend_gemini_model(settings: Settings) -> dict[str, Any]:
    """Best model actually available to this deployment's key, or the error.

    Sanitized: model names and capability metadata only, never the credential.
    """
    from app.services.ai_providers import (
        GeminiProvider,
        ProviderError,
        is_text_generation_model,
        rank_gemini_models,
    )

    try:
        discovered = GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.ai_timeout_seconds,
            thinking_budget=settings.gemini_thinking_budget,
        ).list_models()
    except ProviderError as exc:
        return {"ok": False, "category": exc.category.value, "diagnosis": exc.summary()}

    ranked = rank_gemini_models(
        [
            info
            for info in discovered
            if info.supports_generate_content and is_text_generation_model(info.name)
        ]
    )
    return {
        "ok": True,
        "recommended_model": ranked[0].name if ranked else None,
        "available_text_models": [info.name for info in ranked[:8]],
        "hint": (
            "Set GEMINI_MODEL to the recommended model in Vercel and redeploy."
            if ranked
            else "This key exposes no text-generation model."
        ),
    }


@router.get("/gemini-models", dependencies=[Depends(require_benchmark_token)])
def gemini_models(
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List the Gemini models this deployment's API key can actually use.

    Uses the GEMINI_API_KEY already present in the environment; the key is sent
    only as a request header to Google and is never returned, logged or stored.
    The response contains model names and public capability metadata only.

    This exists so the model choice is driven by what the production key really
    has access to, instead of a guessed model name.
    """
    from app.services.ai_providers import (
        GeminiProvider,
        ProviderError,
        is_text_generation_model,
        rank_gemini_models,
    )

    if not (settings.gemini_api_key or "").strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No Gemini credentials are configured in this environment.",
        )

    provider = GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.ai_timeout_seconds,
        thinking_budget=settings.gemini_thinking_budget,
    )
    try:
        discovered = provider.list_models()
    except ProviderError as exc:
        # Sanitized: category and status only, never the key.
        return {
            "check_version": PROVIDER_CHECK_VERSION,
            "ok": False,
            "category": exc.category.value,
            "diagnosis": exc.summary(),
        }

    usable = [
        info
        for info in discovered
        if info.supports_generate_content and is_text_generation_model(info.name)
    ]
    ranked = rank_gemini_models(usable)
    configured = settings.gemini_model.strip()
    return {
        "check_version": PROVIDER_CHECK_VERSION,
        "ok": True,
        "configured_model": configured,
        "configured_model_available": any(info.name == configured for info in ranked),
        "recommended_model": ranked[0].name if ranked else None,
        "total_models_visible": len(discovered),
        "usable_text_models": [
            {
                "name": info.name,
                "display_name": info.display_name,
                "input_token_limit": info.input_token_limit,
                "output_token_limit": info.output_token_limit,
                "thinking": info.thinking,
                "supports_generate_content": info.supports_generate_content,
            }
            for info in ranked
        ],
    }


@router.post("/provider-check", dependencies=[Depends(require_benchmark_token)])
def provider_check(
    settings: Settings = Depends(get_settings),
    service: AIService = Depends(get_ai_service),
) -> dict[str, Any]:
    """Make ONE real MSEMAX-shaped provider call and report the outcome.

    This is the cheap pre-flight for STEP 9: it exercises the exact path the
    benchmark uses -- same schema, same structured-output call, same
    Gemini-then-Groq fallback -- so a misconfiguration surfaces after one call
    instead of after hundreds.

    Returns provider and model *names* plus a sanitized error category. It never
    returns, logs or accepts a provider key, and never stores anything.
    """
    from app.services.ai_providers import ErrorCategory
    from app.services.ai_service import AIUnavailableError
    from app.services.quiz_msemax import MsemaxQuestion

    configured = {
        "gemini": bool((settings.gemini_api_key or "").strip()),
        "groq": bool((settings.groq_api_key or "").strip()),
    }
    result: dict[str, Any] = {
        # Build marker: lets an operator confirm which revision is actually
        # serving, without shell access to the deployment. Bump when the
        # provider-check contract changes.
        "check_version": PROVIDER_CHECK_VERSION,
        "primary": settings.ai_provider,
        "fallback": settings.ai_fallback_provider,
        "gemini_model": settings.gemini_model,
        # Explicit echo of the model this deployment will actually send to
        # Gemini, so the CheckOnly output names exactly what was tested.
        "selected_gemini_model": settings.gemini_model,
        "groq_model": settings.groq_model,
        # The effective thinking budget actually in force. 0 = thinking off,
        # negative = field omitted so the model uses its own default.
        "gemini_thinking_budget": getattr(settings, "gemini_thinking_budget", None),
        # Booleans only: whether a key exists, never any part of its value.
        "credentials_present": configured,
        "timeout_seconds": settings.ai_timeout_seconds,
    }
    if not any(configured.values()):
        result.update(
            ok=False,
            category=ErrorCategory.CONFIGURATION.value,
            diagnosis="no provider credentials are configured in this environment",
        )
        return result

    try:
        completion = service.complete_structured(
            response_model=MsemaxQuestion,
            system_prompt=(
                "You write exam questions. Reply with one JSON object only."
            ),
            user_prompt=(
                "Evidence: 'Water boils at 100 degrees Celsius at sea level.'\n"
                "Write one multiple-choice question with four options about this "
                "evidence. Return JSON with keys stem, options, correct_option, "
                "answer, explanation."
            ),
            temperature=0.2,
            max_tokens=900,
        )
    except AIUnavailableError as exc:
        result.update(
            ok=False,
            category=exc.category,
            diagnosis=exc.diagnosis(),
            attempts=[failure.summary for failure in exc.failures],
        )
        # If Gemini rejected the configured model, discover what this key can
        # actually use and name the best one. Diagnostic only: this does not
        # change what production generates, it just removes a guess-and-
        # redeploy cycle from the operator's loop.
        if any(
            failure.provider == "gemini"
            and failure.category == ErrorCategory.MODEL_NOT_FOUND.value
            for failure in exc.failures
        ):
            result["model_recommendation"] = _recommend_gemini_model(settings)
        return result
    except Exception as exc:  # never leak an unexpected traceback to the caller
        result.update(
            ok=False,
            category=ErrorCategory.UNKNOWN.value,
            diagnosis=type(exc).__name__,
        )
        return result

    degraded = [failure.summary for failure in completion.failures]
    result.update(
        ok=True,
        provider_used=completion.provider,
        model_used=completion.model,
        fallback_used=completion.fallback_used,
        # Proof a real generation came back, without echoing a whole answer.
        sample_stem_length=len(completion.value.stem),
        sample_option_count=len(completion.value.options),
    )
    if degraded:
        # The call succeeded only because a later provider rescued it. Report
        # the primary's failure rather than a bare "OK", which would hide a
        # broken primary behind a healthy-looking result.
        result.update(
            degraded=True,
            primary_failures=degraded,
            primary_failure_category=completion.failures[0].category,
        )
        # A rescued call still means the primary model is wrong; recommend a
        # model this key can actually use so the operator does not have to
        # guess-and-redeploy.
        if any(
            failure.provider == "gemini"
            and failure.category == ErrorCategory.MODEL_NOT_FOUND.value
            for failure in completion.failures
        ):
            result["model_recommendation"] = _recommend_gemini_model(settings)
    else:
        result["degraded"] = False
    return result
