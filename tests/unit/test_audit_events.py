from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from qharness.infrastructure.database import Database
from qharness.projects.service import ProjectService
from qharness.tasks.service import TaskService


def test_audit_events_are_redacted_and_database_immutable(
    database: Database, tmp_path: Path
) -> None:
    project = ProjectService(database).create("Audit", tmp_path)
    task = TaskService(database).create(project.id, "Fix audit")
    from qharness.tasks.audit import AuditService

    audit = AuditService(database)
    event_id = audit.append(project.id, "TEST_FAILED", {"api_key": "secret"}, task_id=task.id)
    events = audit.notifications(project.id)
    assert (
        next(event for event in events if event["event_type"] == "TEST_FAILED")["payload"][
            "api_key"
        ]
        == "[REDACTED]"
    )
    with pytest.raises(DBAPIError), database.transaction() as session:
        session.execute(
            text("UPDATE audit_events SET event_type='TAMPERED' WHERE id=:id"), {"id": event_id}
        )
    with pytest.raises(DBAPIError), database.transaction() as session:
        session.execute(text("DELETE FROM audit_events WHERE id=:id"), {"id": event_id})
