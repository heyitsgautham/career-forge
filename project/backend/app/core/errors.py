"""
Request ids and unhandled errors
================================
Every request gets an id. It is bound into the structured log context, so all
log lines a request writes share it, and it is returned in the X-Request-ID
header. A client can send its own id, for example from a proxy, and it is
kept when it looks like one.

An exception no route handled becomes a 500 with a fixed message and the
request id. The traceback goes to the log under that id, never to the client,
because exception text can carry tokens, hostnames or SQL.
"""

import re
import uuid

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = structlog.get_logger()


def _incoming_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.decode("latin-1").lower() == REQUEST_ID_HEADER.lower():
            candidate = value.decode("latin-1")
            return candidate if _VALID_ID.match(candidate) else None
    return None


class RequestIdMiddleware:
    """Gives each HTTP request an id, logs with it, and echoes it in the response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_id(scope) or uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=scope["method"], path=scope["path"]
        )

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        # The context is not cleared afterwards: the catch-all handler below runs
        # outside this middleware and still needs the id for its log line.
        await self.app(scope, receive, send_with_id)


def internal_error(message: str) -> HTTPException:
    """A 500 whose detail is `message`, for routes that log the cause themselves."""
    return HTTPException(status_code=500, detail=message)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.scope.get("state", {}).get("request_id", "unknown")
    logger.error("unhandled_error", error_type=type(exc).__name__, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id},
    )


def install_error_handling(app: FastAPI) -> None:
    """Adds the request-id middleware and the catch-all 500 handler to `app`."""
    app.add_exception_handler(Exception, _unhandled_error)
    app.add_middleware(RequestIdMiddleware)
