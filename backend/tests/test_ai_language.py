from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.services.ai_language import (
    detect_language,
    language_instruction,
    normalize_language,
    resolve_ai_language,
)
from app.services.ai_service import AITextCompletion, get_ai_service


def test_normalize_and_detect_arabic_and_english() -> None:
    assert normalize_language("AR") == "ar"
    assert normalize_language("arabic") == "ar"
    assert normalize_language("العربية") == "ar"
    assert normalize_language("en-US") == "en"
    assert normalize_language("English") == "en"
    assert detect_language("اشرح لي قانون نيوتن الثاني") == "ar"
    assert detect_language("Explain Newton's second law") == "en"
    assert "العربية" in language_instruction("ar")
    assert "English" in language_instruction("en")


def test_resolve_language_prefers_explicit_then_profile_then_script() -> None:
    assert resolve_ai_language(requested="ar", preferred="en", text="Hello") == "ar"
    assert resolve_ai_language(requested=None, preferred="ar", text="Hello") == "ar"
    assert resolve_ai_language(requested=None, preferred=None, text="مرحبا كيف ألخص الفصل") == "ar"
    assert resolve_ai_language(requested=None, preferred=None, text="Summarize this chapter") == "en"


def test_chat_endpoint_uses_arabic_instruction() -> None:
    captured: dict[str, str] = {}

    class FakeAIService:
        def complete(self, **kwargs) -> AITextCompletion:
            captured["system"] = kwargs["system_prompt"]
            captured["user"] = kwargs["user_prompt"]
            return AITextCompletion(
                text="قانون نيوتن الثاني يربط القوة بالتسارع.",
                provider="gemini",
                model="gemini-2.5-flash",
                fallback_used=False,
            )

    app.dependency_overrides[get_db] = lambda: iter([SimpleNamespace()])
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        role="student",
        preferred_language="en",
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/chat",
                json={"message": "اشرح نيوتن", "language": "ar"},
            )
            assert response.status_code == 200
            assert response.json()["answer"].startswith("قانون نيوتن")
            assert "العربية" in captured["system"]
            assert "Arabic" in captured["user"]
    finally:
        app.dependency_overrides.clear()
