from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from qharness.security.policy import ApprovalScope


class FileConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    path: Path
    content: str
    sha256: str


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_file(scope: ApprovalScope, path: Path) -> FileSnapshot:
    target = scope.require_path(path)
    content = target.read_bytes()
    return FileSnapshot(target, content.decode("utf-8"), _sha256(content))


def write_file(scope: ApprovalScope, path: Path, content: str, expected_sha256: str) -> str:
    target = scope.require_path(path)
    current = target.read_bytes() if target.exists() else b""
    if _sha256(current) != expected_sha256:
        raise FileConflict("file changed after it was read")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content.encode("utf-8"))
            temporary.flush()
            os.fsync(temporary.fileno())
        scope.require_path(path)
        if _sha256(target.read_bytes() if target.exists() else b"") != expected_sha256:
            raise FileConflict("file changed while preparing the write")
        if target.exists():
            os.chmod(temporary_name, target.stat().st_mode & 0o777)
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return _sha256(content.encode("utf-8"))


def run_command(
    scope: ApprovalScope,
    command: tuple[str, ...],
    cwd: Path,
    timeout_seconds: int = 300,
    keep_running: Callable[[], bool] | None = None,
) -> CommandResult:
    from qharness.config import Settings
    from qharness.infrastructure.sandbox import DockerRunner, SandboxSpec
    from qharness.knowledge.discovery import discover_files
    from qharness.security.redaction import redact

    scope.require_path(cwd)
    scope.require_command(command)
    with tempfile.TemporaryDirectory(prefix="qh-test-") as temporary:
        staged: list[Path] = []
        container_cwd: str | None = None
        for index, root in enumerate(scope.roots):
            scope.require_path(root)
            destination = Path(temporary) / f"repo_{index}"
            destination.mkdir()
            for relative in discover_files(root):
                source = scope.require_path(root / relative)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                target.chmod(target.stat().st_mode | 0o444)
            for directory in (
                destination,
                *(path for path in destination.rglob("*") if path.is_dir()),
            ):
                directory.chmod(0o777)
            staged.append(destination)
            if cwd.resolve().is_relative_to(root):
                container_cwd = (
                    f"/workspace/{destination.name}/{cwd.resolve().relative_to(root).as_posix()}"
                )
        if container_cwd is None:
            raise ValueError("test working directory is outside approval")
        result = DockerRunner(Settings().sandbox_image).run(
            SandboxSpec(writable=tuple(staged), timeout_seconds=timeout_seconds),
            f"cd {shlex.quote(container_cwd)} && {shlex.join(command)}",
            keep_running=keep_running,
        )
    return CommandResult(command, result.returncode, redact(result.stdout), redact(result.stderr))
