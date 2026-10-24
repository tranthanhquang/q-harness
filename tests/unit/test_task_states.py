import pytest

from qharness.domain.states import TaskState, require_transition


def test_task_state_machine_accepts_only_declared_transitions() -> None:
    require_transition(TaskState.CREATED, TaskState.ANALYZING)
    with pytest.raises(ValueError):
        require_transition(TaskState.CREATED, TaskState.COMPLETED)
