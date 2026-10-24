from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from qharness.infrastructure import idempotency  # noqa: F401
from qharness.infrastructure.database import Base
from qharness.knowledge import models as knowledge_models  # noqa: F401
from qharness.projects import models as project_models  # noqa: F401
from qharness.reports import models as report_models  # noqa: F401
from qharness.skills import models as skill_models  # noqa: F401
from qharness.tasks import models as task_models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option(
    "sqlalchemy.url", os.getenv("QH_DATABASE_URL", config.get_main_option("sqlalchemy.url"))
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
