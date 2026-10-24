"""Offline PostgreSQL + artifact snapshots; stop service and worker before use."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from qharness.config import Settings


def inventory(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("snapshots cannot contain symlinks")
        if path.is_file() and path != root / "manifest.json":
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def pg_environment(url: str) -> dict[str, str]:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not parsed.database:
        raise ValueError("a PostgreSQL database URL is required")
    env = dict(os.environ)
    for name, value in {
        "PGHOST": parsed.host or "127.0.0.1",
        "PGPORT": parsed.port or 5432,
        "PGUSER": parsed.username or "",
        "PGPASSWORD": parsed.password or "",
        "PGDATABASE": parsed.database,
    }.items():
        env[name] = str(value)
    return env


def pg_run(program: str, args: list[str], url: str) -> None:
    executable = shutil.which(program)
    if not executable:
        raise ValueError(f"PostgreSQL 18 client {program} is required")
    result = subprocess.run(  # noqa: S603 - fixed pg client, separate arguments, no shell
        [executable, *args],
        env=pg_environment(url),
        capture_output=True,
        check=False,
    )
    if result.returncode:
        # libpq diagnostics may contain credentials; expose only a stable error.
        raise RuntimeError(f"{program} failed; check server/client version and database access")


def backup(destination: Path) -> None:
    settings = Settings()
    source = Path(os.environ.get("QH_ARTIFACT_ROOT", settings.data_dir / "artifacts"))
    if not source.is_dir() or source.is_symlink():
        raise ValueError("artifact root must be an existing non-symlink directory")
    source = source.resolve()
    if destination.exists() or destination.is_symlink() or destination.is_relative_to(source):
        raise ValueError("backup destination must be new and outside the artifact root")
    inventory(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".qh-backup-", dir=destination.parent))
    try:
        pg_run(
            "pg_dump",
            ["--format=custom", "--no-owner", "--no-acl", "--file", str(staging / "database.dump")],
            settings.database_url,
        )
        shutil.copytree(source, staging / "artifacts", symlinks=True)
        (staging / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "files": inventory(staging),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def restore(snapshot: Path) -> None:
    if snapshot.is_symlink():
        raise ValueError("snapshot must not be a symlink")
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or inventory(snapshot) != manifest.get("files"):
        raise ValueError("backup checksum verification failed")
    if not (snapshot / "database.dump").is_file() or not (snapshot / "artifacts").is_dir():
        raise ValueError("incomplete backup")
    target_url = os.environ.get("QH_RESTORE_DATABASE_URL")
    target_root = os.environ.get("QH_RESTORE_ARTIFACT_ROOT")
    if not target_url or not target_root:
        raise ValueError(
            "explicit QH_RESTORE_DATABASE_URL and QH_RESTORE_ARTIFACT_ROOT are required"
        )
    destination = Path(target_root).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("restore artifact destination must not exist")
    engine = create_engine(target_url)
    try:
        with engine.connect() as connection:
            if connection.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN "
                    "('pg_catalog', 'information_schema')"
                )
            ):
                raise ValueError("restore database must be empty")
    finally:
        engine.dispose()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".qh-restore-", dir=destination.parent))
    try:
        shutil.copytree(snapshot / "artifacts", staging / "artifacts", symlinks=True)
        inventory(staging)
        pg_run(
            "pg_restore",
            [
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "--dbname",
                pg_environment(target_url)["PGDATABASE"],
                str(snapshot / "database.dump"),
            ],
            target_url,
        )
        (staging / "artifacts").rename(destination)
    finally:
        shutil.rmtree(staging)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3 or sys.argv[1] not in {"backup", "restore"}:
            raise ValueError("usage: local_backup.py backup|restore DIRECTORY")
        {"backup": backup, "restore": restore}[sys.argv[1]](Path(sys.argv[2]).absolute())
    except (ValueError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
