from __future__ import annotations

import socket
import threading
import time
import uuid
from pathlib import Path

from sqlalchemy import select

from qharness.config import Settings
from qharness.infrastructure.database import Database
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.models import IndexVersion
from qharness.projects.git import inspect_repository
from qharness.projects.models import Repository
from qharness.runtime.agent import CodingAgent
from qharness.runtime.providers import ModelProvider, OpenAIResponsesProvider
from qharness.tasks.approvals import scope_from_payload
from qharness.tasks.models import Approval, Execution, ExecutionRepository, TaskRepository, WorkItem
from qharness.tasks.service import TaskService


def process_execution(
    service: TaskService, execution: Execution, provider: ModelProvider | None = None
) -> None:
    stopped = threading.Event()

    def pulse() -> None:
        while not stopped.wait(5):
            if not service.heartbeat(execution.id):
                return

    heartbeat = threading.Thread(target=pulse, daemon=True)
    heartbeat.start()
    repositories: dict[uuid.UUID, Path] = {}
    state, reason = "FAILED", "required tests NOT_RUN"
    try:
        with service.database.transaction() as session:
            task = service.get(execution.task_id)
            item = session.get(WorkItem, task.work_item_id)
            approval = session.scalar(
                select(Approval)
                .where(Approval.task_id == task.id, Approval.approved.is_(True))
                .order_by(Approval.created_at.desc())
            )
            if not item or not approval:
                raise ValueError("approval or work item missing")
            repositories = {
                repo.id: Path(repo.canonical_path)
                for repo in session.scalars(
                    select(Repository)
                    .join(TaskRepository, TaskRepository.repository_id == Repository.id)
                    .where(
                        TaskRepository.task_id == task.id, Repository.project_id == task.project_id
                    )
                )
            }
            request = item.request
            scope = scope_from_payload(approval.scope)
        if provider is None:
            settings = Settings().model_ready()
            assert settings.model and settings.openai_api_key
            provider = OpenAIResponsesProvider(
                settings.model,
                settings.openai_api_key.get_secret_value(),
                base_url=str(settings.openai_base_url) if settings.openai_base_url else None,
            )
        for repository_id, root in repositories.items():
            before = inspect_repository(root)
            with service.database.transaction() as session:
                link = session.get(ExecutionRepository, (execution.id, repository_id))
                if link:
                    link.before_sha = before.head
            service.append_event(
                execution.id,
                "REPOSITORY_BEFORE",
                {
                    "repository_id": str(repository_id),
                    "branch": before.branch,
                    "commit": before.head,
                    "dirty_fingerprint": before.fingerprint,
                },
            )
        complete = CodingAgent(
            service,
            execution,
            scope,
            repositories,
            provider,
            lambda: service.heartbeat(execution.id),
        ).run(request)
        if complete:
            state, reason = "SUCCEEDED", "all required repository tests passed"
    except InterruptedError:
        state, reason = "CANCELLED", "operator cancelled execution"
    except Exception as exc:
        reason = type(exc).__name__
        service.append_event(execution.id, "EXECUTION_ERROR", {"error_code": reason})
    finally:
        for repository_id, root in repositories.items():
            try:
                after = inspect_repository(root)
                with service.database.transaction() as session:
                    link = session.get(ExecutionRepository, (execution.id, repository_id))
                    if link:
                        link.after_sha = after.head
                service.append_event(
                    execution.id,
                    "REPOSITORY_AFTER",
                    {
                        "repository_id": str(repository_id),
                        "branch": after.branch,
                        "commit": after.head,
                        "dirty_fingerprint": after.fingerprint,
                    },
                )
                KnowledgeIndexer(service.database).refresh_repository(
                    execution.project_id, repository_id, root
                )
            except Exception:
                with service.database.transaction() as session:
                    for version in session.scalars(
                        select(IndexVersion).where(IndexVersion.repository_id == repository_id)
                    ):
                        version.state = "STALE"
                if state == "SUCCEEDED":
                    state, reason = "FAILED", "knowledge refresh failed"
        try:
            service.finish_execution(execution.id, state, reason=reason)
        finally:
            stopped.set()
            heartbeat.join(timeout=6)


def run_worker(once: bool = False) -> None:
    service = TaskService(Database(Settings().database_url))
    from qharness.tasks.recovery import reconcile_startup

    reconcile_startup(service)
    worker_id = socket.gethostname()
    while True:
        execution = service.claim_next(worker_id)
        if execution:
            process_execution(service, execution)
        if once:
            return
        if not execution:
            time.sleep(1)
