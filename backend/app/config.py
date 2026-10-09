from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MINDA API"
    environment: Literal["development", "production", "test"] = "development"

    # Local Postgres (or SQLite) for development; Supabase Postgres in production.
    database_url: str = "sqlite:///./studyup.db"

    # "local"    -> FastAPI verifies per-user password hashes and issues its own tokens.
    # "supabase" -> Supabase Auth issues tokens; FastAPI only verifies them.
    auth_mode: Literal["local", "supabase"] = "local"
    app_secret: str = "dev-only-change-me-please-32-bytes-min"
    token_ttl_minutes: int = 60 * 12
    # Password the seed script gives every demo account. Development only.
    demo_password: str = "demo1234"

    password_reset_ttl_minutes: int = 30
    # Set-password links sent with new accounts (and admin-initiated resets) last longer than self-service resets.
    invite_ttl_hours: int = 72
    login_max_failures: int = 5
    login_window_minutes: int = 15
    # Used to build links in emails (password reset).
    frontend_url: str = "http://localhost:5173"

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    # AI is optional and off by default; every core feature works without it.
    ai_features_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_output_tokens: int = 600
    ai_daily_limit_per_user: int = 60

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("auth_mode", mode="before")
    @classmethod
    def _legacy_demo_mode(cls, v: str) -> str:
        return "local" if v == "demo" else v

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        if self.environment == "production":
            if self.app_secret.startswith("dev-only") or len(self.app_secret) < 32:
                raise ValueError("APP_SECRET must be a random string of at least 32 characters in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point to PostgreSQL in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        return self.ai_features_enabled

    @property
    def is_development(self) -> bool:
        return self.environment in ("development", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
