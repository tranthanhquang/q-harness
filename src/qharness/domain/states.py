from __future__ import annotations

from enum import StrEnum


class TaskState(StrEnum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ExecutionState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class ReportState(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    READY = "READY"
    VIEWED = "VIEWED"
    FAILED = "FAILED"


TASK_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset({TaskState.ANALYZING, TaskState.CANCELLED}),
    TaskState.ANALYZING: frozenset(
        {TaskState.WAITING_APPROVAL, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.WAITING_APPROVAL: frozenset({TaskState.PLANNING, TaskState.CANCELLED}),
    TaskState.PLANNING: frozenset(
        {TaskState.IMPLEMENTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.IMPLEMENTING: frozenset(
        {TaskState.TESTING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.TESTING: frozenset(
        {TaskState.REVIEWING, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.REVIEWING: frozenset(
        {TaskState.COMPLETED, TaskState.BLOCKED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.BLOCKED: frozenset(
        {TaskState.WAITING_APPROVAL, TaskState.PLANNING, TaskState.CANCELLED}
    ),
    TaskState.FAILED: frozenset(),
    TaskState.COMPLETED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


def require_transition(current: TaskState, target: TaskState) -> None:
    if target not in TASK_TRANSITIONS[current]:
        raise ValueError(f"invalid task transition: {current} -> {target}")
