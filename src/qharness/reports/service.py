from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from qharness.infrastructure.artifacts import ArtifactStore
from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyStore
from qharness.projects.models import Project
from qharness.reports.collector import ReportCollector, ReportScope
from qharness.reports.models import Artifact, Report, ReportTemplate
from qharness.reports.registry import (
    ChecksumDrift,
    RegisteredTemplate,
    ReportRegistry,
    load_contract,
)
from qharness.reports.render import render_isolated


class ReportService:
    def __init__(self, database: Database, artifact_root: Path) -> None:
        self.database = database
        self.artifacts = ArtifactStore(artifact_root)

    def register(
        self, contract_path: Path, project_id: uuid.UUID | None, *, license_name: str, trusted: bool
    ) -> ReportTemplate:
        with self.database.transaction() as session:
            project = session.get(Project, project_id) if project_id else None
            if project_id and not project:
                raise ValueError("project not found")
            from qharness.config import Settings

            allowed_root = (
                Path(project.workspace_path) if project else Settings().data_dir / "templates"
            )
            bundled = Path(__file__).with_name("templates").resolve()
            if not contract_path.resolve().is_relative_to(allowed_root.resolve()) and not (
                not project_id and contract_path.resolve().is_relative_to(bundled)
            ):
                raise ValueError("template is outside the allowed project/platform root")
            registered = ReportRegistry().register(
                contract_path, trusted=trusted, license_name=license_name
            )
            front = registered.contract.front_matter
            if (front["scope"] == "project") != (project_id is not None):
                raise ValueError("contract scope does not match registration scope")
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                {"identity": f"template:{project_id}:{front['template_id']}:{front['version']}"},
            )
            existing = session.scalar(
                select(ReportTemplate).where(
                    ReportTemplate.scope_project_id == project_id,
                    ReportTemplate.template_id == front["template_id"],
                    ReportTemplate.version == front["version"],
                )
            )
            if existing:
                if (existing.contract_sha256, existing.template_sha256) != (
                    registered.contract_sha256,
                    registered.template_sha256,
                ):
                    raise ChecksumDrift("registered versions are immutable; register a new version")
                return existing
            record = ReportTemplate(
                scope_project_id=project_id,
                template_id=front["template_id"],
                version=front["version"],
                output_format=front["output_format"],
                contract_path=str(registered.contract.path),
                template_path=str(registered.template_path),
                contract_sha256=registered.contract_sha256,
                template_sha256=registered.template_sha256,
                license=registered.license,
                trusted=trusted,
                contract=front,
            )
            session.add(record)
            session.flush()
            return record

    def list_templates(self, project_id: uuid.UUID) -> list[ReportTemplate]:
        with self.database.transaction() as session:
            return list(
                session.scalars(
                    select(ReportTemplate).where(
                        or_(
                            ReportTemplate.scope_project_id == project_id,
                            ReportTemplate.scope_project_id.is_(None),
                        ),
                        ReportTemplate.trusted.is_(True),
                    )
                )
            )

    def generate(
        self,
        project_id: uuid.UUID,
        template_id: str,
        *,
        idempotency_key: str,
        version: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> Report:
        report_scope = ReportScope.model_validate(scope or {})
        # Validate ownership before reserving a request or reading a template.
        ReportCollector(self.database).collect(project_id, [], report_scope)

        def reserve(session: Session) -> dict[str, Any]:
            if not session.get(Project, project_id):
                raise ValueError("project not found")
            candidates = list(
                session.scalars(
                    select(ReportTemplate).where(
                        or_(
                            ReportTemplate.scope_project_id == project_id,
                            ReportTemplate.scope_project_id.is_(None),
                        ),
                        ReportTemplate.template_id == template_id,
                        ReportTemplate.trusted.is_(True),
                    )
                )
            )
            candidates = [item for item in candidates if version is None or item.version == version]
            if not candidates:
                raise ValueError("trusted report template not found")
            candidates.sort(
                key=lambda item: (
                    item.scope_project_id is not None,
                    tuple(int(part) for part in item.version.split("-")[0].split(".")),
                    "-" not in item.version,
                    item.version,
                ),
                reverse=True,
            )
            template = candidates[0]
            report = Report(
                project_id=project_id,
                template_record_id=template.id,
                template_id=template.template_id,
                template_version=template.version,
                state="GENERATING",
            )
            session.add(report)
            session.flush()
            return {"id": str(report.id)}

        reservation, created = IdempotencyStore(self.database).run(
            f"report:{project_id}",
            idempotency_key,
            {"template_id": template_id, "version": version, "scope": scope or {}},
            reserve,
        )
        report_id = uuid.UUID(reservation["id"])
        if not created:
            return self.get(report_id)
        report = self.get(report_id)
        with self.database.transaction() as session:
            template = session.get(ReportTemplate, report.template_record_id)
        if template is None:
            raise RuntimeError("registered template disappeared")
        try:
            self._render(report, template, report_scope)
        except Exception as exc:
            with self.database.transaction() as session:
                failed = session.get(Report, report_id)
                if failed:
                    failed.state = "FAILED"
                    failed.validation_evidence = {"error_code": type(exc).__name__, "valid": False}
        return self.get(report_id)

    def _render(self, report: Report, template: ReportTemplate, scope: ReportScope) -> None:
        contract = load_contract(Path(template.contract_path))
        registered = RegisteredTemplate(
            contract,
            Path(template.template_path),
            template.contract_sha256,
            template.template_sha256,
            template.license,
            template.trusted,
        )
        ReportRegistry().verify(registered)
        context, provenance = ReportCollector(self.database).collect(
            report.project_id, contract.front_matter["data_sources"], scope
        )
        required = [
            field
            for section in contract.front_matter["required_sections"]
            for field in section.get("required_fields", [])
        ]
        policy = contract.front_matter["missing_data_policy"]
        missing = [
            {"field": field, "policy": policy}
            for field in required
            if field not in context or context[field] is None
        ]
        with self.database.transaction() as session:
            record = session.get(Report, report.id)
            if record is None:
                raise RuntimeError("report disappeared")
            record.missing_data = missing
            record.data_provenance = provenance
            if missing and policy in {"fail", "ask"}:
                record.state = "BLOCKED" if policy == "ask" else "FAILED"
                record.validation_evidence = {"error_code": "MISSING_DATA", "valid": False}
                return
        for gap in missing:
            context[gap["field"]] = "Missing" if policy == "mark_missing" else "N/A"
        rendered = render_isolated(registered.template_path, context, contract.front_matter)
        try:
            ReportRegistry().verify(registered)
            suffix = template.output_format
            published = self.artifacts.publish(
                rendered, f"{report.project_id}/{report.id}.{suffix}"
            )
        finally:
            import shutil

            shutil.rmtree(rendered.parent)
        with self.database.transaction() as session:
            artifact = Artifact(
                project_id=report.project_id,
                path=str(published.path),
                media_type="application/vnd.openxmlformats-officedocument."
                + ("wordprocessingml.document" if suffix == "docx" else "spreadsheetml.sheet"),
                sha256=published.sha256,
                size_bytes=published.size_bytes,
            )
            session.add(artifact)
            session.flush()
            record = session.get(Report, report.id)
            if record is None:
                raise RuntimeError("report disappeared")
            record.artifact_id = artifact.id
            record.state = "READY"
            record.validation_evidence = {
                "valid": True,
                "openable": True,
                "template_sha256": template.template_sha256,
                "contract_sha256": template.contract_sha256,
                "generator_version": "0.1.0",
            }
            from qharness.tasks.audit import append_audit

            append_audit(
                session,
                report.project_id,
                "REPORT_READY",
                {"artifact_id": str(artifact.id), "sha256": artifact.sha256},
                report_id=report.id,
            )

    def get(self, report_id: uuid.UUID) -> Report:
        with self.database.transaction() as session:
            report = session.get(Report, report_id)
            if not report:
                raise ValueError("report not found")
            return report
