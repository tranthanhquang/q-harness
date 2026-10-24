from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitState:
    branch: str | None
    head: str | None
    remote: str | None
    dirty: bool
    fingerprint: str


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(  # noqa: S603 - fixed read-only Git subcommands, no shell
        [shutil.which("git") or "git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def inspect_repository(root: Path) -> GitState:
    branch = _git(root, "branch", "--show-current")
    head = _git(root, "rev-parse", "HEAD")
    remote = _git(root, "remote", "get-url", "origin")
    status = _git(root, "status", "--porcelain=v1") or ""
    fingerprint = hashlib.sha256(f"{head or ''}\n{status}".encode()).hexdigest()
    return GitState(branch or None, head, remote, bool(status), fingerprint)
