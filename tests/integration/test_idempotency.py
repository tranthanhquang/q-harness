import os

import pytest

from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyConflict, IdempotencyStore


@pytest.mark.integration
def test_idempotency_replays_same_request_and_rejects_different_request() -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    store = IdempotencyStore(database)
    first = store.remember("scope", "key", {"value": 1}, {"id": "result"})
    assert store.remember("scope", "key", {"value": 1}, {"id": "ignored"}) == first
    with pytest.raises(IdempotencyConflict):
        store.remember("scope", "key", {"value": 2}, {"id": "other"})
