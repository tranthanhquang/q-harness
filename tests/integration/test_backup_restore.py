import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from qharness.infrastructure.database import Database
from qharness.projects.service import ProjectService


@pytest.mark.integration
def test_backup_restore_to_empty_database(database: Database, tmp_path: Path) -> None:
    source = make_url(os.environ["QH_TEST_DATABASE_URL"])
    project = ProjectService(database).create("Restore proof", tmp_path / "workspace")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "evidence.txt").write_text("restore me", encoding="utf-8")
    backup = tmp_path / "backup"
    env = dict(
        os.environ,
        QH_ARTIFACT_ROOT=str(artifacts),
        QH_PYTHON=str(Path(".venv/bin/python").absolute()),
    )
    subprocess.run(
        ["bash", "scripts/backup-local.sh", str(backup)], env=env, check=True, capture_output=True
    )
    target_name = f"qh_restore_{uuid.uuid4().hex}"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{target_name}"'))
    target = source.set(database=target_name).render_as_string(hide_password=False)
    restored = tmp_path / "restored"
    env.update(QH_RESTORE_DATABASE_URL=target, QH_RESTORE_ARTIFACT_ROOT=str(restored))
    try:
        subprocess.run(
            ["bash", "scripts/restore-local.sh", str(backup)],
            env=env,
            check=True,
            capture_output=True,
        )
        target_db = Database(target)
        assert ProjectService(target_db).get(project.id).name == "Restore proof"
        assert (restored / "evidence.txt").read_text() == "restore me"
        # Existing state is never overwritten on a second restore.
        repeated = subprocess.run(
            ["bash", "scripts/restore-local.sh", str(backup)], env=env, capture_output=True
        )
        assert repeated.returncode != 0
        target_db.engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{target_name}" WITH (FORCE)'))
        admin.dispose()


def test_restore_rejects_modified_backup(database: Database, tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    backup = tmp_path / "backup"
    env = dict(
        os.environ,
        QH_ARTIFACT_ROOT=str(artifacts),
        QH_PYTHON=str(Path(".venv/bin/python").absolute()),
    )
    subprocess.run(
        ["bash", "scripts/backup-local.sh", str(backup)], env=env, check=True, capture_output=True
    )
    (backup / "database.dump").write_bytes(b"corrupted")
    env.update(
        QH_RESTORE_DATABASE_URL=os.environ["QH_TEST_DATABASE_URL"],
        QH_RESTORE_ARTIFACT_ROOT=str(tmp_path / "restored"),
    )
    result = subprocess.run(
        ["bash", "scripts/restore-local.sh", str(backup)], env=env, capture_output=True
    )
    assert result.returncode != 0
    assert b"checksum" in result.stderr
    assert database.healthy()
