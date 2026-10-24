import os
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.projects.service import DuplicateRepository, ProjectService


@pytest.mark.integration
def test_repository_path_is_globally_unique(tmp_path: Path) -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    service = ProjectService(database)
    repository = tmp_path / "repo"
    repository.mkdir()
    first = service.create("first", tmp_path / "first")
    second = service.create("second", tmp_path / "second")
    service.add_repository(first.id, repository, "api", "repo")
    with pytest.raises(DuplicateRepository):
        service.add_repository(second.id, repository, "api", "repo")
