from __future__ import annotations

import builtins
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from qharness.domain.states import TaskState, require_transition
from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyStore
from qharness.projects.models import Repository
from qharness.runtime.classifier import classify
from qharness.tasks.approvals import validate_scope
from qharness.tasks.audit import append_audit
from qharness.tasks.models import (
    Approval,
    Execution,
    ExecutionEvent,
    ExecutionRepository,
    Task,
    TaskRepository,
    TestRun,
    WorkItem,
)


def transition(session: Session, task: Task, target: str) -> None:
    require_transition(TaskState(task.state), TaskState(target))
    task.state = target
    append_audit(session, task.project_id, f"TASK_{target}", {"state": target}, task_id=task.id)


def event(
    session: Session, execution: Execution, event_type: str, payload: dict[str, Any]
) -> ExecutionEvent:
    from qharness.security.redaction import redact

    sequence = (
        session.scalar(
            select(func.max(ExecutionEvent.sequence)).where(
                ExecutionEvent.execution_id == execution.id
            )
        )
        or 0
    )
    record = ExecutionEvent(
        execution_id=execution.id,
        sequence=sequence + 1,
        event_type=event_type,
        payload=redact(payload),
    )
    session.add(record)
    session.flush()
    return record


class TaskService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, project_id: uuid.UUID, request: str) -> Task:
        if not request.strip() or len(request) > 20_000:
            raise ValueError("task request must contain 1 to 20000 characters")
        from qharness.security.redaction import redact

        request = redact(request)
        classification = classify(request)
        with self.database.transaction() as session:
            work_item = WorkItem(
                project_id=project_id,
                request=request,
                intent=classification.intent,
                risk=classification.risk,
            )
            session.add(work_item)
            session.flush()
            sequence = session.scalar(text("SELECT nextval('task_display_sequence')"))
            task = Task(
                project_id=project_id,
                work_item_id=work_item.id,
                display_id=f"QH-T-{sequence:06d}",
                state="CREATED",
            )
            session.add(task)
            session.flush()
            transition(session, task, "ANALYZING")
            transition(session, task, "WAITING_APPROVAL")
            append_audit(
                session,
                project_id,
                "APPROVAL_REQUIRED",
                {
                    "intent": classification.intent,
                    "risk": classification.risk,
                    "document_policy": classification.document_mode,
                },
                task_id=task.id,
            )
            return task

    def list(self, project_id: uuid.UUID) -> builtins.list[Task]:
        with self.database.transaction() as session:
            return list(
                session.scalars(
                    select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
                )
            )

    def get(self, task_id: uuid.UUID) -> Task:
        with self.database.transaction() as session:
            task = session.get(Task, task_id)
            if not task:
                raise ValueError("task not found")
            return task

    def approve(self, task_id: uuid.UUID, scope: dict[str, Any]) -> Task:
        with self.database.transaction() as session:
            task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if not task or task.state != "WAITING_APPROVAL":
                raise ValueError("task is not waiting for approval")
            repositories = list(
                session.scalars(select(Repository).where(Repository.project_id == task.project_id))
            )
            normalized = validate_scope(scope, repositories)
            item = session.get(WorkItem, task.work_item_id)
            if (
                not item
                or {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[normalized["risk_ceiling"]]
                < {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[item.risk.upper()]
            ):
                raise ValueError("task risk exceeds approved ceiling")
            session.add(Approval(task_id=task.id, scope=normalized, approved=True))
            task.required_gates = [
                {
                    **gate,
                    "repository_id": str(
                        next(
                            repository.id
                            for repository in repositories
                            if Path(gate["cwd"]).is_relative_to(Path(repository.canonical_path))
                        )
                    ),
                }
                for gate in normalized["required_gates"]
            ]
            session.execute(delete(TaskRepository).where(TaskRepository.task_id == task.id))
            for repository in repositories:
                if any(
                    Path(root).is_relative_to(Path(repository.canonical_path))
                    for root in normalized["repository_paths"]
                ):
                    session.add(
                        TaskRepository(
                            project_id=task.project_id, task_id=task.id, repository_id=repository.id
                        )
                    )
            transition(session, task, "PLANNING")
            return task

    def cancel(self, task_id: uuid.UUID) -> Task:
        with self.database.transaction() as session:
            task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if not task:
                raise ValueError("task not found")
            transition(session, task, "CANCELLED")
            for execution in session.scalars(
                select(Execution).where(Execution.task_id == task_id, Execution.state == "QUEUED")
            ):
                execution.state = "CANCELLED"
                event(session, execution, "EXECUTION_CANCELLED", {})
            return task

    def continue_blocked(self, task_id: uuid.UUID) -> Task:
        with self.database.transaction() as session:
            task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if not task or task.state != "BLOCKED":
                raise ValueError("task is not blocked")
            transition(session, task, "WAITING_APPROVAL")
            append_audit(session, task.project_id, "APPROVAL_REQUIRED", {}, task_id=task.id)
            return task

    def append_event(
        self, execution_id: uuid.UUID, event_type: str, payload: dict[str, Any]
    ) -> ExecutionEvent:
        with self.database.transaction() as session:
            execution = session.scalar(
                select(Execution).where(Execution.id == execution_id).with_for_update()
            )
            if not execution:
                raise ValueError("execution not found")
            return event(session, execution, event_type, payload)

    def record_test(
        self,
        execution_id: uuid.UUID,
        repository_id: uuid.UUID,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
        *,
        cwd: str | None = None,
    ) -> None:
        from qharness.security.redaction import redact

        with self.database.transaction() as session:
            execution = session.scalar(
                select(Execution).where(Execution.id == execution_id).with_for_update()
            )
            if (
                not execution
                or execution.state != "RUNNING"
                or not session.get(ExecutionRepository, (execution_id, repository_id))
            ):
                raise ValueError("test does not belong to a running execution repository")
            outcome = "PASSED" if returncode == 0 else "FAILED"
            repository = session.get(Repository, repository_id)
            assert repository
            directory = Path(cwd or repository.canonical_path).resolve(strict=True)
            if not directory.is_relative_to(Path(repository.canonical_path)):
                raise ValueError("test directory is outside repository")
            run = TestRun(
                execution_id=execution_id,
                repository_id=repository_id,
                command=redact(command),
                outcome=outcome,
                returncode=returncode,
                stdout=redact(stdout[-20_000:]),
                stderr=redact(stderr[-20_000:]),
            )
            session.add(run)
            session.flush()
            event(
                session,
                execution,
                f"TEST_{outcome}",
                {
                    "test_run_id": str(run.id),
                    "repository_id": str(repository_id),
                    "command": run.command,
                    "outcome": outcome,
                    "cwd": str(directory),
                },
            )
            if returncode:
                append_audit(
                    session,
                    execution.project_id,
                    "TEST_FAILED",
                    {"test_run_id": str(run.id), "repository_id": str(repository_id)},
                    task_id=execution.task_id,
                )

    def create_execution(
        self, task_id: uuid.UUID, *, idempotency_key: str | None = None
    ) -> Execution:
        def reserve(session: Session) -> dict[str, Any]:
            task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if not task or task.state != "PLANNING":
                raise ValueError("task requires approval before execution")
            approval = session.scalar(
                select(Approval)
                .where(Approval.task_id == task_id, Approval.approved.is_(True))
                .order_by(Approval.created_at.desc())
            )
            if not approval:
                raise ValueError("task requires approval before execution")
            if session.scalar(
                select(Execution).where(
                    Execution.task_id == task_id, Execution.state.in_(["QUEUED", "RUNNING"])
                )
            ):
                raise ValueError("task already has an active execution")
            execution = Execution(project_id=task.project_id, task_id=task.id)
            session.add(execution)
            session.flush()
            for link in session.scalars(
                select(TaskRepository).where(TaskRepository.task_id == task.id)
            ):
                session.add(
                    ExecutionRepository(
                        project_id=task.project_id,
                        execution_id=execution.id,
                        repository_id=link.repository_id,
                    )
                )
            event(session, execution, "EXECUTION_QUEUED", {"approval_id": str(approval.id)})
            return {"id": str(execution.id)}

        if idempotency_key:
            result, _ = IdempotencyStore(self.database).run(
                f"task:{task_id}", idempotency_key, {"task_id": str(task_id)}, reserve
            )
        else:
            with self.database.transaction() as session:
                result = reserve(session)
        return self.get_execution(uuid.UUID(result["id"]))

    def claim_next(self, worker_id: str) -> Execution | None:
        with self.database.transaction() as session:
            execution = session.scalar(
                select(Execution)
                .where(Execution.state == "QUEUED")
                .order_by(Execution.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not execution:
                return None
            task = session.get(Task, execution.task_id)
            if not task or task.state != "PLANNING":
                execution.state = "CANCELLED"
                return None
            execution.state = "RUNNING"
            execution.worker_id = worker_id
            execution.heartbeat_at = datetime.now(UTC)
            transition(session, task, "IMPLEMENTING")
            event(session, execution, "EXECUTION_STARTED", {"worker_id": worker_id})
            return execution

    def heartbeat(self, execution_id: uuid.UUID) -> bool:
        with self.database.transaction() as session:
            execution = session.get(Execution, execution_id)
            if not execution or execution.state != "RUNNING":
                return False
            task = session.get(Task, execution.task_id)
            if not task or task.state == "CANCELLED":
                return False
            execution.heartbeat_at = datetime.now(UTC)
            return True

    def reconcile_stale(self, cutoff: datetime) -> builtins.list[uuid.UUID]:
        from qharness.knowledge.models import IndexVersion

        interrupted: list[uuid.UUID] = []
        with self.database.transaction() as session:
            executions = list(
                session.scalars(
                    select(Execution)
                    .where(
                        Execution.state == "RUNNING",
                        (Execution.heartbeat_at < cutoff) | Execution.heartbeat_at.is_(None),
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            for execution in executions:
                execution.state = "INTERRUPTED"
                task = session.get(Task, execution.task_id)
                if task and task.state != "CANCELLED":
                    transition(session, task, "BLOCKED")
                event(
                    session, execution, "EXECUTION_INTERRUPTED", {"worker_id": execution.worker_id}
                )
                for index in session.scalars(
                    select(IndexVersion).where(IndexVersion.project_id == execution.project_id)
                ):
                    index.state = "STALE"
                interrupted.append(execution.id)
        return interrupted

    def get_execution(self, execution_id: uuid.UUID) -> Execution:
        with self.database.transaction() as session:
            execution = session.get(Execution, execution_id)
            if not execution:
                raise ValueError("execution not found")
            return execution

    def gates_passed(self, execution_id: uuid.UUID) -> bool:
        with self.database.transaction() as session:
            execution = session.get(Execution, execution_id)
            if not execution:
                raise ValueError("execution not found")
            task = session.get(Task, execution.task_id)
            assert task
            return self._gates_passed(session, execution, task)

    @staticmethod
    def _gates_passed(session: Session, execution: Execution, task: Task) -> bool:
        repositories = set(
            session.scalars(
                select(ExecutionRepository.repository_id).where(
                    ExecutionRepository.execution_id == execution.id
                )
            )
        )
        required = {
            (uuid.UUID(gate["repository_id"]), gate["cwd"], json.dumps(gate["command"]))
            for gate in task.required_gates
            if gate["required"]
        }
        if not repositories or not repositories.issubset({key[0] for key in required}):
            return False
        evidence: dict[tuple[uuid.UUID, str, str], str] = {}
        for record in session.scalars(
            select(ExecutionEvent)
            .where(ExecutionEvent.execution_id == execution.id)
            .order_by(ExecutionEvent.sequence)
        ):
            if record.event_type == "FILE_WRITTEN":
                evidence = dict.fromkeys(evidence, "NOT_RUN")
            elif record.event_type in {"TEST_PASSED", "TEST_FAILED"}:
                run = session.get(TestRun, uuid.UUID(record.payload["test_run_id"]))
                if run and run.repository_id:
                    evidence[(run.repository_id, record.payload.get("cwd", ""), run.command)] = (
                        run.outcome
                    )
        return all(evidence.get(key) == "PASSED" for key in required)

    def finish_execution(self, execution_id: uuid.UUID, state: str, *, reason: str = "") -> None:
        with self.database.transaction() as session:
            execution = session.scalar(
                select(Execution).where(Execution.id == execution_id).with_for_update()
            )
            if not execution or execution.state != "RUNNING":
                raise ValueError("execution is not running")
            if state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                raise ValueError("invalid terminal execution state")
            task = session.get(Task, execution.task_id)
            if not task:
                raise ValueError("task not found")
            if task.state == "CANCELLED":
                state = "CANCELLED"
            if state == "SUCCEEDED":
                if not self._gates_passed(session, execution, task):
                    raise ValueError("required tests failed or NOT_RUN")
                transition(session, task, "TESTING")
                transition(session, task, "REVIEWING")
                transition(session, task, "COMPLETED")
            elif task.state != "CANCELLED":
                transition(session, task, "BLOCKED")
            execution.state = state
            event(session, execution, f"EXECUTION_{state}", {"reason": reason})
