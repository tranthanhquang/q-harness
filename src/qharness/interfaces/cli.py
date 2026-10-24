"""Q-Harness command line interface."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import typer
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from typer import _click as click
from typer._click.globals import get_current_context
from typer.core import TyperGroup

from qharness.config import Settings
from qharness.domain.errors import HarnessError, NotFound
from qharness.infrastructure.database import Database
from qharness.infrastructure.logging import ensure_correlation_id
from qharness.interfaces.projections import (
    approval_data,
    project_data,
    report_data,
    repository_data,
    template_data,
)
from qharness.projects.models import Project
from qharness.projects.service import ProjectService
from qharness.reports.registry import ChecksumDrift, InvalidReportContract
from qharness.reports.service import ReportService
from qharness.reports.xlsx import ReportValidationError
from qharness.security.policy import ScopeEscalation
from qharness.security.redaction import redact
from qharness.skills.registry import InvalidSkill
from qharness.tasks.service import TaskService


class HarnessGroup(TyperGroup):
    def invoke(self, ctx: click.Context) -> Any:
        json_output = "--json" in ctx.args
        try:
            return super().invoke(ctx)
        except (click.exceptions.Exit, typer.Abort):
            raise
        except Exception as exc:
            if isinstance(exc, NotFound):
                status, code = 4, exc.code
            elif isinstance(
                exc, (InvalidReportContract, ReportValidationError, ChecksumDrift, InvalidSkill)
            ):
                status, code = 7, "VALIDATION_FAILED"
            elif isinstance(exc, HarnessError) and exc.code in {"REPORT_BLOCKED", "REPORT_INVALID"}:
                status, code = (8 if exc.code == "REPORT_BLOCKED" else 7), exc.code
            elif isinstance(exc, ScopeEscalation):
                status, code = 6, "SCOPE_EXCEEDED"
            elif isinstance(exc, PermissionError):
                status, code = 3, "PROJECT_SCOPE_DENIED"
            elif isinstance(exc, (ValidationError, click.ClickException)):
                status, code = 2, "INVALID_REQUEST"
            elif isinstance(exc, (OperationalError, ConnectionError, FileNotFoundError)):
                status, code = 9, "DEPENDENCY_UNAVAILABLE"
            elif isinstance(exc, (IntegrityError, ValueError, HarnessError)):
                status, code = 5, getattr(exc, "code", "STATE_CONFLICT")
            else:
                status, code = 10, "INTERNAL_ERROR"
            message = "Command failed; inspect configuration and local dependencies."
            if not isinstance(exc, ValidationError) and isinstance(
                exc, (HarnessError, ValueError, PermissionError, click.ClickException)
            ):
                message = str(redact(str(exc)))
            correlation = ensure_correlation_id()
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "ok": False,
                            "data": None,
                            "error": {
                                "code": code,
                                "message": message,
                                "details": redact(exc.details)
                                if isinstance(exc, HarnessError)
                                else {},
                            },
                            "correlation_id": correlation,
                        }
                    )
                )
            else:
                typer.echo(f"{code}: {message} ({correlation})", err=True)
            ctx.exit(status)


app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False, cls=HarnessGroup)
project_app = typer.Typer(no_args_is_help=True)
knowledge_app = typer.Typer(no_args_is_help=True)
task_app = typer.Typer(no_args_is_help=True)
report_app = typer.Typer(no_args_is_help=True)
report_template_app = typer.Typer(no_args_is_help=True)
report_app.add_typer(report_template_app, name="template")
app.add_typer(project_app, name="project")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(task_app, name="task")
app.add_typer(report_app, name="report")
notification_app = typer.Typer(no_args_is_help=True)
app.add_typer(notification_app, name="notification")
skill_app = typer.Typer(no_args_is_help=True)
app.add_typer(skill_app, name="skill")


@app.callback()
def main(project: uuid.UUID | None = typer.Option(None, "--project")) -> None:
    """Operate the local Q-Harness service."""


def _projects() -> ProjectService:
    settings = Settings()
    database = Database(settings.database_url)
    return ProjectService(database)


def _active_project(service: ProjectService) -> Project:
    context = get_current_context(silent=True)
    explicit = context.find_root().params.get("project") if context else None
    identity = explicit or Settings().project_id
    return service.get(identity) if identity else service.discover(Path.cwd())


def _check_task_scope(task_id: uuid.UUID) -> None:
    if _task_service().get(task_id).project_id != _active_project(_projects()).id:
        raise PermissionError("task is outside the active Project")


def _emit(value: object, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "ok": True,
                    "data": redact(value),
                    "error": None,
                    "correlation_id": ensure_correlation_id(),
                },
                default=str,
                sort_keys=True,
            )
        )
    else:
        typer.echo(redact(value))


@app.command("init")
def init_project(
    name: str = typer.Option(..., "--name"),
    workspace: Path = typer.Option(..., "--workspace"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    project = _projects().create(name, workspace)
    _emit(project_data(project), json_output)


@project_app.command("add")
def project_add(
    path: Path,
    role: str = typer.Option(..., "--role"),
    name: str | None = typer.Option(None, "--name"),
    project_id: uuid.UUID | None = typer.Option(None, "--project"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = _projects()
    active = service.get(project_id) if project_id else _active_project(service)
    repository = service.add_repository(active.id, path, role, name or path.name)
    _emit(repository_data(repository), json_output)


@project_app.command("list")
def project_list(json_output: bool = typer.Option(False, "--json")) -> None:
    values = [project_data(project) for project in _projects().list()]
    _emit(values, json_output)


@project_app.command("use")
def project_use(
    project_id: uuid.UUID,
    workspace: Path | None = typer.Option(None, "--workspace"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    from qharness.projects.config import write_project_config

    project = _projects().get(project_id)
    workspace = workspace or Path.cwd()
    workspace.mkdir(parents=True, exist_ok=True)
    write_project_config(workspace.resolve(), project.id, project.name)
    _emit(project_data(project), json_output)


@project_app.command("status")
def project_status(json_output: bool = typer.Option(False, "--json")) -> None:
    from qharness.interfaces.projections import project_status as status_data

    service = _projects()
    project = _active_project(service)
    _emit(status_data(service.database, project.id), json_output)


@project_app.command("index")
def project_index(
    full: bool = typer.Option(False, "--full"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    from qharness.knowledge.indexer import KnowledgeIndexer

    service = _projects()
    project = _active_project(service)
    changed: dict[str, list[str]] = {}
    indexer = KnowledgeIndexer(service.database)
    for repository in service.repositories(project.id):
        paths = indexer.index_repository(
            project.id, repository.id, Path(repository.canonical_path), full=full
        )
        changed[repository.name] = [path.as_posix() for path in paths]
    _emit({"project_id": project.id, "full": full, "changed": changed}, json_output)


@project_app.command("refresh")
def project_refresh(json_output: bool = typer.Option(False, "--json")) -> None:
    project_index(full=False, json_output=json_output)


@knowledge_app.command("search")
def knowledge_search(
    query: str,
    repository: uuid.UUID | None = typer.Option(None, "--repository"),
    limit: int = typer.Option(20, "--limit", min=1, max=50),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    from qharness.knowledge.search import KnowledgeSearch

    service = _projects()
    project = _active_project(service)
    results = KnowledgeSearch(service.database).search(project.id, query, limit, repository)
    _emit([item.public() for item in results], json_output)


@app.command("run")
def run_task(request: str, json_output: bool = typer.Option(False, "--json")) -> None:
    from qharness.interfaces.projections import task_data

    projects = _projects()
    project = _active_project(projects)
    task = TaskService(projects.database).create(project.id, request)
    _emit(task_data(projects.database, project.id, task.id), json_output)


def _task_service() -> TaskService:
    from qharness.tasks.service import TaskService

    return TaskService(Database(Settings().database_url))


@task_app.command("list")
def task_list(json_output: bool = typer.Option(False, "--json")) -> None:
    projects = _projects()
    project = _active_project(projects)
    tasks = _task_service().list(project.id)
    _emit(
        [{"id": item.id, "display_id": item.display_id, "state": item.state} for item in tasks],
        json_output,
    )


@task_app.command("status")
def task_status(task_id: uuid.UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    from qharness.interfaces.projections import task_data

    service = _task_service()
    task = service.get(task_id)
    project = _active_project(_projects())
    _emit(task_data(service.database, project.id, task.id), json_output)


@notification_app.command("list")
def notification_list(
    since: int = typer.Option(0, min=0),
    limit: int = typer.Option(50, min=1, max=200),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    from qharness.tasks.audit import AuditService

    projects = _projects()
    project = _active_project(projects)
    _emit(AuditService(projects.database).notifications(project.id, since, limit), json_output)


@task_app.command("approve")
def task_approve(
    task_id: uuid.UUID,
    scope_file: Path = typer.Option(..., "--scope-file"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    scope = json.loads(scope_file.read_text(encoding="utf-8"))
    _check_task_scope(task_id)
    service = _task_service()
    service.approve(task_id, scope)
    _emit(approval_data(service.database, task_id), json_output)


@task_app.command("execute")
def task_execute(
    task_id: uuid.UUID,
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    _check_task_scope(task_id)
    service = _task_service()
    execution = service.create_execution(task_id, idempotency_key=idempotency_key)
    result = {"id": str(execution.id), "task_id": str(task_id), "state": execution.state}
    _emit(result, json_output)


@task_app.command("continue")
def task_continue(task_id: uuid.UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    _check_task_scope(task_id)
    task = _task_service().continue_blocked(task_id)
    _emit({"id": task.id, "state": task.state}, json_output)


@task_app.command("cancel")
def task_cancel(task_id: uuid.UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    _check_task_scope(task_id)
    task = _task_service().cancel(task_id)
    _emit({"id": task.id, "state": task.state}, json_output)


@app.command("worker")
def worker(once: bool = typer.Option(False, "--once")) -> None:
    from qharness.interfaces.worker import run_worker

    run_worker(once)


@app.command("ask")
def ask(question: str, json_output: bool = typer.Option(False, "--json")) -> None:
    from qharness.knowledge.search import KnowledgeSearch
    from qharness.runtime.ask import AskService

    projects = _projects()
    project = _active_project(projects)
    answer = AskService(KnowledgeSearch(projects.database)).ask(project.id, question)
    _emit({"text": answer.text, "citations": answer.citations, "stale": answer.stale}, json_output)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    import uvicorn

    settings = Settings(bind_host=host, port=port).service_ready()
    from qharness.interfaces.http import create_app

    if settings.project_id is None:
        settings.project_id = _active_project(_projects()).id
    assert settings.local_token
    uvicorn.run(
        create_app(settings.local_token.get_secret_value(), allowed_project_id=settings.project_id),
        host=settings.bind_host,
        port=settings.port,
        proxy_headers=False,
    )


def _report_service() -> ReportService:
    from qharness.reports.service import ReportService

    settings = Settings()
    return ReportService(Database(settings.database_url), settings.data_dir / "artifacts")


@report_app.command("list")
def report_list(json_output: bool = typer.Option(False, "--json")) -> None:
    project = _active_project(_projects())
    templates = _report_service().list_templates(project.id)
    _emit([template_data(item) for item in templates], json_output)


@report_app.command("generate")
def report_generate(
    template_id: str,
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    version: str | None = typer.Option(None, "--version"),
    scope_file: Path | None = typer.Option(None, "--scope"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    project = _active_project(_projects())
    service = _report_service()
    report = service.generate(
        project.id,
        template_id,
        idempotency_key=idempotency_key,
        version=version,
        scope=json.loads(scope_file.read_text()) if scope_file else None,
    )
    if report.state != "READY":
        raise HarnessError(
            "REPORT_BLOCKED" if report.state == "BLOCKED" else "REPORT_INVALID",
            "Report generation did not produce a validated artifact.",
            details={"report_id": str(report.id), "state": report.state},
        )
    _emit(report_data(service.database, report), json_output)


@report_app.command("status")
def report_status(report_id: uuid.UUID, json_output: bool = typer.Option(False, "--json")) -> None:
    service = _report_service()
    report = service.get(report_id)
    if report.project_id != _active_project(_projects()).id:
        raise PermissionError("report is outside the active Project")
    _emit(report_data(service.database, report), json_output)


@report_template_app.command("verify")
def report_template_verify(path: Path) -> None:
    from qharness.reports.registry import ReportRegistry

    contract = path / "report.md" if path.is_dir() else path
    registry = ReportRegistry()
    record = registry.register(contract, trusted=True, license_name="UNRELEASED")
    registry.verify(record)
    _emit(
        {
            "valid": True,
            "contract_sha256": record.contract_sha256,
            "template_sha256": record.template_sha256,
        },
        True,
    )


@report_template_app.command("register")
def report_template_register(
    contract: Path,
    license_name: str = typer.Option(..., "--license"),
    platform: bool = typer.Option(False, "--platform"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    project_id = None if platform else _active_project(_projects()).id
    contract = contract / "report.md" if contract.is_dir() else contract
    record = _report_service().register(
        contract, project_id, license_name=license_name, trusted=True
    )
    _emit({"id": str(record.id), **template_data(record)}, json_output)


@skill_app.command("list")
def skill_list(json_output: bool = typer.Option(False, "--json")) -> None:
    from qharness.skills.registry import SkillRegistry

    projects = _projects()
    project = _active_project(projects)
    roots = [
        Path(project.workspace_path) / ".agents/skills",
        Path(project.workspace_path) / ".qharness/skills",
        Settings().data_dir / "skills",
    ]
    registry = SkillRegistry(projects.database, roots)
    _emit(
        {
            "discovered": [str(path) for path in registry.discover()],
            "registered": [
                {
                    "id": item.id,
                    "name": item.name,
                    "version": item.version,
                    "status": item.status,
                    "license": item.license,
                    "permissions": item.permissions,
                }
                for item in registry.list(project.id)
            ],
        },
        json_output,
    )


@skill_app.command("verify")
def skill_verify(
    path: Path,
    platform: bool = typer.Option(False, "--platform"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    from qharness.skills.registry import SkillRegistry

    projects = _projects()
    project = None if platform else _active_project(projects)
    roots = (
        [Settings().data_dir / "skills"]
        if platform
        else [
            Path(project.workspace_path) / ".agents/skills",
            Path(project.workspace_path) / ".qharness/skills",
        ]
        if project
        else []
    )
    record = SkillRegistry(projects.database, roots).verify(path, project.id if project else None)
    _emit({"id": record.id, "status": record.status, "evidence": record.evidence}, json_output)


if __name__ == "__main__":
    app()
