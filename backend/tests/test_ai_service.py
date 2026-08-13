from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.schemas.ai import AISummaryResult
from app.services.ai_documents import AIDocumentNotFoundError, load_owned_pdf
from app.services.ai_providers import (
    AIProvider,
    ProviderCompletion,
    ProviderContentBlockedError,
    ProviderError,
)
from app.services.ai_service import (
    AIContentBlockedError,
    AIService,
    AITextCompletion,
    get_ai_service,
)


class FakeProvider(AIProvider):
    def __init__(self, name: str, result: str | Exception) -> None:
        self.name = name
        self.model = f"{name}-test-model"
        self.result = result
        self.calls = 0

    def generate(self, **_kwargs) -> ProviderCompletion:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return ProviderCompletion(text=self.result, provider=self.name, model=self.model)


def settings() -> Settings:
    return Settings(
        _env_file=None,
        gemini_api_key="test-gemini-key",
        groq_api_key="test-groq-key",
        ai_provider="gemini",
        ai_fallback_provider="groq",
    )


def test_gemini_failure_falls_back_to_groq() -> None:
    gemini = FakeProvider("gemini", ProviderError("rate limited"))
    groq = FakeProvider("groq", "Fallback answer")
    service = AIService(settings(), {"gemini": gemini, "groq": groq})

    result = service.complete(system_prompt="system", user_prompt="question")

    assert result.text == "Fallback answer"
    assert result.provider == "groq"
    assert result.fallback_used is True
    assert gemini.calls == 1
    assert groq.calls == 1


def test_invalid_primary_structured_output_is_validated_then_falls_back() -> None:
    gemini = FakeProvider("gemini", '{"summary": "missing required key points"}')
    groq = FakeProvider(
        "groq",
        """{
          "summary": "Grounded summary",
          "keyPoints": ["Point one"],
          "keyTopics": ["Topic"],
          "importantQuestions": ["Why?"]
        }""",
    )
    service = AIService(settings(), {"gemini": gemini, "groq": groq})

    result = service.complete_structured(
        response_model=AISummaryResult,
        system_prompt="system",
        user_prompt="source",
    )

    assert result.value.summary == "Grounded summary"
    assert result.provider == "groq"
    assert result.fallback_used is True


def test_safety_block_does_not_try_another_provider() -> None:
    gemini = FakeProvider("gemini", ProviderContentBlockedError())
    groq = FakeProvider("groq", "should not be used")
    service = AIService(settings(), {"gemini": gemini, "groq": groq})

    with pytest.raises(AIContentBlockedError):
        service.complete(system_prompt="system", user_prompt="question")

    assert groq.calls == 0


def test_foreign_or_missing_file_is_rejected_before_storage(monkeypatch) -> None:
    class MissingFileSession:
        def scalar(self, _query):
            return None

    called = False

    def unexpected_download(*_args, **_kwargs):
        nonlocal called
        called = True
        return b""

    monkeypatch.setattr("app.services.ai_documents.storage.download_user_object", unexpected_download)

    with pytest.raises(AIDocumentNotFoundError):
        load_owned_pdf(
            db=MissingFileSession(),
            user_id="11111111-1111-1111-1111-111111111111",
            file_id="22222222-2222-2222-2222-222222222222",
            settings=settings(),
        )
    assert called is False


def test_chat_endpoint_is_authenticated_and_uses_ai_service() -> None:
    class FakeAIService:
        def complete(self, **_kwargs) -> AITextCompletion:
            return AITextCompletion(
                text="A real provider response",
                provider="gemini",
                model="gemini-2.5-flash",
                fallback_used=False,
            )

    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    try:
        with TestClient(app) as client:
            unauthorized = client.post("/api/v1/ai/chat", json={"message": "Hello"})
            assert unauthorized.status_code == 401

            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id="11111111-1111-1111-1111-111111111111",
                role="student",
            )
            response = client.post("/api/v1/ai/chat", json={"message": "Hello"})
            assert response.status_code == 200
            assert response.json() == {
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "fallbackUsed": False,
                "answer": "A real provider response",
                "citations": [],
            }
    finally:
        app.dependency_overrides.clear()
