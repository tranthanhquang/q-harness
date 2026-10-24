from __future__ import annotations

import secrets
import uuid
from collections.abc import Awaitable, Callable
from ipaddress import ip_address
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from qharness.infrastructure.logging import correlation_id


def _host_allowed(host: str) -> bool:
    try:
        parsed = urlsplit(f"http://{host}")
        return (
            bool(host)
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.username is None
            and parsed.password is None
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and (parsed.port is None or 1 <= parsed.port <= 65535)
            and (not host.startswith("[") or host == "[::1]" or host.startswith("[::1]:"))
        )
    except ValueError:
        return False


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        return (
            parsed.scheme in {"http", "https"}
            and _host_allowed(parsed.netloc)
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def problem(status: int, code: str, title: str) -> JSONResponse:
    return JSONResponse(
        {
            "type": "about:blank",
            "title": title,
            "status": status,
            "code": code,
            "correlation_id": correlation_id.get(),
            "retryable": False,
        },
        status_code=status,
        media_type="application/problem+json",
        headers={"X-Correlation-ID": correlation_id.get()},
    )


def auth_middleware(
    token: str, allowed_project_id: uuid.UUID | None = None
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def authorize(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        context = correlation_id.set(str(uuid.uuid4()))
        try:
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not secrets.compare_digest(supplied, token):
                return problem(401, "UNAUTHORIZED", "Bearer token required")
            try:
                local_peer = (
                    request.client is not None and ip_address(request.client.host).is_loopback
                )
            except ValueError:
                local_peer = False
            if (
                not local_peer
                or not request.headers.get("authorization", "").startswith("Bearer ")
                or not _host_allowed(request.headers.get("host", ""))
                or not _origin_allowed(request.headers.get("origin"))
            ):
                return problem(403, "LOCAL_SCOPE_DENIED", "Local host and Origin required")
            parts = request.url.path.strip("/").split("/")
            if (
                len(parts) >= 3
                and parts[:2] == ["v1", "projects"]
                and (allowed_project_id is None or parts[2] != str(allowed_project_id))
            ):
                return problem(403, "PROJECT_SCOPE_DENIED", "Project is outside this token scope")
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id.get()
            return response
        finally:
            correlation_id.reset(context)

    return authorize


def require_project_scope(requested: str, allowed: str) -> None:
    if not secrets.compare_digest(requested, allowed):
        raise PermissionError("PROJECT_SCOPE_DENIED")
