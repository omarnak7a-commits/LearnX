"""
Application settings loaded from environment variables.

Reference implementation only — see backend/README.md. Values below are
sane local-dev defaults; every secret must be overridden via a real .env /
secrets manager before this ever runs against production data.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:8443"]

    # --- Database ---
    database_url: str = "postgresql+psycopg://learnx:learnx@localhost:5432/learnx"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Object storage (S3-compatible, e.g. MinIO in dev) ---
    storage_backend: str = "s3"
    storage_endpoint_url: str = "http://localhost:9000"
    storage_region: str = "us-east-1"
    storage_bucket: str = "learnx-uploads"
    storage_bucket_videos: str = "learnx-videos"
    storage_bucket_originals: str = "learnx-originals"
    storage_access_key: str = "changeme"
    storage_secret_key: str = "changeme"
    signed_url_ttl_seconds: int = 900

    # --- Auth ---
    jwt_secret: str = "changeme-generate-a-real-secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    # --- Email (Resend) ---
    resend_api_key: str = ""
    email_from_address: str = "LearnX <onboarding@resend.dev>"

    # --- Google OAuth 2.0 ---
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # --- App URLs / cookies ---
    app_base_url: str = "http://localhost:8443"
    cookie_secure: bool = False
    require_email_verification: bool = False


    # --- AI models ---
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"  # falls back to "cpu" if no GPU (much slower)
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Pipeline tuning (see stages/silence_detection.py for rationale) ---
    silence_min_removable_seconds: float = 4.0
    silence_energy_threshold_db: float = -40.0
    meaningful_pause_max_seconds: float = 6.0

    # --- Upload limits ---
    max_upload_size_bytes: int = 20 * 1024 * 1024 * 1024  # 20 GB
    chunk_size_bytes: int = 8 * 1024 * 1024  # 8 MB per resumable chunk


@lru_cache
def get_settings() -> Settings:
    return Settings()
