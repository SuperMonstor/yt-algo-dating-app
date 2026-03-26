"""
Application configuration from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Postgres
    database_url: str = "postgresql://localhost:5432/ytalgo"

    # Supabase Auth
    supabase_url: str = ""
    supabase_jwk: str = ""

    # YouTube Data API
    youtube_api_key: str = ""

    # Anthropic (for LLM tagging)
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
