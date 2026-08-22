"""HTTP clients for Gemini (primary) and Groq (fallback).

Provider credentials are read only from backend settings. This module never
logs prompts, source documents, authorization headers, or API keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class ProviderCompletion:
    text: str
    provider: str
    model: str


class ErrorCategory(str, Enum):
    """Sanitized, stable classification of why a provider call failed.

    These values are safe to log, persist and return in diagnostics: they
    describe the *kind* of failure only and never carry credentials, prompts
    or document text.
    """

    AUTHENTICATION = "authentication"
    QUOTA_RATE_LIMIT = "quota_rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    INVALID_REQUEST = "invalid_request"
    MODEL_NOT_FOUND = "model_not_found"
    RESPONSE_SCHEMA = "response_schema"
    CONTENT_BLOCKED = "content_blocked"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


def classify_http_status(status_code: int, body_snippet: str = "") -> ErrorCategory:
    """Map an HTTP status (plus a already-sanitized body hint) to a category.

    ``body_snippet`` must never contain credentials. Callers pass only the
    provider's own error ``code``/``status`` strings, never raw request data.
    """
    hint = (body_snippet or "").lower()
    if status_code in (401, 403):
        return ErrorCategory.AUTHENTICATION
    if status_code == 404:
        return ErrorCategory.MODEL_NOT_FOUND
    if status_code == 429:
        return ErrorCategory.QUOTA_RATE_LIMIT
    if status_code == 408:
        return ErrorCategory.TIMEOUT
    if status_code in (400, 422):
        # A decommissioned/unknown model is reported as a 400 by Groq and as a
        # 404 by Gemini, so the status alone is not sufficient here.
        if "decommission" in hint or "model_not_found" in hint or "is not found" in hint:
            return ErrorCategory.MODEL_NOT_FOUND
        if "quota" in hint or "rate limit" in hint or "exceeded" in hint:
            return ErrorCategory.QUOTA_RATE_LIMIT
        if "api key" in hint or "api_key" in hint or "unauthenticated" in hint:
            return ErrorCategory.AUTHENTICATION
        return ErrorCategory.INVALID_REQUEST
    if status_code >= 500:
        return ErrorCategory.PROVIDER_UNAVAILABLE
    return ErrorCategory.UNKNOWN


#: Failure categories where the request itself was fine and a later identical
#: attempt may succeed. Everything else (auth, invalid_request, model_not_found,
#: response_schema, content_blocked, configuration) is a deterministic defect
#: that retrying would only repeat.
_TRANSIENT_CATEGORIES = frozenset(
    {
        ErrorCategory.QUOTA_RATE_LIMIT,
        ErrorCategory.TIMEOUT,
        ErrorCategory.CONNECTION,
        ErrorCategory.PROVIDER_UNAVAILABLE,
    }
)


def parse_retry_after(value: str | None) -> float | None:
    """Seconds to wait from a Retry-After header, when it is a plain delay.

    Only the numeric form is honoured; an HTTP-date form is ignored in favour
    of the caller's own backoff, which keeps this dependency-free and avoids
    trusting a clock skew.
    """
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


class ProviderError(RuntimeError):
    """A provider call failed in a way the fallback layer can classify."""

    def __init__(
        self,
        message: str,
        *,
        recoverable: bool = True,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        provider: str = "",
        model: str = "",
        status_code: int | None = None,
        detail: str = "",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.recoverable = recoverable
        self.category = category
        self.provider = provider
        self.model = model
        self.status_code = status_code
        #: Short, sanitized provider-supplied reason (never credentials).
        self.detail = detail
        #: Server-supplied cooldown in seconds (from Retry-After), when given.
        self.retry_after = retry_after

    @property
    def is_transient(self) -> bool:
        """True when retrying the same request could plausibly succeed.

        Quota/rate limiting is the canonical case: the request is well formed
        and the credential is valid, the caller merely went too fast.
        """
        return self.category in _TRANSIENT_CATEGORIES

    def summary(self) -> str:
        """One-line, credential-free description used for logs and metrics."""
        parts = [f"category={self.category.value}"]
        if self.provider:
            parts.append(f"provider={self.provider}")
        if self.model:
            parts.append(f"model={self.model}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " ".join(parts)


class ProviderConfigurationError(ProviderError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("category", ErrorCategory.CONFIGURATION)
        super().__init__(message, **kwargs)


class ProviderContentBlockedError(ProviderError):
    def __init__(
        self, message: str = "The AI provider blocked this content.", **kwargs: Any
    ) -> None:
        kwargs.setdefault("category", ErrorCategory.CONTENT_BLOCKED)
        kwargs["recoverable"] = False
        super().__init__(message, **kwargs)


class ProviderInvalidResponseError(ProviderError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("category", ErrorCategory.RESPONSE_SCHEMA)
        super().__init__(message, **kwargs)


def _error_hint(body: Any) -> str:
    """Extract a short, sanitized reason from a provider error body.

    Only the provider's own machine-readable ``code``/``status``/``message``
    fields are considered, truncated hard. Request payloads are never touched,
    so no prompt text or credential can leak into logs.
    """
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, str):
        return error[:200]
    if not isinstance(error, dict):
        return ""
    for key in ("code", "status", "type", "message"):
        value = error.get(key)
        if isinstance(value, str) and value:
            return value[:200]
    return ""


#: JSON Schema keywords Gemini's structured-output parser rejects or ignores.
#: ``default`` in particular is refused outright ("Default value is not
#: supported in the response schema for the Gemini API"), and Pydantic emits it
#: for every field declared with ``Field(default=...)``.
_GEMINI_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {"$schema", "default", "additionalProperties", "discriminator", "examples"}
)


def sanitize_gemini_schema(schema: Any) -> Any:
    """Return a copy of ``schema`` accepted by Gemini structured output.

    Strips keywords Gemini rejects and inlines ``$defs``/``$ref``, which its
    schema parser does not resolve. Purely structural: no field is renamed and
    no constraint that Gemini honours is dropped, so the contract the caller
    validates against is unchanged.
    """
    defs: dict[str, Any] = {}
    if isinstance(schema, dict):
        for key in ("$defs", "definitions"):
            found = schema.get(key)
            if isinstance(found, dict):
                defs.update(found)

    def resolve(node: Any, depth: int = 0) -> Any:
        if depth > 12:  # guard against recursive $ref cycles
            return {"type": "string"}
        if isinstance(node, list):
            return [resolve(item, depth + 1) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str):
            target = defs.get(ref.rsplit("/", 1)[-1])
            if isinstance(target, dict):
                merged = {k: v for k, v in node.items() if k != "$ref"}
                return resolve({**target, **merged}, depth + 1)

        cleaned: dict[str, Any] = {}
        for key, value in node.items():
            if key in _GEMINI_UNSUPPORTED_SCHEMA_KEYS or key in ("$defs", "definitions"):
                continue
            cleaned[key] = resolve(value, depth + 1)
        return cleaned

    return resolve(schema)


class AIProvider:
    name: str
    model: str

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
    ) -> ProviderCompletion:
        raise NotImplementedError


@dataclass(frozen=True)
class GeminiModelInfo:
    """Safe, non-sensitive metadata about one discoverable Gemini model."""

    name: str
    display_name: str
    input_token_limit: int
    output_token_limit: int
    supported_methods: tuple[str, ...]
    thinking: bool

    @property
    def supports_generate_content(self) -> bool:
        return "generateContent" in self.supported_methods


#: Model families that are unsuitable for LearnX structured text generation,
#: matched against the model id. Image/video/audio/embedding endpoints do not
#: accept the JSON-schema text contract the quiz pipeline depends on.
_NON_TEXT_MARKERS = (
    "embedding",
    "aqa",
    "imagen",
    "veo",
    "lyria",
    "-tts",
    "-image",
    "-live",
    "robotics",
    "gemma",
    "learnlm",
)


def is_text_generation_model(model_id: str) -> bool:
    """True when the model id looks like a general text-generation model."""
    lowered = model_id.lower()
    if not lowered.startswith("gemini"):
        return False
    return not any(marker in lowered for marker in _NON_TEXT_MARKERS)


def model_generation(model_id: str) -> float:
    """Numeric generation of a Gemini model id (e.g. 3.6 for gemini-3.6-flash).

    Used to pick the strongest available model and to choose the correct
    thinking-control parameter, which differs across generations.
    """
    match = re.search(r"gemini-(\d+)(?:\.(\d+))?", model_id.lower())
    if not match:
        return 0.0
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return major + minor / 10


def rank_gemini_models(models: list[GeminiModelInfo]) -> list[GeminiModelInfo]:
    """Order candidate models best-first for LearnX structured generation.

    Preference order, strongest first:
      1. stable over preview/experimental (preview models can change or vanish)
      2. newer generation over older
      3. flash tier over pro (the workload is short, high-volume phrasing where
         latency and quota matter far more than deep reasoning) and both over
         lite (lite trades away the reasoning quality the quiz gates require)
      4. larger output capacity
    """

    def tier(info: GeminiModelInfo) -> int:
        lowered = info.name.lower()
        if "lite" in lowered:
            return 0
        if "pro" in lowered:
            return 1
        return 2  # flash

    def key(info: GeminiModelInfo) -> tuple:
        lowered = info.name.lower()
        stable = 0 if ("preview" in lowered or "exp" in lowered) else 1
        return (
            stable,
            model_generation(info.name),
            tier(info),
            info.output_token_limit,
        )

    return sorted(models, key=key, reverse=True)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        thinking_budget: int = 0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        #: Gemini 2.5 charges thinking tokens against maxOutputTokens. 0
        #: disables thinking; a negative value omits the field so the model
        #: applies its own default (needed for models that cannot disable it).
        self.thinking_budget = thinking_budget

    def _thinking_config(self) -> dict[str, Any] | None:
        """The correct thinking-control field for this model's generation.

        Gemini 2.5 uses ``thinkingBudget`` (0 disables thinking). Gemini 3
        replaced it with ``thinkingLevel`` and rejects ``thinkingBudget``;
        thinking cannot be fully disabled there, so the lowest level is used.
        A negative configured budget means "omit entirely, let the model
        decide", which stays valid for every generation.
        """
        if self.thinking_budget < 0:
            return None
        if model_generation(self.model) >= 3:
            # 3.x: no budget field, and "off" is not offered. "low" minimises
            # reasoning spend while remaining a supported value.
            return {"thinkingLevel": "low"}
        return {"thinkingBudget": self.thinking_budget}

    def list_models(self) -> list[GeminiModelInfo]:
        """Discover the models this API key can actually use.

        Reads the key from settings exactly as generate() does; the key is sent
        only as a request header and never returned, logged or stored. Only
        non-sensitive model metadata is surfaced.
        """
        if not self.api_key:
            raise ProviderConfigurationError(
                "Gemini is not configured.", provider=self.name
            )

        discovered: list[GeminiModelInfo] = []
        page_token = ""
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                for _ in range(10):  # bounded: avoid an unbounded pagination loop
                    params = {"pageSize": 200}
                    if page_token:
                        params["pageToken"] = page_token
                    response = client.get(
                        "https://generativelanguage.googleapis.com/v1beta/models",
                        headers={"x-goog-api-key": self.api_key},
                        params=params,
                    )
                    if not response.is_success:
                        try:
                            hint = _error_hint(response.json())
                        except ValueError:
                            hint = ""
                        raise ProviderError(
                            f"Gemini model listing returned HTTP {response.status_code}.",
                            category=classify_http_status(response.status_code, hint),
                            provider=self.name,
                            status_code=response.status_code,
                            detail=hint,
                        )
                    body = response.json()
                    for entry in body.get("models") or []:
                        raw_name = str(entry.get("name") or "")
                        discovered.append(
                            GeminiModelInfo(
                                name=raw_name.split("/", 1)[-1],
                                display_name=str(entry.get("displayName") or ""),
                                input_token_limit=int(entry.get("inputTokenLimit") or 0),
                                output_token_limit=int(
                                    entry.get("outputTokenLimit") or 0
                                ),
                                supported_methods=tuple(
                                    str(method)
                                    for method in (
                                        entry.get("supportedGenerationMethods") or []
                                    )
                                ),
                                thinking=bool(entry.get("thinking")),
                            )
                        )
                    page_token = str(body.get("nextPageToken") or "")
                    if not page_token:
                        break
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError(
                "Gemini model listing could not reach the API.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Gemini model listing failed.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
            ) from exc
        return discovered

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
    ) -> ProviderCompletion:
        if not self.api_key:
            raise ProviderConfigurationError(
                "Gemini is not configured.", provider=self.name
            )
        if not self.model:
            raise ProviderConfigurationError(
                "Gemini model is not configured.", provider=self.name
            )

        model_path = quote(self.model, safe="")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:generateContent"
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        thinking_config = self._thinking_config()
        if thinking_config is not None:
            # Without this, thinking models use a dynamic budget and can spend
            # the entire maxOutputTokens allowance reasoning, returning
            # MAX_TOKENS with no text at all.
            generation_config["thinkingConfig"] = thinking_config
        if json_schema is not None:
            generation_config.update(
                {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": sanitize_gemini_schema(json_schema),
                }
            )

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Gemini request timed out.",
                category=ErrorCategory.TIMEOUT,
                provider=self.name,
                model=self.model,
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderError(
                "Gemini could not be reached.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
                model=self.model,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Gemini request failed.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
                model=self.model,
            ) from exc

        if not response.is_success:
            try:
                hint = _error_hint(response.json())
            except ValueError:
                hint = ""
            category = classify_http_status(response.status_code, hint)
            raise ProviderError(
                f"Gemini returned HTTP {response.status_code}.",
                category=category,
                provider=self.name,
                model=self.model,
                status_code=response.status_code,
                detail=hint,
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
                # Still recoverable: the fallback provider has its own key and
                # model, so even an auth or model error here may succeed there.
                recoverable=True,
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderInvalidResponseError(
                "Gemini returned invalid JSON.",
                provider=self.name,
                model=self.model,
            ) from exc

        block_reason = (body.get("promptFeedback") or {}).get("blockReason")
        if block_reason:
            raise ProviderContentBlockedError(provider=self.name, model=self.model)

        candidates = body.get("candidates") or []
        if not candidates:
            raise ProviderInvalidResponseError(
                "Gemini returned no candidates.",
                provider=self.name,
                model=self.model,
            )
        candidate = candidates[0]
        finish_reason = str(candidate.get("finishReason") or "").upper()
        if finish_reason in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            raise ProviderContentBlockedError(provider=self.name, model=self.model)

        parts = ((candidate.get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts).strip()
        if not text:
            # Gemini 2.5 counts "thinking" tokens against maxOutputTokens, so a
            # small budget can return MAX_TOKENS with zero visible output.
            if finish_reason == "MAX_TOKENS":
                raise ProviderInvalidResponseError(
                    "Gemini returned no output before reaching the token limit.",
                    provider=self.name,
                    model=self.model,
                    detail="finish_reason=MAX_TOKENS",
                )
            raise ProviderInvalidResponseError(
                "Gemini returned an empty response.",
                provider=self.name,
                model=self.model,
                detail=f"finish_reason={finish_reason}" if finish_reason else "",
            )
        return ProviderCompletion(text=text, provider=self.name, model=self.model)


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_schema: dict[str, Any] | None = None,
    ) -> ProviderCompletion:
        if not self.api_key:
            raise ProviderConfigurationError(
                "Groq is not configured.", provider=self.name
            )
        if not self.model:
            raise ProviderConfigurationError(
                "Groq model is not configured.", provider=self.name
            )

        system_content = system_prompt
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            # JSON object mode is supported by the configured Groq models.
            # Pydantic still performs the authoritative validation.
            payload["response_format"] = {"type": "json_object"}
            # OpenAI-compatible APIs reject json_object mode unless the literal
            # word "json" appears in the messages.
            if "json" not in f"{system_prompt}\n{user_prompt}".lower():
                system_content = f"{system_prompt}\n\nRespond with a single valid JSON object."
        payload["messages"] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Groq request timed out.",
                category=ErrorCategory.TIMEOUT,
                provider=self.name,
                model=self.model,
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderError(
                "Groq could not be reached.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
                model=self.model,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "Groq request failed.",
                category=ErrorCategory.CONNECTION,
                provider=self.name,
                model=self.model,
            ) from exc

        if not response.is_success:
            try:
                hint = _error_hint(response.json())
            except ValueError:
                hint = ""
            category = classify_http_status(response.status_code, hint)
            raise ProviderError(
                f"Groq returned HTTP {response.status_code}.",
                category=category,
                provider=self.name,
                model=self.model,
                status_code=response.status_code,
                detail=hint,
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
            )

        try:
            body = response.json()
            choice = (body.get("choices") or [])[0]
            finish_reason = str(choice.get("finish_reason") or "").lower()
            text = str((choice.get("message") or {}).get("content") or "").strip()
        except (ValueError, IndexError, KeyError, TypeError) as exc:
            raise ProviderInvalidResponseError(
                "Groq returned an invalid response.",
                provider=self.name,
                model=self.model,
            ) from exc

        if finish_reason in {"content_filter", "safety"}:
            raise ProviderContentBlockedError(provider=self.name, model=self.model)
        if not text:
            raise ProviderInvalidResponseError(
                "Groq returned an empty response.",
                provider=self.name,
                model=self.model,
                detail=f"finish_reason={finish_reason}" if finish_reason else "",
            )
        return ProviderCompletion(text=text, provider=self.name, model=self.model)
