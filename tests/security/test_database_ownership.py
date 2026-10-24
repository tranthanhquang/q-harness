from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from qharness.infrastructure.database import Database
from qharness.knowledge.models import IndexVersion, KnowledgeChunk, SourceFile, Symbol
from qharness.projects.service import ProjectService
from qharness.tasks.models import AuditEvent, Execution, ExecutionRepository, Task, TaskRepository
from qharness.tasks.service import TaskService


@pytest.mark.parametrize(
    "reference",
    [
        "work_item",
        "task",
        "task_repository",
        "execution_repository",
        "index",
        "source",
        "chunk",
        "symbol",
        "audit",
    ],
)
def test_database_rejects_cross_project_references(
    database: Database,
    tmp_path: Path,
    reference: str,
) -> None:
    projects, tasks = ProjectService(database), TaskService(database)
    first = projects.create("Owner", tmp_path / "owner")
    foreign = projects.create("Foreign", tmp_path / "foreign")
    repository = projects.add_repository(foreign.id, tmp_path / "foreign", "api", "api")
    own_task = tasks.create(first.id, "Fix owner")
    foreign_task = tasks.create(foreign.id, "Fix foreign")
    with database.transaction() as session:
        execution = Execution(project_id=first.id, task_id=own_task.id)
        source = SourceFile(
            project_id=foreign.id,
            repository_id=repository.id,
            path="a.py",
            content_hash="a" * 64,
            size_bytes=1,
            modified_ns=1,
        )
        session.add_all([execution, source])
        session.flush()
    rows = {
        "work_item": Task(
            project_id=first.id, work_item_id=foreign_task.work_item_id, display_id="invalid"
        ),
        "task": Execution(project_id=first.id, task_id=foreign_task.id),
        "task_repository": TaskRepository(
            project_id=first.id, task_id=own_task.id, repository_id=repository.id
        ),
        "execution_repository": ExecutionRepository(
            project_id=first.id, execution_id=execution.id, repository_id=repository.id
        ),
        "index": IndexVersion(project_id=first.id, repository_id=repository.id),
        "source": SourceFile(
            project_id=first.id,
            repository_id=repository.id,
            path="bad.py",
            content_hash="a" * 64,
            size_bytes=1,
            modified_ns=1,
        ),
        "chunk": KnowledgeChunk(
            project_id=first.id,
            repository_id=repository.id,
            source_file_id=source.id,
            start_line=1,
            end_line=1,
            content="bad",
        ),
        "symbol": Symbol(
            project_id=first.id,
            repository_id=repository.id,
            source_file_id=source.id,
            name="bad",
            kind="function",
            line=1,
        ),
        "audit": AuditEvent(
            project_id=first.id, task_id=foreign_task.id, event_type="TASK_BLOCKED", payload={}
        ),
    }
    with pytest.raises(IntegrityError) as error, database.transaction() as session:
        session.add(rows[reference])
    assert error.value.orig.sqlstate == "23503"


def test_test_evidence_cannot_reference_an_unlinked_repository(approved_task, tmp_path: Path):
    from qharness.tasks.models import TestRun

    service, task = approved_task
    projects = ProjectService(service.database)
    foreign = projects.create("Foreign", tmp_path / "foreign")
    repository = projects.add_repository(foreign.id, tmp_path / "foreign", "api", "api")
    execution = service.create_execution(task.id)
    with pytest.raises(IntegrityError) as error, service.database.transaction() as session:
        session.add(
            TestRun(
                execution_id=execution.id,
                repository_id=repository.id,
                command="python",
                outcome="PASSED",
                returncode=0,
            )
        )
    assert error.value.orig.sqlstate == "23503"
