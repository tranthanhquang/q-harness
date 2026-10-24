from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from qharness.infrastructure.database import Database
from qharness.reports.models import Artifact, Report
from qharness.security.redaction import redact
from qharness.tasks.models import (
    Approval,
    AuditEvent,
    Execution,
    ExecutionEvent,
    ExecutionRepository,
    Task,
    TestRun,
    ToolInvocation,
)


def append_audit(
    session: Session,
    project_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    *,
    task_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        task_id=task_id,
        report_id=report_id,
        event_type=event_type,
        payload=redact(payload),
    )
    session.add(event)
    session.flush()
    return event


class AuditService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def append(
        self,
        project_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        task_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        with self.database.transaction() as session:
            return append_audit(session, project_id, event_type, payload, task_id=task_id).id

    def notifications(
        self, project_id: uuid.UUID, since: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        if since < 0 or not 1 <= limit <= 200:
            raise ValueError("invalid notification cursor or limit")
        with self.database.transaction() as session:
            query = select(AuditEvent).where(
                AuditEvent.project_id == project_id,
                AuditEvent.event_id > since,
                AuditEvent.event_type.in_(
                    [
                        "SPEC_READY",
                        "APPROVAL_REQUIRED",
                        "TASK_BLOCKED",
                        "TEST_FAILED",
                        "TASK_COMPLETED",
                        "REPORT_READY",
                    ]
                ),
            )
            return [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "payload_version": event.payload_version,
                    "payload": redact(event.payload),
                    "task_id": str(event.task_id) if event.task_id else None,
                    "report_id": str(event.report_id) if event.report_id else None,
                    "occurred_at": event.created_at.isoformat(),
                    "summary": event.event_type.replace("_", " ").lower(),
                }
                for event in session.scalars(query.order_by(AuditEvent.event_id).limit(limit))
            ]

    def task_timeline(self, project_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, Any]:
        with self.database.transaction() as session:
            task = session.get(Task, task_id)
            if not task or task.project_id != project_id:
                raise ValueError("task not found")
            executions = list(
                session.scalars(
                    select(Execution)
                    .where(Execution.task_id == task_id)
                    .order_by(Execution.created_at)
                )
            )
            ids = [item.id for item in executions]
            events = list(
                session.scalars(
                    select(ExecutionEvent)
                    .where(ExecutionEvent.execution_id.in_(ids))
                    .order_by(ExecutionEvent.created_at, ExecutionEvent.sequence)
                )
            )
            runs = list(session.scalars(select(TestRun).where(TestRun.execution_id.in_(ids))))
            tools = list(
                session.scalars(
                    select(ToolInvocation)
                    .where(ToolInvocation.execution_id.in_(ids))
                    .order_by(ToolInvocation.created_at)
                )
            )
            approvals = list(
                session.scalars(
                    select(Approval)
                    .where(Approval.task_id == task_id)
                    .order_by(Approval.created_at)
                )
            )
            repositories = list(
                session.scalars(
                    select(ExecutionRepository).where(ExecutionRepository.execution_id.in_(ids))
                )
            )
            audit_events = list(
                session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.task_id == task_id)
                    .order_by(AuditEvent.event_id)
                )
            )
            reports = session.execute(
                select(Report, Artifact)
                .outerjoin(Artifact, Artifact.id == Report.artifact_id)
                .where(
                    Report.project_id == project_id,
                    Report.data_provenance.cast(JSONB).contains(
                        [{"source": "tasks", "id": str(task_id)}]
                    ),
                )
                .order_by(Report.created_at)
            ).all()
            return {
                "id": str(task.id),
                "project_id": str(project_id),
                "display_id": task.display_id,
                "state": task.state,
                "version": task.version,
                "reports": [
                    {
                        "report_id": str(report.id),
                        "state": report.state,
                        "artifact_id": str(artifact.id) if artifact else None,
                        "sha256": artifact.sha256 if artifact else None,
                    }
                    for report, artifact in reports
                ],
                "repositories": [
                    {
                        "execution_id": str(link.execution_id),
                        "repository_id": str(link.repository_id),
                        "before_sha": link.before_sha,
                        "after_sha": link.after_sha,
                    }
                    for link in repositories
                ],
                "audit_events": [
                    {
                        "event_id": item.event_id,
                        "event_type": item.event_type,
                        "payload_version": item.payload_version,
                        "payload": redact(item.payload),
                        "occurred_at": item.created_at.isoformat(),
                    }
                    for item in audit_events
                ],
                "executions": [
                    {
                        "id": str(item.id),
                        "state": item.state,
                        "heartbeat_at": item.heartbeat_at.isoformat()
                        if item.heartbeat_at
                        else None,
                    }
                    for item in executions
                ],
                "events": [
                    {
                        "id": str(event.id),
                        "execution_id": str(event.execution_id),
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "payload_version": event.payload_version,
                        "payload": redact(event.payload),
                        "occurred_at": event.created_at.isoformat(),
                    }
                    for event in events
                ],
                "test_runs": [
                    {
                        "id": str(run.id),
                        "execution_id": str(run.execution_id),
                        "repository_id": str(run.repository_id) if run.repository_id else None,
                        "command": redact(run.command),
                        "outcome": run.outcome,
                        "returncode": run.returncode,
                    }
                    for run in runs
                ],
                "tools": [
                    {"tool": tool.tool, "input": redact(tool.input), "output": redact(tool.output)}
                    for tool in tools
                ],
                "approvals": [
                    {"id": str(item.id), "scope": redact(item.scope), "approved": item.approved}
                    for item in approvals
                ],
            }
