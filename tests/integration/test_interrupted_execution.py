from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.integration
def test_stale_execution_is_interrupted_and_not_resumed(approved_task) -> None:
    service, task = approved_task
    execution = service.create_execution(task.id)
    service.claim_next("dead-worker")
    assert execution.id in service.reconcile_stale(datetime.now(UTC) + timedelta(minutes=10))
    assert service.get_execution(execution.id).state == "INTERRUPTED"
    assert service.get(task.id).state == "BLOCKED"
    assert service.claim_next("new-worker") is None
