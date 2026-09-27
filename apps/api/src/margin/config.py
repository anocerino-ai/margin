from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MARGIN_", env_file=ROOT / ".env", extra="ignore")
    admin_email: str = ""
    admin_password_hash: SecretStr = SecretStr("")
    credentials_path: str = "data/providers.json"
    cookie_secure: bool = False

    env: Literal["development", "test", "production"] = "development"
    storage: Literal["sqlite", "d1", "d1_worker"] = "sqlite"
    sqlite_path: str = str(ROOT / "margin.db")
    api_token: SecretStr = SecretStr("")
    d1_account_id: str = ""
    d1_database_id: str = ""
    d1_api_token: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    firecrawl_api_key: SecretStr = SecretStr("")

    d1_worker_url: str = ""
    d1_worker_token: SecretStr = SecretStr("")
    resend_api_key: SecretStr = SecretStr("")
    email_from: str = ""
    email_recipient: str = ""
    openrouter_models: str = ""
    max_articles_per_feed: int = 20
    max_new_articles_per_run: int = 20
    context_char_budget: int = 48000
    llm_max_output_tokens: int = 5000
    llm_attempts_per_model: int = Field(default=3, ge=1, le=10)
    llm_retry_initial_seconds: float = Field(default=45, ge=1, le=3600)
    llm_retry_max_seconds: float = Field(default=180, ge=1, le=86400)

    @model_validator(mode="after")
    def production_guard(self):
        if self.env == "production" and len(self.api_token.get_secret_value()) < 32:
            raise ValueError("Production requires an API token of at least 32 characters")
        if self.storage == "d1" and not all(
            [self.d1_account_id, self.d1_database_id, self.d1_api_token.get_secret_value()]
        ):
            raise ValueError("D1 credentials are required")
        if self.storage == "d1_worker" and (
            not self.d1_worker_url.startswith("https://") or not self.d1_worker_token.get_secret_value()
        ):
            raise ValueError("D1 Worker HTTPS URL and token required")
        if self.llm_retry_max_seconds < self.llm_retry_initial_seconds:
            raise ValueError("Retry maximum must be at least the initial delay")
        if self.context_char_budget < 2000 or self.max_articles_per_feed < 1:
            raise ValueError("Invalid pipeline limits")
        return self
