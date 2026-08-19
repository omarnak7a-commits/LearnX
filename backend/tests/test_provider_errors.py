"""Provider failure classification, schema sanitising and fallback behaviour.

STEP 9 produced 210/210 failures reported only as ``{"provider error": 210}``,
which made the cause unknowable from the results. These tests lock in the two
fixes: every failure now carries a sanitized *category*, and the two payload
defects that caused the failures cannot silently return.

No test performs a real network call: ``httpx`` is driven through a
MockTransport so the genuine provider classes, the genuine AIService fallback
loop and the genuine MSEMAX rejection path all execute unchanged.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.ai_providers import (
    ErrorCategory,
    GeminiProvider,
    GroqProvider,
    ProviderError,
    classify_http_status,
    sanitize_gemini_schema,
)
from app.services.ai_service import AIService, AIUnavailableError
from app.services.quiz_msemax import (
    MsemaxQuestion,
    MsemaxStats,
    describe_provider_failure,
    rejection_bucket,
)

VALID_MSEMAX_JSON = json.dumps(
    {
        "stem": "Why does increased pressure raise the reaction rate?",
        "options": ["More collisions", "Fewer collisions", "No change", "Lower energy"],
        "correct_option": 0,
        "answer": "",
        "explanation": "Higher pressure increases collision frequency.",
    }
)


def _groq_ok() -> dict[str, Any]:
    return {
        "choices": [
            {"finish_reason": "stop", "message": {"content": VALID_MSEMAX_JSON}}
        ]
    }


def _gemini_ok() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": VALID_MSEMAX_JSON}]},
            }
        ]
    }


@pytest.fixture
def routed(monkeypatch):
    """Route every httpx.Client through a scripted transport.

    Returns a factory taking the Gemini and Groq (status, body) pairs and
    yielding the AIService plus the ordered list of providers contacted.
    """

    def build(gemini: tuple[int, Any], groq: tuple[int, Any]):
        contacted: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if "googleapis.com" in str(request.url):
                contacted.append("gemini")
                return httpx.Response(gemini[0], json=gemini[1])
            contacted.append("groq")
            return httpx.Response(groq[0], json=groq[1])

        transport = httpx.MockTransport(handler)
        original = httpx.Client

        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(httpx, "Client", Patched)
        settings = Settings(_env_file=None, GEMINI_API_KEY="k", GROQ_API_KEY="k")
        return AIService(settings), contacted

    return build


# --------------------------------------------------------------------------- #
# A. HTTP status -> category
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "status,hint,expected",
    [
        (401, "", ErrorCategory.AUTHENTICATION),
        (403, "", ErrorCategory.AUTHENTICATION),
        (404, "", ErrorCategory.MODEL_NOT_FOUND),
        (429, "", ErrorCategory.QUOTA_RATE_LIMIT),
        (408, "", ErrorCategory.TIMEOUT),
        (500, "", ErrorCategory.PROVIDER_UNAVAILABLE),
        (503, "", ErrorCategory.PROVIDER_UNAVAILABLE),
        (400, "some other problem", ErrorCategory.INVALID_REQUEST),
        # The exact failure the real STEP 9 run hit on the Groq leg.
        (400, "model_decommissioned", ErrorCategory.MODEL_NOT_FOUND),
        (400, "quota exceeded", ErrorCategory.QUOTA_RATE_LIMIT),
        (400, "API key not valid", ErrorCategory.AUTHENTICATION),
    ],
)
def test_status_classification(status: int, hint: str, expected: ErrorCategory) -> None:
    assert classify_http_status(status, hint) is expected


def test_timeout_and_connection_are_distinct(routed) -> None:
    """A hung provider and an unreachable one must not share a category."""
    for raised, expected in (
        (httpx.ConnectTimeout("slow"), ErrorCategory.TIMEOUT),
        (httpx.ConnectError("no route"), ErrorCategory.CONNECTION),
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            raise raised

        transport = httpx.MockTransport(handler)
        provider = GeminiProvider(api_key="k", model="m", timeout_seconds=1)
        original = httpx.Client
        try:
            class Patched(original):  # type: ignore[misc,valid-type]
                def __init__(self, *args: Any, **kwargs: Any) -> None:
                    kwargs["transport"] = transport
                    super().__init__(*args, **kwargs)

            httpx.Client = Patched  # type: ignore[misc]
            with pytest.raises(ProviderError) as excinfo:
                provider.generate(
                    system_prompt="s", user_prompt="u", temperature=0.2, max_tokens=64
                )
            assert excinfo.value.category is expected
        finally:
            httpx.Client = original  # type: ignore[misc]


def test_gemini_max_tokens_without_text_is_reported_precisely() -> None:
    """Thinking tokens can consume the budget, yielding MAX_TOKENS and no text."""
    body = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        provider = GeminiProvider(api_key="k", model="m", timeout_seconds=5)
        with pytest.raises(ProviderError) as excinfo:
            provider.generate(
                system_prompt="s", user_prompt="u", temperature=0.2, max_tokens=8
            )
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert excinfo.value.category is ErrorCategory.RESPONSE_SCHEMA
    assert "MAX_TOKENS" in excinfo.value.detail


# --------------------------------------------------------------------------- #
# B. Gemini schema sanitising (root cause, primary leg)
# --------------------------------------------------------------------------- #


def _all_keys(node: Any, acc: set[str] | None = None) -> set[str]:
    acc = acc if acc is not None else set()
    if isinstance(node, dict):
        for key, value in node.items():
            acc.add(key)
            _all_keys(value, acc)
    elif isinstance(node, list):
        for item in node:
            _all_keys(item, acc)
    return acc


def test_msemax_schema_has_defaults_that_gemini_rejects() -> None:
    """Guards the premise: Pydantic really does emit the rejected keyword."""
    assert "default" in _all_keys(MsemaxQuestion.model_json_schema(by_alias=True))


def test_sanitized_schema_drops_unsupported_keywords_only() -> None:
    raw = MsemaxQuestion.model_json_schema(by_alias=True)
    clean = sanitize_gemini_schema(raw)
    assert "default" not in _all_keys(clean)
    assert "$schema" not in _all_keys(clean)
    # The contract itself is untouched: same fields, same types.
    assert set(clean["properties"]) == set(raw["properties"])
    for name, spec in raw["properties"].items():
        assert clean["properties"][name].get("type") == spec.get("type")


def test_sanitizer_inlines_refs_and_survives_cycles() -> None:
    schema = {
        "$defs": {"Node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Node"}}}},
        "type": "object",
        "properties": {"root": {"$ref": "#/$defs/Node"}},
    }
    clean = sanitize_gemini_schema(schema)
    assert "$defs" not in clean
    assert clean["properties"]["root"]["type"] == "object"


def test_gemini_request_sends_sanitized_schema() -> None:
    """End to end: the wire payload must not carry a rejected keyword."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_gemini_ok())

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        GeminiProvider(api_key="k", model="m", timeout_seconds=5).generate(
            system_prompt="s",
            user_prompt="u",
            temperature=0.2,
            max_tokens=900,
            json_schema=MsemaxQuestion.model_json_schema(by_alias=True),
        )
    finally:
        httpx.Client = original  # type: ignore[misc]
    sent = captured["generationConfig"]["responseJsonSchema"]
    assert "default" not in _all_keys(sent)


# --------------------------------------------------------------------------- #
# C. Groq json_object requirement (root cause, fallback leg)
# --------------------------------------------------------------------------- #


def test_groq_json_mode_guarantees_the_word_json_in_messages() -> None:
    """OpenAI-compatible APIs 400 on json_object mode without the literal word."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_groq_ok())

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        GroqProvider(api_key="k", model="m", timeout_seconds=5).generate(
            system_prompt="Write one exam question.",
            user_prompt="Use the evidence.",
            temperature=0.2,
            max_tokens=900,
            json_schema={"type": "object"},
        )
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert captured["response_format"] == {"type": "json_object"}
    blob = " ".join(message["content"] for message in captured["messages"]).lower()
    assert "json" in blob


# --------------------------------------------------------------------------- #
# D. Fallback behaviour through the real AIService loop
# --------------------------------------------------------------------------- #


def test_gemini_failure_falls_back_to_groq(routed) -> None:
    service, contacted = routed((400, {"error": {"status": "INVALID_ARGUMENT"}}), (200, _groq_ok()))
    result = service.complete_structured(
        response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini", "groq"]
    assert result.provider == "groq"
    assert result.fallback_used is True


def test_healthy_primary_is_not_second_guessed(routed) -> None:
    service, contacted = routed((200, _gemini_ok()), (500, {}))
    result = service.complete_structured(
        response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini"]
    assert result.provider == "gemini"
    assert result.fallback_used is False


def test_both_providers_failing_reports_every_category(routed) -> None:
    """The exact STEP 9 shape: primary schema defect + retired fallback model."""
    service, contacted = routed(
        (400, {"error": {"status": "INVALID_ARGUMENT", "code": 400}}),
        (400, {"error": {"code": "model_decommissioned"}}),
    )
    with pytest.raises(AIUnavailableError) as excinfo:
        service.complete_structured(
            response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
        )
    assert contacted == ["gemini", "groq"]
    failures = excinfo.value.failures
    assert [failure.provider for failure in failures] == ["gemini", "groq"]
    assert failures[0].category == ErrorCategory.INVALID_REQUEST.value
    assert failures[1].category == ErrorCategory.MODEL_NOT_FOUND.value
    # The user-facing message stays generic; the diagnosis is separate.
    assert "temporarily unavailable" in str(excinfo.value)
    assert "model_not_found" in excinfo.value.diagnosis()


def test_malformed_json_is_classified_as_response_schema(routed) -> None:
    bad = {"choices": [{"finish_reason": "stop", "message": {"content": "not json"}}]}
    service, _ = routed((200, {"candidates": [{"content": {"parts": [{"text": "nope"}]}}]}), (200, bad))
    with pytest.raises(AIUnavailableError) as excinfo:
        service.complete_structured(
            response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
        )
    assert {failure.category for failure in excinfo.value.failures} == {
        ErrorCategory.RESPONSE_SCHEMA.value
    }


# --------------------------------------------------------------------------- #
# E. The diagnosis reaches the benchmark, and carries no secret
# --------------------------------------------------------------------------- #


def test_rejection_reason_names_the_category_not_just_provider_error(routed) -> None:
    service, _ = routed(
        (401, {"error": {"status": "UNAUTHENTICATED"}}),
        (401, {"error": {"code": "invalid_api_key"}}),
    )
    with pytest.raises(AIUnavailableError) as excinfo:
        service.complete_structured(
            response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
        )
    reason = f"provider error [{describe_provider_failure(excinfo.value)}]"
    stats = MsemaxStats()
    stats.note_rejection(reason)
    assert list(stats.reasons) == ["provider error: authentication"]
    assert stats.reasons["provider error: authentication"] == 1


def test_distinct_causes_do_not_collapse_into_one_bucket() -> None:
    stats = MsemaxStats()
    stats.note_rejection("provider error [gemini: authentication status=401]")
    stats.note_rejection("provider error [gemini: quota_rate_limit status=429]")
    stats.note_rejection("provider error [gemini: timeout]")
    assert len(stats.reasons) == 3


def test_provider_error_prefix_is_preserved_for_counting() -> None:
    """benchmark_runner counts provider errors via this prefix."""
    reason = "provider error [gemini: timeout]"
    assert reason.startswith("provider error")
    assert rejection_bucket(reason) == "provider error: timeout"


def test_diagnosis_never_leaks_credentials(routed) -> None:
    secret_gemini = "AIzaSyTESTKEYVALUE1234567890abcdef"
    secret_groq = "gsk_TESTKEYVALUE1234567890abcdefghij"

    def handler(request: httpx.Request) -> httpx.Response:
        # A hostile provider echoing the key back must still not leak it.
        return httpx.Response(
            401,
            json={"error": {"status": "UNAUTHENTICATED", "message": f"bad key {secret_gemini}"}},
        )

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        settings = Settings(
            _env_file=None, GEMINI_API_KEY=secret_gemini, GROQ_API_KEY=secret_groq
        )
        with pytest.raises(AIUnavailableError) as excinfo:
            AIService(settings).complete_structured(
                response_model=MsemaxQuestion, system_prompt="s", user_prompt="u"
            )
    finally:
        httpx.Client = original  # type: ignore[misc]

    blob = " ".join(
        [
            str(excinfo.value),
            excinfo.value.diagnosis(),
            describe_provider_failure(excinfo.value),
            rejection_bucket(f"provider error [{describe_provider_failure(excinfo.value)}]"),
            json.dumps([failure.__dict__ for failure in excinfo.value.failures]),
        ]
    )
    assert secret_gemini not in blob
    assert secret_groq not in blob
    # The status code is preferred over the provider's free-text message.
    assert "authentication" in blob
