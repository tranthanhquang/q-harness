from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from qharness.config import Settings
from qharness.domain.errors import HarnessError, NotFound
from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyConflict
from qharness.infrastructure.logging import correlation_id
from qharness.interfaces import payloads
from qharness.interfaces.mcp import build_mcp_server
from qharness.interfaces.projections import (
    approval_data,
    project_data,
    project_status,
    report_data,
    repository_data,
    task_data,
    template_data,
)
from qharness.knowledge.search import KnowledgeSearch, StaleKnowledge
from qharness.projects.service import ProjectService
from qharness.reports.service import ReportService
from qharness.runtime.ask import AskService
from qharness.security.auth import auth_middleware, problem
from qharness.tasks.approvals import ScopePayload
from qharness.tasks.audit import AuditService
from qharness.tasks.service import TaskService

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=16, max_length=128)]


def create_app(
    token: str | None = None,
    database: Database | None = None,
    *,
    allowed_project_id: uuid.UUID | None = None,
) -> FastAPI:
    settings = Settings()
    resolved_token = token or (
        settings.local_token.get_secret_value() if settings.local_token else None
    )
    if not resolved_token or len(resolved_token) < 32:
        raise ValueError("QH_LOCAL_TOKEN must contain at least 32 characters")
    allowed_project_id = allowed_project_id or settings.project_id
    db = database or Database(settings.database_url)
    projects, tasks = ProjectService(db), TaskService(db)
    reports = ReportService(db, settings.data_dir / "artifacts")
    mcp_app = build_mcp_server(allowed_project_id, db).streamable_http_app(
        streamable_http_path="/", stateless_http=True, host="127.0.0.1"
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = FastAPI(title="Q-Harness", version="0.1.0", lifespan=lifespan)
    app.middleware("http")(auth_middleware(resolved_token, allowed_project_id))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        return problem(
            500, "INTERNAL_ERROR", "Request failed; inspect local logs with the correlation ID"
        )

    @app.exception_handler(ValueError)
    async def invalid(_: Request, exc: ValueError) -> JSONResponse:
        if isinstance(exc, StaleKnowledge):
            return problem(409, "KNOWLEDGE_STALE", str(exc))
        code = "IDEMPOTENCY_CONFLICT" if isinstance(exc, IdempotencyConflict) else "STATE_CONFLICT"
        return problem(409, code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(422, "INVALID_REQUEST", "Request fields do not match the contract")

    @app.exception_handler(HarnessError)
    async def domain_error(_: Request, exc: HarnessError) -> JSONResponse:
        return problem(404 if isinstance(exc, NotFound) else 409, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return problem(
            exc.status_code,
            "NOT_FOUND" if exc.status_code == 404 else "REQUEST_DENIED",
            str(exc.detail),
        )

    @app.exception_handler(PermissionError)
    async def denied(_: Request, exc: PermissionError) -> JSONResponse:
        return problem(403, "PROJECT_SCOPE_DENIED", "Request exceeds Project or approved scope")

    @app.exception_handler(IntegrityError)
    async def conflict(_: Request, exc: IntegrityError) -> JSONResponse:
        return problem(409, "STATE_CONFLICT", "A unique identity or Project relationship conflicts")

    def check_task(project_id: uuid.UUID, task_id: uuid.UUID) -> None:
        if tasks.get(task_id).project_id != project_id:
            raise HTTPException(404, "task not found")

    @app.get("/healthz", operation_id="getHealth")
    def health() -> dict[str, Any]:
        healthy = db.healthy()
        return {
            "status": "degraded",
            "database": "ok" if healthy else "unavailable",
            "worker": "unavailable",
            "correlation_id": correlation_id.get(),
        }

    @app.get("/v1/projects", operation_id="listProjects")
    def list_projects() -> dict[str, Any]:
        return {
            "items": [
                project_data(item) for item in projects.list() if item.id == allowed_project_id
            ],
            "correlation_id": correlation_id.get(),
        }

    @app.post("/v1/projects", operation_id="createProject", status_code=201)
    def create_project(payload: payloads.CreateProject) -> dict[str, Any]:
        if allowed_project_id is not None:
            raise PermissionError("scoped token cannot create another Project")
        return project_data(
            projects.create(payload.name, Path(payload.workspace_root), payload.stable_key)
        )

    @app.post(
        "/v1/projects/{project_id}/repositories", operation_id="addRepository", status_code=201
    )
    def add_repository(project_id: uuid.UUID, payload: payloads.AddRepository) -> dict[str, Any]:
        return repository_data(
            projects.add_repository(
                project_id,
                Path(payload.path),
                payload.role,
                payload.name or Path(payload.path).name,
                payload.access_mode,
            )
        )

    @app.get("/v1/projects/{project_id}/status", operation_id="getProjectStatus")
    def status(project_id: uuid.UUID) -> dict[str, Any]:
        return {**project_status(db, project_id), "correlation_id": correlation_id.get()}

    @app.post(
        "/v1/projects/{project_id}/index-jobs", operation_id="createIndexJob", status_code=202
    )
    def index_project(
        project_id: uuid.UUID, payload: payloads.Index, idempotency_key: IdempotencyKey
    ) -> dict[str, Any]:
        from qharness.infrastructure.idempotency import IdempotencyStore
        from qharness.knowledge.indexer import KnowledgeIndexer

        repositories = projects.repositories(project_id)
        selected = {uuid.UUID(value) for value in payload.repository_ids or []}
        if selected - {item.id for item in repositories}:
            raise PermissionError("repository is outside Project scope")
        request = payload.model_dump()
        store = IdempotencyStore(db)
        replay = store.replay(f"index:{project_id}", idempotency_key, request)
        if replay is None:
            for repository in repositories:
                if not selected or repository.id in selected:
                    KnowledgeIndexer(db).index_repository(
                        project_id,
                        repository.id,
                        Path(repository.canonical_path),
                        full=payload.mode == "full",
                    )
            replay = store.remember(
                f"index:{project_id}",
                idempotency_key,
                request,
                {"id": str(uuid.uuid4()), "status": "PENDING"},
            )
        return {**replay, "correlation_id": correlation_id.get()}

    @app.post("/v1/projects/{project_id}/knowledge/search", operation_id="searchKnowledge")
    def search(project_id: uuid.UUID, payload: payloads.Search) -> dict[str, Any]:
        results = KnowledgeSearch(db).search(
            project_id, payload.query, payload.limit, repository_ids=payload.identities()
        )
        return {
            "freshness_checked_at": datetime.now(UTC).isoformat(),
            "items": [item.public() for item in results],
            "correlation_id": correlation_id.get(),
        }

    @app.post("/v1/projects/{project_id}/ask", operation_id="askProject")
    def ask(project_id: uuid.UUID, payload: payloads.Ask) -> dict[str, Any]:
        answer = AskService(KnowledgeSearch(db)).ask(project_id, payload.question)
        return {
            "answer": answer.text,
            "citations": answer.citations,
            "correlation_id": correlation_id.get(),
        }

    @app.get("/v1/projects/{project_id}/tasks", operation_id="listTasks")
    def list_tasks(project_id: uuid.UUID) -> list[dict[str, Any]]:
        return [task_data(db, project_id, task.id) for task in tasks.list(project_id)]

    @app.post("/v1/projects/{project_id}/tasks", operation_id="createTask", status_code=201)
    def create_task(project_id: uuid.UUID, payload: payloads.CreateTask) -> dict[str, Any]:
        projects.get(project_id)
        task = tasks.create(project_id, payload.request)
        return task_data(db, project_id, task.id)

    @app.get("/v1/projects/{project_id}/tasks/{task_id}", operation_id="getTask")
    def get_task(project_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, Any]:
        check_task(project_id, task_id)
        return task_data(db, project_id, task_id)

    @app.post(
        "/v1/projects/{project_id}/tasks/{task_id}/approvals",
        operation_id="approveTaskScope",
        status_code=201,
    )
    def approve_task(
        project_id: uuid.UUID, task_id: uuid.UUID, payload: ScopePayload
    ) -> dict[str, Any]:
        check_task(project_id, task_id)
        tasks.approve(task_id, payload.model_dump())
        return approval_data(db, task_id)

    @app.post(
        "/v1/projects/{project_id}/tasks/{task_id}/executions",
        operation_id="createExecution",
        status_code=202,
    )
    def execute_task(
        project_id: uuid.UUID, task_id: uuid.UUID, idempotency_key: IdempotencyKey
    ) -> dict[str, Any]:
        check_task(project_id, task_id)
        execution = tasks.create_execution(task_id, idempotency_key=idempotency_key)
        return {
            "id": str(execution.id),
            "status": execution.state,
            "correlation_id": correlation_id.get(),
        }

    @app.post(
        "/v1/projects/{project_id}/tasks/{task_id}/actions",
        operation_id="actOnTask",
        status_code=202,
    )
    def act_on_task(
        project_id: uuid.UUID, task_id: uuid.UUID, payload: payloads.TaskAction
    ) -> dict[str, Any]:
        check_task(project_id, task_id)
        (tasks.cancel if payload.action == "cancel" else tasks.continue_blocked)(task_id)
        return task_data(db, project_id, task_id)

    @app.get("/v1/projects/{project_id}/notifications", operation_id="listNotifications")
    def notifications(
        project_id: uuid.UUID, since: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ) -> dict[str, Any]:
        return {
            "items": AuditService(db).notifications(project_id, since, limit),
            "correlation_id": correlation_id.get(),
        }

    @app.get("/v1/projects/{project_id}/report-templates", operation_id="listReportTemplates")
    def report_templates(project_id: uuid.UUID) -> list[dict[str, Any]]:
        return [template_data(item) for item in reports.list_templates(project_id)]

    @app.post("/v1/projects/{project_id}/reports", operation_id="generateReport", status_code=202)
    def generate_report(
        project_id: uuid.UUID, payload: payloads.GenerateReport, idempotency_key: IdempotencyKey
    ) -> dict[str, Any]:
        return report_data(
            db,
            reports.generate(
                project_id,
                payload.template_id,
                idempotency_key=idempotency_key,
                version=payload.version,
                scope=payload.scope,
            ),
        )

    @app.get("/v1/projects/{project_id}/reports/{report_id}", operation_id="getReport")
    def get_report(project_id: uuid.UUID, report_id: uuid.UUID) -> dict[str, Any]:
        report = reports.get(report_id)
        if report.project_id != project_id:
            raise HTTPException(404, "report not found")
        return report_data(db, report)

    app.mount("/mcp", mcp_app)
    return app
