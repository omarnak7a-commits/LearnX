"""
Application settings loaded from environment variables.
"""

import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- App ---
    environment: str = os.getenv("ENVIRONMENT", "production")
    api_prefix: str = "/api/v1"
    cors_origins_raw: str = os.getenv("CORS_ORIGINS_RAW", "https://learn-x-ofvm.vercel.app,http://localhost:8443,http://localhost:5173")
    app_base_url: str = os.getenv("APP_BASE_URL", "https://learn-x-ofvm.vercel.app")
    api_base_url: str = os.getenv("API_BASE_URL", "https://learn-x-ofvm.vercel.app")

    # --- Database ---
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://learnx:learnx@localhost:5432/learnx")

    # --- Object storage (S3-compatible, Supabase Storage) ---
    storage_backend: str = os.getenv("STORAGE_BACKEND", "s3")
    storage_endpoint_url: str = os.getenv("STORAGE_ENDPOINT_URL", "https://nmhqleagwizfyigxakqn.storage.supabase.co/storage/v1/s3")
    storage_region: str = os.getenv("STORAGE_REGION", "us-east-1")
    storage_bucket: str = os.getenv("STORAGE_BUCKET", "learnx-uploads")
    storage_access_key: str = os.getenv("STORAGE_ACCESS_KEY", "")
    storage_secret_key: str = os.getenv("STORAGE_SECRET_KEY", "")
    signed_url_ttl_seconds: int = 900

    # --- Online AI (backend-only secrets; never VITE_ variables) ---
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    ai_provider: str = os.getenv("AI_PROVIDER", "gemini")
    ai_fallback_provider: str = os.getenv("AI_FALLBACK_PROVIDER", "groq")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "25"))
    # --- MSEMAX: optional constrained LLM phrasing layer ---
    # Off by default so the deterministic engine stays the reproducible
    # baseline. When true, MSEMAX phrases blueprints the deterministic planner
    # has already decided; its output still passes every existing validator.
    # Parsed from the raw string rather than typed as bool: pydantic-settings
    # re-reads the environment for a declared field, and MSEMAX_ENABLED=""
    # (a common way to "unset" a variable in shell scripts and CI) is not a
    # boolean it accepts, which crashed startup. Keeping the field a string and
    # normalising it here means an empty or malformed value degrades to "off"
    # instead of taking the whole API down.
    msemax_enabled_raw: str = Field(default="false", alias="MSEMAX_ENABLED")

    # --- STEP 9 benchmark authorisation ---
    # A dedicated shared secret for the batched MSEMAX A/B benchmark, entirely
    # separate from the provider credentials: it authorises *triggering* a
    # benchmark, and grants no access to GEMINI_API_KEY or GROQ_API_KEY.
    # Empty by default, which leaves the benchmark routes unmounted entirely.
    benchmark_token: str = Field(default="", alias="BENCHMARK_TOKEN")

    @property
    def msemax_enabled(self) -> bool:
        return (self.msemax_enabled_raw or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    ai_max_document_bytes: int = int(os.getenv("AI_MAX_DOCUMENT_BYTES", str(15 * 1024 * 1024)))
    ai_max_document_characters: int = int(os.getenv("AI_MAX_DOCUMENT_CHARACTERS", "100000"))

    # --- Auth: JWT ---
    jwt_secret: str = os.getenv("JWT_SECRET", "changeme-generate-a-real-secret")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    # --- Email (Resend) ---
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    email_from_address: str = os.getenv("EMAIL_FROM_ADDRESS", "LearnX <onboarding@resend.dev>")

    # --- Google OAuth 2.0 ---
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "https://learn-x-ofvm.vercel.app/auth/callback/google")

    # --- App URLs / cookies ---
    cookie_secure: bool = True
    cookie_domain: str | None = None
    refresh_cookie_name: str = "learnx_refresh_token"
    require_email_verification: bool = False

    # --- Existing video/worker pipeline defaults ---
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    max_upload_size_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(2 * 1024**3)))
    silence_min_removable_seconds: float = float(os.getenv("SILENCE_MIN_REMOVABLE_SECONDS", "3"))
    meaningful_pause_max_seconds: float = float(os.getenv("MEANINGFUL_PAUSE_MAX_SECONDS", "8"))
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cuda")
    diarization_model: str = os.getenv(
        "DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"
    )
    embeddings_model: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-004")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def google_oauth_configured(self) -> bool:
        cid = self.google_client_id or os.environ.get("GOOGLE_CLIENT_ID", "")
        csec = self.google_client_secret or os.environ.get("GOOGLE_CLIENT_SECRET", "")
        return bool(cid and csec)

    @property
    def email_delivery_configured(self) -> bool:
        key = self.resend_api_key or os.environ.get("RESEND_API_KEY", "")
        return bool(key)

@lru_cache
def get_settings() -> Settings:
    return Settings()
