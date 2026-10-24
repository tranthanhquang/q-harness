from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, InputRequiredResult, TextContent
from mcp.types import Tool as MCPTool
from pydantic import Field

from qharness.config import Settings
from qharness.domain.errors import HarnessError
from qharness.infrastructure.database import Database
from qharness.infrastructure.idempotency import IdempotencyConflict
from qharness.infrastructure.logging import ensure_correlation_id
from qharness.interfaces.projections import project_status, report_data, task_data, template_data
from qharness.knowledge.search import KnowledgeSearch, StaleKnowledge
from qharness.projects.service import ProjectService
from qharness.reports.service import ReportService


class MCPToolFacade:
    tool_names = (
        "qh_project_get",
        "qh_knowledge_search",
        "qh_task_get",
        "qh_report_list",
        "qh_report_generate",
    )

    def __init__(
        self, allowed_project_id: uuid.UUID | None = None, database: Database | None = None
    ) -> None:
        self.allowed_project_id = allowed_project_id
        self.database = database

    def require_project(self, project_id: uuid.UUID) -> Database:
        if self.allowed_project_id is None or project_id != self.allowed_project_id:
            raise PermissionError("PROJECT_SCOPE_DENIED")
        if self.database is None:
            raise RuntimeError("database unavailable")
        ProjectService(self.database).get(project_id)
        return self.database

    def project_get(self, project_id: uuid.UUID) -> dict[str, Any]:
        return project_status(self.require_project(project_id), project_id)

    def knowledge_search(
        self,
        project_id: uuid.UUID,
        query: str,
        limit: int = 10,
        repository_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        database = self.require_project(project_id)
        results = KnowledgeSearch(database).search(
            project_id, query, limit, repository_ids=repository_ids
        )
        return {
            "freshness_checked_at": datetime.now(UTC).isoformat(),
            "results": [item.public() for item in results],
        }

    def task_get(self, project_id: uuid.UUID, task_id: uuid.UUID) -> dict[str, Any]:
        return task_data(self.require_project(project_id), project_id, task_id)

    def report_list(
        self, project_id: uuid.UUID, output_format: str | None = None
    ) -> dict[str, Any]:
        database = self.require_project(project_id)
        templates = ReportService(database, Settings().data_dir / "artifacts").list_templates(
            project_id
        )
        return {
            "templates": [
                template_data(item)
                for item in templates
                if output_format is None or item.output_format.upper() == output_format
            ]
        }

    def report_generate(
        self,
        project_id: uuid.UUID,
        template_id: str,
        idempotency_key: str,
        version: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        database = self.require_project(project_id)
        report = ReportService(database, Settings().data_dir / "artifacts").generate(
            project_id, template_id, idempotency_key=idempotency_key, version=version, scope=scope
        )
        return report_data(database, report)


class HarnessMCPServer(MCPServer[Any]):
    async def list_tools(self) -> list[MCPTool]:
        return [
            item.model_copy(
                update={"input_schema": {**item.input_schema, "additionalProperties": False}}
            )
            for item in await super().list_tools()
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context[Any, Any] | None = None
    ) -> CallToolResult | InputRequiredResult:
        schema = next(
            (item.input_schema for item in await self.list_tools() if item.name == name), None
        )
        if schema is None or not Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).is_valid(arguments):
            return CallToolResult(
                content=[TextContent(type="text", text="Invalid tool arguments.")],
                structured_content={
                    "ok": False,
                    "error": {
                        "code": "INVALID_REQUEST",
                        "message": "Tool arguments do not match the contract.",
                        "retryable": False,
                        "details": {},
                    },
                    "correlation_id": str(uuid.uuid4()),
                },
                is_error=True,
            )
        return await super().call_tool(name, arguments, context)


def tool_result(operation: Callable[[], dict[str, Any]]) -> CallToolResult:
    correlation = ensure_correlation_id(str(uuid.uuid4()))
    try:
        data = operation()
        structured = {"ok": True, "data": data, "correlation_id": correlation}
        return CallToolResult(
            content=[TextContent(type="text", text="Request complete.")],
            structured_content=structured,
        )
    except Exception as exc:
        code = "INTERNAL_ERROR"
        if isinstance(exc, PermissionError):
            code = "PROJECT_SCOPE_DENIED"
        elif isinstance(exc, StaleKnowledge):
            code = "INDEX_STALE"
        elif isinstance(exc, IdempotencyConflict):
            code = "IDEMPOTENCY_CONFLICT"
        elif isinstance(exc, HarnessError):
            code = exc.code
        elif isinstance(exc, ValueError):
            code = "STATE_CONFLICT"
        structured = {
            "ok": False,
            "error": {
                "code": code,
                "message": "Request denied or unavailable.",
                "retryable": False,
                "details": {},
            },
            "correlation_id": correlation,
        }
        return CallToolResult(
            content=[TextContent(type="text", text="Request denied or unavailable.")],
            structured_content=structured,
            is_error=True,
        )


def build_mcp_server(
    allowed_project_id: uuid.UUID | None = None, database: Database | None = None
) -> MCPServer[Any]:
    facade = MCPToolFacade(allowed_project_id, database)
    server: MCPServer[Any] = HarnessMCPServer("Q-Harness", version="0.1.0")

    @server.tool(name="qh_project_get")
    def project_get(project_id: uuid.UUID) -> CallToolResult:
        return tool_result(lambda: facade.project_get(project_id))

    @server.tool(name="qh_knowledge_search")
    def knowledge_search(
        project_id: uuid.UUID,
        query: Annotated[str, Field(min_length=1, max_length=1000)],
        repository_ids: Annotated[list[uuid.UUID] | None, Field(max_length=20)] = None,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> CallToolResult:
        return tool_result(
            lambda: facade.knowledge_search(project_id, query, limit, repository_ids)
        )

    @server.tool(name="qh_task_get")
    def task_get(project_id: uuid.UUID, task_id: uuid.UUID) -> CallToolResult:
        return tool_result(lambda: facade.task_get(project_id, task_id))

    @server.tool(name="qh_report_list")
    def report_list(
        project_id: uuid.UUID, output_format: Literal["DOCX", "XLSX"] | None = None
    ) -> CallToolResult:
        return tool_result(lambda: facade.report_list(project_id, output_format))

    @server.tool(name="qh_report_generate")
    def report_generate(
        project_id: uuid.UUID,
        template_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")],
        idempotency_key: Annotated[str, Field(min_length=16, max_length=128)],
        version: Annotated[str | None, Field(max_length=50)] = None,
        scope: dict[str, Any] | None = None,
    ) -> CallToolResult:
        return tool_result(
            lambda: facade.report_generate(project_id, template_id, idempotency_key, version, scope)
        )

    return server
