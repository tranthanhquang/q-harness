import os
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.search import KnowledgeSearch
from qharness.projects.service import ProjectService


@pytest.mark.e2e
def test_sourced_search_and_one_file_refresh(tmp_path: Path) -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    projects = ProjectService(database)
    project = projects.create("workflow", tmp_path / "workspace")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "api.py").write_text("def route(): return '/health'", encoding="utf-8")
    (root / "web.ts").write_text(
        "export function callApi() { return '/health'; }", encoding="utf-8"
    )
    repository = projects.add_repository(project.id, root, "fullstack", "app")
    indexer = KnowledgeIndexer(database)
    indexer.index_repository(project.id, repository.id, root)
    assert {item.path for item in KnowledgeSearch(database).search(project.id, "health")} == {
        "api.py",
        "web.ts",
    }
    (root / "api.py").write_text("def route(): return '/ready'", encoding="utf-8")
    assert indexer.refresh_repository(project.id, repository.id, root) == [Path("api.py")]
