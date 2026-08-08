"""
Application settings loaded from environment variables.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    require_email_verification: bool = False

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
