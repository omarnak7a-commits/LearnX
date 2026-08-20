"""Authorisation and exposure contract for the STEP 9 benchmark endpoints.

The benchmark can spend real provider quota, so the important properties are
negative ones: without a token the routes must not exist, with a wrong token
they must refuse, and in no case may a response or a stored record reveal a
provider credential.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import Base, get_db
from app.models.benchmark import BenchmarkBatch, BenchmarkPhrasing, BenchmarkRun

TOKEN = "benchmark-token-for-tests-only"


@pytest.fixture(autouse=True)
def _provider_configured(monkeypatch):
    """Satisfy the MSEMAX credential gate, as the Vercel environment does.

    A placeholder is enough: the injected provider double raises before any
    network call, so no real credential is required or used.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "test-placeholder-not-a-real-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    """A minimal app mounting only the benchmark router, with a live SQLite DB."""
    from app.api import benchmark

    # StaticPool keeps ONE in-memory connection alive for the whole test, so
    # every session sees the same tables; the default pool would hand each
    # session a fresh (empty) database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            BenchmarkBatch.__table__,
            BenchmarkRun.__table__,
            BenchmarkPhrasing.__table__,
        ],
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    app.include_router(benchmark.router, prefix="/api/v1")

    def _db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    def _settings():
        return Settings(_env_file=None, BENCHMARK_TOKEN=TOKEN)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = _settings
    # A provider double: the benchmark must never need a real key to be tested.
    from app.services.ai_service import AIServiceError, get_ai_service

    class _Down:
        def complete_structured(self, **kwargs):
            raise AIServiceError("provider unavailable")

    app.dependency_overrides[get_ai_service] = lambda: _Down()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# A. Authorisation
# --------------------------------------------------------------------------- #


def test_request_without_a_token_is_rejected(client) -> None:
    assert client.post("/api/v1/benchmark/runs").status_code == 401


def test_request_with_a_wrong_token_is_rejected(client) -> None:
    response = client.post(
        "/api/v1/benchmark/runs", headers={"X-Benchmark-Token": "wrong"}
    )
    assert response.status_code == 401


def test_routes_do_not_exist_when_no_token_is_configured() -> None:
    """The default deployment must not expose the benchmark at all."""
    from app.main import app as production_app

    paths = {getattr(route, "path", "") for route in production_app.routes}
    assert not [path for path in paths if "benchmark" in path], (
        "benchmark routes must stay unmounted unless BENCHMARK_TOKEN is set"
    )


# --------------------------------------------------------------------------- #
# B. Authorised lifecycle
# --------------------------------------------------------------------------- #


def test_authorised_caller_can_create_and_advance_a_run(client) -> None:
    auth = {"X-Benchmark-Token": TOKEN}

    created = client.post(
        "/api/v1/benchmark/runs", headers=auth, json={"seeds": [1], "count": 8}
    )
    assert created.status_code == 200
    progress = created.json()
    run_id = progress["run_id"]
    assert progress["total_batches"] > 0
    assert progress["completed"] == 0

    # Phrasing is bounded per request, so a unit takes several calls.
    for _ in range(200):
        advanced = client.post(f"/api/v1/benchmark/runs/{run_id}/next", headers=auth)
        assert advanced.status_code == 200
        body = advanced.json()
        if body["batch"] is None or body["batch"]["status"] == "completed":
            break
    assert body["batch"]["status"] == "completed"
    assert body["progress"]["completed"] == 1
    # The provider is down, so MSEMAX contributed nothing and the deterministic
    # arm carried the batch. Coverage is preserved.
    assert body["batch"]["baseline_questions"] > 0
    assert body["batch"]["generations_accepted"] == 0


def test_report_withholds_comparison_until_the_run_finishes(client) -> None:
    auth = {"X-Benchmark-Token": TOKEN}
    run_id = client.post(
        "/api/v1/benchmark/runs", headers=auth, json={"seeds": [1], "count": 8}
    ).json()["run_id"]
    client.post(f"/api/v1/benchmark/runs/{run_id}/next", headers=auth)

    report = client.get(f"/api/v1/benchmark/runs/{run_id}/report", headers=auth).json()

    assert report["status"] == "in_progress"
    assert "comparison" not in report


def test_advancing_a_finished_run_is_a_no_op(client) -> None:
    """Re-triggering must not duplicate work or corrupt totals."""
    auth = {"X-Benchmark-Token": TOKEN}
    created = client.post(
        "/api/v1/benchmark/runs", headers=auth, json={"seeds": [1], "count": 8}
    ).json()
    run_id = created["run_id"]

    for _ in range(5000):
        body = client.post(f"/api/v1/benchmark/runs/{run_id}/next", headers=auth).json()
        if body["batch"] is None:
            break

    extra = client.post(f"/api/v1/benchmark/runs/{run_id}/next", headers=auth).json()
    assert extra["batch"] is None
    assert extra["progress"]["remaining"] == 0
    assert extra["progress"]["completed"] == created["total_batches"]


def test_unknown_run_is_a_404(client) -> None:
    response = client.get(
        "/api/v1/benchmark/runs/does-not-exist", headers={"X-Benchmark-Token": TOKEN}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# C. No credential ever leaves the server
# --------------------------------------------------------------------------- #


def test_responses_never_contain_credentials(client, monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value-abc123")
    auth = {"X-Benchmark-Token": TOKEN}

    created = client.post(
        "/api/v1/benchmark/runs", headers=auth, json={"seeds": [1], "count": 8}
    )
    run_id = created.json()["run_id"]
    client.post(f"/api/v1/benchmark/runs/{run_id}/next", headers=auth)
    report = client.get(f"/api/v1/benchmark/runs/{run_id}/report", headers=auth)
    detail = client.get(f"/api/v1/benchmark/runs/{run_id}", headers=auth)

    for response in (created, report, detail):
        body = response.text
        assert "super-secret-value-abc123" not in body
        assert "api_key" not in body.lower()
        assert TOKEN not in body


# --------------------------------------------------------------------------- #
# D. Bearer-token convenience form
# --------------------------------------------------------------------------- #


def test_bearer_authorization_header_is_accepted(client) -> None:
    """PowerShell/curl users can send the standard Authorization header."""
    response = client.post(
        "/api/v1/benchmark/runs",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"seeds": [1], "count": 8},
    )
    assert response.status_code == 200
    assert response.json()["total_batches"] > 0


def test_bearer_with_a_wrong_token_is_still_rejected(client) -> None:
    response = client.post(
        "/api/v1/benchmark/runs", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_malformed_authorization_header_is_rejected(client) -> None:
    """A bare value without the Bearer scheme must not authenticate."""
    response = client.post(
        "/api/v1/benchmark/runs", headers={"Authorization": TOKEN}
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# E. Provider pre-flight check
# --------------------------------------------------------------------------- #


def test_provider_check_requires_the_token(client) -> None:
    """The pre-flight spends real quota, so it must not be open."""
    assert client.post("/api/v1/benchmark/provider-check").status_code == 401
    assert (
        client.post(
            "/api/v1/benchmark/provider-check",
            headers={"X-Benchmark-Token": "wrong"},
        ).status_code
        == 401
    )


def test_provider_check_reports_a_category_not_a_generic_error(client) -> None:
    """A failing pre-flight must say *why*, which is what STEP 9 could not."""
    from app.services.ai_providers import ErrorCategory
    from app.services.ai_service import AIUnavailableError, ProviderFailure, get_ai_service

    class Broken:
        def complete_structured(self, **_: object):
            raise AIUnavailableError(
                "The AI service is temporarily unavailable. Please try again shortly.",
                failures=[
                    ProviderFailure(
                        provider="gemini",
                        category=ErrorCategory.AUTHENTICATION.value,
                        status_code=401,
                        detail="UNAUTHENTICATED",
                        model="gemini-2.5-flash",
                    ),
                    ProviderFailure(
                        provider="groq",
                        category=ErrorCategory.MODEL_NOT_FOUND.value,
                        status_code=400,
                        detail="model_decommissioned",
                        model="retired-model",
                    ),
                ],
            )

    client.app.dependency_overrides[get_ai_service] = lambda: Broken()
    try:
        response = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        )
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["category"] == "authentication"
    assert "model_not_found" in body["diagnosis"]
    assert len(body["attempts"]) == 2


def test_provider_check_never_returns_a_credential(client) -> None:
    """Only booleans and model names; never any part of a key."""
    from app.services.ai_service import get_ai_service

    secret = "AIzaSyNEVER_RETURN_THIS_VALUE_123456"

    class Echoing:
        def complete_structured(self, **_: object):
            raise RuntimeError(f"upstream said: {secret}")

    def _settings_with_key():
        return Settings(_env_file=None, BENCHMARK_TOKEN=TOKEN, GEMINI_API_KEY=secret)

    client.app.dependency_overrides[get_settings] = _settings_with_key
    client.app.dependency_overrides[get_ai_service] = lambda: Echoing()
    try:
        response = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        )
    finally:
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, BENCHMARK_TOKEN=TOKEN
        )
        client.app.dependency_overrides.pop(get_ai_service, None)

    body = response.text
    assert secret not in body
    assert response.json()["credentials_present"]["gemini"] is True
    assert response.json()["category"] == "unknown"


def test_provider_check_flags_a_fallback_rescue_as_degraded(client) -> None:
    """A Groq rescue must not be reported as a plain OK.

    This is what hid the broken Gemini primary: the pre-flight said "OK ...
    via groq" without saying why gemini failed.
    """
    from app.services.ai_providers import ErrorCategory
    from app.services.ai_service import (
        AIStructuredCompletion,
        ProviderFailure,
        get_ai_service,
    )
    from app.services.quiz_msemax import MsemaxQuestion

    class Rescued:
        def complete_structured(self, **_: object):
            return AIStructuredCompletion(
                value=MsemaxQuestion(
                    stem="Why?", options=["a", "b", "c", "d"], correct_option=0,
                    answer="", explanation="Because.",
                ),
                provider="groq",
                model="openai/gpt-oss-120b",
                fallback_used=True,
                failures=(
                    ProviderFailure(
                        provider="gemini",
                        category=ErrorCategory.RESPONSE_SCHEMA.value,
                        status_code=None,
                        detail="finish_reason=MAX_TOKENS",
                        model="gemini-2.5-flash",
                    ),
                ),
            )

    client.app.dependency_overrides[get_ai_service] = lambda: Rescued()
    try:
        response = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        )
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    body = response.json()
    assert body["ok"] is True
    assert body["degraded"] is True
    assert body["primary_failure_category"] == "response_schema"
    assert "MAX_TOKENS" in body["primary_failures"][0]


def test_provider_check_reports_not_degraded_on_a_clean_primary(client) -> None:
    from app.services.ai_service import AIStructuredCompletion, get_ai_service
    from app.services.quiz_msemax import MsemaxQuestion

    class Healthy:
        def complete_structured(self, **_: object):
            return AIStructuredCompletion(
                value=MsemaxQuestion(
                    stem="Why?", options=["a", "b", "c", "d"], correct_option=0,
                    answer="", explanation="Because.",
                ),
                provider="gemini",
                model="gemini-2.5-flash",
                fallback_used=False,
            )

    client.app.dependency_overrides[get_ai_service] = lambda: Healthy()
    try:
        response = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        )
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    body = response.json()
    assert body["ok"] is True
    assert body["degraded"] is False
    assert body["provider_used"] == "gemini"


def test_provider_check_reports_its_contract_version(client) -> None:
    """The version marker is how an operator proves what is actually deployed.

    Without it, an old deployment and a new one are indistinguishable from the
    client, which is exactly how a stale production build went unnoticed.
    """
    from app.api.benchmark import PROVIDER_CHECK_VERSION
    from app.services.ai_service import AIStructuredCompletion, get_ai_service
    from app.services.quiz_msemax import MsemaxQuestion

    class Healthy:
        def complete_structured(self, **_: object):
            return AIStructuredCompletion(
                value=MsemaxQuestion(
                    stem="Why?", options=["a", "b", "c", "d"], correct_option=0,
                    answer="", explanation="Because.",
                ),
                provider="gemini",
                model="gemini-2.5-flash",
                fallback_used=False,
            )

    client.app.dependency_overrides[get_ai_service] = lambda: Healthy()
    try:
        body = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        ).json()
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert body["check_version"] == PROVIDER_CHECK_VERSION
    assert PROVIDER_CHECK_VERSION >= 2


def test_provider_check_exposes_the_effective_thinking_budget(client) -> None:
    """Confirms GEMINI_THINKING_BUDGET is actually in force in a deployment."""
    from app.services.ai_service import AIStructuredCompletion, get_ai_service
    from app.services.quiz_msemax import MsemaxQuestion

    class Healthy:
        def complete_structured(self, **_: object):
            return AIStructuredCompletion(
                value=MsemaxQuestion(
                    stem="Why?", options=["a", "b", "c", "d"], correct_option=0,
                    answer="", explanation="Because.",
                ),
                provider="gemini",
                model="gemini-2.5-flash",
                fallback_used=False,
            )

    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, BENCHMARK_TOKEN=TOKEN, GEMINI_THINKING_BUDGET=0
    )
    client.app.dependency_overrides[get_ai_service] = lambda: Healthy()
    try:
        body = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        ).json()
    finally:
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, BENCHMARK_TOKEN=TOKEN
        )
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert body["gemini_thinking_budget"] == 0
    # Default is the model verified as available to the production key.
    assert body["gemini_model"] == "gemini-3.7-flash"


# --------------------------------------------------------------------------- #
# F. Gemini model discovery endpoint
# --------------------------------------------------------------------------- #


def test_gemini_models_requires_the_token(client) -> None:
    assert client.get("/api/v1/benchmark/gemini-models").status_code == 401
    assert client.get(
        "/api/v1/benchmark/gemini-models", headers={"X-Benchmark-Token": "wrong"}
    ).status_code == 401


def test_gemini_models_never_returns_the_key(client, monkeypatch) -> None:
    """Discovery uses the deployment's key but must not echo any part of it."""
    import httpx

    secret = "AIzaSyMUST_NOT_APPEAR_IN_RESPONSE_99"
    catalogue = {
        "models": [
            {
                "name": "models/gemini-3.7-flash",
                "displayName": "Gemini 3.7 Flash",
                "inputTokenLimit": 1048576,
                "outputTokenLimit": 65536,
                "supportedGenerationMethods": ["generateContent"],
                "thinking": True,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        # The key travels as a header only, never in the URL.
        assert "key=" not in str(request.url)
        return httpx.Response(200, json=catalogue)

    transport = httpx.MockTransport(handler)
    original = httpx.Client

    class Patched(original):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", Patched)
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        BENCHMARK_TOKEN=TOKEN,
        GEMINI_API_KEY=secret,
        GEMINI_MODEL="gemini-2.5-flash",
    )
    try:
        response = client.get(
            "/api/v1/benchmark/gemini-models", headers={"X-Benchmark-Token": TOKEN}
        )
    finally:
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, BENCHMARK_TOKEN=TOKEN
        )

    assert secret not in response.text
    body = response.json()
    assert body["ok"] is True
    assert body["recommended_model"] == "gemini-3.7-flash"
    # The currently configured model is correctly reported as unavailable.
    assert body["configured_model_available"] is False


def test_provider_check_names_the_selected_model(client) -> None:
    """Requirement: CheckOnly must show exactly which model was tested."""
    from app.services.ai_service import AIStructuredCompletion, get_ai_service
    from app.services.quiz_msemax import MsemaxQuestion

    class Healthy:
        def complete_structured(self, **_: object):
            return AIStructuredCompletion(
                value=MsemaxQuestion(
                    stem="Why?", options=["a", "b", "c", "d"], correct_option=0,
                    answer="", explanation="Because.",
                ),
                provider="gemini",
                model="gemini-3.7-flash",
                fallback_used=False,
            )

    client.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, BENCHMARK_TOKEN=TOKEN, GEMINI_MODEL="gemini-3.7-flash"
    )
    client.app.dependency_overrides[get_ai_service] = lambda: Healthy()
    try:
        body = client.post(
            "/api/v1/benchmark/provider-check", headers={"X-Benchmark-Token": TOKEN}
        ).json()
    finally:
        client.app.dependency_overrides[get_settings] = lambda: Settings(
            _env_file=None, BENCHMARK_TOKEN=TOKEN
        )
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert body["selected_gemini_model"] == "gemini-3.7-flash"
    assert body["model_used"] == "gemini-3.7-flash"
    assert body["degraded"] is False
