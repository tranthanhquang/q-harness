from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
_SECRET_KEYS = re.compile(r"(?:authorization|api[_-]?key|token|password|secret|credential)", re.I)
_INLINE = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+|(?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s,;]+)"
)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _SECRET_KEYS.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _INLINE.sub(lambda match: f"{match.group(1)}{REDACTED}", value)
    return value
