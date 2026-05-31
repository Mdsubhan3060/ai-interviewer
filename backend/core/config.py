# ============================================
# core/config.py
# ============================================
# WHY THIS FILE EXISTS:
# Instead of doing os.getenv("AZURE_OPENAI_API_KEY") everywhere in your code,
# we load ALL environment variables ONCE here into a typed Python class.
# Benefits:
#   1. One place to see all config
#   2. Type checking (catches "you forgot to set this" errors at startup)
#   3. IDE autocomplete works (settings.azure_openai_key vs a string)
# ============================================

from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    All application settings loaded from environment variables.
    Pydantic validates types automatically - if DATABASE_URL is missing,
    the app crashes immediately with a clear error instead of mysteriously
    failing 10 minutes later.
    """

    # --- App ---
    APP_NAME: str = "AI Job Hunter"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str
    DEBUG: bool = True

    # --- Azure OpenAI ---
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    AZURE_OPENAI_GPT4_DEPLOYMENT: str = "gpt-4"
    AZURE_OPENAI_MINI_DEPLOYMENT: str = "gpt-4o-mini"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-ada-002"

    # --- Database ---
    DATABASE_URL: str

    # --- Supabase Auth ---
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: Optional[str] = None

    # --- Azure Blob Storage ---
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "resumes"

    # --- CORS ---
    # We store this as a string in .env and split it into a list here
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert comma-separated string to list for FastAPI CORS middleware"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # --- Cost Control ---
    MAX_TOKENS_GPT4: int = 2000
    MAX_TOKENS_MINI: int = 1000

    # --- Audio ---
    WHISPER_MODEL: str = "base"
    MAX_AUDIO_SIZE_MB: int = 25

    # --- Computed Properties ---
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    class Config:
        """
        Tells pydantic-settings to read from a .env file.
        env_file = ".env" means it looks for .env in the directory
        where you RUN the app (the backend/ folder).
        """
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# ============================================
# @lru_cache - IMPORTANT PATTERN
# ============================================
# lru_cache means "only create this object ONCE, then reuse it".
# Without it, every API request would re-read the .env file.
# With it, settings are loaded once at startup and cached in memory.
# This is the standard pattern for FastAPI config.
# ============================================
@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Single instance used across the entire app
settings = get_settings()
