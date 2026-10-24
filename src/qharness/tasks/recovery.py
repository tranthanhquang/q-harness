import uuid
from datetime import UTC, datetime, timedelta

from qharness.tasks.service import TaskService


def reconcile_startup(service: TaskService, stale_seconds: int = 60) -> list[uuid.UUID]:
    return service.reconcile_stale(datetime.now(UTC) - timedelta(seconds=stale_seconds))
