"""Application configuration.

Everything is optional for local dev: with no env vars set, the app uses SQLite and
the offline (deterministic) tailoring/embedding path so it runs with zero external deps.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  (two parents up from app/config.py)
BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", BACKEND_ROOT.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    secret_key: str = "dev-only-change-me"

    # Database — default SQLite file under storage/
    database_url: str | None = None

    redis_url: str | None = None

    # LLM
    anthropic_api_key: str | None = None
    anthropic_tailor_model: str = "claude-opus-4-8"
    anthropic_fast_model: str = "claude-sonnet-4-6"

    # Discovery
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None

    # Inbound email
    inbound_domain: str = "inbox.applycopilot.local"
    postmark_inbound_token: str | None = None

    # Notifications
    telegram_bot_token: str | None = None

    # Outbound identity — honest, identifiable UA (never spoof a real browser for discovery).
    user_agent: str = "ApplyCoPilot/0.1 (+https://applycopilot.example/bot; co-pilot, human-approved)"

    # Apply automation (co-pilot). OFF by default: adapters refuse to submit unless explicitly enabled.
    apply_live: bool = False
    # Hosts the browser is permitted to submit to. Localhost is for the sandbox/mock; real ATS hosts
    # must be present here too. A non-allowlisted host can NEVER receive a submission.
    apply_allowed_hosts: list[str] = [
        "127.0.0.1", "localhost",
        "boards.greenhouse.io", "job-boards.greenhouse.io",
    ]
    browser_headless: bool = True
    apply_timeout_ms: int = 30000
    # Filled forms contain PII; only capture confirmation-page screenshots unless this is on.
    apply_debug_screenshots: bool = False

    # Storage
    storage_dir: str = str(BACKEND_ROOT / "storage")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = Path(self.storage_dir) / "dev.sqlite3"
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.storage_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
