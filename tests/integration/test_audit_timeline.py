import json

import pytest

from qharness.tasks.audit import AuditService


def test_timeline_keeps_repository_approval_and_test_evidence(approved_task):
    service, task = approved_task
    execution = service.create_execution(task.id)
    service.claim_next("audit-worker")
    repository_id = task.required_gates[0]["repository_id"]
    import uuid

    service.record_test(
        execution.id,
        uuid.UUID(repository_id),
        json.dumps(["python", "tests.py"]),
        1,
        "api_key=do-not-expose",
        "failed",
    )
    service.finish_execution(execution.id, "FAILED", reason="tests failed")
    timeline = AuditService(service.database).task_timeline(task.project_id, task.id)
    assert timeline["state"] == "BLOCKED"
    assert timeline["approvals"][0]["approved"] is True
    assert timeline["test_runs"][0]["outcome"] == "FAILED"
    assert timeline["repositories"][0]["repository_id"] == repository_id
    assert timeline["repositories"][0]["execution_id"] == str(execution.id)
    assert timeline["audit_events"][-1]["event_type"] == "TASK_BLOCKED"
    assert [event["event_id"] for event in timeline["audit_events"]] == sorted(
        event["event_id"] for event in timeline["audit_events"]
    )
    assert all(event["payload_version"] == 1 for event in timeline["events"])
    assert "do-not-expose" not in json.dumps(timeline)
    with pytest.raises(ValueError, match="not running"):
        service.finish_execution(execution.id, "SUCCEEDED")


def test_notifications_have_monotonic_cursor_and_project_isolation(approved_task, tmp_path):
    from qharness.projects.service import ProjectService

    service, task = approved_task
    audit = AuditService(service.database)
    other = ProjectService(service.database).create("Other", tmp_path / "other")
    for kind in ("SPEC_READY", "TEST_FAILED", "REPORT_READY", "TASK_COMPLETED"):
        audit.append(task.project_id, kind, {"api_key": "hidden"}, task_id=task.id)
    notifications = audit.notifications(task.project_id)
    assert len(notifications) == 5
    assert audit.notifications(other.id) == []
    cursor = notifications[1]["event_id"]
    assert audit.notifications(task.project_id, cursor, 2) == notifications[2:4]
    assert "hidden" not in json.dumps(notifications)
    with pytest.raises(ValueError, match="not found"):
        audit.task_timeline(other.id, task.id)
