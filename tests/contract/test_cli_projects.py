import json

from typer.testing import CliRunner

from qharness.interfaces.cli import app


def test_project_help_exposes_contract_commands() -> None:
    result = CliRunner().invoke(app, ["project", "--help"])
    assert result.exit_code == 0
    for command in ("add", "list", "use", "status"):
        assert command in result.stdout


def test_init_requires_name_and_workspace() -> None:
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 2


def test_cli_json_envelopes_optional_repository_name_and_shared_status(database, tmp_path):
    from qharness.interfaces.mcp import MCPToolFacade
    from qharness.projects.service import ProjectService

    projects = ProjectService(database)
    project = projects.create("CLI", tmp_path / "workspace")
    root = tmp_path / "repository"
    root.mkdir()
    runner = CliRunner()
    args = ["--project", str(project.id)]
    result = runner.invoke(app, [*args, "project", "add", str(root), "--role", "api", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["data"]["name"] == "repository"
    result = runner.invoke(app, [*args, "project", "status", "--json"])
    envelope = json.loads(result.stdout)
    assert envelope["ok"] and envelope["error"] is None and envelope["correlation_id"]
    assert envelope["data"] == MCPToolFacade(project.id, database).project_get(project.id)
    result = runner.invoke(app, [*args, "project", "add", str(root), "--role", "api", "--json"])
    assert result.exit_code == 5
    assert json.loads(result.stdout)["error"]["code"] == "STATE_CONFLICT"


def test_cli_cross_project_actions_are_denied_before_mutation(database, tmp_path):
    from qharness.projects.service import ProjectService
    from qharness.tasks.service import TaskService

    projects = ProjectService(database)
    allowed = projects.create("Allowed", tmp_path / "allowed")
    other = projects.create("Other", tmp_path / "other")
    tasks = TaskService(database)
    task = tasks.create(other.id, "Fix other project")
    result = CliRunner().invoke(
        app, ["--project", str(allowed.id), "task", "cancel", str(task.id), "--json"]
    )
    assert result.exit_code == 3, result.output
    assert json.loads(result.stdout)["error"]["code"] == "PROJECT_SCOPE_DENIED"
    assert tasks.get(task.id).state == "WAITING_APPROVAL"
