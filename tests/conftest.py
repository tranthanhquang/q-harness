from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from qharness.infrastructure.database import Database


@pytest.fixture(scope="session", autouse=True)
def test_database_url() -> Iterator[str]:
    source = make_url(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    name = f"qh_test_{uuid.uuid4().hex}"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = source.set(database=name).render_as_string(hide_password=False)
    previous = {key: os.environ.get(key) for key in ("QH_DATABASE_URL", "QH_TEST_DATABASE_URL")}
    os.environ.update(QH_DATABASE_URL=url, QH_TEST_DATABASE_URL=url)
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield url
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(autouse=True)
def database(test_database_url: str) -> Iterator[Database]:
    database = Database(test_database_url)
    with database.engine.begin() as connection:
        tables = connection.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND "
                "tablename <> 'alembic_version'"
            )
        )
        names = ", ".join(f'"{name}"' for name in tables)
        if names:
            connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield database
    database.engine.dispose()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    return path


@pytest.fixture
def local_token() -> str:
    return "test-token-with-at-least-32-characters"


@pytest.fixture
def approved_task(database: Database, tmp_path: Path):
    from qharness.projects.service import ProjectService
    from qharness.tasks.service import TaskService

    projects = ProjectService(database)
    project = projects.create("Execution", tmp_path)
    projects.add_repository(project.id, tmp_path, "api", "api")
    service = TaskService(database)
    task = service.create(project.id, "Fix application")
    task = service.approve(
        task.id,
        {
            "repository_paths": [str(tmp_path)],
            "tools": ["read", "write", "search", "test"],
            "commands": ["python"],
            "network": False,
            "credential_names": [],
            "risk_ceiling": "HIGH",
            "required_gates": [
                {"name": name, "cwd": str(tmp_path), "command": ["python", name]}
                for name in ("tests.py", "smoke.py")
            ],
        },
    )
    return service, task
