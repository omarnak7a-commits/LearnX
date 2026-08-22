"""Provider failure classification, schema sanitising and fallback behaviour.

These tests protect the shared AI provider layer used by every production AI
feature (summaries, topics, flashcards, quizzes): every failure carries a
sanitized *category*, Gemini 3.x support and its thinking configuration stay
correct, Pydantic schemas are sanitised into a form Gemini accepts without
weakening validation, and Gemini -> Groq fallback keeps working.

No test performs a real network call: ``httpx`` is driven through a
MockTransport so the genuine provider classes, the genuine AIService fallback
loop and the real error classification all execute unchanged.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field

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


class StructuredProbe(BaseModel):
    """Stand-in response model for exercising the structured-output path.

    Deliberately declares defaults on every field: Pydantic then emits the
    ``default`` keyword, which Gemini rejects outright, so this doubles as the
    fixture proving the schema sanitiser is still doing its job.
    """

    model_config = ConfigDict(extra="ignore")

    stem: str = Field(default="", description="The question sentence.")
    options: list[str] = Field(default_factory=list, description="Answer options.")
    correct_option: int = Field(default=0, description="0-based correct index.")
    answer: str = Field(default="", description="Answer for non-MCQ types.")
    explanation: str = Field(default="", description="One-sentence justification.")


VALID_STRUCTURED_JSON = json.dumps(
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
            {"finish_reason": "stop", "message": {"content": VALID_STRUCTURED_JSON}}
        ]
    }


def _gemini_ok() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {"parts": [{"text": VALID_STRUCTURED_JSON}]},
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


def test_probe_schema_has_defaults_that_gemini_rejects() -> None:
    """Guards the premise: Pydantic really does emit the rejected keyword."""
    assert "default" in _all_keys(StructuredProbe.model_json_schema(by_alias=True))


def test_sanitized_schema_drops_unsupported_keywords_only() -> None:
    raw = StructuredProbe.model_json_schema(by_alias=True)
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
            json_schema=StructuredProbe.model_json_schema(by_alias=True),
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
        response_model=StructuredProbe, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini", "groq"]
    assert result.provider == "groq"
    assert result.fallback_used is True


def test_healthy_primary_is_not_second_guessed(routed) -> None:
    service, contacted = routed((200, _gemini_ok()), (500, {}))
    result = service.complete_structured(
        response_model=StructuredProbe, system_prompt="s", user_prompt="u"
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
            response_model=StructuredProbe, system_prompt="s", user_prompt="u"
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
            response_model=StructuredProbe, system_prompt="s", user_prompt="u"
        )
    assert {failure.category for failure in excinfo.value.failures} == {
        ErrorCategory.RESPONSE_SCHEMA.value
    }


# --------------------------------------------------------------------------- #
# E. The diagnosis is sanitized and carries no secret
# --------------------------------------------------------------------------- #


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
                response_model=StructuredProbe, system_prompt="s", user_prompt="u"
            )
    finally:
        httpx.Client = original  # type: ignore[misc]

    blob = " ".join(
        [
            str(excinfo.value),
            excinfo.value.diagnosis(),
            " ".join(failure.summary for failure in excinfo.value.failures),
            json.dumps([failure.__dict__ for failure in excinfo.value.failures]),
        ]
    )
    assert secret_gemini not in blob
    assert secret_groq not in blob
    # The status code is preferred over the provider's free-text message.
    assert "authentication" in blob


# --------------------------------------------------------------------------- #
# F. Gemini 2.5 thinking budget (why Gemini fell back to Groq in production)
# --------------------------------------------------------------------------- #


def _capture_gemini(thinking_budget: int, response: dict[str, Any]) -> dict[str, Any]:
    """Run one Gemini call against a scripted response; return the sent payload."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.clear()
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=response)

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        provider = GeminiProvider(
            api_key="k",
            model="gemini-2.5-flash",
            timeout_seconds=25,
            thinking_budget=thinking_budget,
        )
        try:
            provider.generate(
                system_prompt="s",
                user_prompt="u",
                temperature=0.2,
                max_tokens=900,
                json_schema={"type": "object"},
            )
        except ProviderError:
            pass
    finally:
        httpx.Client = original  # type: ignore[misc]
    return captured


def test_thinking_is_disabled_by_default_for_structured_calls() -> None:
    """2.5 Flash bills thinking against maxOutputTokens; 900 is not enough."""
    payload = _capture_gemini(0, _gemini_ok())
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    # The output budget itself must be untouched.
    assert payload["generationConfig"]["maxOutputTokens"] == 900


def test_negative_budget_omits_the_field_entirely() -> None:
    """Escape hatch for models that refuse to disable thinking (2.5 Pro)."""
    payload = _capture_gemini(-1, _gemini_ok())
    assert "thinkingConfig" not in payload["generationConfig"]


def test_explicit_budget_is_forwarded_unchanged() -> None:
    payload = _capture_gemini(1024, _gemini_ok())
    assert payload["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 1024}


def test_reproduces_the_production_thinking_starvation() -> None:
    """The exact pre-fix response: MAX_TOKENS, no content, thoughts consumed all."""
    starved = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {}}],
        "usageMetadata": {
            "promptTokenCount": 420,
            "thoughtsTokenCount": 900,
            "totalTokenCount": 1320,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=starved)

    transport = httpx.MockTransport(handler)
    original = httpx.Client
    try:
        class Patched(original):  # type: ignore[misc,valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.Client = Patched  # type: ignore[misc]
        with pytest.raises(ProviderError) as excinfo:
            GeminiProvider(
                api_key="k", model="gemini-2.5-flash", timeout_seconds=25,
                thinking_budget=-1,
            ).generate(
                system_prompt="s", user_prompt="u", temperature=0.2, max_tokens=900
            )
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert excinfo.value.detail == "finish_reason=MAX_TOKENS"


def test_service_wires_the_configured_thinking_budget() -> None:
    """A default Settings must disable thinking on the real provider object."""
    service = AIService(Settings(_env_file=None, GEMINI_API_KEY="k"))
    assert service.providers["gemini"].thinking_budget == 0
    # The default is the model verified as available to the production key.
    assert service.providers["gemini"].model == "gemini-3.7-flash"


# --------------------------------------------------------------------------- #
# G. Sanitizer must not weaken validation
# --------------------------------------------------------------------------- #


def test_sanitizer_preserves_every_meaningful_constraint() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["a", "b"],
        "properties": {
            "a": {"type": "string", "enum": ["x", "y"], "default": "x", "minLength": 2},
            "b": {"type": "array", "items": {"type": "integer", "minimum": 1}, "default": []},
            "c": {"type": "string", "format": "date-time", "pattern": "^A", "default": ""},
        },
        "additionalProperties": False,
    }
    clean = sanitize_gemini_schema(schema)
    assert clean["required"] == ["a", "b"]
    assert clean["properties"]["a"]["enum"] == ["x", "y"]
    assert clean["properties"]["a"]["minLength"] == 2
    assert clean["properties"]["b"]["items"] == {"type": "integer", "minimum": 1}
    assert clean["properties"]["c"]["format"] == "date-time"
    assert clean["properties"]["c"]["pattern"] == "^A"
    assert "default" not in _all_keys(clean)
    assert "$schema" not in clean


# --------------------------------------------------------------------------- #
# H. Silent degradation must stay visible
# --------------------------------------------------------------------------- #


def test_fallback_success_still_reports_the_primary_failure(routed) -> None:
    """A Groq rescue must not look identical to a healthy Gemini call."""
    service, contacted = routed(
        (200, {"candidates": [{"finishReason": "MAX_TOKENS", "content": {}}]}),
        (200, _groq_ok()),
    )
    result = service.complete_structured(
        response_model=StructuredProbe, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini", "groq"]
    assert result.provider == "groq"
    assert result.fallback_used is True
    # The reason the primary failed survives on the successful result.
    assert len(result.failures) == 1
    assert result.failures[0].provider == "gemini"
    assert result.failures[0].category == ErrorCategory.RESPONSE_SCHEMA.value


def test_clean_primary_success_reports_no_failures(routed) -> None:
    service, contacted = routed((200, _gemini_ok()), (500, {}))
    result = service.complete_structured(
        response_model=StructuredProbe, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini"]
    assert result.failures == ()
    assert result.fallback_used is False


# --------------------------------------------------------------------------- #
# I. Gemini model discovery (choose a real model, never a guessed one)
# --------------------------------------------------------------------------- #

CATALOGUE = {
    "models": [
        {"name": "models/gemini-3.7-flash", "displayName": "Gemini 3.7 Flash",
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536,
         "supportedGenerationMethods": ["generateContent", "countTokens"], "thinking": True},
        {"name": "models/gemini-3.6-flash", "displayName": "Gemini 3.6 Flash",
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536,
         "supportedGenerationMethods": ["generateContent"], "thinking": True},
        {"name": "models/gemini-3.1-pro-preview", "displayName": "Gemini 3.1 Pro Preview",
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536,
         "supportedGenerationMethods": ["generateContent"], "thinking": True},
        {"name": "models/gemini-3.5-flash-lite", "displayName": "Flash Lite",
         "inputTokenLimit": 1048576, "outputTokenLimit": 65536,
         "supportedGenerationMethods": ["generateContent"], "thinking": True},
        {"name": "models/gemini-embedding-001", "displayName": "Embedding",
         "inputTokenLimit": 2048, "outputTokenLimit": 1,
         "supportedGenerationMethods": ["embedContent"], "thinking": False},
        {"name": "models/imagen-4.0-generate-001", "displayName": "Imagen",
         "inputTokenLimit": 480, "outputTokenLimit": 8192,
         "supportedGenerationMethods": ["predict"], "thinking": False},
        {"name": "models/gemini-2.5-flash-image", "displayName": "2.5 Flash Image",
         "inputTokenLimit": 32768, "outputTokenLimit": 8192,
         "supportedGenerationMethods": ["generateContent"], "thinking": False},
    ]
}


def _with_transport(handler):
    transport = httpx.MockTransport(handler)
    original = httpx.Client

    class Patched(original):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    return original, Patched


def test_list_models_filters_to_usable_text_models() -> None:
    from app.services.ai_providers import is_text_generation_model, rank_gemini_models

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CATALOGUE)

    original, patched = _with_transport(handler)
    try:
        httpx.Client = patched  # type: ignore[misc]
        found = GeminiProvider(
            api_key="k", model="gemini-2.5-flash", timeout_seconds=5
        ).list_models()
    finally:
        httpx.Client = original  # type: ignore[misc]

    usable = [
        m for m in found
        if m.supports_generate_content and is_text_generation_model(m.name)
    ]
    names = {m.name for m in usable}
    assert "gemini-3.7-flash" in names
    # Non-text endpoints must never be proposed for quiz generation.
    assert "gemini-embedding-001" not in names
    assert "imagen-4.0-generate-001" not in names
    assert "gemini-2.5-flash-image" not in names
    # Strongest stable model wins; the preview Pro must not outrank it.
    assert rank_gemini_models(usable)[0].name == "gemini-3.7-flash"


def test_preview_models_rank_below_stable_ones() -> None:
    from app.services.ai_providers import GeminiModelInfo, rank_gemini_models

    ranked = rank_gemini_models([
        GeminiModelInfo("gemini-3.1-pro-preview", "", 1, 65536, ("generateContent",), True),
        GeminiModelInfo("gemini-3.6-flash", "", 1, 65536, ("generateContent",), True),
    ])
    assert ranked[0].name == "gemini-3.6-flash"


def test_list_models_sends_the_key_as_a_header_not_a_query_param() -> None:
    """A key in the URL would leak into access logs and proxies."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["has_header"] = "x-goog-api-key" in request.headers
        return httpx.Response(200, json=CATALOGUE)

    original, patched = _with_transport(handler)
    try:
        httpx.Client = patched  # type: ignore[misc]
        GeminiProvider(
            api_key="AIzaSySECRET_VALUE_000", model="m", timeout_seconds=5
        ).list_models()
    finally:
        httpx.Client = original  # type: ignore[misc]

    assert seen["has_header"] is True
    assert "AIzaSySECRET_VALUE_000" not in seen["url"]
    assert "key=" not in seen["url"]


def test_unavailable_model_is_classified_as_model_not_found() -> None:
    """The exact production symptom: 404 NOT_FOUND for the configured model."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"error": {"code": 404, "status": "NOT_FOUND",
                                 "message": "models/gemini-2.5-flash is not found"}}
        )

    original, patched = _with_transport(handler)
    try:
        httpx.Client = patched  # type: ignore[misc]
        with pytest.raises(ProviderError) as excinfo:
            GeminiProvider(
                api_key="k", model="gemini-2.5-flash", timeout_seconds=5
            ).generate(system_prompt="s", user_prompt="u", temperature=0.2, max_tokens=900)
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert excinfo.value.category is ErrorCategory.MODEL_NOT_FOUND
    assert excinfo.value.status_code == 404


def test_list_models_errors_are_categorized_not_raw() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"status": "PERMISSION_DENIED"}})

    original, patched = _with_transport(handler)
    try:
        httpx.Client = patched  # type: ignore[misc]
        with pytest.raises(ProviderError) as excinfo:
            GeminiProvider(api_key="k", model="m", timeout_seconds=5).list_models()
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert excinfo.value.category is ErrorCategory.AUTHENTICATION


# --------------------------------------------------------------------------- #
# J. Thinking control must match the model generation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gemini-2.5-flash", {"thinkingBudget": 0}),
        ("gemini-2.5-pro", {"thinkingBudget": 0}),
        # Gemini 3 rejects thinkingBudget and uses thinkingLevel instead.
        ("gemini-3.6-flash", {"thinkingLevel": "low"}),
        ("gemini-3.7-flash", {"thinkingLevel": "low"}),
        ("gemini-3.1-pro-preview", {"thinkingLevel": "low"}),
    ],
)
def test_thinking_control_matches_generation(model: str, expected: dict) -> None:
    payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload.update(json.loads(request.content))
        return httpx.Response(200, json=_gemini_ok())

    original, patched = _with_transport(handler)
    try:
        httpx.Client = patched  # type: ignore[misc]
        GeminiProvider(
            api_key="k", model=model, timeout_seconds=5, thinking_budget=0
        ).generate(
            system_prompt="s", user_prompt="u", temperature=0.2, max_tokens=900,
            json_schema={"type": "object"},
        )
    finally:
        httpx.Client = original  # type: ignore[misc]
    assert payload["generationConfig"]["thinkingConfig"] == expected


def test_structured_generation_still_works_on_a_gemini_3_model(routed) -> None:
    """Switching generation must not break the structured contract."""
    service, contacted = routed((200, _gemini_ok()), (500, {}))
    service.providers["gemini"].model = "gemini-3.7-flash"
    result = service.complete_structured(
        response_model=StructuredProbe, system_prompt="s", user_prompt="u"
    )
    assert contacted == ["gemini"]
    assert result.fallback_used is False
    assert result.value.stem
    assert len(result.value.options) == 4
