from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from qharness.infrastructure.database import Base


class SkillRecord(Base):
    __tablename__ = "skill_records"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "name",
            "version",
            name="uq_skill_scope_version",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50))
    canonical_path: Mapped[str] = mapped_column(String(2048))
    source: Mapped[str] = mapped_column(String(2048))
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    license: Mapped[str] = mapped_column(String(100))
    permissions: Mapped[list[str]] = mapped_column(JSON)
    file_checksums: Mapped[dict[str, str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
