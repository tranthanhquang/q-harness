from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from qharness.infrastructure.database import Base


class IndexVersion(Base):
    __tablename__ = "index_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "repository_id"],
            ["repositories.project_id", "repositories.id"],
            name="fk_index_versions_repository_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(30), default="BUILDING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint("project_id", "repository_id", "path", name="uq_source_file_scope_path"),
        UniqueConstraint(
            "project_id", "repository_id", "id", name="uq_source_files_project_repository_id"
        ),
        ForeignKeyConstraint(
            ["project_id", "repository_id"],
            ["repositories.project_id", "repositories.id"],
            name="fk_source_files_repository_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    modified_ns: Mapped[int] = mapped_column(BigInteger)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "repository_id", "source_file_id"],
            ["source_files.project_id", "source_files.repository_id", "source_files.id"],
            name="fk_knowledge_chunks_source_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"), index=True
    )
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)


class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "repository_id", "source_file_id"],
            ["source_files.project_id", "source_files.repository_id", "source_files.id"],
            name="fk_symbols_source_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(500), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    line: Mapped[int] = mapped_column(Integer)


class SemanticKnowledge(Base):
    __tablename__ = "semantic_knowledge"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    statement: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    verified: Mapped[bool] = mapped_column(default=False)
