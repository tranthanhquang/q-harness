from typer.testing import CliRunner

from qharness.interfaces.cli import app
from qharness.interfaces.mcp import MCPToolFacade


def test_report_interfaces_expose_list_generate_and_status() -> None:
    result = CliRunner().invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    for command in ("list", "generate", "status"):
        assert command in result.stdout
    assert "qh_report_list" in MCPToolFacade.tool_names


def test_report_cli_http_mcp_share_validated_artifacts_and_error_states(
    database, tmp_path, monkeypatch
):
    import json
    from pathlib import Path

    from fastapi.testclient import TestClient
    from openpyxl import load_workbook

    from qharness.interfaces.http import create_app
    from qharness.projects.service import ProjectService
    from qharness.reports.service import ReportService

    monkeypatch.setenv("QH_DATA_DIR", str(tmp_path / "data"))
    project = ProjectService(database).create("Report parity", tmp_path / "workspace")
    service = ReportService(database, tmp_path / "data/artifacts")
    for name in ("weekly-progress", "test-results"):
        service.register(
            Path("src/qharness/reports/templates") / name / "report.md",
            None,
            license_name="Proprietary",
            trusted=True,
        )
    args = ["--project", str(project.id)]
    runner = CliRunner()
    listed = runner.invoke(app, [*args, "report", "list", "--json"])
    assert listed.exit_code == 0
    facade = MCPToolFacade(project.id, database)
    assert json.loads(listed.stdout)["data"] == facade.report_list(project.id)["templates"]
    result = runner.invoke(
        app,
        [
            *args,
            "report",
            "generate",
            "weekly-progress",
            "--idempotency-key",
            "report-cli-parity",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    cli_report = json.loads(result.stdout)["data"]
    assert cli_report["state"] == "READY"
    with TestClient(
        create_app("x" * 32, database, allowed_project_id=project.id),
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 50000),
        headers={"Authorization": "Bearer " + "x" * 32},
    ) as client:
        prefix = f"/v1/projects/{project.id}"
        assert client.get(prefix + f"/reports/{cli_report['id']}").json() == cli_report
        generated = client.post(
            prefix + "/reports",
            json={"template_id": "test-results"},
            headers={"Idempotency-Key": "report-http-parity"},
        )
        assert generated.status_code == 202
        xlsx_report = generated.json()
        assert xlsx_report["state"] == "READY", xlsx_report
        workbook = load_workbook(xlsx_report["artifact"]["path"])
        assert workbook["Tests"]["B1"].value == "Report parity"
        assert any(item["field"] == "test_passed" for item in xlsx_report["missing_data"])
        workbook.close()
        assert (
            facade.report_generate(project.id, "test-results", "report-http-parity") == xlsx_report
        )
        status = runner.invoke(app, [*args, "report", "status", xlsx_report["id"], "--json"])
        assert json.loads(status.stdout)["data"] == xlsx_report
        report_ids = {
            item["report_id"] for item in client.get(prefix + "/notifications").json()["items"]
        }
        assert report_ids == {cli_report["id"], xlsx_report["id"]}
