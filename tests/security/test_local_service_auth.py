from fastapi.testclient import TestClient

from qharness.interfaces.http import create_app


def test_token_host_and_origin_are_checked_before_data_access() -> None:
    client = TestClient(
        create_app(token="x" * 32), base_url="http://127.0.0.1", client=("127.0.0.1", 51000)
    )
    assert client.get("/healthz").status_code == 401
    headers = {"Authorization": f"Bearer {'x' * 32}"}
    assert client.get("/healthz", headers={**headers, "host": "evil.example"}).status_code == 403
    assert (
        client.get("/healthz", headers={**headers, "origin": "https://evil.example"}).status_code
        == 403
    )
    response = client.get("/healthz", headers=headers)
    assert response.status_code == 200 and response.json()["status"] in {"ok", "degraded"}


def test_remote_peer_cannot_spoof_local_host_or_forwarded_headers() -> None:
    client = TestClient(
        create_app(token="x" * 32), base_url="http://127.0.0.1", client=("192.0.2.1", 51000)
    )
    response = client.get(
        "/healthz", headers={"Authorization": f"Bearer {'x' * 32}", "X-Forwarded-For": "127.0.0.1"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "LOCAL_SCOPE_DENIED"
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]
