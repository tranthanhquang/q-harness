from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    read_only: tuple[Path, ...] = ()
    writable: tuple[Path, ...] = ()
    timeout_seconds: int = 300
    memory: str = "1g"
    cpus: str = "1.0"


class DockerRunner:
    def __init__(self, image: str) -> None:
        self.image = image

    def command(self, spec: SandboxSpec, shell_command: str = "true") -> list[str]:
        command = [
            shutil.which("docker") or "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10001:10001",
            "--memory",
            spec.memory,
            "--cpus",
            spec.cpus,
            "--pids-limit",
            "256",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",  # noqa: S108 - container tmpfs, not host storage
        ]
        for path in spec.read_only:
            command.extend(
                ("--mount", f"type=bind,src={path.resolve()},dst=/workspace/{path.name},readonly")
            )
        for path in spec.writable:
            command.extend(
                ("--mount", f"type=bind,src={path.resolve()},dst=/workspace/{path.name}")
            )
        return [*command, self.image, shell_command]

    def run(
        self,
        spec: SandboxSpec,
        shell_command: str,
        *,
        keep_running: Callable[[], bool] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        name = f"qh-{uuid.uuid4().hex}"
        command = self.command(spec, shell_command)
        command[2:2] = ["--name", name, "--label", "q-harness.managed=true"]
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            # The shell command runs inside the scoped container; no host shell is used.
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)  # noqa: S603
            deadline = time.monotonic() + spec.timeout_seconds
            try:
                while True:
                    if keep_running is not None and not keep_running():
                        raise InterruptedError("execution cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, spec.timeout_seconds)
                    if any(
                        os.fstat(stream.fileno()).st_size > 1_000_000 for stream in (stdout, stderr)
                    ):
                        raise ValueError("sandbox output limit exceeded")
                    try:
                        process.wait(timeout=min(0.1, remaining))
                        if any(
                            os.fstat(stream.fileno()).st_size > 1_000_000
                            for stream in (stdout, stderr)
                        ):
                            raise ValueError("sandbox output limit exceeded")
                        stdout.seek(0)
                        stderr.seek(0)
                        return subprocess.CompletedProcess(
                            command,
                            process.returncode,
                            stdout.read().decode("utf-8", errors="replace"),
                            stderr.read().decode("utf-8", errors="replace"),
                        )
                    except subprocess.TimeoutExpired:
                        continue
            finally:
                try:
                    subprocess.run(  # noqa: S603 - fixed Docker cleanup arguments
                        [command[0], "rm", "--force", name],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)
