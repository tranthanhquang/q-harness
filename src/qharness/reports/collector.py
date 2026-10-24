from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from qharness.infrastructure.database import Database
from qharness.knowledge.models import SourceFile
from qharness.projects.models import Project, Repository
from qharness.reports.models import Artifact
from qharness.tasks.models import Execution, Task, TaskRepository, TestRun, WorkItem


class ReportScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class ReportCollector:
    def __init__(self, database: Database) -> None:
        self.database = database

    def collect(
        self, project_id: uuid.UUID, allowed_sources: list[str], scope: ReportScope | None = None
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        data: dict[str, Any] = {}
        provenance: list[dict[str, str]] = []
        task_ids = scope.task_ids if scope else None
        with self.database.transaction() as session:
            if not session.get(Project, project_id):
                raise ValueError("project not found")
            if task_ids is not None:
                owned = set(session.scalars(select(Task.id).where(Task.project_id == project_id)))
                if set(task_ids) - owned:
                    raise PermissionError("report task scope is outside Project")
                if "artifacts" in allowed_sources:
                    raise ValueError("artifact collection does not support task scope")
            tasks = select(Task).where(Task.project_id == project_id)
            if task_ids is not None:
                tasks = tasks.where(Task.id.in_(task_ids))
            selected_tasks = tasks.with_only_columns(Task.id)
            repositories = select(Repository).where(Repository.project_id == project_id)
            if task_ids is not None:
                repositories = repositories.where(
                    Repository.id.in_(
                        select(TaskRepository.repository_id).where(
                            TaskRepository.task_id.in_(selected_tasks)
                        )
                    )
                )
            selected_repositories = repositories.with_only_columns(Repository.id)
            if "project" in allowed_sources:
                project = session.get(Project, project_id)
                if not project:
                    raise ValueError("project not found")
                data["project_name"] = project.name
                provenance.append({"source": "project", "id": str(project.id)})
            if "repositories" in allowed_sources:
                data["repositories"] = [
                    {"id": str(repo.id), "name": repo.name, "role": repo.role}
                    for repo in session.scalars(repositories.order_by(Repository.name))
                ]
                provenance.extend(
                    {"source": "repositories", "id": item["id"]} for item in data["repositories"]
                )
            if "knowledge" in allowed_sources:
                sources = list(
                    session.scalars(
                        select(SourceFile).where(
                            SourceFile.project_id == project_id,
                            SourceFile.repository_id.in_(selected_repositories),
                        )
                    )
                )
                data["knowledge"] = [
                    {
                        "path": item.path,
                        "repository_id": str(item.repository_id),
                        "content_hash": item.content_hash,
                        "indexed_at": item.indexed_at.isoformat(),
                    }
                    for item in sources
                ]
                provenance.extend(
                    {"source": "knowledge", "id": str(item.id), "content_hash": item.content_hash}
                    for item in sources
                )
            if "work_items" in allowed_sources:
                items = list(
                    session.scalars(
                        select(WorkItem).where(
                            WorkItem.project_id == project_id,
                            WorkItem.id.in_(tasks.with_only_columns(Task.work_item_id)),
                        )
                    )
                )
                data["work_items"] = [
                    {"id": str(item.id), "intent": item.intent, "risk": item.risk} for item in items
                ]
                provenance.extend({"source": "work_items", "id": str(item.id)} for item in items)
            if "artifacts" in allowed_sources:
                artifacts = list(
                    session.scalars(select(Artifact).where(Artifact.project_id == project_id))
                )
                data["artifacts"] = [
                    {"id": str(item.id), "sha256": item.sha256, "media_type": item.media_type}
                    for item in artifacts
                ]
                provenance.extend(
                    {"source": "artifacts", "id": str(item.id), "sha256": item.sha256}
                    for item in artifacts
                )
            if "tasks" in allowed_sources:
                data["task_count"] = (
                    session.scalar(select(func.count()).select_from(tasks.subquery())) or 0
                )
                provenance.append({"source": "tasks", "project_id": str(project_id)})
                data["tasks"] = [
                    {"id": str(task.id), "state": task.state, "display_id": task.display_id}
                    for task in session.scalars(tasks.order_by(Task.created_at))
                ]
                provenance.extend({"source": "tasks", "id": item["id"]} for item in data["tasks"])
            if "executions" in allowed_sources:
                data["executions"] = [
                    {"id": str(item.id), "state": item.state}
                    for item in session.scalars(
                        select(Execution).where(
                            Execution.project_id == project_id,
                            Execution.task_id.in_(selected_tasks),
                        )
                    )
                ]
                provenance.extend(
                    {"source": "executions", "id": item["id"]} for item in data["executions"]
                )
            if "test_runs" in allowed_sources:
                runs = list(
                    session.scalars(
                        select(TestRun)
                        .join(Execution, TestRun.execution_id == Execution.id)
                        .where(
                            Execution.project_id == project_id,
                            Execution.task_id.in_(selected_tasks),
                        )
                    )
                )
                data["test_runs"] = [
                    {
                        "id": str(run.id),
                        "outcome": run.outcome,
                        "repository_id": str(run.repository_id) if run.repository_id else None,
                    }
                    for run in runs
                ]
                provenance.extend({"source": "test_runs", "id": str(run.id)} for run in runs)
                if runs:
                    for outcome in ("PASSED", "FAILED", "NOT_RUN"):
                        data[f"test_{outcome.lower()}"] = sum(
                            run.outcome == outcome for run in runs
                        )
                    data["test_total"] = len(runs)
        return data, provenance
