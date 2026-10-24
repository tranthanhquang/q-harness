import uuid
from pathlib import Path

import jsonschema
import yaml
from fastapi.testclient import TestClient

from qharness.interfaces.http import create_app
from qharness.projects.service import ProjectService

CONTRACT = yaml.safe_load(Path("specs/001-q-harness-platform/contracts/openapi.yaml").read_text())


def validate(name, value):
    jsonschema.Draft202012Validator(
        {"$ref": f"#/components/schemas/{name}", "components": CONTRACT["components"]}
    ).validate(value)


def test_http_contract_authorization_approval_and_idempotency(database, tmp_path):
    projects = ProjectService(database)
    project = projects.create("HTTP", tmp_path / "workspace")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "api.py").write_text('def health_check(): return "ok"\n')
    other = projects.create("Other", tmp_path / "other")
    headers = {"Authorization": "Bearer " + "x" * 32}
    with TestClient(
        create_app("x" * 32, database, allowed_project_id=project.id),
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 51000),
        headers=headers,
    ) as client:
        prefix = f"/v1/projects/{project.id}"
        assert client.get(f"/v1/projects/{other.id}/status").status_code == 403
        listed = client.get("/v1/projects").json()
        assert [item["id"] for item in listed["items"]] == [str(project.id)]
        validate("Project", listed["items"][0])
        response = client.post(prefix + "/repositories", json={"path": str(root), "role": "api"})
        assert response.status_code == 201
        validate("Repository", response.json())
        response = client.post(prefix + "/knowledge/search", json={"query": "health check"})
        assert response.status_code == 200
        validate("KnowledgeResult", response.json()["items"][0])
        assert (
            client.post(
                prefix + "/knowledge/search", json={"query": "health", "limit": 51}
            ).status_code
            == 422
        )
        assert (
            client.post(prefix + "/tasks", json={"request": "Fix health", "unknown": 1}).status_code
            == 422
        )
        response = client.post(prefix + "/tasks", json={"request": "Fix health"})
        assert response.status_code == 201
        validate("Task", response.json())
        task_id = response.json()["id"]
        response = client.post(
            prefix + f"/tasks/{task_id}/approvals",
            json={
                "repository_paths": [str(root)],
                "tools": ["read", "write", "search", "test"],
                "commands": ["python"],
                "network": False,
                "credential_names": [],
                "risk_ceiling": "HIGH",
            },
        )
        assert response.status_code == 201 and response.json()["scope_hash"]
        endpoint = prefix + f"/tasks/{task_id}/executions"
        assert client.post(endpoint).status_code == 422
        first = client.post(endpoint, headers={"Idempotency-Key": "http-execution-key-1"})
        assert first.status_code == 202
        assert (
            client.post(endpoint, headers={"Idempotency-Key": "http-execution-key-1"}).json()["id"]
            == first.json()["id"]
        )
        notifications = client.get(prefix + "/notifications").json()
        assert [item["event_type"] for item in notifications["items"]] == ["APPROVAL_REQUIRED"]
        cursor = notifications["items"][0]["event_id"]
        assert client.get(prefix + f"/notifications?since={cursor}").json()["items"] == []
        problem = client.get(f"/v1/projects/{uuid.uuid4()}/status").json()
        validate("Problem", problem)
