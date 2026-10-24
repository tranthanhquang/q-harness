from __future__ import annotations

import codecs
import os
import shutil
import stat
import subprocess
from collections.abc import Mapping
from pathlib import Path

from qharness.security.paths import contained_path

DENIED_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "__pycache__",
    }
)
DENIED_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".gitignore",
        ".npmrc",
        ".pypirc",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "credentials.json",
    }
)


def discover_files(root: Path, max_bytes: int = 1_000_000) -> list[Path]:
    return [Path(name) for name in sorted(discover_file_metadata(root, max_bytes=max_bytes))]


def discover_file_metadata(
    root: Path,
    *,
    known_files: Mapping[str, tuple[int, int]] | None = None,
    max_bytes: int = 1_000_000,
) -> dict[str, tuple[int, int]]:
    result = subprocess.run(  # noqa: S603 - fixed rg discovery arguments, no shell
        [
            shutil.which("rg") or "rg",
            "--files",
            "--null",
            "--hidden",
            "--no-require-git",
            "--glob",
            "!.git/**",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise OSError("repository discovery failed")
    accepted: dict[str, tuple[int, int]] = {}
    canonical_root = root.resolve(strict=True)
    directories: dict[str, list[tuple[str, str]]] = {}
    for name in filter(None, result.stdout.split("\0")):
        parent_name, _, basename = name.rpartition("/")
        if (
            DENIED_PARTS.intersection(name.split("/"))
            or basename in DENIED_NAMES
            or basename.startswith(".env.")
            or os.path.splitext(basename)[1].lower() in {".pem", ".key", ".p12", ".pfx"}
        ):
            continue
        directories.setdefault(parent_name, []).append((name, basename))
    for parent_name, candidates in directories.items():
        parent = canonical_root / parent_name
        if parent.resolve(strict=True) != parent:
            continue
        # Resolve the parent once; descriptor-relative stat avoids repeated ancestor lookups.
        descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name, basename in candidates:
                metadata = os.stat(basename, dir_fd=descriptor, follow_symlinks=False)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > max_bytes:
                    continue
                fingerprint = (metadata.st_size, metadata.st_mtime_ns)
                # Unchanged indexed files already passed the text checks.
                if known_files is not None and known_files.get(name) == fingerprint:
                    accepted[name] = fingerprint
                    continue
                with contained_path(root, canonical_root / name).open("rb") as stream:
                    sample = stream.read(8192)
                if b"\x00" in sample:
                    continue
                try:
                    codecs.getincrementaldecoder("utf-8")().decode(sample, final=False)
                except UnicodeDecodeError:
                    continue
                accepted[name] = fingerprint
        finally:
            os.close(descriptor)
    return accepted
