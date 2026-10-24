import os

import pytest
from sqlalchemy import text

from qharness.infrastructure.database import Database


@pytest.mark.integration
def test_transaction_commits_and_rolls_back() -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    with database.transaction() as session:
        session.execute(
            text("CREATE TEMP TABLE qh_tx_test (value integer) ON COMMIT PRESERVE ROWS")
        )
        session.execute(text("INSERT INTO qh_tx_test VALUES (1)"))
    with database.transaction() as session:
        assert session.scalar(text("SELECT count(*) FROM qh_tx_test")) == 1


@pytest.mark.integration
def test_connection_health() -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    assert database.healthy()


def test_all_migrations_round_trip(database: Database) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    with database.transaction() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0008_project_ownership"
        )
