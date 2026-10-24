from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from qharness.projects.models import Repository
from qharness.security.policy import ApprovalScope


class GatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=100)
    cwd: str = Field(min_length=1, max_length=4096)
    command: list[str] = Field(min_length=1, max_length=100)
    required: bool = True


class ScopePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    repository_paths: list[str] = Field(min_length=1, max_length=20)
    tools: list[Literal["read", "write", "search", "test"]] = Field(min_length=1, max_length=4)
    commands: list[str] = Field(min_length=1, max_length=20)
    network: bool = False
    credential_names: list[str] = Field(max_length=0)
    risk_ceiling: Literal["LOW", "MEDIUM", "HIGH"]
    required_gates: list[GatePayload] = Field(default_factory=list, max_length=100)


def validate_scope(payload: dict[str, Any], repositories: list[Repository]) -> dict[str, Any]:
    scope = ScopePayload.model_validate(payload)
    if scope.network:
        raise ValueError("network-enabled executions are not supported")
    if any(
        command not in {"python", "pytest", "node", "npm", "git", "rg"}
        for command in scope.commands
    ):
        raise ValueError("unsupported command in approval")
    canonical: list[str] = []
    for value in scope.repository_paths:
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_dir() or not any(
            path.is_relative_to(Path(repository.canonical_path))
            and repository.access_mode == "READ_WRITE"
            for repository in repositories
        ):
            raise ValueError("approval path is outside registered Project repositories")
        canonical.append(str(path))
    normalized = {**scope.model_dump(), "repository_paths": list(dict.fromkeys(canonical))}
    policy = scope_from_payload(normalized)
    names: set[str] = set()
    for gate in normalized["required_gates"]:
        if gate["name"] in names:
            raise ValueError("gate names must be unique")
        names.add(gate["name"])
        cwd = policy.require_path(Path(gate["cwd"]))
        if not cwd.is_dir():
            raise ValueError("gate working directory must exist")
        policy.require_command(tuple(gate["command"]))
        policy.require_tool("test")
        gate["cwd"] = str(cwd)
    return normalized


def scope_from_payload(payload: dict[str, Any]) -> ApprovalScope:
    return ApprovalScope(
        roots=tuple(Path(value) for value in payload["repository_paths"]),
        commands=tuple(payload["commands"]),
        network=payload["network"],
        tools=tuple(payload["tools"]),
    )
