import json

from qharness.infrastructure.sandbox import DockerRunner, SandboxSpec
from tests.fixtures.build import build


def test_quickstart_fixture_gates_run_in_sandbox(tmp_path):
    fixtures = build(tmp_path)
    scope = json.loads(fixtures["scope"].read_text())
    assert set(scope["repository_paths"]) == {str(fixtures[name]) for name in ("api", "web")}
    for gate in scope["required_gates"]:
        root = fixtures[gate["name"]]
        result = DockerRunner("q-harness-sandbox:dev").run(
            SandboxSpec(read_only=(root,)),
            f"cd /workspace/{root.name} && " + " ".join(gate["command"]),
        )
        assert result.returncode == 0, result.stderr
