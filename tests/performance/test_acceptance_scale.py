"""Opt-in real file/row fixture; initial indexing throughput is outside this latency gate."""

import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import insert, text

from qharness.interfaces.projections import project_status
from qharness.knowledge.indexer import KnowledgeIndexer
from qharness.knowledge.models import IndexVersion, KnowledgeChunk, SourceFile
from qharness.knowledge.search import KnowledgeSearch
from qharness.projects.service import ProjectService

pytestmark = [
    pytest.mark.acceptance_scale,
    pytest.mark.skipif(
        os.environ.get("QH_RUN_SCALE") != "1", reason="set QH_RUN_SCALE=1 for 1,000,000 files/rows"
    ),
]


def test_ten_projects_twenty_repositories_and_one_hundred_thousand_files_each(database, tmp_path):
    projects = ProjectService(database)
    owners, repositories = [], []
    for project_number in range(10):
        project = projects.create(f"Scale {project_number}", tmp_path / f"p{project_number}")
        owners.append(project)
        content = f"projecttoken{project_number} source documentation\n".encode()
        digest = hashlib.sha256(content).hexdigest()
        for repository_number in range(20):
            root = tmp_path / f"p{project_number}" / f"r{repository_number}"
            root.mkdir()
            repository = projects.add_repository(
                project.id, root, "source", f"r{repository_number}"
            )
            repositories.append(repository)
            files, chunks = [], []
            for file_number in range(5000):
                relative = f"note_{file_number:04d}.txt"
                path = root / relative
                path.write_bytes(content)
                source_id = uuid.uuid4()
                files.append(
                    {
                        "id": source_id,
                        "project_id": project.id,
                        "repository_id": repository.id,
                        "path": relative,
                        "content_hash": digest,
                        "size_bytes": len(content),
                        "modified_ns": path.stat().st_mtime_ns,
                    }
                )
                chunks.append(
                    {
                        "id": uuid.uuid4(),
                        "project_id": project.id,
                        "repository_id": repository.id,
                        "source_file_id": source_id,
                        "start_line": 1,
                        "end_line": 1,
                        "content": content.decode(),
                    }
                )
            with database.transaction() as session:
                session.execute(insert(SourceFile), files)
                session.execute(insert(KnowledgeChunk), chunks)
                session.add(
                    IndexVersion(
                        project_id=project.id, repository_id=repository.id, state="COMPLETE"
                    )
                )
    with database.transaction() as session:
        for table in ("source_files", "knowledge_chunks", "symbols"):
            session.execute(text(f"ANALYZE {table}"))
        assert session.scalar(text("SELECT count(*) FROM source_files")) == 1_000_000
    latencies = {"status": [], "search": []}
    search = KnowledgeSearch(database)
    for index in range(20):
        project = owners[index % 10]
        started = time.monotonic()
        assert project_status(database, project.id)["project"]["id"] == str(project.id)
        latencies["status"].append(time.monotonic() - started)
        started = time.monotonic()
        results = search.search(project.id, f"projecttoken{index % 10}")
        latencies["search"].append(time.monotonic() - started)
        assert results and all(f"projecttoken{index % 10}" in result.content for result in results)
    repository = repositories[0]
    root = Path(repository.canonical_path)
    (root / "note_0000.txt").write_text("changedtoken source documentation\n")
    started = time.monotonic()
    changed = KnowledgeIndexer(database).refresh_repository(owners[0].id, repository.id, root)
    refresh_seconds = time.monotonic() - started
    assert changed == [Path("note_0000.txt")]
    assert search.search(owners[0].id, "changedtoken", repository_id=repository.id)
    evidence = {
        "projects": 10,
        "repositories_per_project": 20,
        "files_per_project": 100_000,
        "source_rows": 1_000_000,
        "latency_seconds": latencies,
        "one_file_refresh_seconds": refresh_seconds,
        "p95_seconds": {
            name: sorted(values)[math.ceil(len(values) * 0.95) - 1]
            for name, values in latencies.items()
        },
    }
    output = Path(os.environ.get("QH_SCALE_EVIDENCE", ".tmp/scale-evidence.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2))
    assert all(value <= 3 for value in evidence["p95_seconds"].values()), evidence
    assert refresh_seconds <= 30, evidence
