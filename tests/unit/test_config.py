from pathlib import Path

import pytest
from pydantic import ValidationError

from qharness.config import Settings


def test_service_requires_loopback_and_token(tmp_path: Path) -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@127.0.0.1/db",
        data_dir=tmp_path,
        bind_host="127.0.0.1",
        local_token="x" * 32,
    )
    assert settings.service_ready().bind_host == "127.0.0.1"

    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://u:p@localhost/db",
            data_dir=tmp_path,
            bind_host="0.0.0.0",
        )


def test_model_use_requires_explicit_model_and_key(tmp_path: Path) -> None:
    settings = Settings(database_url="postgresql+psycopg://u:p@localhost/db", data_dir=tmp_path)
    with pytest.raises(ValueError, match="QH_MODEL"):
        settings.model_ready()


@pytest.mark.parametrize(
    "value", [None, "", "  ", "https://gateway.example/api/v1", "http://127.0.0.1:9999/v1"]
)
def test_base_url_from_environment(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    else:
        monkeypatch.setenv("OPENAI_BASE_URL", value)
    settings = Settings()
    if value and value.strip():
        assert str(settings.openai_base_url) == value
    else:
        assert settings.openai_base_url is None


@pytest.mark.parametrize("value", ["not-a-url", "ftp://gateway.example/v1"])
def test_base_url_rejects_invalid_http_endpoint(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", value)
    with pytest.raises(ValidationError):
        Settings()
