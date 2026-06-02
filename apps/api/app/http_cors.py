"""CORS registration — must run after all routes and exception handlers are attached."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def register_cors_middleware(app: FastAPI, settings: Settings) -> None:
    """Register CORS as the outermost middleware (call last during app setup)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
