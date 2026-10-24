import uuid

import pytest

from qharness.interfaces.mcp import MCPToolFacade


def test_mcp_advertises_only_supported_tools_and_enforces_project_scope() -> None:
    project_id = uuid.uuid4()
    facade = MCPToolFacade(project_id)
    assert set(facade.tool_names) == {
        "qh_project_get",
        "qh_knowledge_search",
        "qh_task_get",
        "qh_report_list",
        "qh_report_generate",
    }
    with pytest.raises(PermissionError):
        facade.require_project(uuid.uuid4())


def test_mcp_results_have_structured_content(database, tmp_path) -> None:
    from qharness.interfaces.mcp import tool_result
    from qharness.projects.service import ProjectService

    project = ProjectService(database).create("MCP", tmp_path)
    result = tool_result(lambda: MCPToolFacade(project.id, database).project_get(project.id))
    assert result.structured_content["ok"] is True
    assert result.structured_content["data"]["project"]["id"] == str(project.id)
