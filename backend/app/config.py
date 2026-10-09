from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Study Coach API"
    environment: Literal["development", "production", "test"] = "development"

    # SQLite for local development; point this at the Supabase Postgres
    # connection string (postgresql+psycopg://...) in production.
    database_url: str = "sqlite:///./studyup.db"

    # "demo" issues backend-signed tokens for the seeded demo accounts.
    # "supabase" verifies Supabase Auth access tokens.
    auth_mode: Literal["demo", "supabase"] = "demo"
    app_secret: str = "dev-only-change-me-please-32-bytes-min"
    demo_password: str = "demo1234"
    token_ttl_minutes: int = 60 * 12

    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_output_tokens: int = 600
    ai_daily_limit_per_user: int = 60

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
