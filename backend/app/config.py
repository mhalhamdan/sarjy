from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Just the database URL, so migrations can run without the app's other secrets."""

    # The repo-root .env, whether run from the root or from backend/. Real environment
    # variables take priority over the file.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str


class Settings(DatabaseSettings):
    """Application settings, read from environment variables (and `.env` when present).

    Required values have no default, so a missing one fails at startup rather than mid-call.
    """

    # Secrets
    openai_api_key: SecretStr
    access_passcode: SecretStr
    session_secret: SecretStr = Field(min_length=32)

    # Cookie
    cookie_name: str = "sarjy_session"
    cookie_secure: bool = True
    cookie_max_age_days: int = 365

    # Realtime voice session
    realtime_model: str = "gpt-realtime-2.1"
    realtime_voice: str = "marin"
    realtime_reasoning_effort: str = "low"
    transcription_model: str = "gpt-live-transcribe"
    # How long the browser has to use the token to start the call; the call itself can run longer.
    client_secret_ttl_seconds: int = 120

    # Web search tool
    search_model: str = "gpt-6.1-terra"
    search_reasoning_effort: str = "low"
    search_timeout_seconds: float = 20.0

    # Memory: how many of the newest facts are loaded into each session's instructions
    memory_prompt_limit: int = 200

    # Limits (in-memory, per process)
    passcode_attempts_per_15_min: int = 5
    sessions_per_user_per_day: int = 50
    searches_per_user_per_minute: int = 10

    # Built frontend; served when the directory exists (it does in the Docker image).
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()
