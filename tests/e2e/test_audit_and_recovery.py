import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from qharness.knowledge.models import IndexVersion
from qharness.tasks.audit import AuditService


@pytest.mark.parametrize("outcome", ["SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED"])
def test_execution_outcomes_remain_auditable_and_never_resume(approved_task, outcome):
    service, task = approved_task
    execution = service.create_execution(task.id)
    service.claim_next("audit-worker")
    repository_id = uuid.UUID(task.required_gates[0]["repository_id"])
    with service.database.transaction() as session:
        session.add(
            IndexVersion(project_id=task.project_id, repository_id=repository_id, state="COMPLETE")
        )
    if outcome in {"SUCCEEDED", "FAILED"}:
        for gate in task.required_gates:
            service.record_test(
                execution.id,
                repository_id,
                json.dumps(gate["command"]),
                0 if outcome == "SUCCEEDED" else 1,
                "evidence",
                "",
            )
        service.finish_execution(execution.id, outcome)
    elif outcome == "CANCELLED":
        service.cancel(task.id)
        service.finish_execution(execution.id, "CANCELLED")
    else:
        from qharness.tasks.recovery import reconcile_startup

        with service.database.transaction() as session:
            running = session.get(type(execution), execution.id)
            running.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        assert reconcile_startup(service) == [execution.id]
        assert reconcile_startup(service) == []
        with service.database.transaction() as session:
            assert session.scalar(select(IndexVersion.state)) == "STALE"
    timeline = AuditService(service.database).task_timeline(task.project_id, task.id)
    assert timeline["executions"][0]["state"] == outcome
    assert timeline["events"][-1]["event_type"] == f"EXECUTION_{outcome}"
    assert timeline["state"] == {"SUCCEEDED": "COMPLETED", "CANCELLED": "CANCELLED"}.get(
        outcome, "BLOCKED"
    )
    assert service.claim_next("new-worker") is None
