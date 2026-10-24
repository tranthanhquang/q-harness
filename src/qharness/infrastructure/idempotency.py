from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from qharness.infrastructure.database import Base, Database


class IdempotencyConflict(ValueError):
    pass


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


def _fingerprint(request: Any) -> str:
    encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class IdempotencyStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def remember(
        self, scope: str, key: str, request: Any, response: dict[str, Any]
    ) -> dict[str, Any]:
        return self.run(scope, key, request, lambda _: response)[0]

    def run(
        self, scope: str, key: str, request: Any, operation: Callable[[Session], dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        if not key or len(key) > 128:
            raise ValueError("idempotency key must contain 1 to 128 characters")
        fingerprint = _fingerprint(request)
        with self.database.transaction() as session:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                {"identity": _fingerprint([scope, key])},
            )
            existing = session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.scope == scope,
                    IdempotencyRecord.key == key,
                )
            )
            if existing:
                if existing.request_hash != fingerprint:
                    raise IdempotencyConflict("same idempotency key used for a different request")
                return existing.response, False
            response = operation(session)
            session.add(
                IdempotencyRecord(
                    scope=scope,
                    key=key,
                    request_hash=fingerprint,
                    response=response,
                )
            )
        return response, True

    def replay(self, scope: str, key: str, request: Any) -> dict[str, Any] | None:
        fingerprint = _fingerprint(request)
        with self.database.transaction() as session:
            existing = session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.scope == scope,
                    IdempotencyRecord.key == key,
                )
            )
            if not existing:
                return None
            if existing.request_hash != fingerprint:
                raise IdempotencyConflict("same idempotency key used for a different request")
            return existing.response
