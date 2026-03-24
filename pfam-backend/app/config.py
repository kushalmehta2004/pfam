from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PFAM Backend"
    app_version: str = "1.0"
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = Field(default="postgresql+asyncpg://user:pass@localhost:5432/pfam")
    redis_url: str = Field(default="redis://localhost:6379/0")

    clerk_jwks_url: str = Field(default="https://api.clerk.com/v1/jwks")
    clerk_issuer: str = Field(default="https://clerk.dev")
    clerk_audience: str = Field(default="pfam-api")

    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

