from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from typing import Any

from qharness.security.redaction import redact

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def ensure_correlation_id(value: str | None = None) -> str:
    result = value or correlation_id.get() or str(uuid.uuid4())
    correlation_id.set(result)
    return result


def log_event(logger: logging.Logger, event: str, **data: Any) -> None:
    payload = {"event": event, "correlation_id": ensure_correlation_id(), **redact(data)}
    logger.info(json.dumps(payload, sort_keys=True, default=str))
