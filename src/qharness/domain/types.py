from __future__ import annotations

import uuid
from dataclasses import dataclass


def new_id() -> uuid.UUID:
    return uuid.uuid4()


@dataclass(frozen=True, slots=True)
class DisplayId:
    prefix: str
    sequence: int

    def __str__(self) -> str:
        return f"{self.prefix}-{self.sequence:06d}"
