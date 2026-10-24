import json

from sqlalchemy import select

from qharness.tasks.audit import AuditService
from qharness.tasks.models import WorkItem
from qharness.tasks.service import TaskService


def test_credentials_are_redacted_before_task_persistence(approved_task):
    service, approved = approved_task
    task = TaskService(service.database).create(
        approved.project_id, "Fix API with api_key=private-credential-value"
    )
    with service.database.transaction() as session:
        item = session.get(WorkItem, task.work_item_id)
        assert "private-credential-value" not in item.request
        assert "[REDACTED]" in item.request
        persisted = list(session.scalars(select(WorkItem.request)))
        assert "private-credential-value" not in json.dumps(persisted)
    assert "private-credential-value" not in json.dumps(
        AuditService(service.database).task_timeline(task.project_id, task.id)
    )


def test_scope_escalation_cannot_grant_network_or_credentials(approved_task):
    import pytest

    from qharness.projects.service import ProjectService
    from qharness.security.policy import ApprovalScope, ScopeEscalation

    service, task = approved_task
    repository = ProjectService(service.database).repositories(task.project_id)[0]
    from pathlib import Path

    scope = ApprovalScope((Path(repository.canonical_path),), ("python",), False)
    with pytest.raises(ScopeEscalation):
        scope.require_network()
    with pytest.raises(ScopeEscalation):
        scope.require_path(Path(repository.canonical_path) / ".env")
