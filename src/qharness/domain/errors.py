from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class HarnessError(Exception):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class NotFound(HarnessError):
    def __init__(self, message: str = "resource not found") -> None:
        super().__init__("NOT_FOUND", message)


class ScopeDenied(HarnessError):
    def __init__(self, message: str = "project scope denied") -> None:
        super().__init__("PROJECT_SCOPE_DENIED", message)


class StateConflict(HarnessError):
    def __init__(self, message: str) -> None:
        super().__init__("STATE_CONFLICT", message)
