"""HTTP clients for Gemini (primary) and Groq (fallback).

Provider credentials are read only from backend settings. This module never
logs prompts, source documents, authorization headers, or API keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class ProviderCompletion:
    text: str
    provider: str
    model: str


class ProviderError(RuntimeError):
    """A provider call failed in a way the fallback layer can classify."""

    def __init__(self, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.recoverable = recoverable


class ProviderConfigurationError(ProviderError):
    pass


class ProviderContentBlockedError(ProviderError):
    def __init__(self, message: str = "The AI provider blocked this content.") -> None:
        super().__init__(message, recoverable=False)


class ProviderInvalidResponseError(ProviderError):
    pass


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


class GeminiProvider(AIProvider):
    name = "gemini"

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
            raise ProviderConfigurationError("Gemini is not configured.")
        if not self.model:
            raise ProviderConfigurationError("Gemini model is not configured.")

        model_path = quote(self.model, safe="")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:generateContent"
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_schema is not None:
            generation_config.update(
                {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": json_schema,
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
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("Gemini request timed out or could not connect.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Gemini request failed.") from exc

        if not response.is_success:
            raise ProviderError(f"Gemini returned HTTP {response.status_code}.")

        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderInvalidResponseError("Gemini returned invalid JSON.") from exc

        block_reason = (body.get("promptFeedback") or {}).get("blockReason")
        if block_reason:
            raise ProviderContentBlockedError()

        candidates = body.get("candidates") or []
        if not candidates:
            raise ProviderInvalidResponseError("Gemini returned no candidates.")
        candidate = candidates[0]
        finish_reason = str(candidate.get("finishReason") or "").upper()
        if finish_reason in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            raise ProviderContentBlockedError()

        parts = ((candidate.get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts).strip()
        if not text:
            raise ProviderInvalidResponseError("Gemini returned an empty response.")
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
            raise ProviderConfigurationError("Groq is not configured.")
        if not self.model:
            raise ProviderConfigurationError("Groq model is not configured.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            # JSON object mode is supported by the configured versatile Groq
            # models. Pydantic still performs the authoritative validation.
            payload["response_format"] = {"type": "json_object"}

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
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError("Groq request timed out or could not connect.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Groq request failed.") from exc

        if not response.is_success:
            raise ProviderError(f"Groq returned HTTP {response.status_code}.")

        try:
            body = response.json()
            choice = (body.get("choices") or [])[0]
            finish_reason = str(choice.get("finish_reason") or "").lower()
            text = str((choice.get("message") or {}).get("content") or "").strip()
        except (ValueError, IndexError, KeyError, TypeError) as exc:
            raise ProviderInvalidResponseError("Groq returned an invalid response.") from exc

        if finish_reason in {"content_filter", "safety"}:
            raise ProviderContentBlockedError()
        if not text:
            raise ProviderInvalidResponseError("Groq returned an empty response.")
        return ProviderCompletion(text=text, provider=self.name, model=self.model)
