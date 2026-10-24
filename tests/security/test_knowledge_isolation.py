import os
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.search import KnowledgeSearch
from qharness.projects.service import ProjectService


@pytest.mark.security
def test_search_is_project_scoped_and_secrets_are_excluded(tmp_path: Path) -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    projects = ProjectService(database)
    project_a = projects.create("search-a", tmp_path / "workspace-a")
    project_b = projects.create("search-b", tmp_path / "workspace-b")
    root = tmp_path / "repo-b"
    root.mkdir()
    (root / "only_b.py").write_text("needle_b = 1", encoding="utf-8")
    (root / ".env").write_text("SECRET_NEEDLE=never", encoding="utf-8")
    repository = projects.add_repository(project_b.id, root, "api", "api")
    KnowledgeIndexer(database).index_repository(project_b.id, repository.id, root)
    search = KnowledgeSearch(database)
    assert search.search(project_a.id, "needle_b") == []
    assert search.search(project_b.id, "SECRET_NEEDLE") == []
