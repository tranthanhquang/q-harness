import subprocess
from pathlib import Path

import pytest

from qharness.infrastructure.sandbox import DockerRunner, SandboxSpec


@pytest.mark.security
def test_sandbox_command_is_non_root_read_only_networkless_and_bounded(tmp_path: Path) -> None:
    command = DockerRunner("q-harness-sandbox:dev").command(
        SandboxSpec(read_only=(tmp_path,), writable=(tmp_path / "work",), timeout_seconds=30)
    )
    joined = " ".join(command)
    for required in (
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "--user 10001:10001",
        "--memory",
        "--cpus",
    ):
        assert required in joined


@pytest.mark.security
def test_actual_sandbox_denies_host_network_and_root_writes(tmp_path: Path) -> None:
    result = DockerRunner("q-harness-sandbox:dev").run(
        SandboxSpec(timeout_seconds=20),
        'python -c "import os,socket; assert os.getuid()==10001; '
        "assert socket.socket().connect_ex(('1.1.1.1',443))!=0; "
        "assert not os.access('/etc',os.W_OK)\"",
    )
    assert result.returncode == 0, result.stderr


def test_sandbox_timeout_and_output_limit() -> None:
    runner = DockerRunner("q-harness-sandbox:dev")
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run(SandboxSpec(timeout_seconds=1), "python -c 'import time; time.sleep(60)'")
    with pytest.raises(ValueError, match="output limit"):
        runner.run(SandboxSpec(timeout_seconds=10), "python -c 'print(\"x\"*2000000)'")
