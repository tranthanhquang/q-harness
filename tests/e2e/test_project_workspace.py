import os
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.projects.service import ProjectService


@pytest.mark.e2e
def test_two_projects_three_repositories(tmp_path: Path) -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    service = ProjectService(database)
    roots = [tmp_path / name for name in ("api", "web", "docs")]
    for root in roots:
        root.mkdir()
    first = service.create("first", tmp_path / "workspace-a")
    second = service.create("second", tmp_path / "workspace-b")
    service.add_repository(first.id, roots[0], "api", "api")
    service.add_repository(first.id, roots[1], "web", "web")
    service.add_repository(second.id, roots[2], "docs", "docs")
    assert len(service.repositories(first.id)) == 2
    assert len(service.repositories(second.id)) == 1
    assert service.discover(tmp_path / "workspace-a").id == first.id
