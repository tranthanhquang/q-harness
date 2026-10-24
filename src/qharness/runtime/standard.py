from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from qharness.runtime.tools import CommandResult, run_command, write_file
from qharness.security.policy import ApprovalScope


@dataclass(frozen=True, slots=True)
class Change:
    path: Path
    content: str
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class TestEvidence:
    command: tuple[str, ...]
    outcome: str
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    completed: bool
    tests: tuple[TestEvidence, ...]


class StandardWorkflow:
    def __init__(
        self, scope: ApprovalScope, on_sources_changed: Callable[[], None] | None = None
    ) -> None:
        self.scope = scope
        self.on_sources_changed = on_sources_changed

    def execute(
        self,
        changes: list[Change],
        tests: list[tuple[str, ...]],
        cwd: Path,
    ) -> WorkflowResult:
        try:
            for change in changes:
                write_file(self.scope, change.path, change.content, change.expected_sha256)
        finally:
            if changes and self.on_sources_changed:
                self.on_sources_changed()
        evidence: list[TestEvidence] = []
        for command in tests:
            result: CommandResult = run_command(self.scope, command, cwd)
            evidence.append(
                TestEvidence(
                    command,
                    "PASSED" if result.returncode == 0 else "FAILED",
                    result.returncode,
                    result.stdout,
                    result.stderr,
                )
            )
        return WorkflowResult(
            bool(tests) and all(item.outcome == "PASSED" for item in evidence), tuple(evidence)
        )
