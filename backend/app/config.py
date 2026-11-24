"""All settings come from environment variables (or a .env file). Nothing secret lives in code."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    # Database: SQLite on your laptop, Supabase Postgres when live.
    database_url: str = f"sqlite:///{(ROOT / 'scamshield.db').as_posix()}"

    model_dir: Path = ROOT / "models"
    use_transformer: bool = False

    # Optional LLM for friendly explanations (any OpenAI-compatible free tier, e.g. Groq).
    llm_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"
    llm_timeout_seconds: float = 8.0

    max_text_chars: int = 5000
    max_image_mb: int = 5
    rate_limit_per_minute: int = 30
    allowed_origins: str = "*"  # comma separated

    scam_threshold: float = 0.70
    suspicious_threshold: float = 0.40


settings = Settings()
