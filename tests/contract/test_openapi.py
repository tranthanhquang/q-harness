from qharness.interfaces.http import create_app


def test_required_openapi_operations_exist() -> None:
    schema = create_app(token="x" * 32).openapi()
    required = {
        "/healthz",
        "/v1/projects",
        "/v1/projects/{project_id}/status",
        "/v1/projects/{project_id}/knowledge/search",
        "/v1/projects/{project_id}/ask",
        "/v1/projects/{project_id}/tasks",
        "/v1/projects/{project_id}/notifications",
        "/v1/projects/{project_id}/report-templates",
    }
    assert required <= set(schema["paths"])
