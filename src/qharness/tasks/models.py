from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from qharness.infrastructure.database import Base


def now() -> datetime:
    return datetime.now(UTC)


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (UniqueConstraint("project_id", "id", name="uq_work_items_project_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    request: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(50))
    risk: Mapped[str] = mapped_column(String(30))
    workflow: Mapped[str] = mapped_column(String(50), default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_tasks_project_id"),
        ForeignKeyConstraint(
            ["project_id", "work_item_id"],
            ["work_items.project_id", "work_items.id"],
            name="fk_tasks_work_item_scope",
            ondelete="CASCADE",
        ),
    )
    required_gates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), index=True
    )
    display_id: Mapped[str] = mapped_column(String(30), unique=True)
    state: Mapped[str] = mapped_column(String(30), default="CREATED", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __mapper_args__ = {"version_id_col": version}


class TaskRepository(Base):
    __tablename__ = "task_repositories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "task_id"],
            ["tasks.project_id", "tasks.id"],
            name="fk_task_repositories_task_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "repository_id"],
            ["repositories.project_id", "repositories.id"],
            name="fk_task_repositories_repository_scope",
            ondelete="CASCADE",
        ),
    )
    project_id: Mapped[uuid.UUID] = mapped_column()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    approved: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_executions_project_id"),
        ForeignKeyConstraint(
            ["project_id", "task_id"],
            ["tasks.project_id", "tasks.id"],
            name="fk_executions_task_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    worker_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ExecutionRepository(Base):
    __tablename__ = "execution_repositories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "execution_id"],
            ["executions.project_id", "executions.id"],
            name="fk_execution_repositories_execution_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "repository_id"],
            ["repositories.project_id", "repositories.id"],
            name="fk_execution_repositories_repository_scope",
            ondelete="CASCADE",
        ),
    )
    project_id: Mapped[uuid.UUID] = mapped_column()
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), primary_key=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    before_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_execution_event_sequence"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(100))
    payload_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    tool: Mapped[str] = mapped_column(String(100))
    input: Mapped[dict[str, Any]] = mapped_column(JSON)
    output: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["execution_id", "repository_id"],
            ["execution_repositories.execution_id", "execution_repositories.repository_id"],
            name="fk_test_runs_repository_scope",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True
    )
    command: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(30))
    returncode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "task_id"],
            ["tasks.project_id", "tasks.id"],
            name="fk_audit_events_task_scope",
        ),
        ForeignKeyConstraint(
            ["project_id", "report_id"],
            ["reports.project_id", "reports.id"],
            name="fk_audit_events_report_scope",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
