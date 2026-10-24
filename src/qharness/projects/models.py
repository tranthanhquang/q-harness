from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from qharness.infrastructure.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    workspace_path: Mapped[str] = mapped_column(String(2048), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    stable_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    repositories: Mapped[list[Repository]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    __mapper_args__ = {"version_id_col": version}


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("canonical_path", name="uq_repositories_canonical_path"),
        UniqueConstraint("project_id", "name", name="uq_repositories_project_name"),
        UniqueConstraint("project_id", "id", name="uq_repositories_project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(100))
    canonical_path: Mapped[str] = mapped_column(String(2048))
    version: Mapped[int] = mapped_column(Integer, default=1)
    access_mode: Mapped[str] = mapped_column(String(20), default="READ_WRITE")
    project: Mapped[Project] = relationship(back_populates="repositories")
    __mapper_args__ = {"version_id_col": version}
