import os
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.search import KnowledgeSearch, StaleKnowledge
from qharness.projects.service import ProjectService


@pytest.mark.integration
def test_full_and_incremental_index_with_provenance(tmp_path: Path) -> None:
    database = Database(
        os.environ.get(
            "QH_TEST_DATABASE_URL",
            "postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness",
        )
    )
    database.create_schema()
    projects = ProjectService(database)
    project = projects.create("knowledge", tmp_path / "workspace")
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    source = repository_root / "service.py"
    source.write_text("def health_check():\n    return 'ok'\n", encoding="utf-8")
    repository = projects.add_repository(project.id, repository_root, "api", "api")
    indexer = KnowledgeIndexer(database)
    indexer.index_repository(project.id, repository.id, repository_root)
    result = KnowledgeSearch(database).search(project.id, "health check")
    assert result and result[0].path == "service.py" and result[0].content_hash
    source.write_text("def health_check():\n    return 'changed'\n", encoding="utf-8")
    assert indexer.refresh_repository(project.id, repository.id, repository_root) == [
        Path("service.py")
    ]
    assert "changed" in KnowledgeSearch(database).search(project.id, "changed")[0].content


def test_search_refreshes_new_deleted_and_binary_files(database, tmp_path: Path) -> None:
    projects = ProjectService(database)
    project = projects.create("metadata refresh", tmp_path / "workspace")
    root = tmp_path / "repository"
    root.mkdir()
    old = root / "old.txt"
    old.write_text("oldtoken source")
    repository = projects.add_repository(project.id, root, "source", "source")
    KnowledgeIndexer(database).index_repository(project.id, repository.id, root)
    search = KnowledgeSearch(database)
    assert search.search(project.id, "oldtoken")
    new = root / "new.txt"
    new.write_text("newtoken source")
    assert search.search(project.id, "newtoken")[0].path == "new.txt"
    old.unlink()
    assert search.search(project.id, "oldtoken") == []
    new.write_bytes(b"\x00binarytoken")
    assert search.search(project.id, "newtoken") == []
    assert search.search(project.id, "binarytoken") == []


def test_search_refreshes_all_repositories_before_returning_results(database, tmp_path):
    projects = ProjectService(database)
    project = projects.create("multiple refreshes", tmp_path / "workspace")
    roots = []
    for number in range(6):
        root = tmp_path / f"repo{number}"
        root.mkdir()
        (root / "value.txt").write_text("oldtoken source")
        repository = projects.add_repository(project.id, root, "source", root.name)
        KnowledgeIndexer(database).index_repository(project.id, repository.id, root)
        roots.append(root)
    for root in roots:
        (root / "value.txt").write_text("updatedtoken source")
    search = KnowledgeSearch(database)
    assert len(search.search(project.id, "updatedtoken")) == len(roots)
    assert search.search(project.id, "oldtoken") == []
    roots[-1].rename(tmp_path / "inaccessible")
    with pytest.raises(StaleKnowledge):
        search.search(project.id, "updatedtoken")
