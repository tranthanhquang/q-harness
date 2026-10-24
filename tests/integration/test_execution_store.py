import pytest


@pytest.mark.integration
def test_execution_is_claimed_once_and_events_remain_ordered(approved_task) -> None:
    service, task = approved_task
    execution = service.create_execution(task.id)
    claimed = service.claim_next("worker-a")
    assert claimed and claimed.id == execution.id
    assert service.claim_next("worker-b") is None
    service.finish_execution(execution.id, "FAILED", reason="required gates NOT_RUN")
    from qharness.tasks.audit import AuditService

    timeline = AuditService(service.database).task_timeline(task.project_id, task.id)
    assert [event["sequence"] for event in timeline["events"]] == [1, 2, 3]
    assert service.get(task.id).state == "BLOCKED"
