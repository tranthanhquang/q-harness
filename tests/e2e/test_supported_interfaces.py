from fastapi.testclient import TestClient
from typer.testing import CliRunner

from qharness.interfaces.cli import app as cli_app
from qharness.interfaces.http import create_app


def test_cli_http_and_mcp_entrypoints_are_present() -> None:
    assert CliRunner().invoke(cli_app, ["ask", "--help"]).exit_code == 0
    api = create_app(token="x" * 32)
    assert any(getattr(route, "path", "") == "/mcp" for route in api.routes)
    assert TestClient(api, base_url="http://127.0.0.1").get("/healthz").status_code == 401
