from __future__ import annotations

import uuid
from pathlib import Path

import yaml


def write_project_config(workspace: Path, project_id: uuid.UUID, name: str) -> Path:
    target = workspace / ".qharness" / "project.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump({"version": 1, "project_id": str(project_id), "name": name}, sort_keys=True),
        encoding="utf-8",
    )
    return target


def read_project_id(path: Path) -> uuid.UUID:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("project_id"), str):
        raise ValueError("invalid project configuration")
    return uuid.UUID(data["project_id"])
