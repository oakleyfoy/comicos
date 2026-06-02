"""CORS registration — must run after all routes and exception handlers are attached."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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


class EnsureCorsHeadersMiddleware(BaseHTTPMiddleware):
    """Guarantee ACAO on every response (including 500s from exception handlers)."""

    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self._allowed = frozenset(allowed_origins)

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin")
        response = await call_next(request)
        if origin and origin in self._allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            existing_vary = response.headers.get("Vary")
            response.headers["Vary"] = "Origin" if not existing_vary else f"{existing_vary}, Origin"
        return response


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
    app.add_middleware(EnsureCorsHeadersMiddleware, allowed_origins=allowed)
