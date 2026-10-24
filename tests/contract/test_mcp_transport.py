import asyncio
import socket
import threading
import time
import uuid

import httpx2
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from qharness.interfaces.mcp import build_mcp_server
from qharness.projects.service import ProjectService


def test_mcp_dispatch_validates_schema_and_returns_error_envelopes(database, tmp_path):
    project = ProjectService(database).create("MCP dispatch", tmp_path)
    server = build_mcp_server(project.id, database)

    async def check():
        tools = await server.list_tools()
        assert all(item.input_schema["additionalProperties"] is False for item in tools)
        result = await server.call_tool("qh_project_get", {"project_id": str(project.id)})
        assert result.structured_content["ok"] is True
        assert result.structured_content["data"]["project"]["id"] == str(project.id)
        result = await server.call_tool("qh_project_get", {"project_id": str(uuid.uuid4())})
        assert (
            result.is_error and result.structured_content["error"]["code"] == "PROJECT_SCOPE_DENIED"
        )
        for arguments in (
            {"project_id": str(project.id), "unknown": True},
            {"project_id": "invalid"},
        ):
            result = await server.call_tool("qh_project_get", arguments)
            assert (
                result.is_error and result.structured_content["error"]["code"] == "INVALID_REQUEST"
            )
        result = await server.call_tool(
            "qh_knowledge_search", {"project_id": str(project.id), "query": "x", "limit": 51}
        )
        assert result.is_error

    asyncio.run(check())


def test_real_streamable_http_authentication_and_project_isolation(database, tmp_path):
    from qharness.interfaces.http import create_app

    project = ProjectService(database).create("MCP HTTP", tmp_path)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    token = "x" * 32
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(token, database, allowed_project_id=project.id),
            log_level="error",
            proxy_headers=False,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()

    async def check():
        async with (
            httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                follow_redirects=True,
                trust_env=False,
            ) as client,
            streamable_http_client(f"http://127.0.0.1:{port}/mcp/", http_client=client) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            catalog = await session.list_tools()
            assert len(catalog.tools) == 5
            result = await session.call_tool("qh_project_get", {"project_id": str(project.id)})
            assert result.structured_content["data"]["project"]["id"] == str(project.id)
            result = await session.call_tool("qh_project_get", {"project_id": str(uuid.uuid4())})
            assert result.is_error
            assert result.structured_content["error"]["code"] == "PROJECT_SCOPE_DENIED"
        async with httpx2.AsyncClient(trust_env=False) as client:
            response = await client.post(f"http://127.0.0.1:{port}/mcp/", json={})
            assert response.status_code == 401

    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        asyncio.run(check())
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()
