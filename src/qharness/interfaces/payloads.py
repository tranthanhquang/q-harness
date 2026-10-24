from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CreateProject(Payload):
    name: str = Field(min_length=1, max_length=120)
    workspace_root: str = Field(min_length=1, max_length=4096)
    stable_key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{1,63}$")


class AddRepository(Payload):
    path: str = Field(min_length=1, max_length=4096)
    role: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    access_mode: Literal["READ_ONLY", "READ_WRITE"] = "READ_WRITE"


class Search(Payload):
    query: str = Field(min_length=1, max_length=1000)
    repository_ids: list[str] | None = Field(default=None, max_length=20)
    limit: int = Field(default=10, ge=1, le=50)

    def identities(self) -> list[uuid.UUID] | None:
        return [uuid.UUID(item) for item in self.repository_ids] if self.repository_ids else None


class Index(Payload):
    mode: Literal["incremental", "full"] = "incremental"
    repository_ids: list[str] | None = Field(default=None, max_length=20)


class Ask(Payload):
    question: str = Field(min_length=1, max_length=10000)


class CreateTask(Payload):
    request: str = Field(min_length=1, max_length=20000)


class TaskAction(Payload):
    action: Literal["cancel", "continue"]
    decision: str | None = Field(default=None, max_length=1000)


class GenerateReport(Payload):
    template_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    version: str | None = Field(default=None, max_length=50)
    scope: dict[str, Any] | None = None
