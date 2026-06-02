"""CORS registration — must run after all routes and exception handlers are attached."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

COMIC_OS_PRODUCTION_WEB_ORIGINS: tuple[str, ...] = (
    "https://comicosapp.com",
    "https://www.comicosapp.com",
)


def resolve_cors_origins(settings: Settings) -> list[str]:
    """Configured origins plus required production web hosts and FRONTEND_URL."""
    origins: list[str] = [
        origin.strip() for origin in settings.cors_origins_raw.split(",") if origin.strip()
    ]
    frontend = settings.frontend_url.strip().rstrip("/")
    if frontend:
        origins.append(frontend)
    if settings.app_env.lower() == "production":
        origins.extend(COMIC_OS_PRODUCTION_WEB_ORIGINS)

    seen: set[str] = set()
    unique: list[str] = []
    for origin in origins:
        if origin not in seen:
            seen.add(origin)
            unique.append(origin)
    return unique


def _origin_from_scope(scope: Scope) -> str | None:
    for name, value in scope.get("headers", ()):
        if name == b"origin":
            return value.decode("latin-1")
    return None


def _header_names(headers: list[tuple[bytes, bytes]]) -> set[bytes]:
    return {name.lower() for name, _ in headers}


def _append_cors_headers(headers: list[tuple[bytes, bytes]], origin: str) -> list[tuple[bytes, bytes]]:
    names = _header_names(headers)
    out = list(headers)
    if b"access-control-allow-origin" not in names:
        out.append((b"access-control-allow-origin", origin.encode("latin-1")))
    if b"access-control-allow-credentials" not in names:
        out.append((b"access-control-allow-credentials", b"true"))
    if b"vary" not in names:
        out.append((b"vary", b"Origin"))
    return out


class OriginReflectASGIMiddleware:
    """Outermost ASGI wrapper — injects ACAO on every http.response.start (including 500s).

    BaseHTTPMiddleware can skip header injection when the inner stack raises or times out;
    wrapping ``send`` catches all successful response starts from the app and proxies.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self._allowed = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        origin = _origin_from_scope(scope)
        allow_origin = origin if origin and origin in self._allowed else None

        async def send_with_cors(message: Message) -> None:
            if allow_origin and message["type"] == "http.response.start":
                headers = _append_cors_headers(list(message.get("headers", [])), allow_origin)
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_cors)
        except Exception:
            if not allow_origin:
                raise
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={
                    "Access-Control-Allow-Origin": allow_origin,
                    "Access-Control-Allow-Credentials": "true",
                    "Vary": "Origin",
                },
            )
            await response(scope, receive, send)


def register_cors_middleware(app: FastAPI, settings: Settings) -> None:
    """Register CORS as the outermost middleware (call last during app setup)."""
    allowed = resolve_cors_origins(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(OriginReflectASGIMiddleware, allowed_origins=allowed)
