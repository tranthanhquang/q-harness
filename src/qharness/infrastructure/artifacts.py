from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    path: Path
    sha256: str
    size_bytes: int


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, source: Path, relative_name: str) -> PublishedArtifact:
        relative = Path(relative_name)
        if relative.is_absolute() or ".." in relative.parts or not relative.name:
            raise ValueError("artifact path escapes the store")
        target = self.root / relative
        parent = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        temporary_name = f".qh-{uuid.uuid4().hex}"
        try:
            # Hold directory descriptors so a concurrent symlink swap cannot redirect publication.
            for part in relative.parts[:-1]:
                with suppress(FileExistsError):
                    os.mkdir(part, mode=0o700, dir_fd=parent)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            descriptor = os.open(
                temporary_name, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent
            )
            with os.fdopen(descriptor, "w+b") as output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
                output.seek(0)
                content = output.read()
            os.link(
                temporary_name,
                relative.name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
                follow_symlinks=False,
            )
            os.fsync(parent)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name, dir_fd=parent)
            os.close(parent)
        return PublishedArtifact(target, hashlib.sha256(content).hexdigest(), len(content))
