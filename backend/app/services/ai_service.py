"""Provider-agnostic AI service with Gemini-first, Groq fallback execution."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.services.ai_providers import (
    AIProvider,
    ErrorCategory,
    GeminiProvider,
    GroqProvider,
    ProviderCompletion,
    ProviderContentBlockedError,
    ProviderError,
    ProviderInvalidResponseError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ProviderFailure:
    """One provider's sanitized failure record. Never contains credentials."""

    provider: str
    category: str
    status_code: int | None
    detail: str
    model: str = ""

    @property
    def summary(self) -> str:
        parts = [f"{self.provider}: {self.category}"]
        if self.model:
            parts.append(f"model={self.model}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.detail:
            parts.append(f"detail={self.detail}")
        return " ".join(parts)


def _failure_from(name: str, exc: Exception) -> ProviderFailure:
    """Classify any provider-layer exception into a sanitized record."""
    if isinstance(exc, ProviderError):
        return ProviderFailure(
            provider=exc.provider or name,
            category=exc.category.value,
            status_code=exc.status_code,
            detail=exc.detail,
            model=exc.model,
        )
    if isinstance(exc, ValidationError):
        return ProviderFailure(
            provider=name,
            category=ErrorCategory.RESPONSE_SCHEMA.value,
            status_code=None,
            # Field paths only -- never the offending values, which could echo
            # document text back into the logs.
            detail=",".join(
                ".".join(str(part) for part in error.get("loc", ()))
                for error in exc.errors()[:3]
            )[:200],
        )
    if isinstance(exc, ValueError):
        return ProviderFailure(
            provider=name,
            category=ErrorCategory.RESPONSE_SCHEMA.value,
            status_code=None,
            detail=type(exc).__name__,
        )
    return ProviderFailure(
        provider=name,
        category=ErrorCategory.UNKNOWN.value,
        status_code=None,
        detail=type(exc).__name__,
    )


class AIServiceError(RuntimeError):
    pass


class AIUnavailableError(AIServiceError):
    """Every configured provider failed.

    Carries the sanitized per-provider diagnosis so callers (and the benchmark)
    can report *why* instead of a generic "provider error". ``str()`` stays the
    user-safe message; the structured detail lives on the attributes.
    """

    def __init__(
        self,
        message: str,
        *,
        failures: "list[ProviderFailure] | None" = None,
    ) -> None:
        super().__init__(message)
        self.failures: list[ProviderFailure] = failures or []

    @property
    def category(self) -> str:
        """Category of the primary (first) failure, for one-line reporting."""
        return self.failures[0].category if self.failures else ErrorCategory.UNKNOWN.value

    def diagnosis(self) -> str:
        """Credential-free, single-line summary of every provider attempt."""
        if not self.failures:
            return "no providers were attempted"
        return "; ".join(failure.summary for failure in self.failures)


class AIContentBlockedError(AIServiceError):
    pass


@dataclass(frozen=True)
class AITextCompletion:
    text: str
    provider: str
    model: str
    fallback_used: bool


@dataclass(frozen=True)
class AIStructuredCompletion(Generic[T]):
    value: T
    provider: str
    model: str
    fallback_used: bool


class AIService:
    """Execute at most one call per configured provider, in configured order."""

    def __init__(
        self,
        settings: Settings,
        providers: dict[str, AIProvider] | None = None,
    ) -> None:
        self.settings = settings
        self.primary_name = settings.ai_provider.strip().lower()
        self.fallback_name = settings.ai_fallback_provider.strip().lower()
        self.providers = providers or {
            "gemini": GeminiProvider(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.ai_timeout_seconds,
            ),
            "groq": GroqProvider(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                timeout_seconds=settings.ai_timeout_seconds,
            ),
        }

    def _provider_order(self) -> list[tuple[str, AIProvider | None]]:
        names: list[str] = []
        for name in (self.primary_name, self.fallback_name):
            if name and name not in names:
                names.append(name)
        return [(name, self.providers.get(name)) for name in names]

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AITextCompletion:
        failures: list[ProviderFailure] = []
        for index, (name, provider) in enumerate(self._provider_order()):
            if provider is None:
                failures.append(
                    ProviderFailure(
                        provider=name,
                        category=ErrorCategory.CONFIGURATION.value,
                        status_code=None,
                        detail="provider not registered",
                    )
                )
                continue
            try:
                result = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return self._text_result(result, index)
            except ProviderContentBlockedError as exc:
                raise AIContentBlockedError(str(exc)) from exc
            except ProviderError as exc:
                failure = _failure_from(name, exc)
                failures.append(failure)
                logger.warning("AI provider failed (%s)", failure.summary)
                if not exc.recoverable:
                    break

        diagnosis = "; ".join(failure.summary for failure in failures)
        logger.error("All configured AI providers failed (%s)", diagnosis)
        raise AIUnavailableError(
            "The AI service is temporarily unavailable. Please try again shortly.",
            failures=failures,
        )

    def complete_structured(
        self,
        *,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        validator: Callable[[T], None] | None = None,
    ) -> AIStructuredCompletion[T]:
        schema = response_model.model_json_schema(by_alias=True)
        structured_prompt = (
            f"{user_prompt}\n\n"
            "Return only one valid JSON object. Do not use markdown fences or add commentary. "
            "The JSON must match this schema exactly:\n"
            f"{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}"
        )
        failures: list[ProviderFailure] = []

        for index, (name, provider) in enumerate(self._provider_order()):
            if provider is None:
                failures.append(
                    ProviderFailure(
                        provider=name,
                        category=ErrorCategory.CONFIGURATION.value,
                        status_code=None,
                        detail="provider not registered",
                    )
                )
                continue
            try:
                completion = provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=structured_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_schema=schema,
                )
                payload = _extract_json_object(completion.text)
                value = response_model.model_validate_json(payload)
                if validator is not None:
                    validator(value)
                return AIStructuredCompletion(
                    value=value,
                    provider=completion.provider,
                    model=completion.model,
                    fallback_used=index > 0,
                )
            except ProviderContentBlockedError as exc:
                raise AIContentBlockedError(str(exc)) from exc
            except (ProviderError, ValidationError, ValueError) as exc:
                # Invalid provider JSON is a recoverable provider response,
                # just like a timeout: retry once with the configured fallback.
                failure = _failure_from(name, exc)
                failures.append(failure)
                logger.warning("AI provider failed structured output (%s)", failure.summary)
                if isinstance(exc, ProviderError) and not exc.recoverable:
                    break

        diagnosis = "; ".join(failure.summary for failure in failures)
        logger.error("All configured AI providers failed structured output (%s)", diagnosis)
        raise AIUnavailableError(
            "The AI service is temporarily unavailable. Please try again shortly.",
            failures=failures,
        )

    @staticmethod
    def _text_result(result: ProviderCompletion, index: int) -> AITextCompletion:
        return AITextCompletion(
            text=result.text,
            provider=result.provider,
            model=result.model,
            fallback_used=index > 0,
        )


def _extract_json_object(text: str) -> str:
    """Accept plain JSON and defensively strip an accidental markdown fence."""
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ProviderInvalidResponseError("Provider did not return a JSON object.")
    return candidate[start : end + 1]


@lru_cache
def get_ai_service() -> AIService:
    return AIService(get_settings())
