from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_, select

from qharness.infrastructure.database import Database
from qharness.skills.models import SkillRecord


class InvalidSkill(ValueError):
    pass


class Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?$")
    source: str = Field(min_length=1, max_length=2048)
    license: str = Field(min_length=1, max_length=100)
    permissions: list[Annotated[str, Field(min_length=1)]] = Field(max_length=10)


def checksums(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise InvalidSkill("skill contains a symlink")
        if not path.is_file():
            continue
        total_bytes += path.stat().st_size
        if len(result) >= 1000 or total_bytes > 20_000_000:
            raise InvalidSkill("skill exceeds 1000 files or 20 MB")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class SkillRegistry:
    """Verify local content only; skill scripts are never imported or executed."""

    def __init__(self, database: Database, allowed_roots: list[Path]) -> None:
        self.database = database
        self.allowed_roots = [root.absolute() for root in allowed_roots]

    def _root(self, path: Path) -> Path:
        path = path.absolute()
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise InvalidSkill("skill root contains a symlink")
        path = path.resolve()
        if not any(path.is_relative_to(root.resolve()) for root in self.allowed_roots):
            raise InvalidSkill("skill is outside an allowed root")
        if not path.is_dir():
            raise InvalidSkill("skill root is unavailable")
        return path.resolve()

    def discover(self) -> list[Path]:
        return sorted(
            path.parent
            for root in self.allowed_roots
            if root.is_dir()
            for path in root.glob("*/SKILL.md")
            if not path.parent.is_symlink()
        )

    def verify(self, path: Path, project_id: uuid.UUID | None = None) -> SkillRecord:
        root = self._root(path)
        hashes = checksums(root)
        if "SKILL.md" not in hashes:
            raise InvalidSkill("SKILL.md is required")
        content = (root / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", content, re.S)
        if not match:
            raise InvalidSkill("skill requires YAML front matter")
        try:
            manifest = Manifest.model_validate(yaml.safe_load(match.group(1)))
        except (ValidationError, yaml.YAMLError) as exc:
            raise InvalidSkill(
                "skill requires valid name, version, source, license and permissions"
            ) from exc
        if manifest.source != "local":
            source = urlsplit(manifest.source)
            if (
                source.scheme != "https"
                or not source.hostname
                or source.username
                or source.password
            ):
                raise InvalidSkill("source must be local or an HTTPS URL without credentials")
        if set(manifest.permissions) - {"read", "knowledge:read"}:
            raise InvalidSkill("only read permissions are supported")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            reference = target.split("#", 1)[0]
            if not reference or reference not in hashes:
                raise InvalidSkill("referenced asset is missing or outside the skill root")
        if checksums(root) != hashes:
            raise InvalidSkill("skill changed during verification")
        with self.database.transaction() as session:
            existing = session.scalar(
                select(SkillRecord).where(
                    SkillRecord.project_id == project_id,
                    SkillRecord.name == manifest.name,
                    SkillRecord.version == manifest.version,
                )
            )
            if existing:
                if existing.file_checksums != hashes or existing.canonical_path != str(root):
                    raise InvalidSkill("skill version already registered with different content")
                existing.status = "VERIFIED"
                return existing
            record = SkillRecord(
                project_id=project_id,
                name=manifest.name,
                version=manifest.version,
                canonical_path=str(root),
                source=manifest.source,
                license=manifest.license,
                permissions=manifest.permissions,
                manifest_sha256=hashes["SKILL.md"],
                file_checksums=hashes,
                status="VERIFIED",
                evidence={
                    "scripts_executed": False,
                    "checks": [
                        "source",
                        "version",
                        "license",
                        "permissions",
                        "files",
                        "references",
                    ],
                },
            )
            session.add(record)
            session.flush()
            return record

    def list(self, project_id: uuid.UUID) -> list[SkillRecord]:
        with self.database.transaction() as session:
            records = list(
                session.scalars(
                    select(SkillRecord)
                    .where(
                        or_(
                            SkillRecord.project_id == project_id,
                            SkillRecord.project_id.is_(None),
                        )
                    )
                    .order_by(SkillRecord.name, SkillRecord.version)
                )
            )
            for record in records:
                try:
                    current = checksums(self._root(Path(record.canonical_path)))
                    if current != record.file_checksums:
                        record.status = "STALE"
                except (InvalidSkill, OSError):
                    record.status = "STALE"
            return records
