from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from qharness.infrastructure.database import Database
from qharness.projects.git import inspect_repository
from qharness.projects.models import Project, Repository
from qharness.projects.service import ProjectService
from qharness.reports.models import Artifact, Report, ReportTemplate
from qharness.tasks.audit import AuditService
from qharness.tasks.models import Approval, Task, WorkItem


def approval_data(database: Database, task_id: uuid.UUID) -> dict[str, Any]:
    with database.transaction() as session:
        approval = session.scalar(
            select(Approval).where(Approval.task_id == task_id).order_by(Approval.created_at.desc())
        )
        if approval is None:
            raise ValueError("task has no approval")
        return {
            "approval_id": str(approval.id),
            "status": "APPROVED" if approval.approved else "REJECTED",
            "scope_hash": hashlib.sha256(
                json.dumps(approval.scope, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }


def project_data(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "stable_key": project.stable_key,
        "name": project.name,
        "workspace_root": project.workspace_path,
        "status": "ACTIVE" if Path(project.workspace_path).is_dir() else "UNAVAILABLE",
        "version": project.version,
    }


def repository_data(repository: Repository) -> dict[str, Any]:
    root = Path(repository.canonical_path)
    git = inspect_repository(root) if root.is_dir() else None
    return {
        "id": str(repository.id),
        "project_id": str(repository.project_id),
        "name": repository.name,
        "role": repository.role,
        "canonical_path": repository.canonical_path,
        "access_mode": repository.access_mode,
        "branch_name": git.branch if git else None,
        "head_sha": git.head if git else None,
        "status": "MISSING" if not git else "READY" if git.head else "NOT_GIT",
    }


def project_status(database: Database, project_id: uuid.UUID) -> dict[str, Any]:
    projects = ProjectService(database)
    with database.transaction() as session:
        blocked = (
            session.scalar(
                select(func.count(Task.id)).where(
                    Task.project_id == project_id, Task.state == "BLOCKED"
                )
            )
            or 0
        )
    return {
        "project": project_data(projects.get(project_id)),
        "repositories": [repository_data(item) for item in projects.repositories(project_id)],
        "blocked_task_count": blocked,
    }


def task_data(database: Database, project_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, Any]:
    result = AuditService(database).task_timeline(project_id, task_id)
    with database.transaction() as session:
        task = session.get(Task, task_id)
        assert task
        item = session.get(WorkItem, task.work_item_id)
        assert item
        result.update(
            title=item.request[:120],
            status=task.state,
            required_gates=task.required_gates,
            classification={"intent": item.intent, "risk": item.risk, "workflow": item.workflow},
        )
    return result


def template_data(template: ReportTemplate) -> dict[str, Any]:
    return {
        "template_id": template.template_id,
        "version": template.version,
        "scope": "project" if template.scope_project_id else "platform",
        "output_format": template.output_format.upper(),
        "checksum": template.template_sha256,
        "language": template.contract.get("language"),
        "required_permission": template.contract.get("required_permission"),
        "status": "ACTIVE" if template.trusted else "INVALID",
    }


def report_data(database: Database, report: Report) -> dict[str, Any]:
    with database.transaction() as session:
        artifact = session.get(Artifact, report.artifact_id) if report.artifact_id else None
    return {
        "id": str(report.id),
        "project_id": str(report.project_id),
        "template_id": report.template_id,
        "template_version": report.template_version,
        "state": report.state,
        "artifact": {
            "path": artifact.path,
            "media_type": artifact.media_type,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
        }
        if artifact
        else None,
        "missing_data": report.missing_data,
        "data_provenance": report.data_provenance,
        "validation": report.validation_evidence,
    }
