"""Application configuration.

One flat pydantic-settings ``Settings`` class, read from environment variables /
``.env``. Every field here must have a matching, commented entry in
``.env.example`` — that file is the single source of truth for what the
service reads (see PLAYBOOK.md §3 and architecture.md §4).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Walk up from this file to the repo root so the .env path is independent of cwd.
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ──
    environment: Literal["dev", "local", "test", "prod"] = "local"
    log_level: str = "INFO"

    app_api_key: str = "change-me"

    # ── Upstream reporting API ──
    upstream_base_url: str = "https://ai-homework-production-2423.up.railway.app"
    upstream_token: str = "any-token"

    # ── LLM / agent (OpenRouter) ──
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "qwen/qwen3.6-plus"
    llm_temperature: float = 0.1
    agent_max_iterations: int = 20

    # ── Verification loop only (ADR-0003) ──
    dev_fake_upstream: bool = False
    dev_fake_llm: bool = False

    @property
    def is_development(self) -> bool:
        return self.environment in ("dev", "local")

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"

    @model_validator(mode="after")
    def _dev_fakes_only_in_development(self) -> "Settings":
        """ADR-0003: fail closed. A fake flag set outside development is a startup error."""
        if (self.dev_fake_upstream or self.dev_fake_llm) and not self.is_development:
            raise ValueError(
                "DEV_FAKE_UPSTREAM / DEV_FAKE_LLM are development-only (ADR-0003) but "
                f"ENVIRONMENT={self.environment!r} is not a development value."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Singleton settings, and the FastAPI dependency-override seam for tests."""
    return Settings()
