from pathlib import Path

import pytest
from docx import Document

from qharness.infrastructure.artifacts import ArtifactStore
from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyConflict
from qharness.projects.service import ProjectService
from qharness.reports.docx import render_docx
from qharness.reports.service import ReportService
from tests.integration.test_report_registry import build_minimal_contract


@pytest.mark.e2e
def test_validated_report_is_atomically_published(tmp_path: Path) -> None:
    template = tmp_path / "template.docx"
    document = Document()
    document.add_paragraph("{{ project_name }}")
    document.save(template)
    rendered = tmp_path / "rendered.docx"
    render_docx(template, rendered, {"project_name": "Q-Harness"}, ["Q-Harness"])
    artifact = ArtifactStore(tmp_path / "artifacts").publish(rendered, "weekly.docx")
    assert artifact.path.is_file() and artifact.sha256 and artifact.size_bytes > 0


@pytest.mark.e2e
def test_report_service_replays_and_records_checksum_failure(
    database: Database, tmp_path: Path
) -> None:
    project = ProjectService(database).create("Report project", tmp_path)
    contract, template = build_minimal_contract(tmp_path)
    service = ReportService(database, tmp_path / "artifacts")
    service.register(contract, project.id, license_name="MIT", trusted=True)
    report = service.generate(project.id, "weekly-progress", idempotency_key="first-report-request")
    assert report.state == "READY" and report.artifact_id
    assert report.data_provenance and report.validation_evidence["template_sha256"]
    assert (
        service.generate(project.id, "weekly-progress", idempotency_key="first-report-request").id
        == report.id
    )
    with pytest.raises(IdempotencyConflict):
        service.generate(project.id, "other-template", idempotency_key="first-report-request")
    template.write_bytes(template.read_bytes() + b"drift")
    failed = service.generate(
        project.id, "weekly-progress", idempotency_key="second-report-request"
    )
    assert failed.state == "FAILED" and failed.artifact_id is None
    assert failed.validation_evidence["error_code"] == "ChecksumDrift"


@pytest.mark.e2e
def test_report_missing_data_ask_blocks_without_artifact(
    database: Database, tmp_path: Path
) -> None:
    project = ProjectService(database).create("Missing data", tmp_path)
    contract, _ = build_minimal_contract(tmp_path)
    contract.write_text(
        contract.read_text()
        .replace("[project_name]", "[project_name, absent]")
        .replace("missing_data_policy: fail", "missing_data_policy: ask")
    )
    service = ReportService(database, tmp_path / "artifacts")
    service.register(contract, project.id, license_name="MIT", trusted=True)
    report = service.generate(project.id, "weekly-progress", idempotency_key="missing-data-request")
    assert report.state == "BLOCKED" and not report.artifact_id
    assert report.missing_data == [{"field": "absent", "policy": "ask"}]


def test_task_scoped_report_links_artifact_to_audit_timeline(database: Database, tmp_path: Path):
    from qharness.tasks.audit import AuditService
    from qharness.tasks.service import TaskService

    project = ProjectService(database).create("Report audit", tmp_path)
    tasks = TaskService(database)
    task = tasks.create(project.id, "Fix report")
    other = tasks.create(project.id, "Fix other")
    contract, _ = build_minimal_contract(tmp_path)
    contract.write_text(
        contract.read_text().replace("data_sources: [project]", "data_sources: [project, tasks]")
    )
    service = ReportService(database, tmp_path / "artifacts")
    service.register(contract, project.id, license_name="MIT", trusted=True)
    report = service.generate(
        project.id,
        "weekly-progress",
        idempotency_key="report-audit-link",
        scope={"task_ids": [str(task.id)]},
    )
    assert report.state == "READY"
    linked = AuditService(database).task_timeline(project.id, task.id)["reports"]
    assert linked[0]["artifact_id"] == str(report.artifact_id)
    assert linked[0]["report_id"] == str(report.id)
    assert linked[0]["sha256"]
    assert AuditService(database).task_timeline(project.id, other.id)["reports"] == []
