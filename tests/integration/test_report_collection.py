import uuid
from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.knowledge.models import SourceFile
from qharness.projects.service import ProjectService
from qharness.reports.collector import ReportCollector, ReportScope
from qharness.tasks.service import TaskService


@pytest.fixture
def scoped_sources(database: Database, tmp_path: Path):
    projects, tasks = ProjectService(database), TaskService(database)
    selected = []
    for name in ("first", "second", "foreign"):
        root = tmp_path / name
        project = projects.create(name, root)
        if name == "first":
            owner = project
        project_id = project.id if name == "foreign" else owner.id
        repository = projects.add_repository(project_id, root, name, name)
        task = tasks.create(project_id, "Fix application")
        tasks.approve(
            task.id,
            {
                "repository_paths": [str(root)],
                "commands": ["python"],
                "tools": ["read", "write", "search", "test"],
                "network": False,
                "credential_names": [],
                "risk_ceiling": "HIGH",
            },
        )
        execution = tasks.create_execution(task.id)
        tasks.claim_next("collector-test")
        tasks.record_test(execution.id, repository.id, '["python", "tests.py"]', 0, "", "")
        with database.transaction() as session:
            session.add(
                SourceFile(
                    project_id=project_id,
                    repository_id=repository.id,
                    path=f"{name}.py",
                    content_hash="a" * 64,
                    size_bytes=1,
                    modified_ns=1,
                )
            )
        selected.append((task, repository, execution))
    return owner, selected


def test_task_scope_filters_every_supported_source(database: Database, scoped_sources):
    project, records = scoped_sources
    task, repository, execution = records[0]
    sources = [
        "project",
        "repositories",
        "knowledge",
        "work_items",
        "tasks",
        "executions",
        "test_runs",
    ]
    collector = ReportCollector(database)
    data, provenance = collector.collect(project.id, sources, ReportScope(task_ids=[task.id]))
    assert data["task_count"] == data["test_total"] == 1
    assert [item["id"] for item in data["tasks"]] == [str(task.id)]
    assert [item["id"] for item in data["repositories"]] == [str(repository.id)]
    assert [item["id"] for item in data["executions"]] == [str(execution.id)]
    assert [item["id"] for item in data["work_items"]] == [str(task.work_item_id)]
    assert [item["path"] for item in data["knowledge"]] == ["first.py"]
    assert all(str(records[2][0].id) not in str(item) for item in provenance)
    empty, _ = collector.collect(project.id, sources, ReportScope(task_ids=[]))
    assert empty["task_count"] == 0
    for source in ("repositories", "knowledge", "work_items", "tasks", "executions", "test_runs"):
        assert empty[source] == []
    with pytest.raises(ValueError, match="artifact collection"):
        collector.collect(project.id, ["artifacts"], ReportScope(task_ids=[task.id]))


def test_scope_rejects_foreign_and_missing_tasks_before_report_reservation(
    database: Database,
    scoped_sources,
    tmp_path: Path,
):
    from sqlalchemy import func, select

    from qharness.reports.models import Report
    from qharness.reports.service import ReportService

    project, records = scoped_sources
    for task_id in (records[2][0].id, uuid.uuid4()):
        with pytest.raises(PermissionError, match="outside Project"):
            ReportService(database, tmp_path / "artifacts").generate(
                project.id,
                "missing-template",
                idempotency_key="scope-denied",
                scope={"task_ids": [str(task_id)]},
            )
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 0


def test_report_scope_rejects_unrecognized_selectors():
    with pytest.raises(ValueError):
        ReportScope.model_validate({"repository_ids": [str(uuid.uuid4())]})
