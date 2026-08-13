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
    GeminiProvider,
    GroqProvider,
    ProviderCompletion,
    ProviderContentBlockedError,
    ProviderError,
    ProviderInvalidResponseError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIServiceError(RuntimeError):
    pass


class AIUnavailableError(AIServiceError):
    pass


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
        failures: list[str] = []
        for index, (name, provider) in enumerate(self._provider_order()):
            if provider is None:
                failures.append(f"unknown provider {name}")
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
                failures.append(name)
                logger.warning("AI provider %s failed; trying configured fallback", name)
                if not exc.recoverable:
                    break

        logger.error("All configured AI providers failed (%s)", ", ".join(failures))
        raise AIUnavailableError("The AI service is temporarily unavailable. Please try again shortly.")

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
        failures: list[str] = []

        for index, (name, provider) in enumerate(self._provider_order()):
            if provider is None:
                failures.append(f"unknown provider {name}")
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
                failures.append(name)
                logger.warning("AI provider %s failed structured validation; trying fallback", name)
                if isinstance(exc, ProviderError) and not exc.recoverable:
                    break

        logger.error("All configured AI providers failed structured output (%s)", ", ".join(failures))
        raise AIUnavailableError("The AI service is temporarily unavailable. Please try again shortly.")

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
