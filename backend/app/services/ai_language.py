"""Arabic / English resolution for LearnX AI responses."""

from __future__ import annotations

import re

AiLanguage = str  # "ar" | "en"

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_AR_ALIASES = {
    "ar",
    "ara",
    "arabic",
    "العربية",
    "عربي",
    "عربية",
    "عربيه",
}
_EN_ALIASES = {
    "en",
    "eng",
    "english",
    "الإنجليزية",
    "الانجليزية",
    "انجليزي",
    "إنجليزي",
    "انجليزية",
}


def normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower().replace("_", "-")
    if "-" in cleaned:
        cleaned = cleaned.split("-", 1)[0]
    if cleaned in _AR_ALIASES:
        return "ar"
    if cleaned in _EN_ALIASES:
        return "en"
    return None


def detect_language(text: str | None) -> str | None:
    if not text:
        return None
    arabic = len(_ARABIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if arabic == 0 and latin == 0:
        return None
    # Bias slightly toward Arabic so mixed student questions stay in Arabic.
    if arabic > 0 and arabic * 2 >= latin:
        return "ar"
    if latin > 0:
        return "en"
    return None


def resolve_ai_language(
    *,
    requested: str | None = None,
    preferred: str | None = None,
    text: str | None = None,
    default: str = "en",
) -> str:
    """Pick ar/en from explicit request, profile preference, then script detection."""
    return (
        normalize_language(requested)
        or normalize_language(preferred)
        or detect_language(text)
        or (default if default in {"ar", "en"} else "en")
    )


def language_name(language: str) -> str:
    return "Arabic (العربية)" if language == "ar" else "English"


def language_instruction(language: str) -> str:
    if language == "ar":
        return (
            "يجب أن تكون كل مخرجاتك باللغة العربية الفصحى الواضحة والمناسبة للدراسة. "
            "أبقِ الرموز والمعادلات كما هي، ويمكنك ذكر المصطلح العلمي بالإنجليزية بين قوسين عند الحاجة. "
            "اذكر أرقام صفحات المصدر بالصيغة (صفحة N). "
            "لا تخلط بين العربية والإنجليزية في نفس الجملة إلا للمصطلحات."
        )
    return (
        "Write every part of your output in clear study-ready English. "
        "Keep formulas and symbols unchanged. You may keep Arabic proper nouns "
        "when they appear in the source. Cite PDF pages as (Page N)."
    )


def page_citation_label(language: str, page: int) -> str:
    return f"صفحة {page}" if language == "ar" else f"Page {page}"
