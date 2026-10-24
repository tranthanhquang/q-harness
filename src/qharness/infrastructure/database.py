from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(url, pool_pre_ping=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        session = self.sessions()
        try:
            with session.begin():
                yield session
        finally:
            session.close()

    def healthy(self) -> bool:
        try:
            with self.engine.connect() as connection:
                return bool(connection.scalar(text("SELECT 1")) == 1)
        except Exception:
            return False

    def create_schema(self) -> None:
        from qharness.infrastructure import idempotency  # noqa: F401
        from qharness.knowledge import models as knowledge_models  # noqa: F401
        from qharness.projects import models as project_models  # noqa: F401
        from qharness.reports import models as report_models  # noqa: F401
        from qharness.skills import models as skill_models  # noqa: F401
        from qharness.tasks import models as task_models  # noqa: F401

        Base.metadata.create_all(self.engine)

    def schema_version(self) -> str | None:
        with self.engine.connect() as connection:
            exists = connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            if not exists:
                return None
            value = connection.scalar(text("SELECT version_num FROM alembic_version"))
            return str(value) if value is not None else None
