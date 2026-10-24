from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from qharness.infrastructure.database import Base


class ReportTemplate(Base):
    __tablename__ = "report_templates"
    __table_args__ = (
        UniqueConstraint(
            "scope_project_id",
            "template_id",
            "version",
            name="uq_report_template_version",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope_project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    template_id: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50))
    output_format: Mapped[str] = mapped_column(String(10))
    contract_path: Mapped[str] = mapped_column(String(2048))
    template_path: Mapped[str] = mapped_column(String(2048))
    contract_sha256: Mapped[str] = mapped_column(String(64))
    template_sha256: Mapped[str] = mapped_column(String(64))
    license: Mapped[str] = mapped_column(String(100))
    trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    contract: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("project_id", "id", name="uq_artifacts_project_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(2048), unique=True)
    media_type: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_reports_project_id"),
        ForeignKeyConstraint(
            ["project_id", "artifact_id"],
            ["artifacts.project_id", "artifacts.id"],
            name="fk_reports_artifact_scope",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    template_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report_templates.id"))
    template_id: Mapped[str] = mapped_column(String(100))
    template_version: Mapped[str] = mapped_column(String(50))
    state: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    missing_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    data_provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    validation_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
