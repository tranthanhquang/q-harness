import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.interfaces.worker import process_execution
from qharness.projects.service import ProjectService
from qharness.tasks.service import TaskService


class ScriptedProvider:
    def __init__(self, actions: list[dict]) -> None:
        self.actions = iter(actions)

    def respond(self, instructions: str, input: str, tools: list[dict] | None = None) -> str:
        return json.dumps(next(self.actions))


def test_worker_forwards_custom_provider_endpoint(approved_task, monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import Mock

    monkeypatch.setenv("QH_MODEL", "provider/model-name")
    monkeypatch.setenv("OPENAI_API_KEY", "test-provider-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gateway.example/api/v1")
    provider = Mock(return_value=ScriptedProvider([{"tool": "finish"}]))
    monkeypatch.setattr("qharness.interfaces.worker.OpenAIResponsesProvider", provider)
    service, task = approved_task
    service.create_execution(task.id)
    execution = service.claim_next("test-worker")
    assert execution
    process_execution(service, execution)
    provider.assert_called_once_with(
        "provider/model-name", "test-provider-key", base_url="https://gateway.example/api/v1"
    )


@pytest.mark.e2e
def test_worker_runs_two_repositories_and_persists_real_gates(
    database: Database, tmp_path: Path
) -> None:
    projects, tasks = ProjectService(database), TaskService(database)
    project = projects.create("Coding", tmp_path / "workspace")
    actions: list[dict] = []
    test_actions: list[dict] = []
    roots: list[str] = []
    for name in ("api", "web"):
        root = tmp_path / name
        root.mkdir()
        (root / "value.py").write_text("VALUE = 1\n")
        subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@localhost",
                "commit",
                "-m",
                "fixture",
            ],
            check=True,
            capture_output=True,
        )
        projects.add_repository(project.id, root, name, name)
        roots.append(str(root))
        actions.extend(
            [
                {"tool": "read", "path": str(root / "value.py")},
                {
                    "tool": "write",
                    "path": str(root / "value.py"),
                    "content": "VALUE = 2\n",
                    "expected_sha256": hashlib.sha256(b"VALUE = 1\n").hexdigest(),
                },
            ]
        )
        test_actions.append(
            {
                "tool": "test",
                "cwd": str(root),
                "command": ["python", "-c", "from value import VALUE; assert VALUE == 2"],
            }
        )
    actions.extend(test_actions)
    actions.append({"tool": "finish"})
    task = tasks.create(project.id, "Fix values in API and web")
    with pytest.raises(ValueError, match="approval"):
        tasks.create_execution(task.id)
    tasks.approve(
        task.id,
        {
            "repository_paths": roots,
            "commands": ["python"],
            "tools": ["read", "write", "search", "test"],
            "network": False,
            "credential_names": [],
            "risk_ceiling": "HIGH",
            "required_gates": [
                {"name": f"tests-{index}", "cwd": action["cwd"], "command": action["command"]}
                for index, action in enumerate(test_actions)
            ],
        },
    )
    execution = tasks.create_execution(task.id, idempotency_key="coding-worker-execution")
    assert (
        tasks.create_execution(task.id, idempotency_key="coding-worker-execution").id
        == execution.id
    )
    claimed = tasks.claim_next("test-worker")
    assert claimed and claimed.id == execution.id
    process_execution(tasks, claimed, ScriptedProvider(actions))
    assert tasks.get(task.id).state == "COMPLETED"
    assert tasks.get_execution(execution.id).state == "SUCCEEDED"
    from qharness.tasks.audit import AuditService

    timeline = AuditService(database).task_timeline(project.id, task.id)
    assert len(timeline["test_runs"]) == 2
    assert all(run["outcome"] == "PASSED" for run in timeline["test_runs"])
    assert all(
        item["payload"]["commit"]
        for item in timeline["events"]
        if item["event_type"].startswith("REPOSITORY_")
    )


def test_success_requires_latest_result_of_every_command_after_last_write(approved_task):
    from qharness.projects.service import ProjectService

    service, task = approved_task
    repository = ProjectService(service.database).repositories(task.project_id)[0]
    execution = service.create_execution(task.id)
    service.claim_next("test-worker")
    tests = json.dumps(["python", "tests.py"])
    smoke = json.dumps(["python", "smoke.py"])
    service.record_test(execution.id, repository.id, tests, 1, "", "failed")
    service.record_test(execution.id, repository.id, smoke, 0, "ok", "")
    with pytest.raises(ValueError, match="failed or NOT_RUN"):
        service.finish_execution(execution.id, "SUCCEEDED")
    service.record_test(execution.id, repository.id, tests, 0, "ok", "")
    service.append_event(execution.id, "FILE_WRITTEN", {"path": "source.py"})
    with pytest.raises(ValueError, match="failed or NOT_RUN"):
        service.finish_execution(execution.id, "SUCCEEDED")
    service.record_test(execution.id, repository.id, tests, 0, "ok", "")
    with pytest.raises(ValueError, match="failed or NOT_RUN"):
        service.finish_execution(execution.id, "SUCCEEDED")
    service.record_test(execution.id, repository.id, smoke, 0, "ok", "")
    service.finish_execution(execution.id, "SUCCEEDED")
    assert service.get(task.id).state == "COMPLETED"


def test_passing_unapproved_command_or_wrong_directory_cannot_replace_gates(approved_task):
    service, task = approved_task
    repository = ProjectService(service.database).repositories(task.project_id)[0]
    execution = service.create_execution(task.id)
    service.claim_next("test-worker")
    service.record_test(execution.id, repository.id, json.dumps(["python", "-V"]), 0, "", "")
    assert not service.gates_passed(execution.id)
    subdir = Path(repository.canonical_path) / "subdir"
    subdir.mkdir()
    for gate in task.required_gates:
        service.record_test(
            execution.id, repository.id, json.dumps(gate["command"]), 0, "", "", cwd=str(subdir)
        )
    with pytest.raises(ValueError, match="failed or NOT_RUN"):
        service.finish_execution(execution.id, "SUCCEEDED")
    assert service.get(task.id).state == "IMPLEMENTING"
    for gate in task.required_gates:
        service.record_test(execution.id, repository.id, json.dumps(gate["command"]), 0, "", "")
    assert service.gates_passed(execution.id)


@pytest.mark.e2e
def test_worker_cannot_complete_without_required_tests(database: Database, tmp_path: Path) -> None:
    projects, tasks = ProjectService(database), TaskService(database)
    project = projects.create("No tests", tmp_path)
    projects.add_repository(project.id, tmp_path, "api", "api")
    task = tasks.create(project.id, "Fix application")
    tasks.approve(
        task.id,
        {
            "repository_paths": [str(tmp_path)],
            "commands": ["python"],
            "tools": ["read", "write", "search", "test"],
            "network": False,
            "credential_names": [],
            "risk_ceiling": "HIGH",
        },
    )
    execution = tasks.create_execution(task.id)
    claimed = tasks.claim_next("test-worker")
    assert claimed
    process_execution(tasks, claimed, ScriptedProvider([{"tool": "finish"}]))
    assert tasks.get(task.id).state == "BLOCKED"
    assert tasks.get_execution(execution.id).state == "FAILED"
