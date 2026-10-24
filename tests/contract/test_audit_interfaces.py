import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from qharness.interfaces.cli import app
from qharness.interfaces.http import create_app
from qharness.tasks.audit import AuditService


def test_cli_and_http_share_task_timeline_and_notifications(approved_task):
    service, task = approved_task
    runner = CliRunner()
    expected = AuditService(service.database).task_timeline(task.project_id, task.id)
    args = ["--project", str(task.project_id)]
    result = runner.invoke(app, [*args, "task", "status", str(task.id), "--json"])
    assert result.exit_code == 0, result.output
    cli = json.loads(result.stdout)["data"]
    assert cli["approvals"] == expected["approvals"]
    assert cli["audit_events"] == expected["audit_events"]
    with TestClient(
        create_app("x" * 32, service.database, allowed_project_id=task.project_id),
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 50000),
        headers={"Authorization": "Bearer " + "x" * 32},
    ) as client:
        prefix = f"/v1/projects/{task.project_id}"
        assert client.get(prefix + f"/tasks/{task.id}").json() == cli
        notification = runner.invoke(app, [*args, "notification", "list", "--json"])
        assert notification.exit_code == 0
        assert (
            client.get(prefix + "/notifications").json()["items"]
            == (json.loads(notification.stdout)["data"])
        )
