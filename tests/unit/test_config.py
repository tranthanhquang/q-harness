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
