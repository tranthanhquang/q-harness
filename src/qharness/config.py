from __future__ import annotations

import ipaddress
import uuid
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QH_", extra="ignore")

    database_url: str = "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness"
    data_dir: Path = Path(".tmp/qharness-data")
    bind_host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    local_token: SecretStr | None = None
    project_id: uuid.UUID | None = None
    model: str | None = None
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: AnyHttpUrl | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    sandbox_image: str = "q-harness-sandbox:dev"

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: str | AnyHttpUrl | None) -> str | AnyHttpUrl | None:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("bind_host")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        try:
            if not ipaddress.ip_address(value).is_loopback:
                raise ValueError("QH_BIND_HOST must be a loopback address")
        except ValueError as exc:
            if "loopback" in str(exc):
                raise
            if value != "localhost":
                raise ValueError("QH_BIND_HOST must be a loopback address") from exc
        return value

    def service_ready(self) -> Settings:
        if self.local_token is None or len(self.local_token.get_secret_value()) < 32:
            raise ValueError("QH_LOCAL_TOKEN must contain at least 32 characters")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    def model_ready(self) -> Settings:
        if not self.model:
            raise ValueError("QH_MODEL is required for model-backed operations")
        if self.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for model-backed operations")
        return self
